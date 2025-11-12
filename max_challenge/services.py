"""
Services pour la logique métier du Max Challenge
"""
import random
import re
from django.shortcuts import get_object_or_404
from .models import GameSession, Photo, Definition


class GameService:
    """Service pour gérer toute la logique métier du jeu"""
    
    def __init__(self, game_id):
        self.game = get_object_or_404(GameSession, id=game_id, is_active=True)
    
    def get_game_data(self):
        """Retourne les données du jeu formatées pour l'affichage"""
        return {
            'game': self.game,
            'team_a_grid': self._get_team_grid_data('A'),
            'team_b_grid': self._get_team_grid_data('B'),
            'definition_display': self._get_definition_display(),
            'team_a_photo_url': self.game.team_a_photo.image_400x400.url if self.game.team_a_photo_revealed and self.game.team_a_photo.image_400x400 else None,
            'team_b_photo_url': self.game.team_b_photo.image_400x400.url if self.game.team_b_photo_revealed and self.game.team_b_photo.image_400x400 else None,
        }
    
    def add_point_to_team(self, team_name):
        """Ajoute un point à une équipe et révèle toute la définition"""
        if team_name == 'A':
            self.game.team_a_score += 1
        else:
            self.game.team_b_score += 1
        
        # Révéler tous les mots de la définition
        if self.game.current_definition:
            definition_text = self.game.current_definition.definition
            all_words = [w for w in re.findall(r'\b\w+\b', definition_text)]
            self.game.revealed_words = all_words
            self.game.last_revealed_word = ''  # Plus de mot en surbrillance quand tout est révélé
        
        # Révéler des carrés selon la configuration de la partie
        self._reveal_grid_squares(team_name, count=self.game.squares_per_reveal)
        
        self.game.save()
        
        return {
            'success': True,
            'scores': {
                'team_a': self.game.team_a_score,
                'team_b': self.game.team_b_score
            },
            'definition_display': self._get_definition_display()
        }
    
    def reveal_team_photo(self, team):
        """Révèle la photo d'origine d'une équipe"""
        if team == 'A':
            self.game.team_a_photo_revealed = True
        elif team == 'B':
            self.game.team_b_photo_revealed = True
        
        self.game.save()
        return {'success': True}
    
    def hide_team_photo(self, team):
        """Masque la photo d'une équipe et charge une nouvelle photo aléatoire non utilisée"""
        from .models import Photo
        import random
        
        # Récupérer les photos déjà utilisées
        used_photo_ids = self.game.used_photos or []
        
        # Récupérer les photos disponibles (non utilisées)
        available_photos = list(Photo.objects.exclude(pk__in=used_photo_ids))
        
        # Si toutes les photos ont été utilisées, message d'erreur
        if not available_photos:
            return {
                'success': False, 
                'error': 'Toutes les photos ont déjà été utilisées'
            }
        
        new_photo = None
        
        # Sélectionner une nouvelle photo aléatoire différente des photos actuelles
        if team == 'A':
            current_photo_a = self.game.team_a_photo
            current_photo_b = self.game.team_b_photo
            # Exclure les deux photos actuelles
            candidate_photos = [p for p in available_photos if p != current_photo_a and p != current_photo_b]
            if not candidate_photos:
                # Si pas de candidat, au moins exclure la photo de cette équipe
                candidate_photos = [p for p in available_photos if p != current_photo_a]
            if not candidate_photos:
                candidate_photos = available_photos
            
            new_photo = random.choice(candidate_photos)
            self.game.team_a_photo = new_photo
            self.game.team_a_photo_revealed = False
            self.game.team_a_revealed_squares = []  # Réinitialiser les carrés révélés
        elif team == 'B':
            current_photo_a = self.game.team_a_photo
            current_photo_b = self.game.team_b_photo
            # Exclure les deux photos actuelles
            candidate_photos = [p for p in available_photos if p != current_photo_a and p != current_photo_b]
            if not candidate_photos:
                # Si pas de candidat, au moins exclure la photo de cette équipe
                candidate_photos = [p for p in available_photos if p != current_photo_b]
            if not candidate_photos:
                candidate_photos = available_photos
            
            new_photo = random.choice(candidate_photos)
            self.game.team_b_photo = new_photo
            self.game.team_b_photo_revealed = False
            self.game.team_b_revealed_squares = []  # Réinitialiser les carrés révélés
        
        # Ajouter la nouvelle photo à la liste des photos utilisées
        if new_photo and new_photo.pk not in used_photo_ids:
            used_photo_ids.append(new_photo.pk)
            self.game.used_photos = used_photo_ids
        
        self.game.save()
        return {'success': True, 'new_photo_name': new_photo.name if new_photo else ''}
    
    def set_current_definition(self, definition_id):
        """Définit la définition actuelle et révèle 4 mots aléatoires"""
        if definition_id:
            definition = get_object_or_404(Definition, id=definition_id)
            self.game.current_definition = definition

            # Révéler 4 mots aléatoires
            words = re.findall(r'\b\w+\b', definition.definition)
            self.game.revealed_words = random.sample(words, min(4, len(words)))

            self.game.save()
        
        return {'success': True}
    
    def set_next_definition(self, difficulty=None):
        """Définit la prochaine définition selon la difficulté choisie ou aléatoirement"""
        # Exclure les définitions déjà utilisées
        used_definition_ids = self.game.used_definitions or []
        
        if difficulty:
            # Filtrer par difficulté choisie ET exclure celles déjà utilisées
            available_definitions = list(
                Definition.objects
                .filter(difficulty=difficulty)
                .exclude(id__in=used_definition_ids)
                .order_by('?')
            )
            
            if not available_definitions:
                return {
                    'success': False, 
                    'message': f'Aucune définition de niveau {difficulty} disponible (toutes ont été utilisées)'
                }
            
            # Prendre une définition aléatoire du niveau choisi
            next_definition = available_definitions[0]
        else:
            # Mode automatique : ordre de difficulté (ancien comportement) excluant celles déjà utilisées
            all_definitions = list(
                Definition.objects
                .exclude(id__in=used_definition_ids)
                .order_by('difficulty', 'pk')
            )
            
            if not all_definitions:
                return {
                    'success': False,
                    'message': 'Toutes les définitions ont été utilisées'
                }
            
            if not all_definitions:
                return {'success': False, 'message': 'Aucune définition disponible'}
            
            # Si aucune définition n'est active, prendre la première
            if not self.game.current_definition:
                next_definition = all_definitions[0]
            else:
                # Trouver la définition suivante après la définition actuelle
                current_index = None
                for idx, definition in enumerate(all_definitions):
                    if definition.pk == self.game.current_definition.pk:
                        current_index = idx
                        break
                
                # Passer à la suivante, ou revenir à la première si on est à la fin
                if current_index is not None and current_index < len(all_definitions) - 1:
                    next_definition = all_definitions[current_index + 1]
                else:
                    next_definition = all_definitions[0]
        
        # Définir la nouvelle définition
        self.game.current_definition = next_definition
        
        # Ajouter la définition à la liste des définitions utilisées
        if next_definition.pk not in used_definition_ids:
            used_definition_ids.append(next_definition.pk)
            self.game.used_definitions = used_definition_ids
        
        # Révéler 4 mots aléatoires
        words = re.findall(r'\b\w+\b', next_definition.definition)
        self.game.revealed_words = random.sample(words, min(4, len(words)))
        
        # Le dernier mot révélé est le dernier de la liste initiale
        if self.game.revealed_words:
            self.game.last_revealed_word = self.game.revealed_words[-1]
        else:
            self.game.last_revealed_word = ''
        
        self.game.save()
        
        # Obtenir le label de difficulté
        difficulty_labels = {1: 'Facile', 2: 'Moyen', 3: 'Difficile'}
        difficulty_label = difficulty_labels.get(next_definition.difficulty, 'Moyen')
        
        return {
            'success': True,
            'definition': {
                'word': next_definition.word,
                'definition': next_definition.definition,
                'difficulty': next_definition.difficulty,
                'difficulty_display': difficulty_label,
                'definition_display': self._get_definition_display()
            }
        }
    
    def reveal_definition_word(self):
        """Révèle un mot aléatoire de la définition"""
        if not self.game.current_definition:
            return {
                'success': False,
                'message': 'Aucune définition en cours'
            }
        
        definition_text = self.game.current_definition.definition
        all_words = [w for w in re.findall(r'\b\w+\b', definition_text)]
        
        # Mots déjà révélés
        revealed = set(w.lower() for w in self.game.revealed_words)
        
        # Trouver les mots non révélés
        unrevealed_words = [w for w in all_words if w.lower() not in revealed]
        
        if not unrevealed_words:
            return {
                'success': False,
                'message': 'Tous les mots sont déjà révélés',
                'definition_display': self._get_definition_display()
            }
        
        # Révéler un mot aléatoire
        word_to_reveal = random.choice(unrevealed_words)
        self.game.revealed_words.append(word_to_reveal)
        self.game.last_revealed_word = word_to_reveal  # Stocker le dernier mot révélé
        self.game.save()
        
        return {
            'success': True,
            'revealed_word': word_to_reveal,
            'definition_display': self._get_definition_display()
        }
    
    def reset_scores(self):
        """Remet à zéro toute la partie (scores, révélations, définition, etc.)"""
        self.game.team_a_score = 0
        self.game.team_b_score = 0
        self.game.team_a_revealed_squares = []
        self.game.team_b_revealed_squares = []
        self.game.team_a_photo_revealed = False
        self.game.team_b_photo_revealed = False
        self.game.current_definition = None
        self.game.revealed_words = []
        self.game.save()
        return {'success': True}
    
    def get_game_state_json(self):
        """Retourne l'état complet du jeu en JSON pour les APIs"""
        return {
            'team_a_score': self.game.team_a_score,
            'team_b_score': self.game.team_b_score,
            'team_a_grid': self._get_team_grid_data('A'),
            'team_b_grid': self._get_team_grid_data('B'),
            'team_a_photo_url': self.game.team_a_photo.image_400x400.url if self.game.team_a_photo_revealed and self.game.team_a_photo.image_400x400 else None,
            'team_b_photo_url': self.game.team_b_photo.image_400x400.url if self.game.team_b_photo_revealed and self.game.team_b_photo.image_400x400 else None,
            'team_a_photo_revealed': self.game.team_a_photo_revealed,
            'team_b_photo_revealed': self.game.team_b_photo_revealed,
            'definition_display': self._get_definition_display(),
            'current_definition_word': self.game.current_definition.word if self.game.current_definition else None,
        }
    
    def _get_team_grid_data(self, team):
        """Retourne les données de grille pour une équipe"""
        if team == 'A':
            if self.game.team_a_photo_revealed:
                return None  # Photo complète visible
            return {
                'image_url': self.game.team_a_photo.image_400x400.url if self.game.team_a_photo.image_400x400 else None,
                'revealed_squares': self.game.team_a_revealed_squares
            }
        elif team == 'B':
            if self.game.team_b_photo_revealed:
                return None
            return {
                'image_url': self.game.team_b_photo.image_400x400.url if self.game.team_b_photo.image_400x400 else None,
                'revealed_squares': self.game.team_b_revealed_squares
            }
    
    def _get_definition_display(self):
        """Retourne la définition avec le dernier mot révélé en vert et les autres normaux"""
        if not self.game.current_definition:
            return None
        
        definition_text = self.game.current_definition.definition
        words = re.findall(r'\b\w+\b', definition_text)
        
        # Créer une copie pour le traitement
        result = definition_text
        
        # Traiter chaque mot
        for word in words:
            if word.lower() in [w.lower() for w in self.game.revealed_words]:
                # Vérifier si c'est le dernier mot révélé
                if self.game.last_revealed_word and word.lower() == self.game.last_revealed_word.lower():
                    # Dernier mot révélé : fond vert
                    result = re.sub(
                        r'\b' + re.escape(word) + r'\b',
                        f'<span style="background-color: #d4edda; color: #155724; font-weight: bold; padding: 2px 6px; border-radius: 4px;">{word}</span>',
                        result,
                        flags=re.IGNORECASE,
                        count=1
                    )
                else:
                    # Mot révélé mais pas le dernier : style normal (juste pour éviter qu'il soit masqué)
                    pass
            else:
                # Mot masqué : le remplacer par des blocs
                masked_word = '█' * len(word)
                result = re.sub(
                    r'\b' + re.escape(word) + r'\b', 
                    masked_word, 
                    result, 
                    flags=re.IGNORECASE,
                    count=1
                )
        
        return result
    
    def _get_definition_display_with_highlight(self, last_revealed_word=None):
        """Retourne la définition complète avec le dernier mot révélé mis en évidence"""
        if not self.game.current_definition:
            return None
        
        definition_text = self.game.current_definition.definition
        
        # Si un mot vient d'être révélé, le mettre en évidence avec des balises HTML
        if last_revealed_word:
            definition_text = re.sub(
                r'\b' + re.escape(last_revealed_word) + r'\b',
                f'<span class="highlight">{last_revealed_word}</span>',
                definition_text,
                flags=re.IGNORECASE,
                count=1  # Ne remplacer que la première occurrence
            )
        
        return definition_text
    
    def _reveal_grid_squares(self, team, count=2):
        """Révèle un nombre de carrés aléatoires de la grille 10x10 (100 carrés : 0-99)"""
        if team == 'A':
            revealed_squares = self.game.team_a_revealed_squares
        else:
            revealed_squares = self.game.team_b_revealed_squares
        
        # Tous les carrés possibles (0-99 pour une grille 10x10)
        all_squares = set(range(100))
        unrevealed_squares = list(all_squares - set(revealed_squares))
        
        # Révéler jusqu'à 'count' carrés
        squares_to_reveal = min(count, len(unrevealed_squares))
        new_squares = random.sample(unrevealed_squares, squares_to_reveal)
        revealed_squares.extend(new_squares)
        
        # Sauvegarder dans le modèle
        if team == 'A':
            self.game.team_a_revealed_squares = revealed_squares
        else:
            self.game.team_b_revealed_squares = revealed_squares


class GameCreationService:
    """Service pour créer de nouvelles parties"""
    
    @staticmethod
    def create_game(game_data):
        """Crée une nouvelle partie avec les données fournies"""
        # Empêche la création d'une nouvelle fête si une existe déjà
        if GameSession.objects.exists():
            return {'success': False, 'error': 'Il existe déjà une fête. Impossible d\'en créer une nouvelle.'}

        photos = list(Photo.objects.all())
        if len(photos) < 2:
            return {'success': False, 'error': 'Il faut au moins 2 photos différentes pour créer une partie'}

        # Sélectionner des photos aléatoires (au moins 2 différentes)
        selected_photos = random.sample(photos, min(len(photos), 3))
        
        # S'assurer qu'on a au moins 2 photos différentes
        if len(selected_photos) < 2:
            return {'success': False, 'error': 'Il faut au moins 2 photos différentes pour créer une partie'}

        game = GameSession.objects.create(
            name=game_data.get('name'),
            description=game_data.get('description', ''),
            team_a_name=game_data.get('team_a_name', 'Équipe A'),
            team_b_name=game_data.get('team_b_name', 'Équipe B'),
            team_a_photo=selected_photos[0],
            team_b_photo=selected_photos[1],
            max_teams=game_data.get('max_teams', 4),
            points_per_correct=game_data.get('points_per_correct', 10),
            ascii_reveal_speed=game_data.get('ascii_reveal_speed', 'medium'),
            definition_reveal_speed=game_data.get('definition_reveal_speed', 'medium'),
            # Marquer les 2 photos initiales comme utilisées (on a vérifié qu'il y en a 2)
            used_photos=[selected_photos[0].pk, selected_photos[1].pk],
            used_definitions=[],
        )

        # Ajouter les photos globales
        if len(selected_photos) > 2:
            game.global_photos.set(selected_photos[2:])

        return {'success': True, 'game': game}