from django.conf import settings
import requests
import json


def slack_alert(slack_message):
    #breakpoint()

    print(slack_message)
    if settings.SLACK_ENABLED == 'True':
        print("Sending results to slack")
        url = f'{settings.SLACK_URL}/api/chat.postMessage'
        data = {'channel': f'{settings.SLACK_CHANNEL}', 'text': slack_message}
        headers = {'Content-type': 'application/json; charset=utf-8',
                    'Authorization': f'Bearer {settings.SLACK_TOKEN}'}
        response = requests.post(url, data=json.dumps(data), headers=headers)
        slack_response = response.json()
        print(slack_response)
