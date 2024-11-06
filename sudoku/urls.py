from django.urls import path

from . import views
app_name = "sudoku"

urlpatterns = [
    # path("", views.generation, name="index"),
    # path("<int:size>/", views.generation, name="generation"),
    path('', views.home, name='sudoku:home'),
]