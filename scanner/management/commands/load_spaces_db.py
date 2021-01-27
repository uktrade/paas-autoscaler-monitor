from django.core.management.base import BaseCommand
from core.cloudfoundry import cf_get_client
from django.conf import settings

from scanner.models import Spaces, Orgs


class Command(BaseCommand):

    def handle(self, *args, **options):
        print('Running')
        cf_client = cf_get_client(
            settings.CF_USERNAME,
            settings.CF_PASSWORD,
            settings.CF_DOMAIN)

        orgs_list = {}

        for org in cf_client.v3.organizations.list():
            print(org['name'])
            print(org['guid'])
            orgs_list[org['name']] = org['guid']

        for org, org_guid in orgs_list.items():
            Orgs.objects.update_or_create(org_name=org, org_guid=org_guid)

            for space in cf_client.v3.spaces.list(organization_guids=org_guid):
                print(space['name'])
                print(space['guid'])

                Spaces.objects.update_or_create(
                    space_name=space['name'],
                    space_guid=space['guid'],
                    orgs=Orgs.objects.get(org_guid=org_guid))
