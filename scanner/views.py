import requests

from django.shortcuts import render, redirect
from django.views import View
from django.urls import reverse
from django.utils.decorators import method_decorator

from django.contrib.auth.decorators import login_required


class home_page(View):
    template_name = 'home-page.html'

    @method_decorator(login_required)
    def get(self, request, *args, **kwargs):
        return render(request, self.template_name)
