import random
from django.shortcuts import render, redirect
from django.core.files.storage import FileSystemStorage
from django.conf import settings
from django import forms
from django.contrib import messages
from django.contrib.auth.models import User
from django.urls import reverse
from .models import Enigme, Indice, UserProfile, Devinette, IndiceDevinette, get_or_create_profile, ScoreConfig, AuditLog
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404
from django.contrib.auth import get_user_model
from django.core.mail import send_mail, BadHeaderError, EmailMessage
from django.db import models
import unidecode
import re
import socket
from datetime import datetime, timezone
from .forms import ContactForm
from .audit import log_action


def is_access_allowed(user):
    """
    Vérifie si l'utilisateur peut accéder aux énigmes/devinettes.
    Accès autorisé si:
    - L'utilisateur est super admin (superuser)
    - OU la date est >= 01/12/2025
    """
    # Super admin a toujours accès
    if user.is_superuser:
        return True
    
    # Vérifier la date (01 décembre 2025 à 00:00:00)
    release_date = datetime(2025, 12, 1, 0, 0, 0, tzinfo=timezone.utc)
    current_date = datetime.now(timezone.utc)
    
    return current_date >= release_date


def normalize_answer(answer):
    """
    Normalise une réponse en supprimant les variations courantes:
    - Articles définis/indéfinis (le, la, les, l', un, une, des)
    - Espaces multiples
    - Accents (via unidecode)
    - Pluriels (s, x à la fin)
    - Casse
    """
    if not answer:
        return ""
    
    # Convertir en minuscules et supprimer les accents
    normalized = answer.lower()
    normalized = unidecode.unidecode(normalized)
    
    # Supprimer les articles en début de chaîne (avec ou sans apostrophe)
    articles = [r"^les\s+", r"^le\s+", r"^la\s+", r"^l'", r"^un\s+", r"^une\s+", r"^des\s+"]
    for article in articles:
        normalized = re.sub(article, "", normalized)
    
    # Supprimer tous les espaces et caractères non-alphanumériques
    normalized = re.sub(r'[^a-z0-9]', '', normalized)
    
    # Supprimer le 's' ou 'x' final pour gérer les pluriels
    normalized = re.sub(r'[sx]$', '', normalized)
    
    return normalized


def check_answer(user_answer, expected_answers):
    """
    Vérifie si la réponse utilisateur correspond à l'une des réponses attendues.
    Compare les versions normalisées ET les versions originales nettoyées.
    """
    # Normalisation complète (articles, pluriels, etc.)
    normalized_user = normalize_answer(user_answer)
    
    for expected in expected_answers:
        # Normalisation complète
        normalized_expected = normalize_answer(expected)
        if normalized_user == normalized_expected:
            return True
        
        # Aussi vérifier la correspondance exacte sans articles mais avec pluriels
        simple_user = unidecode.unidecode(''.join(user_answer.split()).lower())
        simple_expected = unidecode.unidecode(''.join(expected.split()).lower())
        if simple_user == simple_expected:
            return True
    
    return False


def update_user_score(user_profile):
    """
    Calcule et met à jour le score total de l'utilisateur en fonction de sa progression.
    Utilise ScoreConfig pour les points.
    """
    score_config = ScoreConfig.get_config()
    
    # Calculer le score des énigmes (compter les énigmes réellement résolues)
    enigmes_resolues = 0
    if user_profile.reponses_enigmes:
        enigmes_resolues = len(user_profile.reponses_enigmes)
    
    score_enigmes = enigmes_resolues * score_config.points_enigme_resolue
    malus_erreurs_enigmes = user_profile.erreurEnigma * score_config.malus_erreur_enigme
    
    # Calculer le coût des indices d'énigmes
    cout_indices_enigmes = 0
    if user_profile.indices_enigme_reveles:
        indices_ids = [int(x) for x in user_profile.indices_enigme_reveles.split(",") if x]
        for indice_id in indices_ids:
            try:
                indice = Indice.objects.get(id=indice_id)
                cout_indices_enigmes += indice.cout
            except Indice.DoesNotExist:
                pass
    
    # Calculer le score des devinettes (compter les devinettes réellement résolues)
    devinettes_resolues = 0
    if user_profile.reponses_devinettes:
        devinettes_resolues = len(user_profile.reponses_devinettes)
    
    score_devinettes = devinettes_resolues * score_config.points_devinette_resolue
    malus_erreurs_devinettes = user_profile.erreurDevinette * score_config.malus_erreur_devinette
    
    # Calculer le coût des indices de devinettes
    cout_indices_devinettes = 0
    if user_profile.indices_devinette_reveles:
        indices_ids = [int(x) for x in user_profile.indices_devinette_reveles.split(",") if x]
        for indice_id in indices_ids:
            try:
                indice = IndiceDevinette.objects.get(id=indice_id)
                cout_indices_devinettes += indice.cout
            except IndiceDevinette.DoesNotExist:
                pass
    
    # Score total
    total_score = (
        score_enigmes +
        score_devinettes -
        malus_erreurs_enigmes -
        malus_erreurs_devinettes -
        cout_indices_enigmes -
        cout_indices_devinettes
    )
    
    user_profile.score = max(0, total_score)  # Ne jamais avoir un score négatif
    user_profile.save()

        
@login_required
def home(request):
    # Récupérer la configuration des scores (pour tous les utilisateurs)
    score_config = ScoreConfig.get_config()
    # Calcul du score maximum possible
    max_score = 8 * score_config.points_enigme_resolue + 24 * score_config.points_devinette_resolue
    
    # Contexte de base (disponible pour tous)
    context = {
        "score_config": score_config,
        "max_score": max_score,
        "is_before_release": not is_access_allowed(request.user),  # Indicateur pour afficher le countdown
    }
    
    # Ajouter les données utilisateur si connecté
    if request.user.is_authenticated:
        # Garantir que l'utilisateur a un profil
        profile = get_or_create_profile(request.user)
        
        current_enigma = profile.currentEnigma
        
        # Calculer le nombre d'énigmes résolues et le pourcentage
        enigmes_resolues = max(0, current_enigma - 1) if current_enigma > 0 else 0
        total_enigmes = 8
        pourcentage = int((enigmes_resolues / total_enigmes) * 100) if enigmes_resolues > 0 else 0
        
        # Récupérer les énigmes et devinettes pour vérifier leur disponibilité
        enigmes_disponibles = {}
        enigmes_existent = {}
        for i in range(1, 9):
            try:
                enigme = Enigme.objects.get(id=i)
                enigmes_existent[i] = True
                enigmes_disponibles[i] = enigme.is_dispo
            except Enigme.DoesNotExist:
                enigmes_existent[i] = False
                enigmes_disponibles[i] = False
        
        devinettes_disponibles = {}
        devinettes_existent = {}
        for i in range(1, 25):
            try:
                devinette = Devinette.objects.get(id=i)
                devinettes_existent[i] = True
                devinettes_disponibles[i] = devinette.is_dispo
            except Devinette.DoesNotExist:
                devinettes_existent[i] = False
                devinettes_disponibles[i] = False
        
        # Récupérer les énigmes et devinettes résolues (depuis les réponses enregistrées)
        enigmes_resolues_ids = set()
        if profile.reponses_enigmes:
            enigmes_resolues_ids = {int(k) for k in profile.reponses_enigmes.keys()}
        
        devinettes_resolues_ids = set()
        if profile.reponses_devinettes:
            devinettes_resolues_ids = {int(k) for k in profile.reponses_devinettes.keys()}
        
        context.update({
            "current_enigma": current_enigma,
            "enigmes_resolues": enigmes_resolues,
            "total_enigmes": total_enigmes,
            "pourcentage": pourcentage,
            "enigmes_disponibles": enigmes_disponibles,
            "enigmes_existent": enigmes_existent,
            "devinettes_disponibles": devinettes_disponibles,
            "devinettes_existent": devinettes_existent,
            "enigmes_resolues_ids": enigmes_resolues_ids,
            "devinettes_resolues_ids": devinettes_resolues_ids,
        })
        
        # Log de la visite de la page d'accueil
        log_action(request.user, AuditLog.HOME_VIEW, request)
    
    return render(request, 'avent2025/modern_home.html', context)

def public_home(request):
    """Page d'accueil pour les utilisateurs non connectés"""
    if request.user.is_authenticated:
        return redirect('avent2025:home')
    
    # Récupérer la configuration des scores pour affichage
    score_config = ScoreConfig.get_config()
    
    return render(request, 'modern_welcome.html', {
        'score_config': score_config,
    })

@login_required
def home_devinette(request):
    # Vérifier l'accès avant le 01/12/2025
    if not is_access_allowed(request.user):
        return render(request, 'avent2025/waiting.html', {
            'content_type': 'devinettes',
            'message': '🎄 Le Calendrier de l\'Avent 2025 ouvre le 1er décembre !',
            'description': 'Les devinettes seront disponibles à partir du 1er décembre 2025. Revenez à cette date pour commencer l\'aventure !'
        })
    
    # Garantir que l'utilisateur a un profil
    profile = get_or_create_profile(request.user)
    
    current_devinette_id = profile.currentDevinette
    
    # Vérifier si toutes les devinettes sont terminées
    if current_devinette_id > 0:
        try:
            current_devinette = Devinette.objects.get(id=current_devinette_id)
        except Devinette.DoesNotExist:
            # Toutes les devinettes sont terminées
            return redirect('avent2025:devinettes_completees')
    
    return render(request, 'avent2025/home_devinette.html', {"current_devinette": current_devinette_id})

@login_required
def devinettes_completees(request):
    """Page affichée quand l'utilisateur a terminé toutes les devinettes disponibles"""
    from datetime import datetime
    return render(request, 'avent2025/devinettes_completees.html', {
        'current_date': datetime.now()
    })

@login_required
def start_adventure(request):
    # Vérifier l'accès avant le 01/12/2025
    if not is_access_allowed(request.user):
        return render(request, 'avent2025/waiting.html', {
            'content_type': 'énigmes',
            'message': '🎄 Le Calendrier de l\'Avent 2025 ouvre le 1er décembre !',
            'description': 'Les énigmes seront disponibles à partir du 1er décembre 2025. Revenez à cette date pour commencer l\'aventure !'
        })
    
    # Vérifier qu'il existe au moins une énigme
    if not Enigme.objects.exists():
        return render(request, 'avent2025/waiting.html', {
            'content_type': 'énigmes',
            'message': 'Les énigmes arrivent bientôt !',
            'description': 'Le calendrier de l\'Avent 2025 débutera prochainement. Restez connecté pour découvrir les énigmes passionnantes qui vous attendent.'
        })
    
    # Garantir que l'utilisateur a un profil et mettre à jour la valeur de currentEnigma à 1
    user_profile = get_or_create_profile(request.user)
    user_profile.currentEnigma = 1
    user_profile.save()
    
    # Vérifier que l'énigme 1 existe
    try:
        current_enigma = Enigme.objects.get(id=1)
    except Enigme.DoesNotExist:
        return render(request, 'avent2025/waiting.html', {
            'content_type': 'énigme',
            'message': 'La première énigme arrive bientôt !',
            'description': 'Nous préparons avec soin la première énigme du calendrier de l\'Avent 2025. Elle sera disponible très prochainement.'
        })
    
    return redirect('avent2025:display_enigme')

@login_required
def start_devinette(request):
    # Vérifier l'accès avant le 01/12/2025
    if not is_access_allowed(request.user):
        return render(request, 'avent2025/waiting.html', {
            'content_type': 'devinettes',
            'message': '🎄 Le Calendrier de l\'Avent 2025 ouvre le 1er décembre !',
            'description': 'Les devinettes seront disponibles à partir du 1er décembre 2025. Revenez à cette date pour commencer l\'aventure !'
        })
    
    # Vérifier qu'il existe au moins une devinette
    if not Devinette.objects.exists():
        return render(request, 'avent2025/waiting.html', {
            'content_type': 'devinettes',
            'message': 'Les devinettes arrivent bientôt !',
            'description': 'Les devinettes du calendrier de l\'Avent 2025 seront disponibles prochainement. Revenez bientôt pour tester vos connaissances.'
        })
    
    # Garantir que l'utilisateur a un profil et mettre à jour la valeur de currentDevinette à 1
    user_profile = get_or_create_profile(request.user)
    user_profile.currentDevinette = 1
    user_profile.save()
    
    # Vérifier que la devinette 1 existe
    try:
        current_devinette = Devinette.objects.get(id=1)
    except Devinette.DoesNotExist:
        return render(request, 'avent2025/waiting.html', {
            'content_type': 'devinette',
            'message': 'La première devinette arrive bientôt !',
            'description': 'Nous préparons avec soin la première devinette du calendrier de l\'Avent 2025. Elle sera disponible très prochainement.'
        })
    
    return redirect('avent2025:display_devinette')

@login_required
def display_enigme(request, enigme_id=None, reponse=None):
    # Garantir que l'utilisateur a un profil
    profile = get_or_create_profile(request.user)
    
    # Vérifier que l'utilisateur a commencé l'aventure
    if profile.currentEnigma == 0:
        return render(request, 'avent2025/waiting.html', {
            'content_type': 'énigme',
            'message': 'Commencez votre aventure !',
            'description': 'Cliquez sur "Démarrer l\'aventure" depuis la page d\'accueil pour commencer à résoudre les énigmes du calendrier de l\'Avent 2025.',
            'show_start_button': True
        })
    
    # Si aucun ID spécifié, utiliser l'énigme actuelle
    if enigme_id is None:
        enigme_id = profile.currentEnigma
    
    # Récupérer l'énigme
    try:
        current_enigma = Enigme.objects.get(id=enigme_id)
    except Enigme.DoesNotExist:
        return render(request, 'avent2025/waiting.html', {
            'content_type': 'énigme',
            'message': 'Félicitations ! Vous avez terminé toutes les énigmes disponibles !',
            'description': 'Vous avez résolu toutes les énigmes actuellement disponibles. De nouvelles énigmes seront ajoutées prochainement. Revenez bientôt pour continuer votre aventure !',
            'is_complete': True
        })
    
    # Vérifier la date de disponibilité (sauf pour super utilisateurs)
    is_superuser = request.user.is_superuser
    date_warning = None
    if not current_enigma.is_dispo:
        if is_superuser:
            # Super utilisateur : accès autorisé avec message d'avertissement
            date_warning = f"⚠️ MODE ADMIN : Cette énigme sera disponible le {current_enigma.date_dispo.strftime('%d/%m/%Y')}"
        else:
            # Utilisateur normal : accès bloqué
            return render(request, 'avent2025/waiting.html', {
                'content_type': 'énigme',
                'message': 'Énigme pas encore disponible',
                'description': f'Cette énigme sera disponible le {current_enigma.date_dispo.strftime("%d/%m/%Y")}. Revenez à cette date pour la découvrir !',
                'show_start_button': False
            })
    
    # Récupérer tous les indices de cette énigme
    all_indices = Indice.objects.filter(enigme=current_enigma)
    
    # Vérifier si l'énigme suivante est disponible (pour les indices "last chance")
    try:
        next_enigma = Enigme.objects.get(id=enigme_id + 1)
        next_enigma_available = next_enigma.is_dispo
    except Enigme.DoesNotExist:
        # Pas d'énigme suivante, les indices last chance sont disponibles
        next_enigma_available = True
    
    # Filtrer les indices selon leur type
    if next_enigma_available:
        # L'énigme suivante est dispo : tous les indices sont accessibles
        indices = all_indices
    else:
        # L'énigme suivante n'est pas encore dispo : exclure les indices "last chance"
        indices = all_indices.exclude(type_indice=Indice.LAST_CHANCE)
    
    # Lister les indices révélés
    indice_reveles_list = []
    if profile.indices_enigme_reveles:
        indice_reveles_list = [int(x) for x in profile.indices_enigme_reveles.split(",")]
    
    indices_reveles = indices.filter(id__in=indice_reveles_list)
    indices_hidden = indices.exclude(id__in=indice_reveles_list)
    
    # Vérifier si l'énigme est déjà résolue (présente dans les réponses)
    is_resolved = False
    user_answer = None
    if profile.reponses_enigmes and str(enigme_id) in profile.reponses_enigmes:
        is_resolved = True
        user_answer = profile.reponses_enigmes.get(str(enigme_id))
    
    # Log de la consultation de l'énigme
    log_action(request.user, AuditLog.ENIGME_VIEW, request, enigme_id=enigme_id)
    
    return render(request, 'avent2025/modern_enigme.html', {
        'reponse_enigme': current_enigma.reponse,
        'enigme': current_enigma,
        'user_reponse': reponse,
        'indices': indices,
        'indices_reveles': indices_reveles,
        'indices_hidden': indices_hidden,
        'date_warning': date_warning,
        'is_resolved': is_resolved,
        'user_answer': user_answer,
    })
  
@login_required
def display_devinette(request, devinette_id=None, reponse=None):
    # Garantir que l'utilisateur a un profil
    profile = get_or_create_profile(request.user)
    
    # Vérifier que l'utilisateur a commencé les devinettes
    if profile.currentDevinette == 0:
        return render(request, 'avent2025/waiting.html', {
            'content_type': 'devinette',
            'message': 'Commencez les devinettes !',
            'description': 'Cliquez sur "Démarrer les devinettes" depuis la page d\'accueil pour commencer à résoudre les devinettes du calendrier de l\'Avent 2025.',
            'show_start_button': True
        })
    
    # Si aucun ID spécifié, utiliser la devinette actuelle
    if devinette_id is None:
        devinette_id = profile.currentDevinette
    
    # Vérifier si la devinette existe (cas où toutes les devinettes sont terminées)
    try:
        current_devinette = Devinette.objects.get(id=devinette_id)
    except Devinette.DoesNotExist:
        # Toutes les devinettes sont terminées
        return redirect('avent2025:devinettes_completees')
    
    # Vérifier la date de disponibilité (sauf pour super utilisateurs)
    is_superuser = request.user.is_superuser
    date_warning = None
    if not current_devinette.is_dispo:
        if is_superuser:
            # Super utilisateur : accès autorisé avec message d'avertissement
            date_warning = f"⚠️ MODE ADMIN : Cette devinette sera disponible le {current_devinette.date_dispo.strftime('%d/%m/%Y')}"
        else:
            # Utilisateur normal : accès bloqué
            return render(request, 'avent2025/waiting.html', {
                'content_type': 'devinette',
                'message': 'Devinette pas encore disponible',
                'description': f'Cette devinette sera disponible le {current_devinette.date_dispo.strftime("%d/%m/%Y")}. Revenez à cette date pour la découvrir !',
                'show_start_button': False
            })
    
    # Récupérer tous les indices de cette devinette
    all_indices = IndiceDevinette.objects.filter(enigme=current_devinette)
    
    # Filtrer les indices "last chance" si la devinette suivante n'est pas encore disponible
    try:
        next_devinette = Devinette.objects.get(id=devinette_id + 1)
        if not next_devinette.is_dispo:
            indices = all_indices.exclude(type_indice=IndiceDevinette.LAST_CHANCE)
        else:
            indices = all_indices
    except Devinette.DoesNotExist:
        # Pas de devinette suivante, on affiche tous les indices
        indices = all_indices
    
    # Lister les indice revelés
    indice_reveles_list = []
    if profile.indices_devinette_reveles:
        indice_reveles_list = [int(x) for x in profile.indices_devinette_reveles.split(",")]
    
    
    indices_reveles = indices.filter(id__in= indice_reveles_list)
    indices_hidden = indices.exclude(id__in=indice_reveles_list)
    
    # Vérifier si la devinette est déjà résolue (présente dans les réponses)
    is_resolved = False
    user_answer = None
    if profile.reponses_devinettes and str(devinette_id) in profile.reponses_devinettes:
        is_resolved = True
        user_answer = profile.reponses_devinettes.get(str(devinette_id))
    
    # Log de la consultation de la devinette
    log_action(request.user, AuditLog.DEVINETTE_VIEW, request, devinette_id=devinette_id)
    
    return render(request, 'avent2025/modern_devinette.html',  {
        'reponse_devinette' : current_devinette.reponse,
        'devinette' : current_devinette,
        'user_reponse' : reponse,
        'indices' : indices,
        'indices_reveles' : indices_reveles,
        'indices_hidden' : indices_hidden,
        'date_warning': date_warning,
        'is_resolved': is_resolved,
        'user_answer': user_answer,
    })
      
@login_required
def error_enigme(request):
    # Garantir que l'utilisateur a un profil
    profile = get_or_create_profile(request.user)
    current_enigma = get_object_or_404(Enigme, id=profile.currentEnigma)
    
    return render(request, 'avent2025/enigme.html',  {
        'reponse_enigme' : current_enigma.reponse,
        'enigme' : current_enigma,
        'user_reponse' : 'KO'
    })

@login_required
def validate_enigme(request):
    if request.method == "POST":
        # Garantir que l'utilisateur a un profil
        user_profile = get_or_create_profile(request.user)
        
        # Récupérer l'ID de l'énigme depuis le formulaire
        enigme_id = request.POST.get("enigme_id")
        if not enigme_id:
            messages.error(request, "Erreur : énigme non spécifiée")
            return redirect('avent2025:display_enigme')
        
        enigme_id = int(enigme_id)
        current_enigma = get_object_or_404(Enigme, id=enigme_id)
        reponse = request.POST.get("user_reponse")  # Correspond au nom du champ dans modern_enigme.html
        
        # Vérifier que la réponse n'est pas vide
        if not reponse:
            messages.error(request, "Veuillez entrer une réponse")
            return redirect('avent2025:display_enigme_id', enigme_id=enigme_id)
        
        # Utiliser la fonction de validation robuste
        reponses_possibles = [r.strip() for r in current_enigma.reponse.split(",")]
        
        if check_answer(reponse, reponses_possibles):
            # Enregistrer la réponse validée
            if not user_profile.reponses_enigmes:
                user_profile.reponses_enigmes = {}
            user_profile.reponses_enigmes[str(enigme_id)] = reponse
            
            # Si c'est l'énigme en cours, avancer la progression
            if enigme_id == user_profile.currentEnigma:
                user_profile.currentEnigma += 1
            
            update_user_score(user_profile)  # Mettre à jour le score
            user_profile.save()  # Sauvegarder les modifications
            
            # Log de succès
            log_action(request.user, AuditLog.ENIGME_SUBMIT_SUCCESS, request, 
                      enigme_id=enigme_id, reponse_donnee=reponse)
            
            # Afficher la page de succès avec image humoristique
            image_id = random.randint(1, 13)
            
            # Préparer le contexte pour l'énigme suivante ou actuelle
            try:
                next_enigma = Enigme.objects.get(id=user_profile.currentEnigma)
                context = {
                    'reponse_enigme': next_enigma.reponse,
                    'enigme': next_enigma,
                    'user_reponse': 'OK',
                    'old_enigme_id': enigme_id,
                    'image_reponse': f"gagne{image_id}.gif",
                    'indices': [],
                    'indices_reveles': [],
                    'indices_hidden': [],
                    'is_resolved': False,
                }
            except Enigme.DoesNotExist:
                # Toutes les énigmes terminées
                return redirect('avent2025:home')
            
            return render(request, 'avent2025/modern_enigme.html', context)
        else:
            user_profile.erreurEnigma += 1
            update_user_score(user_profile)  # Mettre à jour le score
            user_profile.save()  # Sauvegarder les modifications
            
            # Log d'échec
            log_action(request.user, AuditLog.ENIGME_SUBMIT_FAIL, request, 
                      enigme_id=enigme_id, reponse_donnee=reponse)
            
            # Afficher la page d'erreur avec image humoristique
            image_id = random.randint(1, 24)
            
            # Récupérer les indices pour l'énigme actuelle
            all_indices = Indice.objects.filter(enigme=current_enigma)
            try:
                next_enigma = Enigme.objects.get(id=enigme_id + 1)
                next_enigma_available = next_enigma.is_dispo
            except Enigme.DoesNotExist:
                next_enigma_available = True
            
            if next_enigma_available:
                indices = all_indices
            else:
                indices = all_indices.exclude(type_indice=Indice.LAST_CHANCE)
            
            indice_reveles_list = []
            if user_profile.indices_enigme_reveles:
                indice_reveles_list = [int(x) for x in user_profile.indices_enigme_reveles.split(",")]
            
            indices_reveles = indices.filter(id__in=indice_reveles_list)
            indices_hidden = indices.exclude(id__in=indice_reveles_list)
            
            # Vérifier si l'énigme est déjà résolue (présente dans les réponses)
            is_resolved = user_profile.reponses_enigmes and str(enigme_id) in user_profile.reponses_enigmes
            
            context = {
                'reponse_enigme': current_enigma.reponse,
                'enigme': current_enigma,
                'user_reponse': 'KO',
                'image_reponse': f"perdu{image_id}.gif",
                'indices': indices,
                'indices_reveles': indices_reveles,
                'indices_hidden': indices_hidden,
                'is_resolved': is_resolved,
            }
            
            return render(request, 'avent2025/modern_enigme.html', context)

    return redirect('avent2025:display_enigme')

@login_required
def validate_devinette(request):
    if request.method == "POST":
        # Garantir que l'utilisateur a un profil
        user_profile = get_or_create_profile(request.user)
        
        # Récupérer l'ID de la devinette depuis le formulaire
        devinette_id = request.POST.get("devinette_id")
        if not devinette_id:
            messages.error(request, "Erreur : devinette non spécifiée")
            return redirect('avent2025:display_devinette')
        
        devinette_id = int(devinette_id)
        current_devinette = get_object_or_404(Devinette, id=devinette_id)
        reponse = request.POST.get("reponse")
        
        # Vérifier que la réponse n'est pas vide
        if not reponse:
            messages.error(request, "Veuillez entrer une réponse")
            return redirect('avent2025:display_devinette_id', devinette_id=devinette_id)
        
        # Utiliser la fonction de validation robuste
        reponses_possibles = [r.strip() for r in current_devinette.reponse.split(",")]
        
        if check_answer(reponse, reponses_possibles):
            # Enregistrer la réponse validée
            if not user_profile.reponses_devinettes:
                user_profile.reponses_devinettes = {}
            user_profile.reponses_devinettes[str(devinette_id)] = reponse
            
            # Si c'est la devinette en cours, avancer la progression
            if devinette_id == user_profile.currentDevinette:
                user_profile.currentDevinette += 1
            
            update_user_score(user_profile)  # Mettre à jour le score
            user_profile.save()  # Sauvegarder les modifications
            
            # Log de succès
            log_action(request.user, AuditLog.DEVINETTE_SUBMIT_SUCCESS, request, 
                      devinette_id=devinette_id, reponse_donnee=reponse)
            
            # Afficher la page de succès avec image humoristique
            image_id = random.randint(1, 13)
            
            # Vérifier si une devinette suivante existe
            try:
                next_devinette = Devinette.objects.get(id=user_profile.currentDevinette)
                context = {
                    'reponse_devinette': next_devinette.reponse,
                    'devinette': next_devinette,
                    'user_reponse': 'OK',
                    'old_devinette_id': devinette_id,
                    'image_reponse': f"gagne{image_id}.gif",
                    'indices': [],
                    'indices_reveles': [],
                    'indices_hidden': [],
                    'is_resolved': False,
                }
                return render(request, 'avent2025/modern_devinette.html', context)
            except Devinette.DoesNotExist:
                # Toutes les devinettes sont terminées
                return redirect('avent2025:devinettes_completees')
        else:
            user_profile.erreurDevinette += 1
            update_user_score(user_profile)  # Mettre à jour le score
            user_profile.save()  # Sauvegarder les modifications
            
            # Log d'échec
            log_action(request.user, AuditLog.DEVINETTE_SUBMIT_FAIL, request, 
                      devinette_id=devinette_id, reponse_donnee=reponse)
            
            # Afficher la page d'erreur avec image humoristique
            image_id = random.randint(1, 24)
            
            # Récupérer les indices pour la devinette actuelle
            all_indices = IndiceDevinette.objects.filter(enigme=current_devinette)
            
            try:
                next_devinette = Devinette.objects.get(id=devinette_id + 1)
                if not next_devinette.is_dispo:
                    indices = all_indices.exclude(type_indice=IndiceDevinette.LAST_CHANCE)
                else:
                    indices = all_indices
            except Devinette.DoesNotExist:
                indices = all_indices
            
            indice_reveles_list = []
            if user_profile.indices_devinette_reveles:
                indice_reveles_list = [int(x) for x in user_profile.indices_devinette_reveles.split(",")]
            
            indices_reveles = indices.filter(id__in=indice_reveles_list)
            indices_hidden = indices.exclude(id__in=indice_reveles_list)
            
            # Vérifier si la devinette est déjà résolue (présente dans les réponses)
            is_resolved = user_profile.reponses_devinettes and str(devinette_id) in user_profile.reponses_devinettes
            
            context = {
                'reponse_devinette': current_devinette.reponse,
                'devinette': current_devinette,
                'user_reponse': 'KO',
                'image_reponse': f"perdu{image_id}.gif",
                'indices': indices,
                'indices_reveles': indices_reveles,
                'indices_hidden': indices_hidden,
                'is_resolved': is_resolved,
            }
            
            return render(request, 'avent2025/modern_devinette.html', context)

    return redirect('avent2025:display_devinette')

def register(request):
    if request.method == 'POST':
        username1 = request.POST['username']
        email1 = request.POST['email']
        password = request.POST['password']
        password1 = request.POST['password1']
        if password== password1:
            if User.objects.filter(email = email1).exists():
                messages.info(request,'Email already exists')
                return redirect('register')
            elif User.objects.filter(username = username1).exists():
                messages.info(request,'Username already exists')
                return redirect('register')
            else:
                user= User.objects.create_user(username=username1,email=email1,password=password)
                user.save()
            return redirect('login')
        else:
            messages.info(request,'Password not the same')
            return redirect('register')
    else:
        return render(request, 'avent2025/register.html')

@login_required
def reveler_indice(request):
    indice_id = int(request.POST.get("indice_id"))
    indice = get_object_or_404(Indice, id=indice_id)
    # Garantir que l'utilisateur a un profil
    user_profile = get_or_create_profile(request.user)
    if len(user_profile.indices_enigme_reveles)>0:
        tmp_list = user_profile.indices_enigme_reveles.split(",")
    else: 
        tmp_list=[]
    tmp_list.append(str(indice.id))
    user_profile.indices_enigme_reveles = ",".join(tmp_list)
    update_user_score(user_profile)  # Mettre à jour le score
    
    # Log de la révélation de l'indice
    log_action(request.user, AuditLog.INDICE_REVEAL, request, 
              enigme_id=indice.enigme.id, indice_id=indice.id, 
              details=f"Coût: {indice.cout} points")
    
    # Rediriger vers l'énigme de l'indice révélé
    return redirect(reverse('avent2025:display_enigme_id', kwargs={'enigme_id': indice.enigme.id}) + "#indices")


@login_required
def reveler_indice_devinette(request):
    indice_id = int(request.POST.get("indice_id"))
    indice = get_object_or_404(IndiceDevinette, id=indice_id)
    # Garantir que l'utilisateur a un profil
    user_profile = get_or_create_profile(request.user)
    if len(user_profile.indices_devinette_reveles)>0:
        tmp_list = user_profile.indices_devinette_reveles.split(",")
    else: 
        tmp_list=[]
    tmp_list.append(str(indice.id))
    user_profile.indices_devinette_reveles = ",".join(tmp_list)
    update_user_score(user_profile)  # Mettre à jour le score
    
    # Log de la révélation de l'indice (le champ s'appelle 'enigme' mais référence Devinette)
    log_action(request.user, AuditLog.INDICE_DEVINETTE_REVEAL, request, 
              devinette_id=indice.enigme.id, indice_id=indice.id, 
              details=f"Coût: {indice.cout} points")
    
    # Rediriger vers la devinette de l'indice révélé
    return redirect(reverse('avent2025:display_devinette_id', kwargs={'devinette_id': indice.enigme.id}) + "#indices")


def classement(request):
    
    User = get_user_model()
    
    # Récupérer les paramètres de filtrage
    filter_type = request.GET.get('filter', 'all')  # all, family, public
    score_type = request.GET.get('type', 'general')  # general, enigmes, devinettes
    
    users = User.objects.all().exclude(is_superuser=True)
    enigme_score = {}
    devinette_score = {}
    nb_indice_enigme = {}
    nb_indice_devinette = {}
    moy_indices_enigme ={}
    moy_indices_devinette = {}
    total = {}
    
    # Filtrer uniquement les utilisateurs qui ont un profil
    users_with_profile = []
    for u in users:
        if hasattr(u, 'userprofile_2025'):
            # Exclure les tricheurs du classement
            if u.userprofile_2025.is_cheater:
                continue
                
            # Appliquer le filtre famille/public
            if filter_type == 'family' and not u.userprofile_2025.is_family:
                continue
            if filter_type == 'public' and u.userprofile_2025.is_family:
                continue
                
            users_with_profile.append(u)
            
            # Calculer le nombre d'indices
            nb_indice_enigme[u.id] = 0 if u.userprofile_2025.indices_enigme_reveles=='' else len(u.userprofile_2025.indices_enigme_reveles.split(','))
            nb_indice_devinette[u.id] = 0 if u.userprofile_2025.indices_devinette_reveles=='' else len(u.userprofile_2025.indices_devinette_reveles.split(','))
            
            # Utiliser ScoreConfig pour calculer les scores partiels (pour affichage)
            score_config = ScoreConfig.get_config()
            
            # Compter les énigmes et devinettes réellement résolues
            enigmes_resolues = 0
            if u.userprofile_2025.reponses_enigmes:
                enigmes_resolues = len(u.userprofile_2025.reponses_enigmes)
            
            devinettes_resolues = 0
            if u.userprofile_2025.reponses_devinettes:
                devinettes_resolues = len(u.userprofile_2025.reponses_devinettes)
            
            # Calculer les coûts réels des indices
            cout_indices_enigmes = 0
            if u.userprofile_2025.indices_enigme_reveles:
                for indice_id in u.userprofile_2025.indices_enigme_reveles.split(','):
                    if indice_id:
                        try:
                            cout_indices_enigmes += Indice.objects.get(id=int(indice_id)).cout
                        except:
                            pass
            
            cout_indices_devinettes = 0
            if u.userprofile_2025.indices_devinette_reveles:
                for indice_id in u.userprofile_2025.indices_devinette_reveles.split(','):
                    if indice_id:
                        try:
                            cout_indices_devinettes += IndiceDevinette.objects.get(id=int(indice_id)).cout
                        except:
                            pass
            
            enigme_score[u.id] = max(0, 
                enigmes_resolues * score_config.points_enigme_resolue - 
                u.userprofile_2025.erreurEnigma * score_config.malus_erreur_enigme - 
                cout_indices_enigmes
            )
            devinette_score[u.id] = max(0,
                devinettes_resolues * score_config.points_devinette_resolue - 
                u.userprofile_2025.erreurDevinette * score_config.malus_erreur_devinette - 
                cout_indices_devinettes
            )
            
            moy_indices_enigme[u.id] = 0 if enigmes_resolues <= 0 else round(nb_indice_enigme[u.id] / enigmes_resolues, 1)
            moy_indices_devinette[u.id] = 0 if devinettes_resolues <= 0 else round(nb_indice_devinette[u.id] / devinettes_resolues, 1)
            
            # Utiliser le score stocké dans le profil
            total[u.id] = u.userprofile_2025.score
        
    users = users_with_profile
    
    # Trier selon le type de score demandé
    if score_type == 'enigmes':
        sorted_users = sorted(users, key=lambda item: enigme_score[item.id], reverse=True)
    elif score_type == 'devinettes':
        sorted_users = sorted(users, key=lambda item: devinette_score[item.id], reverse=True)
    else:  # general
        sorted_users = sorted(users, key=lambda item: total[item.id], reverse=True)
    
    sorted_users_enigme = sorted(users, key=lambda item: enigme_score[item.id],reverse=True)
    sorted_users_devinette = sorted(users, key=lambda item: devinette_score[item.id],reverse=True)
    
    # Calculer quelques stats supplémentaires
    nb_enigmes = {u.id: len(u.userprofile_2025.reponses_enigmes) if u.userprofile_2025.reponses_enigmes else 0 for u in users}
    nb_devinettes = {u.id: len(u.userprofile_2025.reponses_devinettes) if u.userprofile_2025.reponses_devinettes else 0 for u in users}
    nb_erreurs = {u.id: u.userprofile_2025.erreurEnigma for u in users}
    scores = {u.id: total[u.id] for u in users}
    total_enigmes = 8
    total_devinettes = 24
    avg_score = sum(scores.values()) / len(scores) if scores else 0
    
    # Compter les totaux pour les filtres
    all_users = User.objects.all().exclude(is_superuser=True)
    total_users = sum(1 for u in all_users if hasattr(u, 'userprofile_2025'))
    family_count = sum(1 for u in all_users if hasattr(u, 'userprofile_2025') and u.userprofile_2025.is_family)
    public_count = sum(1 for u in all_users if hasattr(u, 'userprofile_2025') and not u.userprofile_2025.is_family)
    
    # Log de la consultation du classement
    if request.user.is_authenticated:
        details = f"Type: {score_type}, Filtre: {filter_type}"
        log_action(request.user, AuditLog.CLASSEMENT_VIEW, request, details=details)
    
    return render(request, 'avent2025/modern_classement.html',  {
        'users' : sorted_users,
        'users_enigme' : sorted_users_enigme,
        'users_devinette' : sorted_users_devinette,
        'nb_indice_enigme' : nb_indice_enigme,
        'nb_indice_devinette': nb_indice_devinette,
        'moy_indices_enigme' : moy_indices_enigme,
        'moy_indices_devinette' : moy_indices_devinette,
        'enigme_score' : enigme_score,
        'devinette_score': devinette_score,
        'total': total,
        'nb_enigmes': nb_enigmes,
        'nb_devinettes': nb_devinettes,
        'nb_erreurs': nb_erreurs,
        'scores': scores,
        'total_enigmes': total_enigmes,
        'total_devinettes': total_devinettes,
        'avg_score': avg_score,
        'filter_type': filter_type,
        'score_type': score_type,
        'total_users': total_users,
        'family_count': family_count,
        'public_count': public_count,
    })
    
@login_required
def all_enigmes(request):
    current_enigma_id = request.user.userprofile_2025.currentEnigma if request.user.userprofile_2025.currentEnigma>0 else 1
    current_enigma = get_object_or_404(Enigme, id=current_enigma_id)
    current_devinette_id = request.user.userprofile_2025.currentDevinette if request.user.userprofile_2025.currentDevinette>0 else 1
    current_devinette = get_object_or_404(Devinette, id=current_devinette_id)
    
    print(f"enigme : {current_enigma.id} Devi : {current_devinette_id}")
    
    all_enigmes = Enigme.objects.filter(
        id__lte=current_enigma.id
    )
    all_devinettes = Devinette.objects.filter(
        id__lte=current_devinette.id
    )
    # Lister les indice revelés
    indices = Indice.objects.filter(
        enigme__lte=current_enigma
    )
    indice_reveles_list = []
    if request.user.userprofile_2025.indices_enigme_reveles:
        indice_reveles_list = [int(x) for x in request.user.userprofile_2025.indices_enigme_reveles.split(",")]
    
    indices_reveles = indices.filter(id__in= indice_reveles_list)
    indices_hidden = indices.exclude(id__in=indice_reveles_list)
    # Lister les indice revelés pour les devinettes
    indices = IndiceDevinette.objects.filter(
        enigme__lte=current_devinette
    )
    indice_reveles_list_devi = []
    if request.user.userprofile_2025.indices_devinette_reveles:
        indice_reveles_list_devi = [int(x) for x in request.user.userprofile_2025.indices_devinette_reveles.split(",")]
    
    indices_reveles_devi = indices.filter(id__in= indice_reveles_list_devi)
    indices_hidden_devi = indices.exclude(id__in=indice_reveles_list_devi)
    return render(request, 'avent2025/all_enigme.html',  {
        'enigmes' : all_enigmes,
        'devinettes' : all_devinettes,
        'indices' : indices,
        'indices_reveles': indices_reveles,
        'indices_hidden': indices_hidden,
        'indices_reveles_devi': indices_reveles_devi,
        'indices_hidden_devi': indices_hidden_devi,
    })


def contact(request):
    """Vue pour le formulaire de contact"""
    if request.method == 'POST':
        form = ContactForm(request.POST)
        if form.is_valid():
            name = form.cleaned_data['name']
            email = form.cleaned_data['email']
            subject = form.cleaned_data['subject']
            message = form.cleaned_data['message']
            
            # Construire le message email
            email_subject = f"[Calendrier Avent 2025] {subject}"
            email_body = f"""
                Nouveau message de contact depuis le Calendrier de l'Avent 2025

                Nom: {name}
                Email: {email}
                Sujet: {subject}

                Message:
                {message}

                ---
                Ce message a été envoyé depuis le formulaire de contact du site.
                Pour répondre, utilisez l'adresse: {email}
            """
            
            import logging
            import socket
            logger = logging.getLogger(__name__)
            
            try:
                logger.info(f"Tentative d'envoi d'email depuis {email}")
                
                # Envoyer l'email (utiliser EMAIL_HOST_USER comme expéditeur pour Gmail)
                email_message = EmailMessage(
                    subject=email_subject,
                    body=email_body,
                    from_email=settings.EMAIL_HOST_USER,
                    to=[email],
                    reply_to=[settings.DEFAULT_FROM_EMAIL]
                )
                
                # Définir un timeout pour éviter le blocage
                original_timeout = socket.getdefaulttimeout()
                socket.setdefaulttimeout(20)  # 10 secondes de timeout
                
                try:
                    email_message.send(fail_silently=False)
                    logger.info("Email envoyé avec succès")
                finally:
                    socket.setdefaulttimeout(original_timeout)
                
                # Afficher une page de confirmation avec redirection automatique
                return render(request, 'avent2025/contact_success.html', {
                    'name': name,
                    'redirect_delay': 3  # Redirection après 3 secondes
                })
            except socket.timeout:
                logger.error('Timeout lors de l\'envoi du mail de contact')
                messages.error(request, '❌ Le serveur mail ne répond pas. Veuillez réessayer plus tard.')
            except BadHeaderError as e:
                logger.error(f'BadHeaderError lors de l\'envoi du mail de contact: {str(e)}')
                messages.error(request, '❌ Erreur: en-tête email invalide.')
            except Exception as e:
                import traceback
                error_details = traceback.format_exc()
                logger.error(f'Erreur lors de l\'envoi du mail de contact: {str(e)}\n{error_details}')
                messages.error(request, f'❌ Une erreur est survenue lors de l\'envoi du message: {str(error_details)}')
    else:
        # Pré-remplir le formulaire avec les infos de l'utilisateur connecté
        initial_data = {}
        if request.user.is_authenticated:
            initial_data['name'] = request.user.get_full_name() or request.user.username
            if request.user.email:
                initial_data['email'] = request.user.email
        
        form = ContactForm(initial=initial_data)
    
    return render(request, 'avent2025/contact.html', {'form': form})


@login_required
def statistiques(request):
    """
    Affiche les statistiques globales du calendrier de l'avent.
    Exclut les admins (staff et superusers) de toutes les statistiques.
    """
    # Filtrer les utilisateurs non-admins et non-tricheurs
    users_non_admin = User.objects.filter(is_staff=False, is_superuser=False)
    profiles_non_admin = UserProfile.objects.filter(
        user__is_staff=False, 
        user__is_superuser=False,
        is_cheater=False  # Exclure les tricheurs
    )
    
    # Statistiques générales
    total_users = users_non_admin.count()
    
    # Joueurs actifs = ceux qui ont commencé au moins une énigme OU une devinette
    active_players = profiles_non_admin.filter(
        models.Q(currentEnigma__gt=1) | models.Q(currentDevinette__gt=1)
    ).count()
    
    total_enigmes = Enigme.objects.count()
    total_devinettes = Devinette.objects.count()
    
    # Statistiques sur les énigmes (parmi les joueurs actifs)
    users_started_enigmes = profiles_non_admin.filter(currentEnigma__gt=1).count()
    users_completed_all_enigmes = profiles_non_admin.filter(currentEnigma__gt=total_enigmes).count()
    
    # Statistiques sur les devinettes (parmi les joueurs actifs)
    users_started_devinettes = profiles_non_admin.filter(currentDevinette__gt=1).count()
    users_completed_all_devinettes = profiles_non_admin.filter(currentDevinette__gt=total_devinettes).count()
    
    # Nombre total d'erreurs
    total_erreurs_enigmes = profiles_non_admin.aggregate(total=models.Sum('erreurEnigma'))['total'] or 0
    total_erreurs_devinettes = profiles_non_admin.aggregate(total=models.Sum('erreurDevinette'))['total'] or 0
    
    # Awards rigolos
    # Le plus chanceux (meilleur ratio énigmes résolues / erreurs)
    lucky_player = None
    best_ratio = -1
    for profile in profiles_non_admin:
        enigmes_resolues = len(profile.reponses_enigmes) if profile.reponses_enigmes else 0
        if enigmes_resolues > 0:
            ratio = enigmes_resolues / max(1, profile.erreurEnigma)
            if ratio > best_ratio:
                best_ratio = ratio
                lucky_player = profile
    # Si aucun joueur chanceux, prendre celui avec le moins d'erreurs et au moins 1 énigme
    if not lucky_player and profiles_non_admin.exists():
        lucky_player = profiles_non_admin.filter(currentEnigma__gt=1).order_by('erreurEnigma').first()
    
    # Le plus persévérant (le plus d'erreurs mais continue quand même)
    persistent_player = None
    if profiles_non_admin.exists():
        candidate = profiles_non_admin.order_by('-erreurEnigma', '-erreurDevinette').first()
        # Afficher seulement si le joueur a au moins 1 erreur
        if candidate and (candidate.erreurEnigma > 0 or candidate.erreurDevinette > 0):
            persistent_player = candidate
    
    # Le collectionneur d'indices (le plus d'indices révélés)
    collector_player = None
    max_indices = 0
    for profile in profiles_non_admin:
        total_indices = 0
        if profile.indices_enigme_reveles:
            total_indices += len(profile.indices_enigme_reveles.split(','))
        if profile.indices_devinette_reveles:
            total_indices += len(profile.indices_devinette_reveles.split(','))
        if total_indices > max_indices:
            max_indices = total_indices
            collector_player = profile
    # Si aucun collectionneur, prendre n'importe quel joueur
    if not collector_player and profiles_non_admin.exists():
        collector_player = profiles_non_admin.first()
    
    # Le perfectionniste (meilleur score sans erreurs ou avec le moins d'erreurs)
    perfectionist_player = None
    if profiles_non_admin.exists():
        candidate = profiles_non_admin.order_by('erreurEnigma', 'erreurDevinette', '-score').first()
        # Toujours afficher un perfectionniste s'il y a des joueurs
        perfectionist_player = candidate
    
    # L'acharné du classement (celui qui consulte le plus le classement)
    classement_addict = None
    max_views = 0
    classement_logs = AuditLog.objects.filter(
        user__is_staff=False,
        user__is_superuser=False,
        action=AuditLog.CLASSEMENT_VIEW
    )
    # Compter par utilisateur
    from django.db.models import Count
    user_views = classement_logs.values('user').annotate(view_count=Count('id')).order_by('-view_count').first()
    if user_views:
        classement_addict_user = User.objects.get(id=user_views['user'])
        if hasattr(classement_addict_user, 'userprofile_2025'):
            classement_addict = classement_addict_user.userprofile_2025
            max_views = user_views['view_count']
    
    # Lucky Luke (celui qui a résolu le plus de devinettes en moins de 2 minutes)
    lucky_luke = None
    max_fast_devinettes = 0
    
    for profile in profiles_non_admin:
        fast_count = 0
        # Récupérer toutes les vues et succès de devinettes pour cet utilisateur
        devinette_views = AuditLog.objects.filter(
            user=profile.user,
            action=AuditLog.DEVINETTE_VIEW
        ).order_by('devinette_id', 'timestamp')
        
        devinette_success = AuditLog.objects.filter(
            user=profile.user,
            action=AuditLog.DEVINETTE_SUBMIT_SUCCESS
        ).order_by('devinette_id', 'timestamp')
        
        # Pour chaque devinette réussie, vérifier si elle a été résolue en moins de 2 minutes
        for success in devinette_success:
            # Trouver la première consultation de cette devinette
            first_view = devinette_views.filter(devinette_id=success.devinette_id).first()
            if first_view and success.devinette_id:
                time_diff = (success.timestamp - first_view.timestamp).total_seconds()
                if time_diff <= 120:  # 2 minutes = 120 secondes
                    fast_count += 1
        
        if fast_count > max_fast_devinettes:
            max_fast_devinettes = fast_count
            lucky_luke = profile
    
    # Top 3 joueurs
    top_players = profiles_non_admin.order_by('-score')[:3]
    
    # Statistiques par énigme (seulement les énigmes disponibles)
    enigme_stats = []
    for enigme in Enigme.objects.all().order_by('id'):
        # Ignorer les énigmes pas encore disponibles
        if not enigme.is_dispo:
            continue
        
        # Compter les joueurs qui ont résolu cette énigme (présent dans reponses_enigmes)
        completed = 0
        for profile in profiles_non_admin:
            if profile.reponses_enigmes and str(enigme.id) in profile.reponses_enigmes:
                completed += 1
        
        # Calculer le taux de complétion par rapport aux joueurs actifs
        completion_rate = (completed / active_players * 100) if active_players > 0 else 0
        
        enigme_stats.append({
            'enigme': enigme,
            'completed': completed,
            'completion_rate': completion_rate,
            'active_players': active_players,
        })
    
    # Statistiques par devinette (seulement les devinettes disponibles)
    devinette_stats = []
    for devinette in Devinette.objects.all().order_by('id'):
        # Ignorer les devinettes pas encore disponibles
        if not devinette.is_dispo:
            continue
        
        # Compter les joueurs qui ont résolu cette devinette (présent dans reponses_devinettes)
        completed = 0
        for profile in profiles_non_admin:
            if profile.reponses_devinettes and str(devinette.id) in profile.reponses_devinettes:
                completed += 1
        
        # Calculer le taux de complétion par rapport aux joueurs actifs
        completion_rate = (completed / active_players * 100) if active_players > 0 else 0
        
        devinette_stats.append({
            'devinette': devinette,
            'completed': completed,
            'completion_rate': completion_rate,
            'active_players': active_players,
        })
    
    # Indices révélés
    total_indices_enigmes = Indice.objects.count()
    total_indices_devinettes = IndiceDevinette.objects.count()
    
    # Compter les indices révélés (en parsant les champs CSV)
    indices_enigmes_reveles = 0
    indices_devinettes_reveles = 0
    for profile in profiles_non_admin:
        if profile.indices_enigme_reveles:
            indices_enigmes_reveles += len(profile.indices_enigme_reveles.split(','))
        if profile.indices_devinette_reveles:
            indices_devinettes_reveles += len(profile.indices_devinette_reveles.split(','))
    
    # Activité récente (logs des 7 derniers jours)
    from datetime import timedelta
    from django.utils import timezone
    
    seven_days_ago = timezone.now() - timedelta(days=7)
    recent_logs = AuditLog.objects.filter(
        user__is_staff=False,
        user__is_superuser=False,
        timestamp__gte=seven_days_ago
    )
    
    enigmes_validated_7d = recent_logs.filter(action=AuditLog.ENIGME_SUBMIT_SUCCESS).count()
    devinettes_validated_7d = recent_logs.filter(action=AuditLog.DEVINETTE_SUBMIT_SUCCESS).count()
    indices_revealed_7d = recent_logs.filter(
        action__in=[AuditLog.INDICE_REVEAL, AuditLog.INDICE_DEVINETTE_REVEAL]
    ).count()
    
    context = {
        'total_users': total_users,
        'active_players': active_players,
        'users_started_enigmes': users_started_enigmes,
        'users_completed_all_enigmes': users_completed_all_enigmes,
        'users_started_devinettes': users_started_devinettes,
        'users_completed_all_devinettes': users_completed_all_devinettes,
        'total_erreurs_enigmes': total_erreurs_enigmes,
        'total_erreurs_devinettes': total_erreurs_devinettes,
        'top_players': top_players,
        'enigme_stats': enigme_stats,
        'devinette_stats': devinette_stats,
        'total_indices_enigmes': total_indices_enigmes,
        'total_indices_devinettes': total_indices_devinettes,
        'indices_enigmes_reveles': indices_enigmes_reveles,
        'indices_devinettes_reveles': indices_devinettes_reveles,
        'enigmes_validated_7d': enigmes_validated_7d,
        'devinettes_validated_7d': devinettes_validated_7d,
        'indices_revealed_7d': indices_revealed_7d,
        # Awards
        'lucky_player': lucky_player,
        'persistent_player': persistent_player,
        'collector_player': collector_player,
        'perfectionist_player': perfectionist_player,
        'classement_addict': classement_addict,
        'classement_addict_views': max_views,
        'lucky_luke': lucky_luke,
        'lucky_luke_count': max_fast_devinettes,
    }
    
    # Log de la consultation des statistiques
    log_action(request.user, AuditLog.CLASSEMENT_VIEW, request, details="Consultation des statistiques")
    
    return render(request, 'avent2025/statistiques.html', context)


@login_required
def admin_triche(request):
    """
    Page de détection de triche réservée aux administrateurs.
    Analyse plusieurs indicateurs de fraude potentielle :
    - Comptes multiples sur même IP
    - Réponses anormalement rapides
    - Patterns de réponses suspects
    - Comptes avec noms/emails similaires
    - Activité suspecte (scores impossibles, progression anormale)
    """
    if not request.user.is_superuser:
        messages.error(request, "Accès refusé. Cette page est réservée aux administrateurs.")
        return redirect('avent2025:home')
    
    from collections import defaultdict, Counter
    from datetime import timedelta
    from difflib import SequenceMatcher
    
    # Récupérer tous les utilisateurs avec profil (exclure les admins)
    users = User.objects.filter(
        userprofile_2025__isnull=False,
        is_staff=False,
        is_superuser=False
    ).select_related('userprofile_2025')
    
    # ==== 1. DÉTECTION DES IPs MULTIPLES ====
    ip_users = defaultdict(set)  # Utiliser un set pour éviter les doublons
    for user in users:
        # Récupérer les IPs des logs d'audit
        user_logs = AuditLog.objects.filter(user=user).values_list('ip_address', flat=True).distinct()
        for ip in user_logs:
            if ip:
                ip_users[ip].add(user)  # add au lieu de append pour éviter les doublons
    
    # Filtrer les IPs avec plusieurs comptes
    suspicious_ips = []
    for ip, ip_user_set in ip_users.items():
        ip_user_list = list(ip_user_set)  # Convertir le set en liste
        if len(ip_user_list) > 1:
            # Vérifier si ce ne sont pas des membres de la même famille
            family_members = [u for u in ip_user_list if hasattr(u, 'userprofile_2025') and u.userprofile_2025.is_family]
            non_family = [u for u in ip_user_list if u not in family_members]
            
            # Calculer les scores pour évaluer la suspicion
            total_score = sum(u.userprofile_2025.score for u in ip_user_list if hasattr(u, 'userprofile_2025'))
            
            suspicious_ips.append({
                'ip': ip,
                'users': ip_user_list,
                'count': len(ip_user_list),
                'family_count': len(family_members),
                'non_family_count': len(non_family),
                'total_score': total_score,
                'suspicion_level': 'high' if len(non_family) > 1 and total_score > 100 else 'medium' if len(non_family) > 1 else 'low'
            })
    
    suspicious_ips.sort(key=lambda x: (x['suspicion_level'] == 'high', x['non_family_count'], x['total_score']), reverse=True)
    
    # ==== 2. RÉPONSES ANORMALEMENT RAPIDES ====
    fast_solvers = []
    for user in users:
        profile = user.userprofile_2025
        
        # Analyser les énigmes résolues rapidement (< 30 secondes depuis la PREMIÈRE ouverture)
        enigme_logs = AuditLog.objects.filter(
            user=user,
            action__in=[AuditLog.ENIGME_VIEW, AuditLog.ENIGME_SUBMIT_SUCCESS]
        ).order_by('timestamp')
        
        very_fast_enigmes = []
        # Dictionnaire pour stocker la première vue de chaque énigme
        first_views = {}
        
        for log in enigme_logs:
            # Extraire l'ID de l'énigme/devinette depuis les détails
            if 'Énigme' in log.details:
                item_id = log.details.split('Énigme ')[1].split(' ')[0] if 'Énigme ' in log.details else None
            else:
                item_id = None
            
            if log.action == AuditLog.ENIGME_VIEW and item_id:
                # Enregistrer la première vue de cette énigme
                if item_id not in first_views:
                    first_views[item_id] = log
                    
            elif log.action == AuditLog.ENIGME_SUBMIT_SUCCESS and item_id:
                # Vérifier le temps depuis la PREMIÈRE vue de cette énigme
                if item_id in first_views:
                    time_diff = (log.timestamp - first_views[item_id].timestamp).total_seconds()
                    if time_diff < 120:  # Moins de 2 minutes depuis la première ouverture
                        very_fast_enigmes.append({
                            'enigme_id': item_id,
                            'time': time_diff,
                            'first_view_timestamp': first_views[item_id].timestamp,
                            'success_timestamp': log.timestamp,
                            'timestamp': log.timestamp
                        })
        
        # Analyser les devinettes résolues rapidement (< 10 secondes depuis la PREMIÈRE ouverture)
        devinette_logs = AuditLog.objects.filter(
            user=user,
            action__in=[AuditLog.DEVINETTE_VIEW, AuditLog.DEVINETTE_SUBMIT_SUCCESS]
        ).order_by('timestamp')
        
        very_fast_devinettes = []
        # Dictionnaire pour stocker la première vue de chaque devinette
        first_views = {}
        
        for log in devinette_logs:
            # Extraire l'ID de la devinette depuis les détails
            if 'Devinette' in log.details:
                item_id = log.details.split('Devinette ')[1].split(' ')[0] if 'Devinette ' in log.details else None
            else:
                item_id = None
            
            if log.action == AuditLog.DEVINETTE_VIEW and item_id:
                # Enregistrer la première vue de cette devinette
                if item_id not in first_views:
                    first_views[item_id] = log
                    
            elif log.action == AuditLog.DEVINETTE_SUBMIT_SUCCESS and item_id:
                # Vérifier le temps depuis la PREMIÈRE vue de cette devinette
                if item_id in first_views:
                    time_diff = (log.timestamp - first_views[item_id].timestamp).total_seconds()
                    if time_diff < 60:  # Moins de 1 minute depuis la première ouverture
                        very_fast_devinettes.append({
                            'devinette_id': item_id,
                            'time': time_diff,
                            'first_view_timestamp': first_views[item_id].timestamp,
                            'success_timestamp': log.timestamp,
                            'timestamp': log.timestamp
                        })
        
        if very_fast_enigmes or very_fast_devinettes:
            fast_count = len(very_fast_enigmes) + len(very_fast_devinettes)
            fast_solvers.append({
                'user': user,
                'enigmes': very_fast_enigmes,
                'devinettes': very_fast_devinettes,
                'total_fast': fast_count,
                'score': profile.score,
                'suspicion_level': 'high' if fast_count > 5 else 'medium' if fast_count > 2 else 'low'
            })
    
    fast_solvers.sort(key=lambda x: (x['suspicion_level'] == 'high', x['total_fast']), reverse=True)
    
    # ==== 3. COMPTES AVEC NOMS/EMAILS SIMILAIRES ====
    similar_accounts = []
    users_list = list(users)
    
    def similarity(a, b):
        return SequenceMatcher(None, a.lower(), b.lower()).ratio()
    
    checked_pairs = set()
    for i, user1 in enumerate(users_list):
        for user2 in users_list[i+1:]:
            pair_key = tuple(sorted([user1.id, user2.id]))
            if pair_key in checked_pairs:
                continue
            checked_pairs.add(pair_key)
            
            # Comparer usernames
            username_sim = similarity(user1.username, user2.username)
            
            # Comparer emails si disponibles
            email_sim = 0
            if user1.email and user2.email:
                email_sim = similarity(user1.email.split('@')[0], user2.email.split('@')[0])
            
            # Comparer first_name et last_name
            name_sim = 0
            if user1.first_name and user2.first_name:
                name_sim = max(name_sim, similarity(user1.first_name, user2.first_name))
            if user1.last_name and user2.last_name:
                name_sim = max(name_sim, similarity(user1.last_name, user2.last_name))
            
            max_similarity = max(username_sim, email_sim, name_sim)
            
            if max_similarity > 0.7:  # Seuil de similarité
                # Vérifier s'ils partagent une IP
                user1_ips = set(AuditLog.objects.filter(user=user1).values_list('ip_address', flat=True))
                user2_ips = set(AuditLog.objects.filter(user=user2).values_list('ip_address', flat=True))
                shared_ips = user1_ips & user2_ips
                
                similar_accounts.append({
                    'user1': user1,
                    'user2': user2,
                    'username_similarity': round(username_sim * 100, 1),
                    'email_similarity': round(email_sim * 100, 1),
                    'name_similarity': round(name_sim * 100, 1),
                    'max_similarity': round(max_similarity * 100, 1),
                    'shared_ips': list(shared_ips),
                    'suspicion_level': 'high' if (max_similarity > 0.85 and shared_ips) else 'medium' if max_similarity > 0.85 else 'low'
                })
    
    similar_accounts.sort(key=lambda x: (x['suspicion_level'] == 'high', x['max_similarity']), reverse=True)
    
    # ==== 4. PATTERNS DE RÉPONSES SUSPECTS ====
    suspicious_patterns = []
    for user in users:
        profile = user.userprofile_2025
        
        issues = []
        
        # Score trop élevé avec trop peu d'erreurs (possiblement des réponses copiées)
        enigmes_resolues = len(profile.reponses_enigmes) if profile.reponses_enigmes else 0
        devinettes_resolues = len(profile.reponses_devinettes) if profile.reponses_devinettes else 0
        total_resolues = enigmes_resolues + devinettes_resolues
        
        if total_resolues > 15 and profile.erreurEnigma < 3:
            issues.append(f"Taux de réussite suspect : {total_resolues} résolues avec seulement {profile.erreurEnigma} erreurs")
        
        # Nombre d'indices révélés anormal (tous révélés d'un coup ?)
        indices_enigme_count = len(profile.indices_enigme_reveles) if profile.indices_enigme_reveles else 0
        indices_devinette_count = len(profile.indices_devinette_reveles) if profile.indices_devinette_reveles else 0
        total_indices = indices_enigme_count + indices_devinette_count
        
        if total_indices > 30:  # Beaucoup d'indices révélés
            issues.append(f"Nombre d'indices révélés très élevé : {total_indices}")
        
        # Progression trop rapide (toutes les énigmes résolues en très peu de temps)
        first_log = AuditLog.objects.filter(user=user).order_by('timestamp').first()
        last_success = AuditLog.objects.filter(
            user=user,
            action__in=[AuditLog.ENIGME_SUBMIT_SUCCESS, AuditLog.DEVINETTE_SUBMIT_SUCCESS]
        ).order_by('-timestamp').first()
        
        if first_log and last_success and total_resolues > 10:
            time_span = (last_success.timestamp - first_log.timestamp).total_seconds() / 3600  # en heures
            if time_span < 2 and total_resolues > 15:  # Plus de 15 réponses en moins de 2h
                issues.append(f"Progression très rapide : {total_resolues} résolues en {time_span:.1f}h")
        
        # Score anormalement bas pour le nombre de résolutions (possiblement un bug ou manipulation)
        expected_min_score = enigmes_resolues * 50 + devinettes_resolues * 20  # Score minimum attendu
        actual_score = profile.score
        if total_resolues > 5 and actual_score < expected_min_score * 0.5:
            issues.append(f"Score anormalement bas : {actual_score} pour {total_resolues} résolutions (attendu ≥{expected_min_score})")
        
        if issues:
            suspicious_patterns.append({
                'user': user,
                'issues': issues,
                'enigmes_resolues': enigmes_resolues,
                'devinettes_resolues': devinettes_resolues,
                'erreurs': profile.erreurEnigma,
                'indices': total_indices,
                'score': actual_score,
                'suspicion_level': 'high' if len(issues) >= 3 else 'medium' if len(issues) >= 2 else 'low'
            })
    
    suspicious_patterns.sort(key=lambda x: (x['suspicion_level'] == 'high', len(x['issues'])), reverse=True)
    
    # ==== 5. ACTIVITÉ ANORMALE (sessions multiples simultanées, etc.) ====
    unusual_activity = []
    for user in users:
        # Détecter les sessions suspectes (beaucoup d'actions en peu de temps)
        recent_logs = AuditLog.objects.filter(user=user).order_by('-timestamp')[:100]
        
        if recent_logs.count() > 50:
            # Grouper par minute
            actions_per_minute = defaultdict(int)
            for log in recent_logs:
                minute_key = log.timestamp.strftime('%Y-%m-%d %H:%M')
                actions_per_minute[minute_key] += 1
            
            max_actions_per_minute = max(actions_per_minute.values()) if actions_per_minute else 0
            
            if max_actions_per_minute > 20:  # Plus de 20 actions par minute
                unusual_activity.append({
                    'user': user,
                    'max_actions_per_minute': max_actions_per_minute,
                    'total_logs': recent_logs.count(),
                    'issue': f"Activité anormalement élevée : {max_actions_per_minute} actions/minute",
                    'suspicion_level': 'high' if max_actions_per_minute > 30 else 'medium'
                })
    
    unusual_activity.sort(key=lambda x: (x['suspicion_level'] == 'high', x['max_actions_per_minute']), reverse=True)
    
    # ==== 6. STATISTIQUES GLOBALES ====
    total_users_count = users.count()
    high_suspicion_count = (
        sum(1 for x in suspicious_ips if x['suspicion_level'] == 'high') +
        sum(1 for x in fast_solvers if x['suspicion_level'] == 'high') +
        sum(1 for x in similar_accounts if x['suspicion_level'] == 'high') +
        sum(1 for x in suspicious_patterns if x['suspicion_level'] == 'high') +
        sum(1 for x in unusual_activity if x['suspicion_level'] == 'high')
    )
    medium_suspicion_count = (
        sum(1 for x in suspicious_ips if x['suspicion_level'] == 'medium') +
        sum(1 for x in fast_solvers if x['suspicion_level'] == 'medium') +
        sum(1 for x in similar_accounts if x['suspicion_level'] == 'medium') +
        sum(1 for x in suspicious_patterns if x['suspicion_level'] == 'medium') +
        sum(1 for x in unusual_activity if x['suspicion_level'] == 'medium')
    )
    
    context = {
        'suspicious_ips': suspicious_ips[:20],  # Limiter à 20 résultats
        'fast_solvers': fast_solvers[:20],
        'similar_accounts': similar_accounts[:20],
        'suspicious_patterns': suspicious_patterns[:20],
        'unusual_activity': unusual_activity[:20],
        'total_users': total_users_count,
        'high_suspicion_count': high_suspicion_count,
        'medium_suspicion_count': medium_suspicion_count,
        'total_suspicious_ips': len(suspicious_ips),
        'total_fast_solvers': len(fast_solvers),
        'total_similar_accounts': len(similar_accounts),
        'total_suspicious_patterns': len(suspicious_patterns),
        'total_unusual_activity': len(unusual_activity),
    }
    
    return render(request, 'avent2025/admin_triche.html', context)


@login_required
def toggle_cheater(request, user_id):
    """
    Toggle le statut de tricheur d'un utilisateur (admin uniquement).
    """
    if not request.user.is_superuser:
        messages.error(request, "Accès refusé. Cette action est réservée aux administrateurs.")
        return redirect('avent2025:home')
    
    if request.method != 'POST':
        messages.error(request, "Méthode non autorisée.")
        return redirect('avent2025:admin_triche')
    
    try:
        user = User.objects.get(id=user_id)
        profile = user.userprofile_2025
        
        # Toggle le statut
        profile.is_cheater = not profile.is_cheater
        profile.save()
        
        if profile.is_cheater:
            messages.success(request, f"✅ L'utilisateur {user.username} a été marqué comme tricheur. Il est maintenant exclu des classements.")
        else:
            messages.success(request, f"✅ L'utilisateur {user.username} n'est plus marqué comme tricheur. Il est à nouveau inclus dans les classements.")
        
    except User.DoesNotExist:
        messages.error(request, "Utilisateur introuvable.")
    except Exception as e:
        messages.error(request, f"Erreur lors du changement de statut : {str(e)}")
    
    return redirect('avent2025:admin_triche')
