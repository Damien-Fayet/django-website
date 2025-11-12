from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.contrib import messages
import json
from .models import Definition, GameSession
from .services import GameService, GameCreationService

def index(request):
    """Page d'accueil pour sélectionner ou créer une partie"""
    active_games = GameSession.objects.filter(is_active=True).order_by('-created_at')
    return render(request, 'max_challenge/index.html', {
        'active_games': active_games
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
    definitions = Definition.objects.all().order_by('?')  # Ordre aléatoire
    
    context = game_data.copy()
    context['definitions'] = definitions
    
    return render(request, 'max_challenge/admin.html', context)

@csrf_exempt
@require_POST
def team_point(request, game_id):
    """Attribuer un point à une équipe"""
    game = get_object_or_404(GameSession, id=game_id, is_active=True)
    data = json.loads(request.body)
    team = data.get('team')  # 'A' ou 'B'
    
    if team == 'A':
        game.team_a_score += 1
        # Révéler un nouveau caractère ASCII pour l'équipe A
        reveal_next_ascii_char(game, 'A')
    elif team == 'B':
        game.team_b_score += 1
        # Révéler un nouveau caractère ASCII pour l'équipe B
        reveal_next_ascii_char(game, 'B')
    
    # Révéler une photo dans l'image globale
    reveal_global_photo(game)
    
    game.save()
    
    return JsonResponse({'success': True, 'team_a_score': game.team_a_score, 'team_b_score': game.team_b_score})

@csrf_exempt
@require_POST
def set_definition(request, game_id):
    """Définir la définition actuelle"""
    game = get_object_or_404(GameSession, id=game_id, is_active=True)
    data = json.loads(request.body)
    definition_id = data.get('definition_id')
    
    if definition_id:
        definition = get_object_or_404(Definition, id=definition_id)
        game.current_definition = definition
        game.revealed_words = []  # Reset des mots révélés
        game.save()
    
    return JsonResponse({'success': True})

@csrf_exempt
@require_POST
def reveal_word(request, game_id):
    """Révéler un mot de la définition"""
    game = get_object_or_404(GameSession, id=game_id, is_active=True)
    
    if game.current_definition:
        words = re.findall(r'\b\w+\b', game.current_definition.definition)
        unrevealed_words = [word for word in words if word.lower() not in [w.lower() for w in game.revealed_words]]
        
        if unrevealed_words:
            word_to_reveal = random.choice(unrevealed_words)
            game.revealed_words.append(word_to_reveal)
            game.save()
    
    return JsonResponse({'success': True})

@csrf_exempt
@require_POST
def reveal_photo(request, game_id):
    """Révéler la photo d'origine d'une équipe"""
    game = get_object_or_404(GameSession, id=game_id, is_active=True)
    data = json.loads(request.body)
    team = data.get('team')  # 'A' ou 'B'
    
    if team == 'A':
        game.team_a_photo_revealed = True
    elif team == 'B':
        game.team_b_photo_revealed = True
    
    game.save()
    
    return JsonResponse({'success': True})

def get_game_state(request, game_id):
    """Obtenir l'état actuel du jeu (pour les mises à jour en temps réel)"""
    game = get_object_or_404(GameSession, id=game_id, is_active=True)
    
    # Préparer les données ASCII avec caractères révélés ou photo révélée
    if game.team_a_photo_revealed:
        team_a_ascii = None
        team_a_photo_url = game.team_a_photo.image.url
    else:
        team_a_ascii = prepare_ascii_display(game.team_a_photo.ascii_art, game.team_a_revealed_chars)
        team_a_photo_url = None
    
    if game.team_b_photo_revealed:
        team_b_ascii = None
        team_b_photo_url = game.team_b_photo.image.url
    else:
        team_b_ascii = prepare_ascii_display(game.team_b_photo.ascii_art, game.team_b_revealed_chars)
        team_b_photo_url = None
    
    definition_display = prepare_definition_display(game.current_definition, game.revealed_words) if game.current_definition else None
    
    return JsonResponse({
        'team_a_score': game.team_a_score,
        'team_b_score': game.team_b_score,
        'team_a_ascii': team_a_ascii,
        'team_b_ascii': team_b_ascii,
        'team_a_photo_url': team_a_photo_url,
        'team_b_photo_url': team_b_photo_url,
        'team_a_photo_revealed': game.team_a_photo_revealed,
        'team_b_photo_revealed': game.team_b_photo_revealed,
        'definition_display': definition_display,
        'current_definition_word': game.current_definition.word if game.current_definition else None,
    })

def prepare_ascii_display(ascii_art, revealed_chars):
    """Prépare l'affichage ASCII avec les caractères révélés"""
    if not ascii_art or not revealed_chars:
        # Afficher tous les caractères masqués par défaut
        return re.sub(r'[^\s\n]', '█', ascii_art) if ascii_art else ''
    
    display = ascii_art
    for char in ascii_art:
        if char not in revealed_chars and char not in [' ', '\n']:
            display = display.replace(char, '█', 1)
    
    return display

def prepare_definition_display(definition, revealed_words):
    """Prépare l'affichage de la définition avec les mots révélés"""
    if not definition:
        return None
    
    definition_text = definition.definition
    words = re.findall(r'\b\w+\b', definition_text)
    
    for word in words:
        if word.lower() not in [w.lower() for w in revealed_words]:
            # Masquer le mot avec des caractères █
            masked_word = '█' * len(word)
            definition_text = re.sub(r'\b' + re.escape(word) + r'\b', masked_word, definition_text, flags=re.IGNORECASE)
    
    return definition_text

def reveal_next_ascii_char(game, team):
    """Révèle le prochain caractère ASCII pour une équipe"""
    if team == 'A':
        ascii_art = game.team_a_photo.ascii_art
        revealed_chars = game.team_a_revealed_chars
    else:
        ascii_art = game.team_b_photo.ascii_art
        revealed_chars = game.team_b_revealed_chars
    
    # Trouver tous les caractères uniques non encore révélés
    all_chars = set(ascii_art) - set([' ', '\n']) - set(revealed_chars)
    
    if all_chars:
        # Choisir un caractère au hasard
        new_char = random.choice(list(all_chars))
        revealed_chars.append(new_char)
        
        if team == 'A':
            game.team_a_revealed_chars = revealed_chars
        else:
            game.team_b_revealed_chars = revealed_chars

def reveal_global_photo(game):
    """Révèle une nouvelle photo dans l'image globale"""
    total_photos = game.global_photos.count()
    revealed_count = len(game.global_revealed_photos)
    
    if revealed_count < total_photos:
        # Révéler la prochaine photo
        game.global_revealed_photos.append(revealed_count)

def create_game(request):
    """Créer une nouvelle partie"""
    if request.method == 'POST':
        name = request.POST.get('name')
        description = request.POST.get('description', '')
        max_teams = int(request.POST.get('max_teams', 4))
        points_per_correct = int(request.POST.get('points_per_correct', 10))
        ascii_reveal_speed = request.POST.get('ascii_reveal_speed', 'medium')
        definition_reveal_speed = request.POST.get('definition_reveal_speed', 'medium')
        
        if name:
            # Sélectionner des photos aléatoires pour commencer
            photos = list(Photo.objects.all())
            if len(photos) >= 2:
                selected_photos = random.sample(photos, min(len(photos), 3))
                team_a_photo = selected_photos[0]
                team_b_photo = selected_photos[1] if len(selected_photos) > 1 else selected_photos[0]
                global_photos = selected_photos
            else:
                messages.error(request, 'Pas assez de photos disponibles. Veuillez en ajouter via l\'admin.')
                return render(request, 'max_challenge/create_game.html')
            
            game = GameSession.objects.create(
                name=name,
                description=description,
                team_a_name='Équipe A',
                team_b_name='Équipe B',
                team_a_photo=team_a_photo,
                team_b_photo=team_b_photo,
                max_teams=max_teams,
                points_per_correct=points_per_correct,
                ascii_reveal_speed=ascii_reveal_speed,
                definition_reveal_speed=definition_reveal_speed,
            )
            
            # Ajouter les photos globales
            if len(global_photos) > 2:
                game.global_photos.set(global_photos[2:])
            
            messages.success(request, f'Fête "{name}" créée avec succès!')
            return redirect('max_challenge:game', game_id=game.pk)
        else:
            messages.error(request, 'Veuillez remplir le nom de la fête.')
    
    return render(request, 'max_challenge/create_game.html')
