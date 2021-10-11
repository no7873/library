from django.urls import path

from . import views

app_name = 'search'

urlpatterns = [
    path('', views.searchResult, name='searchResult'),
]