"""
Vue pour afficher les classements (famille et public)
"""
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from avent2025.models import UserProfile, get_or_create_profile
from django.db.models import F, Case, When, IntegerField


@login_required
def leaderboard(request):
    """Affiche le classement avec filtrage famille/public"""
    
    # Récupérer le profil de l'utilisateur actuel
    current_profile = get_or_create_profile(request.user)
    
    # Déterminer quel classement afficher par défaut
    filter_type = request.GET.get('filter', 'all')  # all, family, public
    
    # Calculer le score pour tous les profils
    # Score = (enigmes résolues * 100) - (erreurs énigmes * 10) + (devinettes résolues * 10) - (erreurs devinettes * 2)
    all_profiles = UserProfile.objects.select_related('user').annotate(
        calculated_score=Case(
            When(currentEnigma__gt=0, then=(
                (F('currentEnigma') - 1) * 100 - 
                F('erreurEnigma') * 10 +
                (F('currentDevinette') - 1) * 10 -
                F('erreurDevinette') * 2
            )),
            default=0,
            output_field=IntegerField()
        )
    )
    
    # Filtrer selon le type demandé
    if filter_type == 'family':
        profiles = all_profiles.filter(is_family=True)
    elif filter_type == 'public':
        profiles = all_profiles.filter(is_family=False)
    else:  # all
        profiles = all_profiles
    
    # Trier par score décroissant
    profiles = profiles.order_by('-calculated_score', '-currentEnigma', '-currentDevinette')
    
    # Préparer les données du classement avec rang
    leaderboard_data = []
    for rank, profile in enumerate(profiles, start=1):
        is_current_user = (profile.user == request.user)
        leaderboard_data.append({
            'rank': rank,
            'username': profile.user.username,
            'is_family': profile.is_family,
            'is_current_user': is_current_user,
            'enigmes_resolues': max(0, profile.currentEnigma - 1) if profile.currentEnigma > 0 else 0,
            'devinettes_resolues': max(0, profile.currentDevinette - 1) if profile.currentDevinette > 0 else 0,
            'erreurs_enigmes': profile.erreurEnigma,
            'erreurs_devinettes': profile.erreurDevinette,
            'score': profile.calculated_score,
        })
    
    # Compter les totaux
    total_users = all_profiles.count()
    family_count = all_profiles.filter(is_family=True).count()
    public_count = all_profiles.filter(is_family=False).count()
    
    context = {
        'leaderboard': leaderboard_data,
        'filter_type': filter_type,
        'current_user_is_family': current_profile.is_family,
        'total_users': total_users,
        'family_count': family_count,
        'public_count': public_count,
    }
    
    return render(request, 'avent2025/leaderboard.html', context)
