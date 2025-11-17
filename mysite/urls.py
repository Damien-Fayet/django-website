"""
URL configuration for mysite project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from django.urls import path, include
from django.views.generic.base import TemplateView
from avent2025.views import public_home

urlpatterns = [
    path("admin/", admin.site.urls),
    path("ckeditor5/", include('django_ckeditor_5.urls')),
    path("sudoku/", include("sudoku.urls")),
    path("avent/", include("avent2024.urls")),  # Nouveau chemin pour avent
    path("avent2025/", include("avent2025.urls")),  # Nouveau chemin pour avent 2025
    path("biblio/", include("biblio.urls")),    # Nouveau chemin pour biblio
    path("chessTrainer/", include("chessTrainer.urls")),      # Nouveau chemin pour chessTrainer
    path("max_challenge/", include("max_challenge.urls")),    # Nouveau chemin pour max_challenge
    path("accounts/", include("accounts.urls")),
    path("accounts/", include("django.contrib.auth.urls")),
    path("", public_home, name="home"),  # Page d'accueil publique
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)