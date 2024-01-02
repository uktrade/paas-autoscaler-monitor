
from .views import (home_page)

from django.urls import path
from django.views.generic import RedirectView

urlpatterns = [
    path(r'^$', RedirectView.as_view(pattern_name='home_page')),
    path('home/', home_page.as_view(), name='home_page'),
]
