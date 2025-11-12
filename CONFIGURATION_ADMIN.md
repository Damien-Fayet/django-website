# Configuration de l'interface administrateur - Max Challenge

## Paramètres de configuration de la partie

Dans l'interface admin Django (`/admin/max_challenge/gamesession/`), vous pouvez configurer les paramètres suivants :

### Nombre de carrés révélés par tour
**Champ : `squares_per_reveal`**  
**Valeur par défaut : 6**

Ce paramètre détermine combien de carrés de la grille 10x10 (100 carrés au total) seront révélés lorsqu'une équipe trouve la bonne réponse à une définition.

- **Minimum recommandé :** 1 carré (pour un jeu très long et difficile)
- **Valeur par défaut :** 6 carrés (équilibre entre progression et difficulté)
- **Maximum recommandé :** 20 carrés (pour un jeu plus rapide)

**Impact sur le jeu :**
- Plus la valeur est **faible**, plus le jeu est **long** et **difficile** (il faudra plus de bonnes réponses pour révéler toute l'image)
- Plus la valeur est **élevée**, plus le jeu est **rapide** (moins de bonnes réponses nécessaires)

**Exemple :**
- Avec 6 carrés par révélation : environ 17 bonnes réponses nécessaires pour révéler les 100 carrés
- Avec 10 carrés par révélation : environ 10 bonnes réponses nécessaires
- Avec 3 carrés par révélation : environ 34 bonnes réponses nécessaires

### Autres paramètres de configuration

- **Nombre maximum d'équipes** (`max_teams`) : Nombre d'équipes pouvant participer (par défaut : 4)
- **Points par bonne réponse** (`points_per_correct`) : Points attribués à chaque bonne réponse (par défaut : 10)
- **Vitesse révélation ASCII** (`ascii_reveal_speed`) : Vitesse d'affichage de l'art ASCII (Lente/Moyenne/Rapide)
- **Vitesse révélation définitions** (`definition_reveal_speed`) : Vitesse d'affichage des mots de la définition (Lente/Moyenne/Rapide)

## Modification des paramètres

1. Accédez à l'interface admin : `http://127.0.0.1:8000/admin/`
2. Allez dans **Max Challenge** → **Parties**
3. Cliquez sur la partie active
4. Modifiez le champ **"Nombre de carrés révélés par tour"** dans la section **Configuration**
5. Cliquez sur **Enregistrer**

Les modifications prennent effet immédiatement pour les prochaines révélations de carrés.
