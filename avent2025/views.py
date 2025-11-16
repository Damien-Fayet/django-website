import random
from django.shortcuts import render, redirect
from django.core.files.storage import FileSystemStorage
from django.conf import settings
from django import forms
from django.contrib import messages
from django.contrib.auth.models import User
from django.urls import reverse
from .models import Enigme, Indice, UserProfile, Devinette, IndiceDevinette, get_or_create_profile
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404
from django.contrib.auth import get_user_model
from django.core.mail import send_mail, BadHeaderError
import unidecode
import re
from datetime import datetime, timezone
from .forms import ContactForm


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

        
@login_required
def home(request):
    # Vérifier l'accès avant le 01/12/2025
    if not is_access_allowed(request.user):
        return render(request, 'avent2025/waiting.html', {
            'content_type': 'énigmes',
            'message': '🎄 Le Calendrier de l\'Avent 2025 ouvre le 1er décembre !',
            'description': 'Les énigmes seront disponibles à partir du 1er décembre 2025. Revenez à cette date pour commencer l\'aventure !'
        })
    
    # Garantir que l'utilisateur a un profil
    profile = get_or_create_profile(request.user)
    
    current_enigma = profile.currentEnigma
    
    # Calculer le nombre d'énigmes résolues et le pourcentage
    enigmes_resolues = max(0, current_enigma - 1) if current_enigma > 0 else 0
    total_enigmes = 8
    pourcentage = int((enigmes_resolues / total_enigmes) * 100) if enigmes_resolues > 0 else 0
    
    context = {
        "current_enigma": current_enigma,
        "enigmes_resolues": enigmes_resolues,
        "total_enigmes": total_enigmes,
        "pourcentage": pourcentage,
    }
    
    return render(request, 'avent2025/modern_home.html', context)

def public_home(request):
    """Page d'accueil pour les utilisateurs non connectés"""
    if request.user.is_authenticated:
        return redirect('avent2025:home')
    return render(request, 'modern_welcome.html')

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
    else:
        # Vérifier que l'énigme demandée est accessible (débloquée)
        if enigme_id > profile.currentEnigma:
            return render(request, 'avent2025/waiting.html', {
                'content_type': 'énigme',
                'message': 'Énigme non accessible',
                'description': f'L\'énigme #{enigme_id} n\'est pas encore débloquée. Résolvez d\'abord les énigmes précédentes !',
                'show_start_button': False
            })
    
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
    indices = Indice.objects.filter(enigme=current_enigma)
    
    # Lister les indices révélés
    indice_reveles_list = []
    if profile.indices_enigme_reveles:
        indice_reveles_list = [int(x) for x in profile.indices_enigme_reveles.split(",")]
    
    indices_reveles = indices.filter(id__in=indice_reveles_list)
    indices_hidden = indices.exclude(id__in=indice_reveles_list)
    
    return render(request, 'avent2025/modern_enigme.html', {
        'reponse_enigme': current_enigma.reponse,
        'enigme': current_enigma,
        'user_reponse': reponse,
        'indices': indices,
        'indices_reveles': indices_reveles,
        'indices_hidden': indices_hidden,
        'date_warning': date_warning,
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
    else:
        # Vérifier que la devinette demandée est accessible (débloquée)
        if devinette_id > profile.currentDevinette:
            return render(request, 'avent2025/waiting.html', {
                'content_type': 'devinette',
                'message': 'Devinette non accessible',
                'description': f'La devinette #{devinette_id} n\'est pas encore débloquée. Résolvez d\'abord les devinettes précédentes !',
                'show_start_button': False
            })
    
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
    indices = IndiceDevinette.objects.filter(enigme=current_devinette)
    
    
    # Lister les indice revelés
    indice_reveles_list = []
    if profile.indices_devinette_reveles:
        indice_reveles_list = [int(x) for x in profile.indices_devinette_reveles.split(",")]
    
    
    indices_reveles = indices.filter(id__in= indice_reveles_list)
    indices_hidden = indices.exclude(id__in=indice_reveles_list)
    return render(request, 'avent2025/modern_devinette.html',  {
        'reponse_devinette' : current_devinette.reponse,
        'devinette' : current_devinette,
        'user_reponse' : reponse,
        'indices' : indices,
        'indices_reveles' : indices_reveles,
        'indices_hidden' : indices_hidden,
        'date_warning': date_warning,
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
        current_enigma_number = user_profile.currentEnigma
        current_enigma = get_object_or_404(Enigme, id=current_enigma_number)
        reponse = request.POST.get("user_reponse")  # Correspond au nom du champ dans modern_enigme.html
        
        # Vérifier que la réponse n'est pas vide
        if not reponse:
            messages.error(request, "Veuillez entrer une réponse")
            return redirect('avent2025:display_enigme')
        
        # Utiliser la fonction de validation robuste
        reponses_possibles = [r.strip() for r in current_enigma.reponse.split(",")]
        
        if check_answer(reponse, reponses_possibles):
            messages.success(request, "Bonne reponse")
            user_profile.currentEnigma += 1
            current_enigma = get_object_or_404(Enigme, id=user_profile.currentEnigma)
            user_profile.save()
            image_id = random.randint(1, 13)
            return render(request, 'avent2025/enigme.html',  {
                'reponse_enigme' : current_enigma.reponse,
                'enigme' : current_enigma,
                'user_reponse' : 'OK',
                'old_enigme_id' : current_enigma.id -1,
                'image_reponse' : f"gagne{image_id}.gif"
            })
        else:
            image_id = random.randint(1, 24)
            user_profile.erreurEnigma += 1
            user_profile.save()
            return render(request, 'avent2025/enigme.html',  {
                'reponse_enigme' : current_enigma.reponse,
                'enigme' : current_enigma,
                'user_reponse' : 'KO',
                'image_reponse' : f"perdu{image_id}.gif"
            })

    return redirect('avent2025:display_enigme')

@login_required
def validate_devinette(request):
    if request.method == "POST":
        # Garantir que l'utilisateur a un profil
        user_profile = get_or_create_profile(request.user)
        current_devinette_number = user_profile.currentDevinette
        current_devinette = get_object_or_404(Devinette, id=current_devinette_number)
        reponse = request.POST.get("reponse")
        
        # Vérifier que la réponse n'est pas vide
        if not reponse:
            messages.error(request, "Veuillez entrer une réponse")
            return redirect('avent2025:display_devinette')
        
        # Utiliser la fonction de validation robuste
        reponses_possibles = [r.strip() for r in current_devinette.reponse.split(",")]
        
        if check_answer(reponse, reponses_possibles):
            messages.success(request, "Bonne réponse !")
            user_profile.currentDevinette += 1
            user_profile.save()
            
            # Vérifier si une devinette suivante existe
            next_devinette = Devinette.objects.filter(id=user_profile.currentDevinette).first()
            
            if next_devinette:
                # Il y a une devinette suivante
                image_id = random.randint(1, 13)
                return render(request, 'avent2025/modern_devinette.html',  {
                    'reponse_devinette' : next_devinette.reponse,
                    'devinette' : next_devinette,
                    'user_reponse' : 'OK',
                    'old_devinette_id' : next_devinette.id - 1,
                    'image_reponse' : f"gagne{image_id}.gif"
                })
            else:
                # Toutes les devinettes sont terminées
                return redirect('avent2025:devinettes_completees')
        else:
            image_id = random.randint(1, 24)
            user_profile.erreurDevinette += 1
            user_profile.save()
            return render(request, 'avent2025/modern_devinette.html',  {
                'reponse_devinette' : current_devinette.reponse,
                'devinette' : current_devinette,
                'user_reponse' : 'KO',
                'image_reponse' : f"perdu{image_id}.gif"
            })

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
        
    user_profile.save()
    
    return redirect(reverse('avent2025:display_enigme') + "#indices")


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
        
    user_profile.save()
    return redirect(reverse('avent2025:display_devinette') + "#indices")


def classement(request):
    
    User = get_user_model()
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
            users_with_profile.append(u)
            nb_indice_enigme[u.id] = 0 if u.userprofile_2025.indices_enigme_reveles=='' else len(u.userprofile_2025.indices_enigme_reveles.split(','))
            nb_indice_devinette[u.id] = 0 if u.userprofile_2025.indices_devinette_reveles=='' else len(u.userprofile_2025.indices_devinette_reveles.split(','))
            enigme_score[u.id] = max(0,(max(1,u.userprofile_2025.currentEnigma) -1)*100 - u.userprofile_2025.erreurEnigma*5 - nb_indice_enigme[u.id])
            devinette_score[u.id] = max(0,(max(1,u.userprofile_2025.currentDevinette) -1)*50 - u.userprofile_2025.erreurDevinette*5 - nb_indice_devinette[u.id])
            moy_indices_enigme[u.id] = 0 if max(1,u.userprofile_2025.currentEnigma) -1 <= 0 else round(nb_indice_enigme[u.id] / (max(1,u.userprofile_2025.currentEnigma) -1),1)
            moy_indices_devinette[u.id] = 0 if max(1,u.userprofile_2025.currentDevinette) -1 <= 0 else round(nb_indice_devinette[u.id] / (max(1,u.userprofile_2025.currentDevinette) -1),1)
            total[u.id] = enigme_score[u.id] + devinette_score[u.id]
        
    users = users_with_profile
    sorted_users = sorted(users, key=lambda item: total[item.id],reverse=True)
    sorted_users_enigme = sorted(users, key=lambda item: enigme_score[item.id],reverse=True)
    sorted_users_devinette = sorted(users, key=lambda item: devinette_score[item.id],reverse=True)
    
    # Calculer quelques stats supplémentaires
    nb_enigmes = {u.id: max(0, u.userprofile_2025.currentEnigma - 1) for u in users}
    nb_devinettes = {u.id: max(0, u.userprofile_2025.currentDevinette - 1) for u in users}
    nb_erreurs = {u.id: u.userprofile_2025.erreurEnigma for u in users}
    scores = {u.id: total[u.id] for u in users}
    total_enigmes = 8
    total_devinettes = 24
    avg_score = sum(scores.values()) / len(scores) if scores else 0
    
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
            
            try:
                # Envoyer l'email
                send_mail(
                    email_subject,
                    email_body,
                    settings.DEFAULT_FROM_EMAIL,  # Expéditeur
                    ['fayet.damien63@gmail.com'],  # Destinataire
                    fail_silently=False,
                    reply_to=[email]  # Email de réponse
                )
                messages.success(request, '✅ Votre message a été envoyé avec succès ! Je vous répondrai dès que possible.')
                return redirect('avent2025:contact')
            except BadHeaderError:
                messages.error(request, '❌ Erreur: en-tête email invalide.')
            except Exception as e:
                messages.error(request, f'❌ Une erreur est survenue lors de l\'envoi du message. Veuillez réessayer plus tard.')
                # En développement, vous pouvez afficher l'erreur : messages.error(request, f'Erreur: {str(e)}')
    else:
        form = ContactForm()
    
    return render(request, 'avent2025/contact.html', {'form': form})
