from django.urls import path

from . import views

app_name = "avent2026"

urlpatterns = [
    path("", views.home, name="home"),
    path("jour/<int:day>/", views.day_view, name="day"),
    path("puzzle/<int:puzzle_id>/", views.puzzle_view, name="puzzle"),
    path("puzzle/<int:puzzle_id>/repondre/", views.answer, name="answer"),
    path("puzzle/<int:puzzle_id>/indice/", views.reveal_hint, name="hint"),
    path("journal/", views.journal, name="journal"),
    path("classement/", views.leaderboard, name="leaderboard"),
]
