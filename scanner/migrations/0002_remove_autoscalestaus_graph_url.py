# Generated by Django 3.1.4 on 2021-01-27 16:55

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('scanner', '0001_initial'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='autoscalestaus',
            name='graph_url',
        ),
    ]
