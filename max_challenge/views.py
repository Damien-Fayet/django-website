from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.contrib import messages
import json
from .models import Definition, GameSession, Photo
from .services import GameService, GameCreationService

def index(request):
    """Page d'accueil pour sélectionner ou créer une partie"""
    # Récupérer la fête unique (s'il y en a une)
    game = GameSession.objects.first()
    return render(request, 'max_challenge/index.html', {
        'game': game
    })

def game_view(request, game_id):
    """Vue principale du jeu"""
    service = GameService(game_id)
    game_data = service.get_game_data()
    
    return render(request, 'max_challenge/game.html', game_data)

def admin_view(request, game_id):
    """Interface d'administration pour l'animateur"""
    service = GameService(game_id)
    game_data = service.get_game_data()
    definitions = Definition.objects.all().order_by('?')
    photos = Photo.objects.all()  # Récupérer toutes les photos disponibles
    
    context = game_data.copy()
    context['definitions'] = definitions
    context['photos'] = photos  # Ajouter les photos au contexte
    
    return render(request, 'max_challenge/admin.html', context)

@csrf_exempt
@require_POST
def team_point(request, game_id):
    """Attribuer un point à une équipe"""
    service = GameService(game_id)
    data = json.loads(request.body)
    team = data.get('team')
    
    result = service.add_point_to_team(team)
    return JsonResponse(result)

@csrf_exempt
@require_POST
def set_definition(request, game_id):
    """Définir la définition actuelle"""
    service = GameService(game_id)
    data = json.loads(request.body)
    definition_id = data.get('definition_id')
    
    result = service.set_current_definition(definition_id)
    return JsonResponse(result)

@csrf_exempt
@require_POST
def reveal_word(request, game_id):
    """Révéler un mot de la définition"""
    service = GameService(game_id)
    result = service.reveal_definition_word()
    return JsonResponse(result)

@csrf_exempt
@require_POST
def next_definition(request, game_id):
    """Passer à la prochaine définition avec choix de difficulté"""
    service = GameService(game_id)
    data = json.loads(request.body) if request.body else {}
    difficulty = data.get('difficulty')
    result = service.set_next_definition(difficulty=difficulty)
    return JsonResponse(result)

@csrf_exempt
@require_POST
def reveal_photo(request, game_id):
    """Révéler la photo d'origine d'une équipe"""
    service = GameService(game_id)
    data = json.loads(request.body)
    team = data.get('team')
    
    result = service.reveal_team_photo(team)
    return JsonResponse(result)

@csrf_exempt
@require_POST
def hide_photo(request, game_id):
    """Masquer la photo d'une équipe pour permettre d'en changer"""
    service = GameService(game_id)
    data = json.loads(request.body)
    team = data.get('team')
    
    result = service.hide_team_photo(team)
    return JsonResponse(result)

@csrf_exempt
@require_POST
def change_photo(request, game_id):
    """Changer la photo d'une équipe"""
    game = GameSession.objects.get(pk=game_id)
    data = json.loads(request.body)
    team = data.get('team')
    photo_id = data.get('photo_id')
    
    try:
        photo = Photo.objects.get(pk=photo_id)
        if team == 'A':
            game.team_a_photo = photo
        elif team == 'B':
            game.team_b_photo = photo
        game.save()
        return JsonResponse({'success': True})
    except Photo.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Photo non trouvée'})

@csrf_exempt
@require_POST
def reset_scores(request, game_id):
    """Remet à zéro les scores"""
    service = GameService(game_id)
    result = service.reset_scores()
    return JsonResponse(result)

@csrf_exempt
@require_POST
def update_squares_per_reveal(request, game_id):
    """Met à jour le nombre de carrés révélés par bonne réponse"""
    try:
        import json
        data = json.loads(request.body)
        squares_per_reveal = data.get('squares_per_reveal', 6)
        
        game = GameSession.objects.get(pk=game_id)
        game.squares_per_reveal = squares_per_reveal
        game.save()
        
        return JsonResponse({
            'success': True,
            'squares_per_reveal': squares_per_reveal
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

def reset_game(request):
    """Supprime la fête existante pour pouvoir en créer une nouvelle"""
    if request.method == 'POST':
        GameSession.objects.all().delete()
        messages.success(request, 'La fête a été réinitialisée avec succès!')
        return redirect('max_challenge:index')
    return redirect('max_challenge:index')

def get_game_state(request, game_id):
    """Obtenir l'état actuel du jeu (pour les mises à jour en temps réel)"""
    service = GameService(game_id)
    return JsonResponse(service.get_game_state_json())

def create_game(request):
    """Créer une nouvelle partie"""
    if request.method == 'POST':
        game_data = {
            'name': request.POST.get('name'),
            'description': request.POST.get('description', ''),
            'team_a_name': request.POST.get('team_a_name', 'Équipe A'),
            'team_b_name': request.POST.get('team_b_name', 'Équipe B'),
            'max_teams': int(request.POST.get('max_teams', 4)),
            'points_per_correct': int(request.POST.get('points_per_correct', 10)),
            'ascii_reveal_speed': request.POST.get('ascii_reveal_speed', 'medium'),
            'definition_reveal_speed': request.POST.get('definition_reveal_speed', 'medium'),
        }
        
        if game_data['name']:
            result = GameCreationService.create_game(game_data)
            
            if result['success']:
                messages.success(request, f'Fête "{game_data["name"]}" créée avec succès!')
                return redirect('max_challenge:game', game_id=result['game'].pk)
            else:
                messages.error(request, result['error'])
        else:
            messages.error(request, 'Veuillez remplir le nom de la fête.')
    
    return render(request, 'max_challenge/create_game.html')