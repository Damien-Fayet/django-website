from django.shortcuts import render, redirect
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.http import StreamingHttpResponse
import requests
import json
from datetime import datetime
from .models import ChessGame, PlayerSyncStatus, TrainingPosition, TrainingAttempt
import threading
import time

try:
    import chess
    import chess.pgn
    import chess.engine
    from io import StringIO
    CHESS_AVAILABLE = True
    print("Librairies d'échecs importées avec succès")
except ImportError as e:
    print(f"Erreur d'importation des librairies d'échecs: {e}")
    CHESS_AVAILABLE = False

# Configuration Stockfish
STOCKFISH_PATH = "/opt/homebrew/bin/stockfish"  # Chemin par défaut sur macOS avec Homebrew
STOCKFISH_AVAILABLE = False

def check_stockfish():
    """Vérifier si Stockfish est disponible"""
    global STOCKFISH_AVAILABLE
    import shutil
    
    # Essayer plusieurs emplacements possibles
    possible_paths = [
        "/opt/homebrew/bin/stockfish",  # Homebrew sur Apple Silicon
        "/usr/local/bin/stockfish",     # Homebrew sur Intel
        "stockfish",                    # Dans le PATH
        "/usr/bin/stockfish",          # Installation système Linux
    ]
    
    for path in possible_paths:
        if shutil.which(path):
            global STOCKFISH_PATH
            STOCKFISH_PATH = path
            STOCKFISH_AVAILABLE = True
            print(f"✅ Stockfish trouvé: {path}")
            return True
    
    print("❌ Stockfish non trouvé. Installation recommandée: brew install stockfish")
    return False

# Vérifier Stockfish au démarrage
check_stockfish()

# Dictionnaire global pour les événements d'analyse en temps réel
analysis_events = {}  # {username_gameId: {'progress': 0, 'message': '', 'current_move': 0, 'total_moves': 0, 'errors_count': 0, 'status': 'running|completed|error'}}

def send_analysis_event(username, game_id, progress, message, current_move=0, total_moves=0, errors_count=0, status='running'):
    """Envoyer un événement d'analyse"""
    key = f"{username}_{game_id}"
    analysis_events[key] = {
        'progress': progress,
        'message': message,
        'current_move': current_move,
        'total_moves': total_moves,
        'errors_count': errors_count,
        'status': status,
        'timestamp': time.time()
    }

def clear_analysis_event(username, game_id):
    """Nettoyer un événement d'analyse terminé"""
    key = f"{username}_{game_id}"
    if key in analysis_events:
        del analysis_events[key]


def deduce_player_results(game_result, white_player, black_player):
    """Déduire le résultat de chaque joueur à partir du résultat global de la partie"""
    if game_result == 'white_win':
        return 'win', 'loss'
    elif game_result == 'black_win':
        return 'loss', 'win'
    elif game_result in ['agreed', 'stalemate', 'repetition', 'insufficient']:
        return game_result, game_result  # Les deux joueurs ont le même résultat pour les nulles
    else:
        # Si on ne peut pas déterminer, retourner unknown
        return 'unknown', 'unknown'


def get_time_class_category(time_class):
    """Catégoriser les parties selon leur cadence"""
    time_class_map = {
        'bullet': {
            'name': 'Bullet',
            'icon': '⚡',
            'description': '< 3 minutes',
            'order': 1
        },
        'blitz': {
            'name': 'Blitz', 
            'icon': '🔥',
            'description': '3-10 minutes',
            'order': 2
        },
        'rapid': {
            'name': 'Rapid',
            'icon': '⏰', 
            'description': '10+ minutes',
            'order': 3
        },
        'daily': {
            'name': 'Correspondance',
            'icon': '📧',
            'description': 'Parties par correspondance',
            'order': 4
        }
    }
    
    return time_class_map.get(time_class, {
        'name': time_class.title() if time_class else 'Autre',
        'icon': '♟️',
        'description': 'Autre cadence',
        'order': 5
    })


def chess_analysis(request):
    """Page principale d'analyse des parties d'échecs"""
    
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        if username:
            return redirect('chessTrainer:analyze_game', username=username)
        else:
            messages.error(request, "Veuillez entrer un nom d'utilisateur valide.")
    
    # Récupérer les dernières parties analysées
    recent_games = ChessGame.objects.filter(analyzed=True)[:10]
    
    context = {
        'recent_games': recent_games,
    }
    return render(request, 'chessTrainer/analysis.html', context)


@csrf_exempt
def analyze_game_async(request, username):
    """Démarrer une analyse asynchrone avec SSE"""
    import uuid
    import threading
    import json
    
    if request.method != 'POST':
        return JsonResponse({'error': 'Méthode non autorisée'}, status=405)

    if not CHESS_AVAILABLE:
        return JsonResponse({'error': 'Les librairies d\'analyse d\'échecs ne sont pas installées.'}, status=500)

    if not STOCKFISH_AVAILABLE:
        return JsonResponse({'error': 'Stockfish n\'est pas disponible. Installation recommandée: brew install stockfish'}, status=500)

    try:
        # Lire les paramètres du body JSON
        body_data = {}
        if request.body:
            try:
                body_data = json.loads(request.body.decode('utf-8'))
            except json.JSONDecodeError:
                pass
        
        full_sync = body_data.get('full_sync', False)
        search_months = body_data.get('search_months', '3')
        check_only = body_data.get('check_only', False)
        
        # Générer un ID de session unique
        session_id = str(uuid.uuid4())
        
        # Initialiser les événements de progression
        analysis_events[f"{username}_{session_id}"] = {
            'progress': 0,
            'message': 'Démarrage de l\'analyse...',
            'current_game': 0,
            'total_games': 0,
            'errors_count': 0,
            'status': 'starting'
        }
        
        # Lancer l'analyse en arrière-plan
        def run_full_analysis():
            try:
                # 1. Synchronisation des parties
                send_analysis_progress(username, session_id, 'sync_start', 'Synchronisation des parties...', 0, 0, 0)
                
                # Convertir search_months en paramètre pour fetch_new_games_only
                months_limit = None
                if search_months != 'all':
                    try:
                        months_limit = int(search_months)
                    except ValueError:
                        months_limit = 3
                
                new_games = fetch_new_games_only(username, force_full_sync=full_sync, months_limit=months_limit, session_id=session_id)
                games_count = 0
                
                if new_games:
                    for game_data in new_games:
                        game_details = fetch_game_details(game_data)
                        if game_details:
                            save_or_update_game(username, game_data, game_details, auto_analyze=False)
                            games_count += 1
                
                send_analysis_progress(username, session_id, 'sync_complete', f'{games_count} nouvelles parties trouvées', 0, 0, 0, extra={'games_count': games_count})
                
                # Si check_only et pas de nouvelles parties, arrêter ici
                if check_only and games_count == 0:
                    send_analysis_progress(username, session_id, 'complete', 'Aucune nouvelle partie trouvée (0 nouvelles parties)', 0, 0, 0, extra={
                        'analyzed_games': 0,
                        'training_positions': 0,
                        'games_count': 0
                    })
                    
                    # Envoyer finished pour cohérence avec les autres analyses
                    send_analysis_progress(username, session_id, 'finished', 'Import terminé - aucune nouvelle partie', 0, 0, 0, extra={
                        'status': 'completed',
                        'analyzed_games': 0,
                        'training_positions': 0,
                        'games_count': 0
                    })
                    
                    # Attendre un peu pour laisser le temps à la connexion SSE de recevoir l'événement
                    import time
                    time.sleep(3)
                    
                    # Nettoyer la session après envoi de l'événement final
                    if f"{username}_{session_id}" in analysis_events:
                        del analysis_events[f"{username}_{session_id}"]
                    
                    return
                
                # 2. Analyse des parties non analysées
                unanalyzed_games = ChessGame.objects.filter(
                    username=username,
                    analyzed=False,
                    pgn__isnull=False
                ).exclude(pgn='')
                
                total_games = unanalyzed_games.count()
                send_analysis_progress(username, session_id, 'analysis_start', 'Début de l\'analyse...', 0, total_games, 0, extra={'total_games': total_games})
                
                analyzed_count = 0
                total_training_positions = 0
                for i, chess_game in enumerate(unanalyzed_games):
                    try:
                        game_info = f"{chess_game.white_player} vs {chess_game.black_player}"
                        send_analysis_progress(username, session_id, 'analysis_progress', f'Analyse en cours...', i + 1, total_games, 0, extra={'game_info': game_info})
                        
                        # L'analyse crée automatiquement les positions d'entraînement
                        analyze_game_with_stockfish(chess_game)
                        analyzed_count += 1
                        
                        # Compter les positions d'entraînement créées pour ce joueur
                        from .models import TrainingPosition
                        user_training_positions = TrainingPosition.objects.filter(username=username).count()
                        total_training_positions = user_training_positions
                        
                    except Exception as e:
                        print(f"Erreur analyse partie {chess_game.game_id}: {e}")
                
                # Terminé - les positions d'entraînement ont été créées pendant l'analyse
                send_analysis_progress(username, session_id, 'complete', f'Analyse terminée ! {games_count} nouvelles parties synchronisées et analysées', total_games, total_games, 0, extra={
                    'analyzed_games': analyzed_count,
                    'training_positions': total_training_positions,
                    'games_count': games_count
                })
                
                # Envoyer finished pour cohérence avec les autres analyses
                send_analysis_progress(username, session_id, 'finished', f'Import et analyse terminés avec succès', total_games, total_games, 0, extra={
                    'status': 'completed',
                    'analyzed_games': analyzed_count,
                    'training_positions': total_training_positions,
                    'games_count': games_count
                })
                
            except Exception as e:
                send_analysis_progress(username, session_id, 'error', f'Erreur: {str(e)}', 0, 0, 0)
        
        # Démarrer le thread d'analyse
        analysis_thread = threading.Thread(target=run_full_analysis)
        analysis_thread.daemon = True
        analysis_thread.start()
        
        return JsonResponse({'success': True, 'session_id': session_id})
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
def analyze_all_async(request, username):
    """Analyse asynchrone de toutes les parties non analysées avec SSE"""
    if request.method == 'POST':
        # Générer un ID de session unique
        import uuid
        session_id = str(uuid.uuid4())
        
        def run_analysis_all():
            try:
                # Compter les parties non analysées
                unanalyzed_games = ChessGame.objects.filter(
                    username=username,
                    analyzed=False,
                    pgn__isnull=False
                ).exclude(pgn='')
                
                total_games = unanalyzed_games.count()
                
                if total_games == 0:
                    send_analysis_progress(username, session_id, 'complete', 'Toutes les parties sont déjà analysées', 0, 0, 0, extra={
                        'analyzed_games': 0,
                        'games_count': 0
                    })
                    send_analysis_progress(username, session_id, 'finished', 'Analyse terminée - toutes les parties déjà analysées', 0, 0, 0, extra={
                        'status': 'completed',
                        'analyzed_games': 0,
                        'games_count': 0
                    })
                    return
                
                send_analysis_progress(username, session_id, 'analysis_start', f'Début de l\'analyse de {total_games} parties', 0, total_games, 0)
                
                analyzed_count = 0
                total_errors = 0
                
                for i, chess_game in enumerate(unanalyzed_games):
                    try:
                        send_analysis_progress(username, session_id, 'analysis_progress', f'Analyse de la partie {i+1}/{total_games}', i+1, total_games, total_errors)
                        
                        # Analyser la partie
                        analyze_game_with_stockfish(chess_game)
                        analyzed_count += 1
                        
                        # Compter les erreurs pour cette partie
                        errors = get_game_errors(chess_game)
                        if errors:
                            total_errors += len(errors)
                            
                    except Exception as e:
                        print(f"❌ Erreur lors de l'analyse de la partie {chess_game.game_id}: {e}")
                        continue
                
                # Terminé
                send_analysis_progress(username, session_id, 'complete', f'Analyse terminée ! {analyzed_count} parties analysées', total_games, total_games, total_errors, extra={
                    'analyzed_games': analyzed_count,
                    'games_count': analyzed_count
                })
                
                send_analysis_progress(username, session_id, 'finished', f'Analyse de toutes les parties terminée avec succès', total_games, total_games, total_errors, extra={
                    'status': 'completed',
                    'analyzed_games': analyzed_count,
                    'games_count': analyzed_count
                })
                
            except Exception as e:
                send_analysis_progress(username, session_id, 'error', f'Erreur: {str(e)}', 0, 0, 0)
        
        # Démarrer le thread d'analyse
        analysis_thread = threading.Thread(target=run_analysis_all)
        analysis_thread.daemon = True
        analysis_thread.start()
        
        return JsonResponse({'success': True, 'session_id': session_id})
        
    return JsonResponse({'error': 'Method not allowed'}, status=405)


def send_analysis_progress(username, session_id, event_type, message, current, total, errors, extra=None):
    """Envoyer un événement de progression pour l'analyse"""
    import time
    key = f"{username}_{session_id}"
    
    # Logger l'événement envoyé
    print(f"📤 Envoi événement SSE: {event_type} - {message} (session: {session_id})")
    
    # Récupérer les données existantes pour conserver le start_time
    existing_data = analysis_events.get(key, {})
    
    event_data = {
        'progress': int((current / total * 100)) if total > 0 else 0,
        'message': message,
        'current_game': current,
        'total_games': total,
        'errors_count': errors,
        'status': 'running',
        'type': event_type,
        'start_time': existing_data.get('start_time', time.time())  # Conserver le start_time existant
    }
    
    if extra:
        event_data.update(extra)
    
    if event_type in ['complete', 'finished', 'error']:
        event_data['status'] = event_type
    
    analysis_events[key] = event_data
    print(f"📊 Événement stocké dans analysis_events[{key}]: {event_data['type']} - {event_data['message']}")


def analysis_progress_stream(request, username, session_id):
    """Stream SSE pour le suivi de l'analyse asynchrone avec reconnexion"""
    import time
    import json
    
    def event_stream():
        key = f"{username}_{session_id}"
        last_progress = -1
        start_time = time.time()
        sent_initial = False
        
        while True:
            try:
                if key in analysis_events:
                    event_data = analysis_events[key]
                    current_progress = event_data.get('progress', 0)
                    
                    # Logger l'événement trouvé
                    print(f"📡 Streaming SSE: {event_data.get('type')} - {event_data.get('message')} (session: {session_id})")
                    
                    # Envoyer un événement initial avec l'état actuel (pour reconnexions)
                    if not sent_initial:
                        initial_event = {**event_data, 'type': 'reconnected', 'message': f"Reprise: {event_data.get('message', 'En cours...')}"}
                        print(f"📤 Envoi initial SSE: {initial_event}")
                        yield f"data: {json.dumps(initial_event)}\n\n".encode('utf-8')
                        sent_initial = True
                        last_progress = current_progress
                    
                    # Envoyer seulement si changement significatif
                    if (current_progress != last_progress or 
                        event_data.get('type') in ['sync_start', 'sync_progress', 'sync_complete', 'analysis_start', 'complete', 'finished', 'error']):
                        print(f"📤 Envoi événement SSE: {event_data}")
                        yield f"data: {json.dumps(event_data)}\n\n".encode('utf-8')
                        last_progress = current_progress
                    
                    # Si terminé, arrêter (finished est maintenant explicite, pas besoin de doubler)
                    if event_data.get('status') in ['finished', 'error']:
                        # Garder l'événement un peu plus longtemps pour les reconnexions tardives
                        time.sleep(10)
                        if key in analysis_events:
                            del analysis_events[key]
                        break
                else:
                    # Si pas d'événement trouvé, envoyer un heartbeat
                    if not sent_initial:
                        heartbeat = {
                            'type': 'heartbeat', 
                            'message': 'Session non trouvée ou terminée',
                            'progress': 0,
                            'timestamp': int(time.time())
                        }
                        yield f"data: {json.dumps(heartbeat)}\n\n".encode('utf-8')
                        sent_initial = True
                        
                        # Si aucune session trouvée après 30 secondes, arrêter
                        if time.time() - start_time > 30:
                            error_event = {'type': 'session_not_found', 'message': 'Session expirée ou introuvable'}
                            yield f"data: {json.dumps(error_event)}\n\n".encode('utf-8')
                            break
                        
            except Exception as e:
                error_data = {'type': 'error', 'message': f'Erreur SSE: {str(e)}'}
                yield f"data: {json.dumps(error_data)}\n\n".encode('utf-8')
                break
            
            time.sleep(2)  # Vérifier toutes les 2 secondes (plus fréquent pour les reconnexions)
            
            # Timeout après 45 minutes (plus long pour les analyses longues)
            if time.time() - start_time > 2700:
                timeout_data = {'type': 'timeout', 'message': 'Timeout de connexion (45 minutes)'}
                yield f"data: {json.dumps(timeout_data)}\n\n".encode('utf-8')
                break
    
    response = StreamingHttpResponse(event_stream(), content_type='text/event-stream')
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'
    return response


def check_analysis_status(request, username):
    """Vérifier s'il y a une analyse en cours pour un utilisateur"""
    try:
        # Vérifier s'il y a des événements d'analyse en cours pour ce joueur
        matching_keys = [key for key in analysis_events.keys() if key.startswith(f"{username}_")]
        
        if matching_keys:
            # Il y a une analyse en cours
            latest_key = max(matching_keys, key=lambda k: analysis_events[k].get('start_time', 0))
            event_data = analysis_events[latest_key]
            session_id = latest_key.split('_', 1)[1]  # Récupérer l'ID de session
            
            return JsonResponse({
                'analysis_in_progress': True,
                'session_id': session_id,
                'progress': event_data.get('progress', 0),
                'message': event_data.get('message', 'Analyse en cours...'),
                'status': event_data.get('status', 'running'),
                'is_full_sync': event_data.get('is_full_sync', False)
            })
        else:
            # Pas d'analyse en cours
            return JsonResponse({
                'analysis_in_progress': False
            })
            
    except Exception as e:
        return JsonResponse({
            'analysis_in_progress': False,
            'error': str(e)
        }, status=500)


def list_games(request, username):
    """Lister toutes les parties disponibles pour un joueur avec synchronisation incrémentale"""
    
    if not CHESS_AVAILABLE:
        messages.error(request, "Les librairies d'analyse d'échecs ne sont pas installées. Veuillez installer python-chess et stockfish.")
        return redirect('chessTrainer:chess_analysis')
    
    try:
        # Paramètres de synchronisation
        force_full_sync = request.GET.get('full_sync', '').lower() == 'true'
        sync_only = request.GET.get('sync_only', '').lower() == 'true'
        
        # Récupérer l'état de synchronisation actuel
        sync_status = PlayerSyncStatus.objects.filter(username=username).first()
        
        if sync_only:
            # Mode synchronisation seule - récupérer nouvelles parties et rediriger
            print(f"� Mode synchronisation seule pour {username}")
            new_games = fetch_new_games_only(username, force_full_sync=force_full_sync, months_limit=None)
            
            if new_games:
                # Sauvegarder les nouvelles parties en base (l'analyse se fera après)
                for game_data in new_games:
                    game_details = fetch_game_details(game_data)
                    if game_details:
                        save_or_update_game(username, game_data, game_details, auto_analyze=False)
                
                messages.success(request, f"✅ {len(new_games)} nouvelles parties synchronisées !")
                
                # Analyser toutes les parties non analysées en arrière-plan
                analyzed_count = analyze_unanalyzed_games(username)
                if analyzed_count > 0:
                    messages.info(request, f"🔍 {analyzed_count} parties analysées automatiquement")
            else:
                messages.info(request, "ℹ️ Aucune nouvelle partie trouvée.")
            
            return redirect('chessTrainer:list_games', username=username)
        
        # Mode affichage normal - récupérer les parties depuis la base
        print(f"📋 Affichage des parties pour {username}")
        
        # Récupérer toutes les parties depuis la base de données
        all_games_db = ChessGame.objects.filter(username=username).order_by('-end_time')
        
        if not all_games_db.exists():
            # Aucune partie en base - faire une première synchronisation
            print("🆕 Aucune partie en base - synchronisation initiale")
            new_games = fetch_new_games_only(username, force_full_sync=True, months_limit=None)
            
            if new_games:
                # Sauvegarder en base (l'analyse se fera après)
                for game_data in new_games:
                    game_details = fetch_game_details(game_data)
                    if game_details:
                        save_or_update_game(username, game_data, game_details, auto_analyze=False)
                
                # Recharger les parties depuis la base
                all_games_db = ChessGame.objects.filter(username=username).order_by('-end_time')
                messages.success(request, f"✅ {len(new_games)} parties synchronisées pour la première fois !")
                
                # Analyser toutes les parties non analysées
                analyzed_count = analyze_unanalyzed_games(username)
                if analyzed_count > 0:
                    messages.info(request, f"🔍 {analyzed_count} parties analysées automatiquement")
            else:
                messages.error(request, f"❌ Aucune partie trouvée pour {username}")
                return redirect('chessTrainer:chess_analysis')
        
        # Convertir les parties de la base en format d'affichage
        games_with_analysis = []
        for chess_game in all_games_db:
            # Déduire le résultat de chaque joueur à partir du résultat global
            white_result, black_result = deduce_player_results(chess_game.result, chess_game.white_player, chess_game.black_player)
            
            # Reconstruire le format game_data depuis la base
            game_data = {
                'url': chess_game.game_url,
                'game_id': chess_game.game_id,
                'white': {'username': chess_game.white_player, 'result': white_result},
                'black': {'username': chess_game.black_player, 'result': black_result},
                'time_class': 'unknown',  # On pourrait l'ajouter au modèle plus tard
                'time_control': chess_game.time_control,
                'start_time': chess_game.start_time,
                'end_time': chess_game.end_time
            }
            
            # Déterminer la cadence depuis le time_control
            time_control = chess_game.time_control
            if '+' in time_control:
                base_time = int(time_control.split('+')[0])
            else:
                base_time = int(time_control) if time_control.isdigit() else 600
            
            if base_time < 180:
                game_data['time_class'] = 'bullet'
            elif base_time < 600:
                game_data['time_class'] = 'blitz'
            elif base_time < 86400:  # Moins d'un jour
                game_data['time_class'] = 'rapid'
            else:
                game_data['time_class'] = 'daily'
            
            # Enrichir avec les informations de cadence
            time_class_info = get_time_class_category(game_data['time_class'])
            game_data['time_class_info'] = time_class_info
            
            # Compter les erreurs
            error_count = len(chess_game.get_errors()) if chess_game.analyzed else None
            
            games_with_analysis.append({
                'game_data': game_data,
                'existing_game': chess_game,
                'error_count': error_count,
                'is_analyzed': chess_game.analyzed,
                'time_class': game_data['time_class'],
                'time_class_info': time_class_info
            })
        
        # Grouper les parties par cadence
        games_by_time_class = {}
        for game_info in games_with_analysis:
            time_class = game_info['time_class']
            time_class_info = game_info['time_class_info']
            
            if time_class not in games_by_time_class:
                games_by_time_class[time_class] = {
                    'info': time_class_info,
                    'games': [],
                    'count': 0,
                    'analyzed_count': 0,
                    'total_errors': 0
                }
            
            games_by_time_class[time_class]['games'].append(game_info)
            games_by_time_class[time_class]['count'] += 1
            
            if game_info['is_analyzed']:
                games_by_time_class[time_class]['analyzed_count'] += 1
                if game_info['error_count'] is not None:
                    games_by_time_class[time_class]['total_errors'] += game_info['error_count']
        
        # Trier les groupes par ordre de cadence
        sorted_time_classes = sorted(
            games_by_time_class.items(),
            key=lambda x: x[1]['info']['order']
        )
        
        # Calculer les statistiques globales
        total_analyzed = sum(1 for game in games_with_analysis if game['is_analyzed'])
        
        # Calculer la plage de dates
        date_range = None
        if games_with_analysis:
            dates = [game['game_data']['start_time'] for game in games_with_analysis if game['game_data']['start_time']]
            if dates:
                date_range = {
                    'start': min(dates),
                    'end': max(dates)
                }
        
        context = {
            'username': username,
            'games': games_with_analysis,
            'games_by_time_class': sorted_time_classes,
            'total_games': len(games_with_analysis),
            'analyzed_count': total_analyzed,
            'date_range': date_range,
            'sync_status': sync_status
        }
        
        return render(request, 'chessTrainer/games_list.html', context)
        
    except Exception as e:
        print(f"Erreur dans list_games: {e}")
        messages.error(request, f"Erreur lors de la récupération des parties: {str(e)}")
        return redirect('chessTrainer:chess_analysis')


def analyze_specific_game(request, username, game_id):
    """Analyser une partie spécifique"""
    
    if not CHESS_AVAILABLE:
        messages.error(request, "Les librairies d'analyse d'échecs ne sont pas installées.")
        return redirect('chessTrainer:chess_analysis')
    
    if not STOCKFISH_AVAILABLE:
        messages.error(request, "❌ Stockfish n'est pas disponible. Analyse impossible. Installation recommandée: brew install stockfish")
        return redirect('chessTrainer:list_games', username=username)
    
    try:
        # D'abord, chercher la partie dans la base de données
        try:
            chess_game = ChessGame.objects.get(game_id=game_id, username=username)
            
            # Actualiser depuis la DB au cas où la partie vient d'être modifiée par une autre vue
            chess_game.refresh_from_db()
            
            # Si la partie est déjà en base, vérifier si elle est analysée
            if chess_game.pgn:
                print(f"🎯 Analyse de la partie {game_id} depuis la base de données")
                
                # Analyser seulement si pas encore analysée
                if not chess_game.analyzed:
                    print(f"📊 Partie non analysée - lancement de l'analyse Stockfish")
                    
                    # Toujours lancer l'analyse en arrière-plan pour éviter les blocages
                    analysis_thread = threading.Thread(
                        target=analyze_game_in_background, 
                        args=(chess_game, username, game_id, False)
                    )
                    analysis_thread.daemon = True
                    analysis_thread.start()
                    
                    # Si c'est une requête AJAX, retourner immédiatement
                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                        return JsonResponse({
                            'status': 'started',
                            'message': 'Analyse lancée en arrière-plan'
                        })
                    else:
                        # Pour les requêtes normales, attendre un moment puis rediriger
                        messages.info(request, "Analyse lancée en arrière-plan. Rafraîchissez la page dans quelques instants.")
                        return redirect('chessTrainer:analyze_specific_game', username=username, game_id=game_id)
                else:
                    print(f"✅ Partie déjà analysée - utilisation des données existantes")
                
                # Récupérer les erreurs pour l'affichage
                errors = get_game_errors(chess_game)
                
                # Déterminer la couleur du joueur analysé
                if username.lower() == chess_game.white_player.lower():
                    orientation = 'white'
                elif username.lower() == chess_game.black_player.lower():
                    orientation = 'black'
                else:
                    orientation = 'white'  # fallback

                # Préparer le contexte pour l'affichage enrichi
                context = {
                    'chess_game': chess_game,
                    'username': username,
                    'orientation': orientation,
                    'errors_count': 0,
                    'best_moves_count': 0,
                    'excellent_moves_count': 0,
                    'good_moves_count': 0,
                    'inaccuracies_count': 0,
                    'mistakes_count': 0,
                    'blunders_count': 0,
                    'average_accuracy': 0,
                }
                
                if chess_game.analyzed and chess_game.moves_data:
                    # Accéder aux données de mouvement
                    moves_data = chess_game.moves_data
                    if isinstance(moves_data, dict) and 'moves' in moves_data:
                        moves_list = moves_data['moves']
                        # Garder le format original pour le template
                        chess_game.moves_data = moves_list
                    else:
                        moves_list = moves_data if isinstance(moves_data, list) else []
                        # Pas besoin de modification si déjà en format liste
                    
                    # Récupérer les statistiques améliorées (en vérifiant le type)
                    if isinstance(moves_data, dict):
                        context['inaccuracies_count'] = moves_data.get('inaccuracies_count', 0)
                        context['mistakes_count'] = moves_data.get('mistakes_count', 0)
                        context['blunders_count'] = moves_data.get('blunders_count', 0)
                        context['average_accuracy'] = moves_data.get('average_accuracy', 0)
                        context['errors_count'] = moves_data.get('errors_count', 0)
                    else:
                        # Fallback pour anciens formats de données
                        context['inaccuracies_count'] = 0
                        context['mistakes_count'] = 0
                        context['blunders_count'] = 0
                        context['average_accuracy'] = 0
                        context['errors_count'] = 0
                    

                    # Déterminer la couleur du joueur analysé
                    if username.lower() == chess_game.white_player.lower():
                        player_is_white = True
                    elif username.lower() == chess_game.black_player.lower():
                        player_is_white = False
                    else:
                        player_is_white = True  # fallback

                    # Ajouter cette information au contexte pour le JavaScript
                    context['player_is_white'] = player_is_white

                    # Compter les différents types de coups du joueur analysé uniquement
                    for move_data in moves_list:
                        # On considère le coup du joueur analysé si c'est son tour
                        is_white_move = move_data.get('is_white', None)
                        if is_white_move is not None and is_white_move != player_is_white:
                            continue  # ignorer les coups de l'adversaire
                        move_quality = move_data.get('move_quality', '')
                        if move_quality == 'best':
                            context['best_moves_count'] += 1
                        elif move_quality == 'excellent':
                            context['excellent_moves_count'] += 1
                        elif move_quality == 'good':
                            context['good_moves_count'] += 1
                
                return render(request, 'chessTrainer/game_detail_enhanced.html', context)
            else:
                print(f"⚠️ Partie {game_id} trouvée en base mais sans PGN - récupération depuis l'API")
                
        except ChessGame.DoesNotExist:
            print(f"⚠️ Partie {game_id} non trouvée en base - récupération depuis l'API")
        
        # Si la partie n'est pas en base ou sans PGN, la récupérer depuis l'API
        # Récupérer toutes les parties pour trouver celle demandée
        all_games = fetch_all_games(username)
        
        if not all_games:
            messages.error(request, f"Aucune partie trouvée pour {username}")
            return redirect('chessTrainer:list_games', username=username)
        
        # Trouver la partie spécifique
        selected_game = None
        for game in all_games:
            if game.get('url', '').endswith(f'/{game_id}'):
                selected_game = game
                break
        
        if not selected_game:
            messages.error(request, "Partie non trouvée")
            return redirect('chessTrainer:list_games', username=username)
        
        # Récupérer les détails de la partie (PGN)
        game_details = fetch_game_details(selected_game)
        
        if not game_details:
            messages.error(request, "Impossible de récupérer les détails de la partie")
            return redirect('chessTrainer:list_games', username=username)
        
        # Sauvegarder ou mettre à jour la partie en base
        chess_game = save_or_update_game(username, selected_game, game_details, auto_analyze=True)
        
        # Analyser la partie avec Stockfish
        analysis_result = analyze_game_with_stockfish(chess_game)
        
        if not analysis_result:
            messages.error(request, "Erreur lors de l'analyse de la partie. Le PGN pourrait être invalide.")
            return redirect('chessTrainer:list_games', username=username)
        
        # Préparer le contexte pour l'affichage enrichi
        context = {
            'chess_game': chess_game,
            'username': username,
            'errors_count': 0,
            'best_moves_count': 0,
            'excellent_moves_count': 0,
            'good_moves_count': 0,
            'inaccuracies_count': 0,
            'mistakes_count': 0,
            'blunders_count': 0,
            'average_accuracy': 0,
        }
        
        if chess_game.analyzed and chess_game.moves_data:
            # Accéder aux données de mouvement
            moves_data = chess_game.moves_data
            if isinstance(moves_data, dict) and 'moves' in moves_data:
                moves_list = moves_data['moves']
            else:
                moves_list = moves_data if isinstance(moves_data, list) else []
            
            # Ajouter les moves_data au context pour le template
            context['chess_game'].moves_data = moves_list
            
            # Récupérer les statistiques améliorées (en vérifiant le type)
            if isinstance(moves_data, dict):
                context['inaccuracies_count'] = moves_data.get('inaccuracies_count', 0)
                context['mistakes_count'] = moves_data.get('mistakes_count', 0)
                context['blunders_count'] = moves_data.get('blunders_count', 0)
                context['average_accuracy'] = moves_data.get('average_accuracy', 0)
                context['errors_count'] = moves_data.get('errors_count', 0)
            else:
                # Fallback pour anciens formats de données
                context['inaccuracies_count'] = 0
                context['mistakes_count'] = 0
                context['blunders_count'] = 0
                context['average_accuracy'] = 0
                context['errors_count'] = 0
            
            # Compter les différents types de coups depuis les données individuelles
            for move_data in moves_list:
                move_quality = move_data.get('move_quality', '')
                if move_quality == 'best':
                    context['best_moves_count'] += 1
                elif move_quality == 'excellent':
                    context['excellent_moves_count'] += 1
                elif move_quality == 'good':
                    context['good_moves_count'] += 1
        
        if context['errors_count'] > 0:
            messages.success(request, f"Partie analysée avec succès ! {context['errors_count']} erreur(s) détectée(s).")
        else:
            messages.info(request, "Partie analysée ! Aucune erreur majeure détectée.")
        
        return render(request, 'chessTrainer/game_detail_enhanced.html', context)
        
    except Exception as e:
        print(f"Erreur dans analyze_specific_game: {e}")
        messages.error(request, f"Erreur lors de l'analyse: {str(e)}")
        return redirect('chessTrainer:list_games', username=username)


def analyze_game_in_background(chess_game, username, game_id, force_reanalyze=False):
    """Analyser une partie en arrière-plan avec callback de progression"""
    def progress_callback(progress, message, current, total, errors):
        # Envoyer des événements SSE
        send_analysis_event(username, game_id, progress, message, current, total, errors, 'running')
    
    try:
        # Initialiser la progression
        send_analysis_event(username, game_id, 0, "Démarrage de l'analyse...", 0, 0, 0, 'running')
        
        if force_reanalyze:
            # Marquer comme non analysée pour forcer la re-analyse
            chess_game.analyzed = False
            chess_game.moves_data = {}
            chess_game.save()
        
        # Lancer l'analyse avec callback de progression
        analyze_game_with_stockfish(chess_game, progress_callback=progress_callback)
        
        # Calculer le nombre total de coups
        total_moves = len(chess_game.moves_data.get('moves', [])) if chess_game.moves_data else 0
        errors_count = len([m for m in chess_game.moves_data.get('moves', []) if m.get('is_error', False)]) if chess_game.moves_data else 0
        
        # Marquer comme terminée
        send_analysis_event(username, game_id, 100, "Analyse terminée !", 
                           total_moves, total_moves, errors_count, 'completed')
        
        print(f"✅ Analyse de {game_id} terminée en arrière-plan")
        
        # Nettoyer l'événement après 3 secondes
        def cleanup():
            time.sleep(3)
            clear_analysis_event(username, game_id)
        
        cleanup_thread = threading.Thread(target=cleanup)
        cleanup_thread.daemon = True
        cleanup_thread.start()
        
    except Exception as e:
        print(f"❌ Erreur lors de l'analyse en arrière-plan: {e}")
        send_analysis_event(username, game_id, -1, f"Erreur: {str(e)}", 0, 0, 0, 'error')

def force_analyze_game(request, username, game_id):
    """Forcer la re-analyse d'une partie (même si déjà analysée)"""
    
    if not CHESS_AVAILABLE:
        messages.error(request, "Les librairies d'analyse d'échecs ne sont pas installées.")
        return redirect('chessTrainer:list_games', username=username)
    
    if not STOCKFISH_AVAILABLE:
        messages.error(request, "❌ Stockfish n'est pas disponible. Re-analyse impossible. Installation recommandée: brew install stockfish")
        return redirect('chessTrainer:list_games', username=username)
    
    try:
        # Chercher la partie dans la base de données
        try:
            chess_game = ChessGame.objects.get(game_id=game_id, username=username)
            
            if chess_game.pgn:
                print(f"🔄 Lancement re-analyse de la partie {game_id} en arrière-plan")
                
                # Lancer l'analyse en arrière-plan
                analysis_thread = threading.Thread(
                    target=analyze_game_in_background, 
                    args=(chess_game, username, game_id, True)
                )
                analysis_thread.daemon = True
                analysis_thread.start()
                
                # Retourner immédiatement une réponse JSON pour les requêtes AJAX
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'status': 'started',
                        'message': 'Analyse lancée en arrière-plan'
                    })
                
                messages.success(request, f"✅ Re-analyse de la partie lancée en arrière-plan !")
                
                # Rediriger vers l'affichage
                return redirect('chessTrainer:analyze_specific_game', username=username, game_id=game_id)
            else:
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({'error': 'Aucun PGN disponible pour cette partie'})
                messages.error(request, "❌ Aucun PGN disponible pour cette partie")
                return redirect('chessTrainer:list_games', username=username)
                
        except ChessGame.DoesNotExist:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'error': 'Partie non trouvée en base de données'})
            messages.error(request, f"❌ Partie {game_id} non trouvée en base de données")
            return redirect('chessTrainer:list_games', username=username)
        
    except Exception as e:
        print(f"❌ Erreur dans force_analyze_game: {e}")
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'error': f'Erreur lors de la re-analyse: {str(e)}'})
        messages.error(request, f"Erreur lors de la re-analyse: {str(e)}")
        return redirect('chessTrainer:list_games', username=username)


def fetch_new_games_only(username, force_full_sync=False, months_limit=None, session_id=None):
    """Récupérer uniquement les nouvelles parties depuis la dernière synchronisation"""
    
    try:
        # Récupérer l'état de synchronisation
        sync_status, created = PlayerSyncStatus.objects.get_or_create(
            username=username,
            defaults={
                'total_games_count': 0,
                'sync_count': 0
            }
        )
        
        print(f"🔄 Synchronisation pour {username}")
        print(f"📊 État actuel: {sync_status.total_games_count} parties, dernière sync: {sync_status.last_sync_time}")
        
        if session_id:
            send_analysis_progress(username, session_id, 'sync_progress', f'Vérification des archives Chess.com...', 0, 0, 0)
        
        if created or force_full_sync:
            print("🆕 Première synchronisation ou synchronisation forcée - récupération complète")
            max_archives = months_limit if months_limit else 12
        else:
            # Synchronisation incrémentale - chercher dans les archives récentes
            print("⚡ Synchronisation incrémentale - recherche des nouvelles parties")
            max_archives = months_limit if months_limit else 3  # Utiliser months_limit ou 3 par défaut
        
        print(f"📅 Recherche dans les {max_archives if max_archives else 'toutes les'} dernières archives")
        
        if session_id:
            send_analysis_progress(username, session_id, 'sync_progress', f'Téléchargement des {max_archives} dernières archives...', 0, 0, 0)
        
        # Récupérer les parties depuis l'API
        all_games = fetch_all_games(username, max_archives=max_archives)
        
        if not all_games:
            print("❌ Aucune partie récupérée depuis l'API")
            if session_id:
                send_analysis_progress(username, session_id, 'sync_progress', 'Aucune partie trouvée sur Chess.com', 0, 0, 0)
            return []
        
        if session_id:
            send_analysis_progress(username, session_id, 'sync_progress', f'{len(all_games)} parties récupérées, filtrage en cours...', 0, 0, 0)
        
        # Filtrer les nouvelles parties si on fait une sync incrémentale
        if not created and not force_full_sync and sync_status.last_game_end_time:
            print(f"🔍 Filtrage des parties postérieures à {sync_status.last_game_end_time}")
            
            last_sync_timestamp = sync_status.last_game_end_time.timestamp()
            new_games = []
            
            for game in all_games:
                game_end_time = game.get('end_time', 0)
                if game_end_time > last_sync_timestamp:
                    new_games.append(game)
            
            print(f"✨ {len(new_games)} nouvelles parties trouvées sur {len(all_games)} récupérées")
            filtered_games = new_games
        else:
            print(f"📥 Récupération complète de {len(all_games)} parties")
            filtered_games = all_games
        
        # Mettre à jour l'état de synchronisation
        if filtered_games:
            # Trouver la partie la plus récente
            latest_game = max(filtered_games, key=lambda x: x.get('end_time', 0))
            latest_end_time = datetime.fromtimestamp(latest_game.get('end_time', 0))
            
            sync_status.last_game_end_time = latest_end_time
            sync_status.last_sync_time = timezone.now()
            sync_status.total_games_count = len(ChessGame.objects.filter(username=username)) + len(filtered_games)
            sync_status.sync_count += 1
            sync_status.save()
            
            print(f"💾 État de sync mis à jour: dernière partie du {latest_end_time}")
        
        return filtered_games
        
    except Exception as e:
        print(f"❌ Erreur lors de la synchronisation: {e}")
        return []


def fetch_all_games(username, max_archives=12):
    """Récupérer toutes les parties d'un joueur depuis Chess.com API avec pagination intelligente"""
    
    try:
        # Récupérer la liste des archives
        archives_url = f"https://api.chess.com/pub/player/{username}/games/archives"
        
        print(f"Récupération des archives: {archives_url}")
        
        response = requests.get(archives_url, timeout=15, headers={
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        })
        
        if response.status_code == 200:
            data = response.json()
            archives = data.get('archives', [])
            
            if archives:
                all_games = []
                
                # Récupérer plus d'archives pour avoir plus de parties
                # Prendre les dernières archives (max_archives au lieu de 3)
                recent_archives = archives[-max_archives:] if len(archives) > max_archives else archives
                
                print(f"Récupération de {len(recent_archives)} archives sur {len(archives)} disponibles")
                
                for i, archive_url in enumerate(recent_archives):
                    print(f"Récupération de l'archive {i+1}/{len(recent_archives)}: {archive_url}")
                    
                    try:
                        archive_response = requests.get(archive_url, timeout=15, headers={
                            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
                        })
                        
                        if archive_response.status_code == 200:
                            archive_data = archive_response.json()
                            games = archive_data.get('games', [])
                            all_games.extend(games)
                            print(f"  → {len(games)} parties ajoutées (total: {len(all_games)})")
                        else:
                            print(f"  → Erreur HTTP {archive_response.status_code}")
                            
                    except requests.exceptions.Timeout:
                        print(f"  → Timeout pour l'archive {archive_url}")
                        continue
                    except requests.exceptions.RequestException as e:
                        print(f"  → Erreur réseau pour l'archive {archive_url}: {e}")
                        continue
                
                if all_games:
                    # Trier par date décroissante
                    all_games.sort(key=lambda x: x.get('end_time', 0), reverse=True)
                    print(f"✅ Total final: {len(all_games)} parties récupérées pour {username}")
                    
                    # Afficher quelques statistiques
                    time_classes = {}
                    for game in all_games:
                        tc = game.get('time_class', 'unknown')
                        time_classes[tc] = time_classes.get(tc, 0) + 1
                    
                    print("📊 Répartition par cadence:")
                    for tc, count in sorted(time_classes.items()):
                        print(f"  - {tc}: {count} parties")
                    
                    return all_games
                else:
                    print("❌ Aucune partie trouvée dans les archives")
                    return []
            else:
                print("❌ Aucune archive trouvée")
                return []
        
        elif response.status_code == 404:
            print(f"❌ Joueur {username} non trouvé")
            return []
        else:
            print(f"❌ Erreur API {response.status_code}: {response.text}")
            return []
        
    except Exception as e:
        print(f"❌ Erreur API Chess.com: {e}")
        return []


def fetch_game_details(game_data):
    """Récupérer les détails d'une partie (PGN)"""
    
    try:
        # Le PGN peut être directement dans les données de la partie
        pgn = game_data.get('pgn', '')
        
        if pgn:
            return {
                'pgn': pgn,
                'white': game_data.get('white', {}).get('username', ''),
                'black': game_data.get('black', {}).get('username', ''),
                'result': game_data.get('white', {}).get('result', ''),
                'time_control': game_data.get('time_control', ''),
                'time_class': game_data.get('time_class', ''),
                'rated': game_data.get('rated', True),
                'url': game_data.get('url', ''),
                'uuid': game_data.get('uuid', '')
            }
        
        # Si pas de PGN, retourner None car on ne peut pas analyser sans PGN
        if not pgn:
            print("Aucun PGN trouvé dans les données de la partie")
            return None
        
        return {
            'pgn': pgn,
            'white': game_data.get('white', {}).get('username', ''),
            'black': game_data.get('black', {}).get('username', ''),
            'result': game_data.get('white', {}).get('result', ''),
            'time_control': game_data.get('time_control', ''),
            'time_class': game_data.get('time_class', ''),
            'rated': game_data.get('rated', True),
            'url': game_data.get('url', ''),
            'uuid': game_data.get('uuid', '')
        }
        
    except Exception as e:
        print(f"Erreur récupération détails: {e}")
        return None


def save_or_update_game(username, game_data, game_details, auto_analyze=True):
    """Sauvegarder ou mettre à jour une partie en base"""
    
    game_id = str(game_data.get('uuid', ''))
    
    # Convertir les timestamps
    start_time_raw = game_data.get('start_time', 0)
    end_time_raw = game_data.get('end_time', 0)
    
    # Si start_time est 0 (manquant), utiliser end_time comme fallback
    if start_time_raw == 0 and end_time_raw > 0:
        start_time = datetime.fromtimestamp(end_time_raw)
        print(f"⚠️ start_time manquant pour {game_id[:8]}, utilisation de end_time: {start_time}")
    else:
        start_time = datetime.fromtimestamp(start_time_raw)
    
    end_time = datetime.fromtimestamp(end_time_raw)
    
    # Déterminer qui a gagné en regardant les résultats des deux joueurs
    white_result = game_data.get('white', {}).get('result', '')
    black_result = game_data.get('black', {}).get('result', '')
    
    if white_result == 'win':
        overall_result = 'white_win'
    elif black_result == 'win':
        overall_result = 'black_win'
    else:
        overall_result = white_result  # draw, agreed, etc.
    
    chess_game, created = ChessGame.objects.get_or_create(
        game_id=game_id,
        defaults={
            'username': username,
            'game_url': game_data.get('url', ''),
            'white_player': game_data.get('white', {}).get('username', ''),
            'black_player': game_data.get('black', {}).get('username', ''),
            'time_control': game_data.get('time_control', ''),
            'rated': game_data.get('rated', True),
            'result': overall_result,
            'start_time': start_time,
            'end_time': end_time,
            'pgn': game_details.get('pgn', ''),
        }
    )
    
    # Si la partie existe déjà mais n'est pas analysée, on met à jour le PGN
    if not created and not chess_game.analyzed:
        chess_game.pgn = game_details.get('pgn', '')
        chess_game.save()
    
    # Analyser automatiquement si demandé et pas encore analysé
    if auto_analyze and not chess_game.analyzed and chess_game.pgn:
        analyze_game_with_stockfish(chess_game)
    
    return chess_game


def analyze_unanalyzed_games(username):
    """Analyser toutes les parties non analysées d'un utilisateur avec Stockfish uniquement"""
    
    if not CHESS_AVAILABLE:
        print("❌ Librairies d'échecs non disponibles")
        return 0
    
    if not STOCKFISH_AVAILABLE:
        print("❌ Stockfish non disponible - aucune partie ne sera analysée")
        return 0
    
    unanalyzed_games = ChessGame.objects.filter(
        username=username,
        analyzed=False,
        pgn__isnull=False
    ).exclude(pgn='')
    
    print(f"🔍 Analyse de {unanalyzed_games.count()} parties non analysées pour {username}")
    
    analyzed_count = 0
    for chess_game in unanalyzed_games:
        try:
            analyze_game_with_stockfish(chess_game)
            analyzed_count += 1
            print(f"  ✅ Partie {chess_game.game_id} analysée ({analyzed_count}/{unanalyzed_games.count()})")
        except Exception as e:
            print(f"  ❌ Erreur lors de l'analyse de la partie {chess_game.game_id}: {e}")
    
    print(f"🎯 {analyzed_count} parties analysées avec succès")
    return analyzed_count


def analyze_game_with_stockfish(chess_game, depth=18, time_limit=0.5, progress_callback=None):
    """
    Analyser une partie avec Stockfish - Version améliorée
    
    Améliorations :
    - Profondeur adaptative selon la phase de jeu
    - Seuils d'erreur ajustés selon les standards modernes
    - Calcul du centipawn loss plus précis
    - Gestion des positions de mat et nulle
    - Analyse plus rapide mais plus précise
    - Évaluation toujours du point de vue des blancs
    - Callback de progression pour la barre de progression
    """
    
    def score_to_centipawns(score):
        """Convertir un score Stockfish en centipawns du point de vue des blancs"""
        if score.is_mate():
            mate_value = score.white().mate()
            if mate_value is None:
                return 0
            return 1000 if mate_value > 0 else -1000
        else:
            cp_score = score.white().score()
            return cp_score if cp_score is not None else 0
    
    if not CHESS_AVAILABLE:
        print("❌ Librairies d'échecs non disponibles")
        chess_game.moves_data = {
            'moves': [],
            'total_moves': 0,
            'errors_count': 0,
            'error_message': 'Les librairies d\'analyse d\'échecs ne sont pas installées.'
        }
        chess_game.analyzed = False
        chess_game.save()
        return False
    
    if not STOCKFISH_AVAILABLE:
        print("❌ Stockfish non disponible - partie marquée comme non analysée")
        chess_game.analyzed = False
        chess_game.save()
        return False
    
    try:
        # Parser le PGN avec python-chess
        pgn_io = StringIO(chess_game.pgn)
        game = chess.pgn.read_game(pgn_io)
        
        if not game:
            print("❌ Impossible de parser le PGN")
            chess_game.moves_data = {
                'moves': [],
                'total_moves': 0,
                'errors_count': 0,
                'error_message': 'Impossible de parser le PGN de la partie'
            }
            chess_game.analyzed = True
            chess_game.save()
            return False
        
        # Initialiser Stockfish avec des paramètres optimisés
        with chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH) as engine:
            # Configurer Stockfish pour de meilleures performances
            engine.configure({"Hash": 128, "Threads": 1})
            
            board = game.board()
            move_analysis = []
            ply_count = 0  # Compteur de demi-coups (ply)
            errors_count = 0
            inaccuracies_count = 0
            mistakes_count = 0
            blunders_count = 0
            
            # Compter le nombre total de coups pour la progression
            total_moves = sum(1 for node in game.mainline() if node.move is not None)
            if progress_callback:
                progress_callback(0, "Début de l'analyse...", 0, total_moves, 0)
            
            current_move_index = 0
            last_sent_progress = -1  # Pour éviter d'envoyer le même pourcentage plusieurs fois
            
            # Analyser chaque coup
            for node in game.mainline():
                if node.move is None:
                    continue
                    
                ply_count += 1
                current_move_index += 1
                move = node.move
                
                # Calculer le numéro de coup selon la notation standard d'échecs
                move_number = (ply_count + 1) // 2  # Numéro du coup (1, 2, 3, ...)
                is_white_move = (ply_count % 2 == 1)  # True si c'est le coup des blancs
                
                # Mettre à jour la progression - envoyer uniquement quand on change de tranche de 10%
                progress_percent = int((current_move_index / total_moves) * 100)
                
                # Envoyer un événement de progression tous les 10% ou pour certains coups importants
                if (progress_percent >= last_sent_progress + 10 or 
                    progress_percent == 100 or 
                    current_move_index == 1 or
                    current_move_index % max(1, total_moves // 10) == 0):
                    
                    if progress_callback:
                        progress_callback(
                            progress_percent, 
                            f"Analyse en cours... {progress_percent}% (coup {move_number}{'.' if is_white_move else '...'})", 
                            current_move_index, 
                            total_moves, 
                            errors_count
                        )
                    last_sent_progress = progress_percent
                
                # Position avant le coup
                position_before = board.copy()
                
                # Profondeur adaptative selon la phase de jeu
                piece_count = len(position_before.piece_map())
                if piece_count <= 10:  # Finale
                    adaptive_depth = min(depth + 4, 22)
                elif piece_count <= 20:  # Milieu de jeu
                    adaptive_depth = depth
                else:  # Ouverture
                    adaptive_depth = max(depth - 2, 12)
                
                try:
                    # Analyse de la position avant le coup avec MultiPV
                    limit = chess.engine.Limit(depth=adaptive_depth, time=time_limit)
                    
                    try:
                        # Analyser avec MultiPV=5 pour plus de précision
                        multi_info = engine.analyse(position_before, limit, multipv=5)
                        
                        top_moves = []
                        evaluation_before = None
                        
                        if isinstance(multi_info, list):
                            # Stockfish retourne une liste avec MultiPV
                            for i, pv_info in enumerate(multi_info):
                                if 'pv' in pv_info and pv_info['pv'] and len(pv_info['pv']) > 0:
                                    move_candidate = pv_info['pv'][0]
                                    score = pv_info.get('score', chess.engine.PovScore(chess.engine.Cp(0), position_before.turn))
                                    
                                    # Gestion des scores de mat - toujours du point de vue des blancs
                                    eval_cp = score_to_centipawns(score)
                                    
                                    # Extraire les 6 premiers coups de la variante principale
                                    pv_moves = []
                                    temp_board = position_before.copy()
                                    for j, pv_move in enumerate(pv_info['pv'][:6]):  # Limiter à 6 coups
                                        try:
                                            san_move = temp_board.san(pv_move)
                                            pv_moves.append({
                                                'uci': pv_move.uci(),
                                                'san': san_move,
                                                'move_number': (temp_board.fullmove_number if temp_board.turn == chess.WHITE 
                                                               else temp_board.fullmove_number),
                                                'is_white': temp_board.turn == chess.WHITE
                                            })
                                            temp_board.push(pv_move)
                                        except:
                                            break  # Arrêter si coup invalide
                                    
                                    top_moves.append({
                                        'move': move_candidate.uci(),
                                        'move_san': position_before.san(move_candidate),
                                        'evaluation': eval_cp,
                                        'rank': i + 1,
                                        'is_mate': score.is_mate(),
                                        'mate_in': score.relative.mate() if score.is_mate() else None,
                                        'pv_line': pv_moves  # Nouvelle donnée : variante principale
                                    })
                                    
                                    # L'évaluation de référence est celle du meilleur coup
                                    if i == 0:
                                        evaluation_before = score
                        else:
                            # Fallback pour un seul résultat
                            if 'pv' in multi_info and multi_info['pv'] and len(multi_info['pv']) > 0:
                                move_candidate = multi_info['pv'][0]
                                score = multi_info.get('score', chess.engine.PovScore(chess.engine.Cp(0), position_before.turn))
                                
                                # Gestion des scores de mat - toujours du point de vue des blancs
                                eval_cp = score_to_centipawns(score)
                                
                                top_moves.append({
                                    'move': move_candidate.uci(),
                                    'move_san': position_before.san(move_candidate),
                                    'evaluation': eval_cp,
                                    'rank': 1,
                                    'is_mate': score.is_mate(),
                                    'mate_in': score.relative.mate() if score.is_mate() else None
                                })
                                evaluation_before = score
                        
                    except Exception as multipv_error:
                        print(f"⚠️ MultiPV échoué, fallback: {multipv_error}")
                        # Analyse simple
                        info = engine.analyse(position_before, limit)
                        evaluation_before = info.get("score", chess.engine.PovScore(chess.engine.Cp(0), position_before.turn))
                        
                        best_move_result = engine.play(position_before, limit)
                        best_move_candidate = best_move_result.move
                        
                        # Utiliser notre fonction pour normaliser l'évaluation
                        eval_cp = score_to_centipawns(evaluation_before)
                        
                        top_moves = [{
                            'move': best_move_candidate.uci(),
                            'move_san': position_before.san(best_move_candidate),
                            'evaluation': eval_cp,
                            'rank': 1,
                            'is_mate': evaluation_before.is_mate(),
                            'mate_in': evaluation_before.relative.mate() if evaluation_before.is_mate() else None
                        }]
                    
                    if not top_moves:
                        raise Exception("Aucun coup trouvé par Stockfish")
                    
                    best_move_uci = top_moves[0]['move']
                    best_move_obj = chess.Move.from_uci(best_move_uci)
                    
                    # Calculer l'évaluation du coup joué
                    played_move_eval = None
                    played_move_rank = None
                    
                    # Chercher le coup joué dans les top moves
                    for i, top_move in enumerate(top_moves):
                        if chess.Move.from_uci(top_move['move']) == move:
                            played_move_eval = top_move['evaluation']
                            played_move_rank = i + 1
                            break
                    
                    # Si le coup joué n'est pas dans les top moves, l'analyser séparément
                    if played_move_eval is None:
                        temp_board = position_before.copy()
                        temp_board.push(move)
                        played_info = engine.analyse(temp_board, chess.engine.Limit(depth=adaptive_depth-2, time=time_limit*0.5))
                        played_score = played_info.get("score", chess.engine.PovScore(chess.engine.Cp(0), temp_board.turn))
                        
                        # Le score est du point de vue du joueur qui vient de jouer (temp_board.turn)
                        # Mais nous voulons toujours l'évaluation du point de vue des blancs
                        played_move_eval = score_to_centipawns(played_score)
                        
                        played_move_rank = len(top_moves) + 1
                    
                    # Calculer le centipawn loss du point de vue du joueur actuel
                    best_eval = top_moves[0]['evaluation']
                    
                    # Avec .white(), les évaluations sont toujours du point de vue des blancs
                    # Le centipawn_loss est la différence entre le meilleur coup et le coup joué
                    if position_before.turn == chess.WHITE:
                        # Tour des blancs : meilleur coup a une évaluation plus élevée
                        centipawn_loss = max(0, best_eval - played_move_eval)
                    else:
                        # Tour des noirs : meilleur coup a une évaluation plus basse (du point de vue des blancs)
                        # Donc la perte est : (évaluation du coup joué) - (évaluation du meilleur coup)
                        centipawn_loss = max(0, played_move_eval - best_eval)
                    
                    # Jouer le coup réel
                    board.push(move)
                    
                    # Pour les erreurs importantes, analyser aussi le meilleur coup de l'adversaire
                    opponent_punishment = None
                    if centipawn_loss >= 100:  # Pour les erreurs et gaffes
                        try:
                            # Analyser la position APRÈS le coup de gaffe pour trouver le meilleur coup de l'adversaire
                            position_after_blunder = board.copy()
                            opponent_analysis = engine.analyse(position_after_blunder, 
                                                            chess.engine.Limit(depth=adaptive_depth, time=time_limit), 
                                                            multipv=3)
                            
                            if isinstance(opponent_analysis, list) and len(opponent_analysis) > 0:
                                best_opponent_move = opponent_analysis[0]
                                if 'pv' in best_opponent_move and best_opponent_move['pv']:
                                    # Extraire la ligne de jeu de l'adversaire qui punit la gaffe
                                    punishment_moves = []
                                    temp_board = position_after_blunder.copy()
                                    for j, pv_move in enumerate(best_opponent_move['pv'][:6]):  # 6 coups max
                                        try:
                                            san_move = temp_board.san(pv_move)
                                            punishment_moves.append({
                                                'uci': pv_move.uci(),
                                                'san': san_move,
                                                'move_number': (temp_board.fullmove_number if temp_board.turn == chess.WHITE 
                                                               else temp_board.fullmove_number),
                                                'is_white': temp_board.turn == chess.WHITE
                                            })
                                            temp_board.push(pv_move)
                                        except:
                                            break
                                    
                                    opponent_punishment = {
                                        'move_san': position_after_blunder.san(best_opponent_move['pv'][0]),
                                        'evaluation': score_to_centipawns(best_opponent_move.get('score', 
                                                     chess.engine.PovScore(chess.engine.Cp(0), position_after_blunder.turn))),
                                        'pv_line': punishment_moves
                                    }
                        except Exception as e:
                            print(f"⚠️ Erreur analyse coup adversaire: {e}")
                    
                    # Classification améliorée selon les nouveaux critères
                    is_best_move = (move == best_move_obj)
                    is_in_top5 = played_move_rank <= 5 if played_move_rank else False
                    
                    # Déterminer la qualité du coup selon les nouveaux critères
                    if is_best_move or centipawn_loss < 10:
                        move_quality = "best"
                        error_type = "aucune"
                        quality_icon = "⭐"
                        quality_text = "Meilleur coup"
                    elif is_in_top5 and centipawn_loss < 20:
                        move_quality = "good"
                        error_type = "aucune"
                        quality_icon = "👍"
                        quality_text = "Bon coup"
                    elif centipawn_loss >= 200:
                        # Gaffe : perte très importante
                        move_quality = "blunder"
                        error_type = "blunder"
                        quality_icon = "💥"
                        quality_text = "Gaffe"
                        blunders_count += 1
                    elif centipawn_loss >= 100:
                        # Erreur grave
                        move_quality = "mistake"
                        error_type = "mistake"
                        quality_icon = "❌"
                        quality_text = "Erreur"
                        mistakes_count += 1
                    elif centipawn_loss >= 70:
                        # Imprécision : première catégorie d'erreur
                        move_quality = "inaccuracy"
                        error_type = "inaccuracy"
                        quality_icon = "?!"
                        quality_text = "Imprécision"
                        inaccuracies_count += 1
                    else:
                        # Coup acceptable : toutes les pertes < 80 cp
                        move_quality = "acceptable"
                        error_type = "aucune"
                        quality_icon = "✓"
                        quality_text = "Coup acceptable"
                    
                    # Compter les erreurs selon la nouvelle classification
                    is_error = error_type != "aucune"
                    if is_error:
                        errors_count += 1
                        # Log détaillé pour chaque erreur/gaffe/imprécision du côté du joueur analysé
                        # On ne log que les erreurs du côté du joueur (noir ou blanc selon la partie)
                        joueur_analyse_noir = chess_game.username.lower() == chess_game.black_player.lower()
                        if (joueur_analyse_noir and not is_white_move) or (not joueur_analyse_noir and is_white_move):
                            # Notation officielle : 14. ..f5 ou 14. f5
                            notation = f"{move_number}. {'..' if not is_white_move else ''}{position_before.san(move)}"
                            print(f"   ➡️ Erreur détectée : {notation} ({error_type})")
                    
                    # Calculer l'accuracy (pourcentage)
                    accuracy = max(0, 100 - (centipawn_loss / 2))  # Formule simplifiée
                    
                    move_analysis.append({
                        'move_number': move_number,
                        'is_white_move': is_white_move,  # Nouveau champ pour indiquer si c'est le coup des blancs
                        'ply_count': ply_count,  # Numéro du demi-coup
                        'move': move.uci(),
                        'move_san': position_before.san(move),
                        'best_move': best_move_uci,
                        'best_move_san': top_moves[0]['move_san'],
                        'top_moves': top_moves,
                        'opponent_punishment': opponent_punishment,  # Nouveau : coup de l'adversaire qui punit la gaffe
                        'evaluation_before': best_eval,
                        'evaluation_after': played_move_eval,
                        'evaluation_diff': -centipawn_loss,  # Négatif car c'est une perte
                        'centipawn_loss': centipawn_loss,
                        'accuracy': round(accuracy, 1),
                        'move_rank': played_move_rank,
                        'is_error': is_error,
                        'error_type': error_type,
                        'move_quality': move_quality,
                        'quality_icon': quality_icon,
                        'quality_text': quality_text,
                        'is_best_move': is_best_move,
                        'is_in_top5': is_in_top5,
                        'depth': adaptive_depth,
                        'time_spent': time_limit,
                        'piece_count': piece_count,  # Pour statistiques
                    })
                    
                    if ply_count % 10 == 0:  # Afficher tous les 10 demi-coups (= 5 coups complets)
                        print(f"  📊 Analysé {ply_count//2} coups complets... (Prof: {adaptive_depth}, Erreurs: {errors_count})")
                        
                except Exception as e:
                    print(f"❌ Erreur analyse coup {move_number}: {e}")
                    # Jouer le coup même en cas d'erreur
                    board.push(move)
                    continue
        
        # Calculer des statistiques avancées
        total_accuracy = sum(move['accuracy'] for move in move_analysis) / len(move_analysis) if move_analysis else 0
        
        # Sauvegarder les résultats avec plus de détails
        chess_game.moves_data = {
            'moves': move_analysis,
            'total_moves': ply_count,  # Nombre de demi-coups
            'total_full_moves': move_number,  # Nombre de coups complets
            'errors_count': errors_count,
            'inaccuracies_count': inaccuracies_count,
            'mistakes_count': mistakes_count,
            'blunders_count': blunders_count,
            'average_accuracy': round(total_accuracy, 1),
            'analysis_engine': 'stockfish',
            'analysis_depth': depth,
            'analysis_time': time_limit,
            'version': '2.0'  # Version améliorée
        }
        chess_game.analyzed = True
        chess_game.save()
        
        # Créer les objets MoveAnalysis et TrainingPosition pour le module d'entraînement
        training_positions_created = create_move_analyses_from_data(chess_game, move_analysis)
        
        # Mise à jour finale de la progression
        if progress_callback:
            progress_callback(100, "Analyse terminée !", ply_count//2, ply_count//2, errors_count)
        
        print(f"✅ Analyse Stockfish améliorée terminée:")
        print(f"   📊 {ply_count} demi-coups analysés ({ply_count//2} coups complets)")
        print(f"   ❌ {blunders_count} gaffes, {mistakes_count} erreurs, {inaccuracies_count} imprécisions")
        print(f"   🎯 Précision moyenne: {total_accuracy:.1f}%")
        print(f"   🏋️ {training_positions_created} positions d'entraînement créées")
        return True
        
    except Exception as e:
        print(f"❌ Erreur lors de l'analyse Stockfish: {e}")
        chess_game.analyzed = False
        chess_game.moves_data = {
            'moves': [],
            'total_moves': 0,
            'errors_count': 0,
            'error_message': f'Erreur lors de l\'analyse Stockfish: {str(e)}'
        }
        chess_game.save()
        return False


def create_move_analyses_from_data(chess_game, move_analysis_data):
    """Créer les objets MoveAnalysis et TrainingPosition à partir des données d'analyse"""
    from .models import MoveAnalysis, TrainingPosition
    
    # Supprimer les analyses existantes pour cette partie
    MoveAnalysis.objects.filter(game=chess_game).delete()
    TrainingPosition.objects.filter(original_game=chess_game).delete()
    
    if not CHESS_AVAILABLE:
        return 0
    
    training_positions_created = 0
    
    try:
        import chess
        from io import StringIO
        
        # Parser le PGN pour obtenir les positions FEN
        pgn_io = StringIO(chess_game.pgn)
        game = chess.pgn.read_game(pgn_io)
        
        if not game:
            return 0
        
        # Déterminer la couleur du joueur dans cette partie
        player_is_white = game.headers.get('White', '').lower() == chess_game.username.lower()
        player_color = 'white' if player_is_white else 'black'
        
        board = game.board()
        move_index = 0
        
        # Parcourir chaque coup et créer les objets MoveAnalysis + TrainingPosition
        for node in game.mainline():
            if node.move is None or move_index >= len(move_analysis_data):
                continue
            
            move_data = move_analysis_data[move_index]
            move = node.move
            
            # Position avant le coup
            fen_before = board.fen()
            
            # Jouer le coup pour obtenir la position après
            board.push(move)
            fen_after = board.fen()
            
            # Déterminer la qualité selon nos critères d'entraînement
            quality = None
            if move_data.get('move_quality') in ['mistake', 'blunder']:  # ✅ Seulement erreurs et gaffes
                quality = move_data['move_quality']
            
            # Vérifier si c'est bien le tour du joueur
            is_white_move = move_data.get('is_white_move', True)
            is_player_move = (player_is_white and is_white_move) or (not player_is_white and not is_white_move)
            
            # Créer l'objet MoveAnalysis seulement pour les erreurs et gaffes DU JOUEUR
            if quality and is_player_move:
                try:
                    move_analysis_obj = MoveAnalysis.objects.create(
                        game=chess_game,
                        move_number=move_data.get('move_number', move_index + 1),
                        move_notation=move_data.get('move_san', move.uci()),
                        evaluation_before=move_data.get('evaluation_before', 0),
                        evaluation_after=move_data.get('evaluation_after', 0),
                        quality=quality,
                        fen_before=fen_before,
                        fen_after=fen_after,
                        best_move=move_data.get('best_move', '')
                    )
                    
                    # Créer la position d'entraînement pour cette erreur du joueur
                    # Déterminer la difficulté basée sur la qualité du coup
                    difficulty = 'medium' if quality == 'mistake' else 'hard'  # blunder = hard
                    
                    # Préparer les évaluations
                    original_eval = move_data.get('evaluation_after', 0)
                    best_eval = move_data.get('evaluation_before', 0)
                    
                    # Créer la position d'entraînement directement
                    TrainingPosition.objects.create(
                        username=chess_game.username,
                        original_game=chess_game,
                        move_analysis=move_analysis_obj,
                        fen_position=fen_before,
                        player_color=player_color,
                        original_move=move_data.get('move_san', move.uci()),
                        original_evaluation=original_eval,
                        best_move=move_data.get('best_move', ''),
                        best_evaluation=best_eval,
                        difficulty=difficulty
                    )
                    
                    training_positions_created += 1
                    print(f"✅ Position d'entraînement créée: {move_data.get('move_san')} ({quality}) - Tour du joueur: {'Blancs' if is_white_move else 'Noirs'}")
                        
                except Exception as e:
                    # Ignorer les erreurs de contrainte unique
                    if 'UNIQUE constraint' not in str(e):
                        print(f"⚠️ Erreur création MoveAnalysis/TrainingPosition #{move_index}: {e}")
            elif quality:
                # Erreur de l'adversaire - on l'affiche dans les logs mais on ne crée pas d'objet
                print(f"ℹ️ Erreur adverse ignorée: {move_data.get('move_san')} ({quality}) - Tour de l'adversaire: {'Blancs' if is_white_move else 'Noirs'}")
            
            move_index += 1
            
        print(f"✅ Créé {MoveAnalysis.objects.filter(game=chess_game).count()} objets MoveAnalysis")
        print(f"✅ Créé {training_positions_created} positions d'entraînement")
        
        return training_positions_created
        
    except Exception as e:
        print(f"⚠️ Erreur création MoveAnalysis/TrainingPosition: {e}")
        return 0


def get_game_errors(chess_game):
    """Récupérer seulement les erreurs réelles d'une partie"""
    
    if chess_game.moves_data:
        # Gérer différents formats de données
        if isinstance(chess_game.moves_data, dict) and 'moves' in chess_game.moves_data:
            all_moves = chess_game.moves_data['moves']
        elif isinstance(chess_game.moves_data, list):
            all_moves = chess_game.moves_data
        else:
            return []
            
        # Filtrer pour ne retourner que les vraies erreurs selon notre nouveau système
        errors = []
        for move in all_moves:
            if isinstance(move, dict):
                # Utiliser le nouveau système de qualité s'il existe
                move_quality = move.get('move_quality', '')
                if move_quality in ['mistake', 'blunder']:
                    errors.append(move)
                # Fallback sur l'ancien système si move_quality n'existe pas
                elif not move_quality:
                    is_error = move.get('is_error', False)
                    error_type = move.get('error_type', 'aucune')
                    if is_error or error_type != 'aucune':
                        errors.append(move)
        return errors
    return []


def parse_pgn_moves(pgn):
    """Parser simple pour extraire les coups du PGN"""
    
    try:
        # Trouver la ligne avec les coups (après les métadonnées)
        lines = pgn.strip().split('\n')
        moves_line = ""
        
        for line in lines:
            if not line.startswith('[') and line.strip():
                moves_line += line + " "
        
        # Nettoyer et extraire les coups
        moves_text = moves_line.strip()
        
        # Supprimer les commentaires et annotations avec regex plus robuste
        import re
        
        # Supprimer tous les commentaires entre accolades { ... }
        moves_text = re.sub(r'\{[^}]*\}', ' ', moves_text)
        
        # Supprimer toutes les annotations entre crochets [ ... ] (y compris %clk)
        moves_text = re.sub(r'\[[^\]]*\]', ' ', moves_text)
        
        # Supprimer les numéros de coups (ex: 1. 2. 15. etc.)
        moves_text = re.sub(r'\d+\.+', ' ', moves_text)
        
        # Supprimer le résultat final
        moves_text = re.sub(r'\b(1-0|0-1|1/2-1/2|\*)\b', ' ', moves_text)
        
        # Supprimer les espaces multiples
        moves_text = re.sub(r'\s+', ' ', moves_text)
        
        # Diviser en coups individuels et nettoyer
        moves = moves_text.split()
        
        # Filtrer les coups valides (ne contiennent que des caractères d'échecs)
        valid_moves = []
        chess_pattern = re.compile(r'^[NBRQK]?[a-h]?[1-8]?x?[a-h][1-8](\+|#)?$|^O-O(-O)?(\+|#)?$')
        
        for move in moves:
            move = move.strip()
            if move and not move.startswith('{') and not move.startswith('['):
                # Enlever les caractères parasites
                clean_move = re.sub(r'[{}[\]%]', '', move)
                if clean_move and (chess_pattern.match(clean_move) or len(clean_move) >= 2):
                    valid_moves.append(clean_move)
        
        print(f"Coups extraits: {valid_moves[:10]}...")  # Debug: afficher les 10 premiers coups
        return valid_moves
        
    except Exception as e:
        print(f"Erreur parsing PGN: {e}")
        return []


def get_game_positions(pgn):
    """Calculer les positions pour chaque coup avec python-chess"""
    
    if CHESS_AVAILABLE:
        try:
            # Utiliser python-chess pour calculer les vraies positions
            pgn_io = StringIO(pgn)
            game = chess.pgn.read_game(pgn_io)
            
            if not game:
                print("Impossible de parser le PGN pour les positions")
                return ['rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1']
            
            positions = []
            board = game.board()
            positions.append(board.fen())  # Position initiale
            
            for move in game.mainline_moves():
                board.push(move)
                positions.append(board.fen())
                
            return positions
        except Exception as e:
            print(f"Erreur lors du calcul des positions: {e}")
    
    # Fallback : retourner seulement la position initiale
    print("Utilisation du fallback pour les positions")
    return ['rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1']


def get_player_color(username, game_data):
    """Déterminer la couleur du joueur dans la partie"""
    
    white_player = game_data.get('white', {}).get('username', '').lower()
    black_player = game_data.get('black', {}).get('username', '').lower()
    
    if username.lower() == white_player:
        return 'white'
    elif username.lower() == black_player:
        return 'black'
    else:
        # Si on ne trouve pas le joueur, on assume qu'il est blanc par défaut
        return 'white'


def get_move_analysis_data(request, username, game_id):
    """API pour récupérer les données d'analyse détaillées d'une partie"""
    
    try:
        chess_game = ChessGame.objects.get(game_id=game_id, username=username)
        
        if not chess_game.analyzed or not chess_game.moves_data:
            return JsonResponse({'error': 'Partie non analysée'})
        
        # Vérifier le type de moves_data avant d'utiliser .get()
        if isinstance(chess_game.moves_data, dict):
            moves_data = chess_game.moves_data.get('moves', [])
        else:
            moves_data = chess_game.moves_data if isinstance(chess_game.moves_data, list) else []
        
        # Formater les données pour l'affichage
        formatted_moves = []
        for move_data in moves_data:
            formatted_move = {
                'move_number': move_data.get('move_number'),
                'move_san': move_data.get('move_san'),
                'evaluation_before': move_data.get('evaluation_before', 0),
                'evaluation_after': move_data.get('evaluation_after', 0),
                'evaluation_diff': move_data.get('evaluation_diff', 0),
                'error_type': move_data.get('error_type', 'aucune'),
                'best_move_san': move_data.get('best_move_san'),
                'is_best_move': move_data.get('is_best_move', False),
            }
            formatted_moves.append(formatted_move)
        
        # Récupérer les statistiques en fonction du type de données
        if isinstance(chess_game.moves_data, dict):
            total_moves = chess_game.moves_data.get('total_moves', 0)
            errors_count = chess_game.moves_data.get('errors_count', 0)
            analysis_engine = chess_game.moves_data.get('analysis_engine', 'unknown')
        else:
            total_moves = len(moves_data)
            errors_count = sum(1 for move in moves_data if move.get('is_error', False))
            analysis_engine = 'unknown'
        
        return JsonResponse({
            'moves': formatted_moves,
            'total_moves': total_moves,
            'errors_count': errors_count,
            'analysis_engine': analysis_engine
        })
        
    except ChessGame.DoesNotExist:
        return JsonResponse({'error': 'Partie non trouvée'})


# Ancien système de cache supprimé - utilisation des SSE analysis_events

def analysis_events_stream(request, username, game_id):
    """
    Server-Sent Events pour le suivi en temps réel de l'analyse
    """
    def event_stream():
        key = f"{username}_{game_id}"
        last_progress = -1
        start_time = time.time()
        
        # Envoyer un événement initial
        initial_json = json.dumps({'type': 'connected', 'message': 'Connexion établie'})
        yield f"data: {initial_json}\n\n".encode('utf-8')
        
        while True:
            try:
                if key in analysis_events:
                    event_data = analysis_events[key]
                    current_progress = event_data['progress']
                
                    # Envoyer seulement si il y a du changement
                    if current_progress != last_progress:
                        event_json = json.dumps({
                            'type': 'progress',
                            'progress': current_progress,
                            'message': event_data['message'],
                            'current_move': event_data['current_move'],
                            'total_moves': event_data['total_moves'],
                            'errors_count': event_data['errors_count'],
                            'status': event_data['status']
                        })
                        yield f"data: {event_json}\n\n".encode('utf-8')
                        last_progress = current_progress
                    
                    # Si terminé, envoyer l'événement final et arrêter
                    if event_data['status'] in ['completed', 'error']:
                        final_json = json.dumps({
                            'type': 'finished',
                            'status': event_data['status'],
                            'message': event_data['message']
                        })
                        yield f"data: {final_json}\n\n".encode('utf-8')
                        break
            except Exception as e:
                # En cas d'erreur, envoyer un message d'erreur
                error_json = json.dumps({'type': 'error', 'message': f'Erreur SSE: {str(e)}'})
                yield f"data: {error_json}\n\n".encode('utf-8')
            
            time.sleep(0.5)  # Vérifier toutes les 500ms
            
            # Timeout après 5 minutes
            if time.time() - start_time > 300:
                timeout_json = json.dumps({'type': 'timeout', 'message': 'Timeout de connexion'})
                yield f"data: {timeout_json}\n\n".encode('utf-8')
                break
    
    response = StreamingHttpResponse(event_stream(), content_type='text/event-stream')
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'  # Pour les proxies nginx
    return response


# ===== MODULE D'ENTRAÎNEMENT =====

def training_home(request):
    """Page d'accueil du module d'entraînement"""
    return render(request, 'chessTrainer/training/home.html')


def training_session(request, username):
    """Démarrer une session d'entraînement pour un utilisateur"""
    from .models import TrainingPosition, TrainingSession
    
    # Récupérer toutes les positions d'entraînement disponibles (sans limite)
    available_positions = TrainingPosition.objects.filter(username=username).order_by('?')
    
    if not available_positions:
        messages.warning(request, f"Aucune position d'entraînement trouvée pour {username}. Analysez d'abord quelques parties pour générer des positions d'entraînement.")
        return redirect('chessTrainer:chess_analysis')
    
    # Pour une session d'entraînement, on peut prendre un échantillon plus large
    # mais pas forcément toutes les positions pour éviter une session trop longue
    max_positions_per_session = 50  # Limite raisonnable pour une session
    session_positions = available_positions[:max_positions_per_session]
    
    # Créer une nouvelle session d'entraînement
    session = TrainingSession.objects.create(
        username=username,
        max_positions=len(session_positions)
    )
    
    context = {
        'username': username,
        'session': session,
        'positions': session_positions,
        'total_positions': len(session_positions),
        'total_available': available_positions.count()
    }
    
    return render(request, 'chessTrainer/training/session.html', context)


def training_position(request, username, position_id):
    """Afficher une position d'entraînement spécifique"""
    from .models import TrainingPosition
    
    try:
        position = TrainingPosition.objects.get(id=position_id, username=username)
    except TrainingPosition.DoesNotExist:
        messages.error(request, "Position d'entraînement introuvable.")
        return redirect('chessTrainer:training_session', username=username)
    
    # Préparer les évaluations pour l'affichage (conversion en pions seulement)
    def normalize_evaluation(eval_value):
        """Normalise une évaluation pour l'affichage (conversion en pions uniquement)"""
        # Convertir en pions si nécessaire (valeurs en centipions)
        if abs(eval_value) > 50:
            eval_value = eval_value / 100.0
            
        return eval_value
    
    # Normaliser les évaluations pour l'affichage (sans inversion pour les noirs)
    display_original_eval = normalize_evaluation(position.original_evaluation)
    display_best_eval = normalize_evaluation(position.best_evaluation)
    
    # Calculer la perte due au coup original
    evaluation_loss = abs(display_best_eval - display_original_eval)
    
    context = {
        'username': username,
        'position': position,
        'fen': position.fen_position,
        'player_color': position.player_color,
        'original_move': position.original_move,
        'best_move': position.best_move,
        'display_original_eval': display_original_eval,
        'display_best_eval': display_best_eval,
        'evaluation_loss': evaluation_loss,
    }
    
    return render(request, 'chessTrainer/training/position.html', context)


def next_training_position(request, username, current_position_id):
    """Obtenir la position d'entraînement suivante"""
    from .models import TrainingPosition
    
    try:
        # Obtenir toutes les positions de l'utilisateur, triées par ID
        positions = TrainingPosition.objects.filter(username=username).order_by('id')
        
        # Trouver la position suivante
        next_position = positions.filter(id__gt=current_position_id).first()
        
        # Si pas de position suivante, prendre la première (boucle)
        if not next_position:
            next_position = positions.first()
        
        if next_position:
            return redirect('chessTrainer:training_position', username=username, position_id=next_position.id)
        else:
            # Aucune position disponible
            messages.info(request, "Aucune autre position d'entraînement disponible.")
            return redirect('chessTrainer:training_session', username=username)
            
    except TrainingPosition.DoesNotExist:
        messages.error(request, "Position d'entraînement introuvable.")
        return redirect('chessTrainer:training_session', username=username)


@csrf_exempt
def check_training_move(request):
    """API pour vérifier un coup d'entraînement (AJAX)"""
    import json
    
    if request.method != 'POST':
        return JsonResponse({'error': 'Méthode non autorisée'}, status=405)
    
    try:
        data = json.loads(request.body)
        position_id = data.get('position_id')
        attempted_move = data.get('move')
        time_spent = data.get('time_spent', 0)
        
        if not position_id or not attempted_move:
            return JsonResponse({'error': 'Données manquantes'}, status=400)
        
        position = TrainingPosition.objects.get(id=position_id)
        
        # Analyser le coup avec Stockfish
        result = analyze_training_move(position, attempted_move)
        
        # Enregistrer la tentative
        attempt = TrainingAttempt.objects.create(
            training_position=position,
            attempted_move=attempted_move,
            evaluation_after_attempt=result['evaluation'],
            result_quality=result['quality'],
            improvement_points=result['improvement_points'],
            is_better_than_original=result['is_better'],
            is_best_move=result['is_best'],
            time_spent_seconds=time_spent
        )
        
        # Mettre à jour les statistiques de la position
        position.times_played += 1
        if result['is_better'] or result['is_best']:
            position.times_solved += 1
        position.save()
        
        return JsonResponse({
            'success': True,
            'result': result
        })
        
    except TrainingPosition.DoesNotExist:
        return JsonResponse({'error': 'Position introuvable'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
    
    try:
        data = json.loads(request.body)
        position_id = data.get('position_id')
        attempted_move = data.get('move')
        time_spent = data.get('time_spent', 0)
        
        if not position_id or not attempted_move:
            return JsonResponse({'error': 'Données manquantes'}, status=400)
        
        position = TrainingPosition.objects.get(id=position_id)
        
        # Analyser le coup avec Stockfish
        result = analyze_training_move(position, attempted_move)
        
        # Enregistrer la tentative
        attempt = TrainingAttempt.objects.create(
            training_position=position,
            attempted_move=attempted_move,
            evaluation_after_attempt=result['evaluation'],
            result_quality=result['quality'],
            improvement_points=result['improvement_points'],
            is_better_than_original=result['is_better'],
            is_best_move=result['is_best'],
            time_spent_seconds=time_spent
        )
        
        # Mettre à jour les statistiques de la position
        position.times_played += 1
        if result['is_better'] or result['is_best']:
            position.times_solved += 1
        position.save()
        
        return JsonResponse({
            'success': True,
            'result': result,
            'attempt_id': attempt.id
        })
        
    except TrainingPosition.DoesNotExist:
        return JsonResponse({'error': 'Position introuvable'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


def analyze_training_move(position, attempted_move):
    """Analyser un coup d'entraînement avec Stockfish"""
    
    if not STOCKFISH_AVAILABLE:
        return {
            'evaluation': 0,
            'quality': 'unknown',
            'improvement_points': 0,
            'is_better': False,
            'is_best': False,
            'message': 'Stockfish non disponible'
        }
    
    try:
        import chess
        import chess.engine
        
        # Charger la position
        board = chess.Board(position.fen_position)
        
        # Vérifier si le coup est légal
        try:
            move = chess.Move.from_uci(attempted_move)
            if move not in board.legal_moves:
                return {
                    'evaluation': -999,
                    'quality': 'illegal',
                    'improvement_points': 0,
                    'is_better': False,
                    'is_best': False,
                    'message': 'Coup illégal'
                }
        except:
            return {
                'evaluation': -999,
                'quality': 'invalid',
                'improvement_points': 0,
                'is_better': False,
                'is_best': False,
                'message': 'Coup invalide'
            }
        
        # Analyser avec Stockfish
        with chess.engine.SimpleEngine.popen_uci("/opt/homebrew/bin/stockfish") as engine:
            # Analyser la position initiale pour les 5 meilleurs coups
            initial_board = chess.Board(position.fen_position)
            multipv_info = engine.analyse(initial_board, chess.engine.Limit(depth=16), multipv=5)
            
            # Extraire les 5 meilleurs coups avec leurs évaluations
            top_moves = []
            player_move_evaluation = None
            original_move_evaluation = None
            
            for i, info in enumerate(multipv_info):
                if 'pv' in info and len(info['pv']) > 0:
                    move_uci = info['pv'][0]
                    move_san = initial_board.san(move_uci)
                    score = info['score'].white()  # Toujours du point de vue des blancs
                    
                    if score.is_mate():
                        eval_score = 999 if score.mate() > 0 else -999
                    else:
                        eval_score = score.score() / 100.0
                    
                    # Pas d'ajustement selon la couleur ici, on garde l'évaluation brute
                    top_moves.append({
                        'rank': i + 1,
                        'move_san': move_san,
                        'move_uci': move_uci.uci(),
                        'evaluation': eval_score
                    })
                    
                    # Vérifier si c'est le coup du joueur pour récupérer son évaluation
                    if move_uci.uci() == attempted_move:
                        player_move_evaluation = eval_score
                    
                    # Vérifier si c'est le coup original pour récupérer son évaluation
                    if move_san == position.original_move:
                        original_move_evaluation = eval_score
            
            # Si le coup du joueur n'est pas dans le top 5, l'évaluer séparément avec la même méthode
            if player_move_evaluation is None:
                # Utiliser la même méthode que pour le multipv : évaluer depuis la position initiale
                temp_board = chess.Board(position.fen_position)
                # Analyser le coup spécifique depuis la position initiale
                info = engine.analyse(temp_board, chess.engine.Limit(depth=16), root_moves=[move])
                score = info["score"].white()  # Toujours du point de vue des blancs
                
                if score.is_mate():
                    player_move_evaluation = 999 if score.mate() > 0 else -999
                else:
                    player_move_evaluation = score.score() / 100.0
            
            # L'évaluation finale est celle du coup du joueur (point de vue des blancs)
            evaluation = player_move_evaluation
        
        # Comparer avec le coup original et le meilleur coup
        # Utiliser l'évaluation Stockfish si disponible, sinon fallback sur la base de données
        if original_move_evaluation is not None:
            original_eval = original_move_evaluation
        else:
            original_eval = position.original_evaluation / 100.0 if abs(position.original_evaluation) > 50 else position.original_evaluation
        
        best_eval = position.best_evaluation / 100.0 if abs(position.best_evaluation) > 50 else position.best_evaluation
        
        # Calculer l'amélioration selon la perspective du joueur qui joue
        # Vérifier qui joue dans la position actuelle (depuis le FEN)
        board = chess.Board(position.fen_position)
        current_turn = 'white' if board.turn else 'black'
        
        if current_turn == 'black':
            # Pour les noirs, une augmentation de l'évaluation (plus favorable aux blancs) est une détérioration
            improvement_points = original_eval - evaluation
        else:
            # Pour les blancs, une augmentation de l'évaluation est une amélioration
            improvement_points = evaluation - original_eval
            
        is_better = improvement_points > 0.2  # Amélioration significative
        is_best = attempted_move == position.best_move
        
        # Déterminer la qualité basée sur le rang dans le top 5 et l'amélioration
        player_rank_in_top5 = None
        for i, move_data in enumerate(top_moves):
            if move_data['move_uci'] == attempted_move:
                player_rank_in_top5 = i + 1
                break
        
        if is_best:
            quality = 'perfect'
        elif improvement_points < -1.0:
            # Si le coup perd plus d'un pion, c'est une gaffe peu importe le rang
            quality = 'blunder'
        elif player_rank_in_top5 is not None and player_rank_in_top5 <= 3 and improvement_points > 0.0:
            # Si le coup est dans le top 3 ET améliore la position
            quality = 'good'
        elif player_rank_in_top5 is not None and player_rank_in_top5 <= 5:
            # Si le coup est dans le top 5 (mais peut perdre un peu)
            quality = 'suboptimal'
        elif improvement_points > 1.0:
            quality = 'good'
        elif improvement_points > 0.0:
            quality = 'suboptimal'
        else:
            quality = 'poor'
        
        return {
            'evaluation': evaluation,
            'original_evaluation': original_eval,
            'best_evaluation': best_eval,
            'quality': quality,
            'improvement_points': improvement_points,
            'is_better': is_better,
            'is_best': is_best,
            'top_moves': top_moves,
            'message': f'Évaluation: {evaluation:.2f}, Amélioration vs original: {improvement_points:+.2f}'
        }
        
    except Exception as e:
        return {
            'evaluation': 0,
            'quality': 'error',
            'improvement_points': 0,
            'is_better': False,
            'is_best': False,
            'message': f'Erreur d\'analyse: {str(e)}'
        }
