from django.urls import path
from . import views

app_name = 'max_challenge'

urlpatterns = [
    path('', views.index, name='index'),
    path('create/', views.create_game, name='create_game'),
    path('reset/', views.reset_game, name='reset_game'),
    path('game/<int:game_id>/', views.game_view, name='game'),
    path('admin/<int:game_id>/', views.admin_view, name='admin'),
    path('api/team_point/<int:game_id>/', views.team_point, name='team_point'),
    path('api/set_definition/<int:game_id>/', views.set_definition, name='set_definition'),
    path('api/next_definition/<int:game_id>/', views.next_definition, name='next_definition'),
    path('api/reveal_word/<int:game_id>/', views.reveal_word, name='reveal_word'),
    path('api/reveal_photo/<int:game_id>/', views.reveal_photo, name='reveal_photo'),
    path('api/hide_photo/<int:game_id>/', views.hide_photo, name='hide_photo'),
    path('api/change_photo/<int:game_id>/', views.change_photo, name='change_photo'),
    path('api/reset_scores/<int:game_id>/', views.reset_scores, name='reset_scores'),
    path('api/update_squares_per_reveal/<int:game_id>/', views.update_squares_per_reveal, name='update_squares_per_reveal'),
    path('api/game_state/<int:game_id>/', views.get_game_state, name='game_state'),
]
