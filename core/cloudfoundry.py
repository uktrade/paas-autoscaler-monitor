from cloudfoundry_client.client import CloudFoundryClient
from django.conf import settings


def cf_get_client(username, password, endpoint, http_proxy="", https_proxy=""):
    target_endpoint = endpoint
    proxy = dict(http=http_proxy, https=https_proxy)
    client = CloudFoundryClient(target_endpoint, proxy=proxy)
    client.init_with_user_credentials(username, password)

    return client


def cf_login():
    cf_client = cf_get_client(settings.CF_USERNAME, settings.CF_PASSWORD, settings.CF_DOMAIN)
    return cf_client
