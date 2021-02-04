#!/usr/bin/env python
from django.core.management.base import BaseCommand
from core.cloudfoundry import cf_login
from core.slack import slack_alert
from django.conf import settings
import time

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


def get_max_inst(app_guid):

    max_inst = Autoscalestaus.objects.get(app_guid=app_guid).max_count

    return max_inst


def run_scanner(cf_client, cf_token):
    print(f"{bcolours.HEADER}Running Autoscaler Monitor...{bcolours.ENDC}")

    for app in cf_client.apps.list():
        app_name = app['entity']['name']
        app_guid = app['metadata']['guid']
        no_of_instances = app['entity']['instances']
        # check to see if app is in DB, i.e. app is bound to autoscaler
        try:
            get_app_obj = Autoscalestaus.objects.get(app_guid=app_guid)
        except Autoscalestaus.DoesNotExist:
            get_app_obj = 0

        if get_app_obj != 0:
            # check to see if this is first time that app is checked
            if not get_app_obj.previous_count:
                previous_count = no_of_instances
            else:
                previous_count = get_app_obj.current_count

            max_inst = get_max_inst(app_guid)
            # breakpoint()

            Autoscalestaus.objects.update_or_create(
                            app_guid=app_guid, defaults={"previous_count": previous_count, "current_count": no_of_instances}
                        )
            if no_of_instances > previous_count:
                scaled_up_msg = f"*{app_name}:* `scaled UP to {no_of_instances}`"
                print(f"{bcolours.WARNING}" + scaled_up_msg + f"{bcolours.ENDC}")
                slack_alert(scaled_up_msg)

                # Alert if you are now at Max instance
                if no_of_instances == max_inst:
                    max_count_msg = f"*{app_name}:* `has now scaled up to the MAXIMUM set instance count of {max_inst}`"
                    print(f"{bcolours.WARNING}" + max_count_msg + f"{bcolours.ENDC}")
                    slack_alert(max_count_msg)

            elif no_of_instances < previous_count:
                scaled_down_msg = f"*{app_name}:* `scaled DOWN to {no_of_instances}`"
                print(f"{bcolours.WARNING}" + scaled_down_msg + f"{bcolours.ENDC}")
                slack_alert(scaled_down_msg)


class Command(BaseCommand):
    def handle(self, *args, **options):
        while True:
            cf_client = cf_login()
            cf_token = cf_client._access_token
            run_scanner(cf_client, cf_token)
            print(f"{bcolours.OKBLUE}Sleeping {settings.CHECK_INTERVAL}s...{bcolours.ENDC}")
            time.sleep(int(settings.CHECK_INTERVAL))
