web: python manage.py migrate && gunicorn -b 0.0.0.0:$PORT config.wsgi:application
worker: python manage.py check_app_scaling
