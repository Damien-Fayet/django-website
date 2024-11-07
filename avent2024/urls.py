from django.urls import path

from . import views
app_name = "avent2024"

urlpatterns = [
    # path("", views.generation, name="index"),
    # path("<int:size>/", views.generation, name="generation"),
    path('', views.home, name='home'),
    path('register',views.register,name='register'),
    path("avent2024", views.home, name="avent2024"),
]