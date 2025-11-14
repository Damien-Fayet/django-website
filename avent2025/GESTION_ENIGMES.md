# 🎄 Guide : Ajouter des énigmes au Calendrier de l'Avent 2025

## Page d'attente automatique

Quand aucune énigme n'est disponible, les utilisateurs verront automatiquement une **belle page d'attente** avec :
- 🎄 Un message d'accueil chaleureux
- ⏳ Une explication claire
- 🏠 Un bouton de retour à l'accueil
- 🚀 Un bouton pour démarrer l'aventure (quand disponible)

Cette page s'affiche automatiquement dans les cas suivants :
- Aucune énigme n'existe dans la base de données
- L'utilisateur a terminé toutes les énigmes disponibles
- L'utilisateur n'a pas encore commencé l'aventure

## Ajouter des énigmes via l'interface d'administration

### 1. Accéder à l'admin Django

```
http://127.0.0.1:8000/admin/
```

Connectez-vous avec vos identifiants d'administrateur.

### 2. Créer une énigme

1. Allez dans **Avent2025 > Énigmes**
2. Cliquez sur **Ajouter Énigme**
3. Remplissez les champs :

| Champ | Description | Exemple |
|-------|-------------|---------|
| **ID** | Numéro de l'énigme (ordre) | 1, 2, 3... |
| **Titre** | Titre de l'énigme | "Le mystère du cadeau perdu" |
| **Texte** | Énoncé de l'énigme | "Je suis rouge et blanc, j'apporte des cadeaux..." |
| **Réponse** | Réponse(s) acceptée(s) | "Père Noël" ou "PèreNoël,SantaClaus" |
| **Date de disponibilité** | Quand l'énigme devient accessible | 2025-12-01 |
| **Image (optionnel)** | Image associée à l'énigme | photo.jpg |

### 3. Ajouter des indices (optionnel)

1. Allez dans **Avent2025 > Indices**
2. Cliquez sur **Ajouter Indice**
3. Remplissez :
   - **Énigme** : Sélectionnez l'énigme
   - **Numéro** : Ordre de l'indice (1, 2, 3...)
   - **Catégorie** : 
     - **Mécanique** : Indice sur la façon de résoudre (méthode, approche)
     - **Réponse attendue** : Indice sur la nature de la réponse (format, type)
   - **Coût en points** : Combien de points l'indice coûte (1, 2 ou 3)
   - **Texte** : Contenu de l'indice
   - **Image (optionnel)** : Image d'illustration

#### Exemples de catégories d'indices

**Indices de type "Mécanique"** (comment résoudre) :
- "Cherchez dans le texte les mots en majuscules" → **1 point**
- "Les premières lettres de chaque phrase forment un mot" → **2 points**
- "Comptez le nombre d'étoiles dans l'image" → **1 point**

**Indices de type "Réponse attendue"** (format de la réponse) :
- "La réponse est un nombre entre 1 et 24" → **1 point**
- "C'est le nom d'un personnage de Noël" → **2 points**
- "Répondez en un seul mot, sans espace" → **1 point**

#### Stratégie de coût des indices

- **1 point** : Indice léger, donne une petite aide
- **2 points** : Indice moyen, donne une aide significative
- **3 points** : Indice fort, révèle beaucoup d'information

💡 **Astuce** : Les premiers indices devraient coûter moins cher (1-2 pts) et les derniers plus cher (2-3 pts) car ils donnent plus d'informations.

### 4. Créer des devinettes (optionnel)

Même processus que pour les énigmes, dans **Avent2025 > Devinettes**.

## Ajouter des énigmes via code Python

### Script rapide pour ajouter une énigme

```python
python manage.py shell
```

```python
from avent2025.models import Enigme, Indice
from datetime import date

# Créer l'énigme
enigme = Enigme.objects.create(
    id=1,
    titre="La première énigme",
    texte="Quel est le symbole de Noël par excellence ?",
    reponse="Sapin,Sapin de Noël",
    date_dispo=date(2025, 12, 1)
)

# Ajouter des indices
Indice.objects.create(
    enigme=enigme,
    numero=1,
    categorie='ME',  # 'ME' pour Mécanique, 'RE' pour Réponse attendue
    cout=1,  # Coût en points : 1, 2 ou 3
    texte="C'est vert toute l'année"
)

Indice.objects.create(
    enigme=enigme,
    numero=2,
    categorie='RE',
    cout=2,
    texte="La réponse est un nom d'arbre"
)

Indice.objects.create(
    enigme=enigme,
    numero=2,
    texte="On le décore avec des guirlandes"
)

print(f"✅ Énigme '{enigme.titre}' créée avec {enigme.indice_set.count()} indices")
```

### Script pour créer plusieurs énigmes

Créez un fichier `avent2025/management/commands/create_enigmes.py` :

```python
from django.core.management.base import BaseCommand
from avent2025.models import Enigme, Indice
from datetime import date

class Command(BaseCommand):
    help = 'Crée les énigmes du calendrier de l\'Avent 2025'

    def handle(self, *args, **options):
        enigmes_data = [
            {
                'id': 1,
                'titre': 'Énigme du 1er décembre',
                'texte': 'Je suis...',
                'reponse': 'Réponse',
                'date': date(2025, 12, 1),
                'indices': ['Indice 1', 'Indice 2']
            },
            # Ajoutez d'autres énigmes ici
        ]

        for data in enigmes_data:
            enigme, created = Enigme.objects.get_or_create(
                id=data['id'],
                defaults={
                    'titre': data['titre'],
                    'texte': data['texte'],
                    'reponse': data['reponse'],
                    'date_dispo': data['date']
                }
            )
            
            if created:
                for i, texte in enumerate(data['indices'], 1):
                    Indice.objects.create(
                        enigme=enigme,
                        numero=i,
                        texte=texte
                    )
                self.stdout.write(
                    self.style.SUCCESS(f'✅ Énigme {enigme.id} créée')
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f'⚠️  Énigme {enigme.id} existe déjà')
                )
```

Puis lancez :
```bash
python manage.py create_enigmes
```

## Format des réponses

Les réponses peuvent avoir plusieurs variantes séparées par des virgules :

```python
reponse = "Père Noël,PèreNoël,Pere Noel,Santa Claus"
```

Le système normalise automatiquement :
- Conversion en minuscules
- Suppression des espaces
- Suppression des accents

Donc "Père Noël", "pere noel", "PERE NOEL" seront tous acceptés !

## Dates de disponibilité

- Les énigmes avec `date_dispo` dans le futur ne seront **pas accessibles**
- La méthode `is_dispo` vérifie automatiquement si la date est passée
- Utilisez des dates progressives pour un vrai calendrier de l'Avent :
  - Énigme 1 : 1er décembre 2025
  - Énigme 2 : 2 décembre 2025
  - Etc.

## Vérifier le statut

### Via l'admin Django
L'interface admin affiche :
- Le nombre d'énigmes
- Les dates de disponibilité
- Le statut "Disponible" (oui/non)
- Le nombre d'indices par énigme

### Via le shell
```python
python manage.py shell
```

```python
from avent2025.models import Enigme

# Compter les énigmes
print(f"Total d'énigmes : {Enigme.objects.count()}")

# Énigmes disponibles aujourd'hui
from datetime import date
disponibles = Enigme.objects.filter(date_dispo__lte=date.today())
print(f"Énigmes disponibles : {disponibles.count()}")

# Lister toutes les énigmes
for e in Enigme.objects.all():
    print(f"#{e.id} - {e.titre} - {'✅ Dispo' if e.is_dispo else '⏳ Bientôt'}")
```

## Tester la page d'attente

Pour tester l'affichage de la page d'attente :

1. **Sans énigmes** : Supprimez toutes les énigmes
2. **Aventure non commencée** : Créez un utilisateur qui n'a pas encore cliqué sur "Démarrer l'aventure"
3. **Toutes résolues** : Créez 3 énigmes, résolvez-les toutes, la page s'affichera automatiquement

## Conseils

✅ **Numérotez vos énigmes séquentiellement** (1, 2, 3...) sans trous  
✅ **Testez vos réponses** avec différentes variantes  
✅ **Ajoutez au moins 1-2 indices** par énigme pour aider les joueurs  
✅ **Programmez les dates** à l'avance pour un déploiement automatique  
✅ **Variez la difficulté** pour maintenir l'intérêt

## En cas de problème

Si une erreur 404 apparaît au lieu de la page d'attente :
1. Vérifiez les logs du serveur
2. Vérifiez que le template `waiting.html` existe
3. Testez avec `python manage.py check`
4. Redémarrez le serveur Django

Profitez bien du calendrier de l'Avent 2025 ! 🎄✨
