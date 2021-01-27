#!/usr/bin/env python
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
    # breakpoint()
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
    # breakpoint()
    for space in spaces_response['resources']:
        spaces[space['name']] = space['guid']

    return spaces


def get_autoscaler(cf_token, space_guid):
    # breakpoint()
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


def get_app_cpus(cf_token, app):
    # print(f"checking app: {app}")
    # breakpoint()
    response = requests.get(
        settings.CF_DOMAIN + "/v3/processes",
        params={"app_guids": [app, ]},
        headers={"Authorization": f"Bearer {cf_token}"},
    )
    # breakpoint()
    process_response = response.json()

    no_of_instances = process_response['resources'][0]['instances']
    app_name = get_app_name(cf_token, app)

    return app_name, no_of_instances

def run_scanner(cf_token):
    print("Running scanner")

    for org in ast.literal_eval(settings.ORG_GUID):
        org_guid = get_org_guid(cf_token, org)

        spaces = get_spaces(cf_token, org_guid)

        for space_name in spaces:
            print(f"{bcolours.HEADER}Checking Autoscaler for space {space_name}...{bcolours.ENDC}")

            apps_scaling = get_autoscaler(cf_token, spaces[space_name])
            # print(apps_scaling)

            for app in apps_scaling:
                app_name, instances = get_app_cpus(cf_token, app)
                print(f"{bcolours.OKGREEN}App: {app_name} currently has {instances} instances{bcolours.ENDC}")
                # breakpoint()
                # get previous instance_count
                try:
                    previous_count = Autoscalestaus.objects.get(app_guid=app).current_count
                except Autoscalestaus.DoesNotExist:
                    previous_count = instances
                # Store in DB
                Autoscalestaus.objects.update_or_create(
                                app_guid=app, defaults={"previous_count": previous_count, "current_count": instances}
                            )
                # check to see if app has scaled.
                if instances > previous_count:
                    scaled_up_msg = f"*{app_name}* `scaled UP to {instances}`"
                    print(f"{bcolours.WARNING}" + scaled_up_msg + f"{bcolours.WARNING}")
                    slack_alert(scaled_up_msg)
                elif instances < previous_count:
                    scaled_down_msg = f"*{app_name}* `scaled DOWN to {instances}`"
                    print(f"{bcolours.WARNING}" + scaled_down_msg + f"{bcolours.WARNING}")
                    slack_alert(scaled_down_msg)


class Command(BaseCommand):
    def handle(self, *args, **options):
        cf_client = cf_login()
        cf_token = cf_client._access_token

        run_scanner(cf_token)
