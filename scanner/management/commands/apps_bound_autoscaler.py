import json
import requests
import ast
from django.core.management.base import BaseCommand
from core.cloudfoundry import cf_login
from core.slack import slack_alert
from django.conf import settings

from scanner.models import Autoscalestaus


class bcolours:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


def get_org_guid(cf_token, org_name):
    response = requests.get(
        settings.CF_DOMAIN + "/v3/organizations",
        headers={"Authorization": f"Bearer {cf_token}"},
    )
    org_response = response.json()
    for org in org_response['resources']:
        if org['name'] == org_name:
            org_guid = org['guid']
    return org_guid


def clean_table(cf_token):
    app_guids = []
    print(f"{bcolours.OKCYAN}purging unwanted apps from DB{bcolours.ENDC}")

    for org_name in ast.literal_eval(settings.ORG_GUID):
        org_guid = get_org_guid(cf_token, org_name)

        response = requests.get(
            settings.CF_DOMAIN + "/v3/apps",
            params={"organization_guids": [org_guid, ]},
            headers={"Authorization": f"Bearer {cf_token}"},
        )
        apps_response = response.json()

        for app_guid in apps_response['resources']:
            app_guids.append(app_guid['guid'])

        next_url = apps_response['pagination']['next']
        while next_url:
            response = requests.get(
                next_url["href"],
                headers={"Authorization": f"Bearer {cf_token}"},
            )
            apps_response = response.json()
            for app_guid in apps_response['resources']:
                app_guids.append(app_guid['guid'])

            next_url = apps_response['pagination']['next']

    for obj in Autoscalestaus.objects.all():
        if obj.app_guid not in app_guids:
            print (f"{bcolours.WARNING}This app ({obj.app_guid}) no longer exists, removing from DB{bcolours.ENDC}")
            obj.delete()



def get_spaces(cf_token, org_guid):
    spaces = {}
    print(f"{bcolours.OKCYAN}Getting list of spaces{bcolours.ENDC}")
    response = requests.get(
        settings.CF_DOMAIN + "/v3/spaces",
        params={"organization_guids": [org_guid, ]},
        headers={"Authorization": f"Bearer {cf_token}"},
    )
    spaces_response = response.json()
    for space in spaces_response['resources']:
        spaces[space['name']] = space['guid']

    return spaces


def get_env(cf_token, env_url):
    TRUTHY_VALUES = ['off', 'no', 'false', 'False', 'FALSE']
    response = requests.get(env_url,
        headers={"Authorization": f"Bearer {cf_token}"},
    )
    env_response = response.json()
    return env_response['var'].get('X_AUTOSCALING', 'True') in TRUTHY_VALUES


def get_app_name(cf_token, app):
    response = requests.get(
        settings.CF_DOMAIN + "/v3/apps",
        params={"guids": [app, ]},
        headers={"Authorization": f"Bearer {cf_token}"},
    )
    app_response = response.json()
    return app_response['resources'][0]['name']


def bind_app_autoscaler(cf_token, app_name, app_guid, autoscaler_guid, apps_not_autoscaling):
    json_data = {
        'type': 'app',
        'relationships': {
            'app': {
                'data': {
                    'guid': app_guid
                }
            },
            'service_instance': {
                'data': {
                    'guid': autoscaler_guid
                }
            }
        }
    }
    if not settings.REPORT_MODE:
        print(f"{bcolours.OKGREEN}Binding {app_name} to Autoscaler{bcolours.ENDC}")
        response = requests.post(
            settings.CF_DOMAIN + "/v3/service_bindings",
            headers={"Authorization": f"Bearer {cf_token}", "Content-Type": "application/json"},
            data=json.dumps(json_data),
        )
        bind_response = response.json()
        print(f"{bcolours.OKBLUE}{app_name} is now bound to: {bind_response['data']['name']}{bcolours.ENDC}")

        # Attach policy
        print(f"{bcolours.OKGREEN}Attaching default policy to {app_name}{bcolours.ENDC}")
        default_policy = {
              "instance_min_count": int(settings.MIN_COUNT),
              "instance_max_count": int(settings.MAX_COUNT),
              "scaling_rules": [
                    {
                      "metric_type": "cpu",
                      "breach_duration_secs": 120,
                      "threshold": int(settings.MIN_THRESHOLD),
                      "operator": "<",
                      "cool_down_secs": 60,
                      "adjustment": "-1"
                    },
                    {
                      "metric_type": "cpu",
                      "breach_duration_secs": 120,
                      "threshold": int(settings.MAX_THRESHOLD),
                      "operator": ">=",
                      "cool_down_secs": 60,
                      "adjustment": "+1"
                    }
              ]
        }

        response = requests.put(
            settings.CF_AUTOSCALE_DOMAIN + f"/v1/apps/{app_guid}/policy",
            headers={"Authorization": f"Bearer {cf_token}"},
            data=json.dumps(default_policy)
        )
        print(f"{bcolours.OKGREEN}{response.status_code}{bcolours.ENDC}")
    else:
        print(f"{bcolours.OKBLUE}Running in reporting mode {app_name} will NOT be bound{bcolours.ENDC}")
        apps_not_autoscaling.append(app_name)


def get_max_inst(cf_token, app_guid, app_name):
    response = requests.get(
        settings.CF_AUTOSCALE_DOMAIN + f"/v1/apps/{app_guid}/policy",
        headers={"Authorization": f"Bearer {cf_token}"},
    )
    scale_response = response.json()
    if response.status_code == 404:
        print(f"{bcolours.WARNING}No scaling policy has been added to the app: {app_name}{bcolours.ENDC}")
        max_int = -1
    elif response.status_code == 403:
        print(f"{bcolours.WARNING}The app: {app_name} is not bound to autoscaler{bcolours.ENDC}")
        max_int = -2
    else:
        max_int = scale_response['instance_max_count']
    return max_int


def check_autoscaled_apps(cf_token, space_guid, apps_not_autoscaling):
    app_guid_list = []

    # Get autoscaler guid
    response = requests.get(
        settings.CF_DOMAIN + "/v3/service_instances",
        params={"space_guids": [space_guid, ],
            "service_plan_names": "autoscaler-free-plan"
            },
        headers={"Authorization": f"Bearer {cf_token}"},
    )
    service_response = response.json()

    # Check if there is autoscaler in space
    if service_response['pagination']['total_results'] > 0:
        autoscaler_guid = service_response['resources'][0]['guid']

        # Get service bindings
        response = requests.get(
            settings.CF_DOMAIN + "/v3/service_bindings",
            params={"service_instance_guids": [autoscaler_guid, ]},
            headers={"Authorization": f"Bearer {cf_token}"},
        )
        bindings_response = response.json()
        for app in bindings_response['resources']:
            # Get app guid
            app_guid_list.append(app['links']['app']['href'].split('/')[-1])

        # Get list of apps
        response = requests.get(
            settings.CF_DOMAIN + "/v3/apps",
            params={"space_guids": [space_guid, ]},
            headers={"Authorization": f"Bearer {cf_token}"},
        )
        app_response = response.json()

        # Check if app is bound to autoscaler
        for app in app_response['resources']:
            if app['state'] == 'STARTED':
                bind = get_env(cf_token, app['links']['environment_variables']['href'])
                # If not check env if it should be bound
                if not bind:
                    # Service not already bound so bind
                    if app['guid'] not in app_guid_list:
                        bind_app_autoscaler(cf_token, app['name'], app['guid'], autoscaler_guid, apps_not_autoscaling)
                    else:
                        print(f"{bcolours.OKGREEN}App: {app['name']} is already bound to autoscaler{bcolours.ENDC}")

                    # Check for changes in max inst count and update if needed.
                    max_inst = get_max_inst(cf_token, app['guid'], app['name'])
                    Autoscalestaus.objects.update_or_create(
                                    app_guid=app['guid'], defaults={"app_guid": app['guid'], "app_name": app['name'], "max_count": max_inst}
                                )
                else:
                    print(f"{bcolours.WARNING}App: {app['name']} will NOT be bound to autoscaler as exclude VAR set in app.{bcolours.ENDC}")
    else:
        print(f"{bcolours.WARNING}There is no autoscaler in this space.{bcolours.ENDC}")


def run_scanner(cf_token):
    print(f"{bcolours.HEADER}Running scanner{bcolours.ENDC}")

    # Remove from DB table all apps that are no longer present in CF
    clean_table(cf_token)
    apps_not_autoscaling = []

    for org in ast.literal_eval(settings.ORG_GUID):
        print(f"{bcolours.BOLD}Org Name: {bcolours.UNDERLINE}{org}{bcolours.ENDC}")
        org_guid = get_org_guid(cf_token, org)
        spaces = get_spaces(cf_token, org_guid)
        for space_name in spaces:
            print(f"{bcolours.HEADER}Checking for Autoscaler in space {space_name}...{bcolours.ENDC}")
            check_autoscaled_apps(cf_token, spaces[space_name], apps_not_autoscaling)

    if apps_not_autoscaling:
        print(f"{bcolours.BOLD}The following apps are not attached to autoscaler{bcolours.ENDC}")
        for app in apps_not_autoscaling:
            print(f"{bcolours.FAIL}{app}{bcolours.ENDC}")


class Command(BaseCommand):
    def handle(self, *args, **options):
        cf_client = cf_login()
        cf_token = cf_client._access_token

        run_scanner(cf_token)
