from django.urls import path

from . import views
app_name = "avent2024"

urlpatterns = [
    # path("", views.generation, name="index"),
    # path("<int:size>/", views.generation, name="generation"),
    path('', views.home, name='home'),
    path('register',views.register,name='register'),
    path("avent2024", views.home, name="avent2024"),
    path('display_enigme/', views.display_enigme, name='display_enigme'),
    path('start_adventure/', views.start_adventure, name='start_adventure'),
    path('validate_enigme/', views.validate_enigme, name='validate_enigme'),
    path('reveler_indice/', views.reveler_indice, name='reveler_indice'),
    
]