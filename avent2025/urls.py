from django.urls import path

from . import views
app_name = "avent2025"

urlpatterns = [
    # path("", views.generation, name="index"),
    # path("<int:size>/", views.generation, name="generation"),
    path('', views.home, name='home'),
    path('register',views.register,name='register'),
    path("avent2025", views.home, name="avent2025"),
    path("avent2025_devinette", views.home_devinette, name="avent2025_devinette"),
    path('display_enigme/', views.display_enigme, name='display_enigme'),
    path('display_enigme/<int:enigme_id>/', views.display_enigme, name='display_enigme_id'),
    path('display_devinette/', views.display_devinette, name='display_devinette'),
    path('display_devinette/<int:devinette_id>/', views.display_devinette, name='display_devinette_id'),
    path('start_adventure/', views.start_adventure, name='start_adventure'),
    path('start_devinette/', views.start_devinette, name='start_devinette'),
    path('validate_enigme/', views.validate_enigme, name='validate_enigme'),
    path('validate_devinette/', views.validate_devinette, name='validate_devinette'),
    path('reveler_indice/', views.reveler_indice, name='reveler_indice'),
    path('reveler_indice_devinette/', views.reveler_indice_devinette, name='reveler_indice_devinette'),
    path('classement/', views.classement, name='classement'),
    path('all_enigmes/', views.all_enigmes, name='all_enigmes'),
    
    
    
    
]