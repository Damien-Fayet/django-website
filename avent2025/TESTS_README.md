# Tests d'intégration - Calendrier de l'Avent 2025

## Vue d'ensemble

Ce fichier contient une suite complète de tests d'intégration pour l'application avent2025. Les tests simulent l'expérience utilisateur complète, de l'inscription jusqu'à la résolution d'énigmes.

## Fichier de tests

**Emplacement** : `avent2025/tests.py`

## Structure des tests

### 1. UserExperienceTestCase
Tests du parcours utilisateur complet.

#### Tests inclus :

- **test_01_home_page_accessible** : Vérifie l'accès à la page d'accueil principale
- **test_02_avent2025_redirect_when_not_logged** : Vérifie la redirection vers login si non authentifié
- **test_03_user_registration** : Teste la création d'un nouveau compte utilisateur
- **test_04_user_login** : Teste la connexion avec un compte existant
- **test_05_complete_user_journey** : **Test principal** - Parcours complet utilisateur
- **test_06_score_calculation** : Vérifie le calcul du score
- **test_07_multiple_users_ranking** : Teste le classement avec plusieurs utilisateurs
- **test_08_enigme_not_available_yet** : Vérifie qu'une énigme future n'est pas accessible
- **test_09_userprofile_creation_on_signup** : Vérifie la création automatique du profil
- **test_10_navigation_flow** : Teste le flux de navigation complet

### 2. ModelTestCase
Tests unitaires pour les modèles.

- **test_enigme_str** : Test de la représentation string d'une énigme
- **test_devinette_str** : Test de la représentation string d'une devinette
- **test_userprofile_str** : Test de la représentation string du profil utilisateur

### 3. EdgeCaseTestCase
Tests des cas limites et erreurs.

- **test_empty_response_validation** : Test de validation avec réponse vide
- **test_case_insensitive_answer** : Test que les réponses ne sont pas sensibles à la casse

## Test principal : Parcours complet utilisateur

Le test `test_05_complete_user_journey` simule l'ensemble du parcours utilisateur :

### Étapes du test :

1. **Création du compte** - Créer un nouvel utilisateur
2. **Connexion** - Se connecter avec les identifiants
3. **Accès page d'accueil** - Accéder à la page d'accueil avent2025
4. **Démarrage de l'aventure** - Initialiser le parcours énigmes
5. **Affichage de l'énigme** - Afficher la première énigme
6. **Réponse incorrecte** - Tester une mauvaise réponse
7. **Révélation d'un indice** - Débloquer un indice
8. **Réponse correcte** - Résoudre l'énigme
9. **Consultation du classement** - Voir le classement général
10. **Démarrage des devinettes** - Initialiser le parcours devinettes
11. **Affichage de la devinette** - Afficher la première devinette
12. **Déconnexion** - Se déconnecter de l'application

## Exécution des tests

### Lancer tous les tests
```bash
python manage.py test avent2025.tests
```

### Lancer tous les tests avec verbosité
```bash
python manage.py test avent2025.tests -v 2
```

### Lancer un test spécifique
```bash
python manage.py test avent2025.tests.UserExperienceTestCase.test_05_complete_user_journey
```

### Lancer une classe de tests
```bash
python manage.py test avent2025.tests.UserExperienceTestCase
```

### S'arrêter au premier échec
```bash
python manage.py test avent2025.tests --failfast
```

## Données de test

Les tests créent automatiquement des données de test :

- **Utilisateur temporaire** : `test_user_2025`
- **Énigmes de test** : 2 énigmes avec indices
- **Devinettes de test** : 1 devinette

Toutes les données sont **automatiquement supprimées** après chaque test grâce à la méthode `tearDown()`.

## Couverture des tests

Les tests couvrent les fonctionnalités suivantes :

✅ Authentification (inscription, connexion, déconnexion)  
✅ Gestion des énigmes (affichage, validation, progression)  
✅ Système d'indices (révélation, comptage)  
✅ Gestion des erreurs (mauvaises réponses, réponses vides)  
✅ Système de score (calcul dynamique)  
✅ Classement (affichage, tri)  
✅ Navigation (redirection, accès protégés)  
✅ Gestion des devinettes (affichage, progression)  
✅ Validation insensible à la casse  
✅ Dates de disponibilité des énigmes

## Résultats attendus

Lorsque tous les tests passent, vous devez voir :

```
Ran 15 tests in X.XXXs

OK
```

Le test principal affiche également un résumé visuel :

```
=== TEST PARCOURS COMPLET UTILISATEUR ===
1. Création du compte...
   ✓ Utilisateur créé: test_user_2025
2. Connexion...
   ✓ Connexion réussie
...
12. Déconnexion...
   ✓ Déconnexion réussie

=== PARCOURS COMPLET TERMINÉ AVEC SUCCÈS ===
```

## Notes importantes

### Calcul du score
Le score n'est PAS stocké directement dans la base de données. Il est calculé dynamiquement selon la formule :

```python
score_enigme = (currentEnigma - 1) * 100 - erreurs * 5 - nb_indices
score_devinette = (currentDevinette - 1) * 50 - erreurs * 5 - nb_indices
```

### Validation des réponses
Les réponses sont normalisées avant comparaison :
- Conversion en minuscules
- Suppression des espaces
- Normalisation des accents (via unidecode)

### Signaux Django
Les tests vérifient que les signaux Django créent automatiquement un `UserProfile` à la création d'un `User`.

## Maintenance

Pour ajouter de nouveaux tests :

1. Ajouter une nouvelle méthode `test_XX_nom_descriptif` dans la classe appropriée
2. Utiliser les assertions Django (`assertEqual`, `assertContains`, etc.)
3. Nettoyer les données dans `tearDown()` si nécessaire
4. Documenter le test dans ce README

## Debugging

Pour débugger un test qui échoue :

```python
# Ajouter des prints dans le test
print(f"Valeur actuelle: {variable}")

# Ou utiliser pdb
import pdb; pdb.set_trace()

# Voir les détails HTTP
print(response.content)
print(response.status_code)
```

## Dépendances

Les tests requièrent :
- Django Test Framework (inclus dans Django)
- Base de données de test (SQLite en mémoire)
- Toutes les apps listées dans `INSTALLED_APPS`

Aucune dépendance externe supplémentaire n'est nécessaire.

## Migration
# 1. Faire une sauvegarde de la base de données
python manage.py dumpdata avent2025 > backup_avent2025.json

# 2. Exécuter le script de migration
source django/bin/activate
python migrate_user_responses.py

# 3. Vérifier les logs pour s'assurer que tout s'est bien passé

# 4. Déployer le nouveau code