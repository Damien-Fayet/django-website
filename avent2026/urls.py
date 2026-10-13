from django.urls import path

from . import views

app_name = "avent2026"

urlpatterns = [
    path("", views.home, name="home"),
    # Ancienne page « Jour N » (supprimée avec les deux pistes) : on renvoie vers la scène.
    path("jour/<int:day>/", views.old_day_redirect, name="day"),
    path("puzzle/<int:puzzle_id>/", views.puzzle_view, name="puzzle"),
    path("puzzle/<int:puzzle_id>/repondre/", views.answer, name="answer"),
    path("puzzle/<int:puzzle_id>/indice/", views.reveal_hint, name="hint"),
    path("journal/", views.journal, name="journal"),
    path("classement/", views.leaderboard, name="leaderboard"),
    path("carte/<str:kind>/vue/", views.carte_seen, name="carte_seen"),
    path("suivi/", views.tracking, name="tracking"),
]
