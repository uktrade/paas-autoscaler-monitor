# paas-autoscaler-monitor

Usage
=====

There are two part to this monitor, the script (apps_bound_autoscaler.py) and the script (check_app_scaling.py)


apps_bound_autoscaler
---------------------

This needs to run at a set interval, eg via jenkins once every hour.  The purpose of this script it to scan though CF and find which apps are using the autoscaler.  

  python manage.py check_app_scaling


check_app_scaling
-----------------

This script needs to run during app startup.  This will run every set interval (defined in a VAR), this script will check if any application has scaled and report any changes to Slack.


VARs that need to be set
------------------------
```
DEBUG = condition
SECRET_KEY = some-secret
DATABASE_URL  = db-url
ALLOWED_HOSTS = app-url
AUTHBROKER_CLIENT_ID = auth-id
AUTHBROKER_CLIENT_SECRET = auth-secret
AUTHBROKER_URL = sso-url
CHECK_INTERVAL = check-interval
CF_USERNAME = cf-user
CF_PASSWORD = cf-password
CF_DOMAIN = cf-api-url
ORG_GUID = ['org-name',]
SLACK_ENABLED = condition
SLACK_TOKEN = token
SLACK_URL = slack-team-url
SLACK_CHANNEL = channel-id
```
