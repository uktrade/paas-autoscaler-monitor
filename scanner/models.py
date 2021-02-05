from django.db import models


class Autoscalestaus(models.Model):
    app_guid = models.CharField(max_length=90)
    app_name = models.CharField(max_length=60)
    previous_count = models.IntegerField(null=True)
    current_count = models.IntegerField(null=True)
    max_count = models.IntegerField(null=True)
    pd_dedup_key = models.CharField(null=True, max_length=60)
