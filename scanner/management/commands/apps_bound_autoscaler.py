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
    print(f"{bcolours.BOLD}Org Name: {bcolours.UNDERLINE}{org_name}{bcolours.ENDC}")
    response = requests.get(
        settings.CF_DOMAIN + "/v3/organizations",
        headers={"Authorization": f"Bearer {cf_token}"},
    )
    org_response = response.json()
    for org in org_response['resources']:
        if org['name'] == org_name:
            org_guid = org['guid']
    return org_guid


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


def get_autoscaler(cf_token, space_guid):
    app_guid = []

    response = requests.get(
        settings.CF_DOMAIN + "/v3/service_instances",
        params={"space_guids": [space_guid, ]},
        headers={"Authorization": f"Bearer {cf_token}"},
    )
    service_response = response.json()

    for service in service_response["resources"]:
        if service["name"] == "autoscaler":
            autoscaler_guid = service["guid"]

            # get service bindings
            response = requests.get(
                settings.CF_DOMAIN + "/v3/service_bindings",
                params={"service_instance_guids": [autoscaler_guid, ]},
                headers={"Authorization": f"Bearer {cf_token}"},
            )
            # breakpoint()
            bindings_response = response.json()
            for app in bindings_response['resources']:
                # get app guid
                app_guid.append(app['links']['app']['href'].split('/')[-1])
    return app_guid


def get_app_name(cf_token, app):
    response = requests.get(
        settings.CF_DOMAIN + "/v3/apps",
        params={"guids": [app, ]},
        headers={"Authorization": f"Bearer {cf_token}"},
    )
    # breakpoint()
    app_response = response.json()
    app_name = app_response['resources'][0]['name']
    return app_name


def run_scanner(cf_token):
    print("Running scanner")

    for org in ast.literal_eval(settings.ORG_GUID):
        org_guid = get_org_guid(cf_token, org)
        spaces = get_spaces(cf_token, org_guid)

        for space_name in spaces:
            print(f"{bcolours.HEADER}Checking for Autoscaler in space {space_name}...{bcolours.ENDC}")
            apps_scaling = get_autoscaler(cf_token, spaces[space_name])

            for app_guid in apps_scaling:
                app_name = get_app_name(cf_token, app_guid)
                print(f"{bcolours.OKGREEN}App: {app_name} is bound to autoscaler{bcolours.ENDC}")
                Autoscalestaus.objects.update_or_create(
                                app_guid=app_guid, defaults={"app_guid": app_guid, "app_name": app_name}
                            )


class Command(BaseCommand):
    def handle(self, *args, **options):
        cf_client = cf_login()
        cf_token = cf_client._access_token

        run_scanner(cf_token)
