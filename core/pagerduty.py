from django.conf import settings
from scanner.models import Autoscalestaus
import pdpyras
import json
import requests

def pager_duty_alert(app_guid, app_name, no_of_instances, space_guid, cf_token):
    # breakpoint()
    response = requests.get(
        settings.CF_DOMAIN + "/v3/spaces",
        params={"guids": [space_guid, ]},
        headers={"Authorization": f"Bearer {cf_token}"},
    )
    space_response = response.json()

    routing_key = settings.PD_RKEY
    session = pdpyras.EventsAPISession(routing_key)
    message = f"The application: {app_name} " \
        f"in the space: {space_response['resources'][0]['name']} " \
        f"has scaled to the maximum set number of instances " \
        f"({no_of_instances}) on PaaS.  Please investigate."
    dedup_key = session.trigger(message, "Autoscale-Monitor")
    Autoscalestaus.objects.update_or_create(
                    app_guid=app_guid, defaults={"pd_dedup_key": dedup_key}
                )


def pager_duty_clear(app_guid):

    routing_key = settings.PD_RKEY
    session = pdpyras.EventsAPISession(routing_key)
    dedup_key = Autoscalestaus.objects.get(app_guid=app_guid).pd_dedup_key

    session.resolve(dedup_key)

    Autoscalestaus.objects.update_or_create(
                    app_guid=app_guid, defaults={"pd_dedup_key": None}
                )
