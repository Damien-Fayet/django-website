from django.urls import path

from . import views

app_name = "avent2026"

urlpatterns = [
    path("", views.home, name="home"),
]
