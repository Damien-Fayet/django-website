from django.urls import path
from . import views

app_name = 'chessTrainer'

urlpatterns = [
    path('', views.chess_analysis, name='chess_analysis'),
    path('games/<str:username>/', views.list_games, name='list_games'),
    path('analyze/<str:username>/<str:game_id>/', views.analyze_specific_game, name='analyze_specific_game'),
    path('force-analyze/<str:username>/<str:game_id>/', views.force_analyze_game, name='force_analyze_game'),
    path('analyze-all-async/<str:username>/', views.analyze_all_async, name='analyze_all_async'),
    path('events/<str:username>/<str:game_id>/', views.analysis_events_stream, name='analysis_events'),
    
    # Analyse asynchrone avec SSE
    path('analyze-async/<str:username>/', views.analyze_game_async, name='analyze_game_async'),
    path('analysis-progress/<str:username>/<str:session_id>/', views.analysis_progress_stream, name='analysis_progress'),
    path('check-analysis-status/<str:username>/', views.check_analysis_status, name='check_analysis_status'),
    
    # Module d'entraînement
    path('training/', views.training_home, name='training_home'),
    path('training/check-move/', views.check_training_move, name='check_training_move'),
    path('training/<str:username>/', views.training_session, name='training_session'),
    path('training/<str:username>/position/<int:position_id>/', views.training_position, name='training_position'),
    path('training/<str:username>/next/<int:current_position_id>/', views.next_training_position, name='next_training_position'),
]
