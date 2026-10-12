# Illustrations des deux villages

Le jeu affiche deux villages enneigés, un par piste : **le village des énigmes** et **le village des devinettes**.
Chacun porte 24 lumières (une par jour) qui s'allument quand on résout le puzzle du jour.
Ce document dit quoi fournir, comment le fournir et comment régler les lumières.

## 1. Les deux images

| Fichier à déposer | Village |
|---|---|
| `static/avent2026/img/village-enigmes.webp` | le village des énigmes |
| `static/avent2026/img/village-devinettes.webp` | le village des devinettes |

Formats acceptés : `webp` (recommandé), `jpg`, `png`. Tant qu'une image manque, le jeu reste jouable sur un fond de nuit neigeuse.

**Contraintes techniques**
- Format **paysage 3:2** (par exemple 1800 × 1200 px). Le cadre affiché est en 3:2, une autre proportion sera rognée.
- **Moins de 200 Ko par image** (hébergement à espace limité). En webp qualité 70 à 80 c'est largement atteignable ; sinon réduire à 1600 × 1067 px.
- Aucun texte dans l'image.

**Contraintes de composition**
- **Nuit, neige, ambiance bleu nuit.** C'est le décor « éteint » : le code ajoute la lueur dorée sur les fenêtres au fil des résolutions.
- **Toutes les fenêtres et lanternes doivent être éteintes** (sombres), sinon la lueur ne se verra pas.
- **24 endroits bien distincts** à allumer : des fenêtres de maisons (village des énigmes) ou des lanternes, lampadaires et guirlandes (village des devinettes), assez espacés pour qu'on puisse les toucher du doigt (au moins 1/20 de la largeur de l'image entre deux).
- **Un parcours qui se lit** : une rue ou un chemin qui serpente du premier plan (jour 1) jusqu'à la place du fond avec un **grand sapin** (jour 24). Plus la lumière avance, plus on se rapproche du but.
- Le **jour 24** est l'élément final : le grand sapin et son étoile (ou la plus grande fenêtre).
- Éviter les détails importants sur les bords : sur téléphone l'image défile horizontalement.

## 2. Suggestion de prompt (à adapter à ton outil : Midjourney, DALL·E, Firefly, Leonardo…)

> Illustration de livre pour enfants, village de montagne enneigé la nuit, vue légèrement en plongée, un chemin
> serpente depuis le premier plan jusqu'à une petite place avec un très grand sapin de Noël au fond, maisons en bois
> aux toits couverts de neige, **toutes les fenêtres sont éteintes et sombres**, cheminées sans fumée, ciel étoilé bleu
> nuit avec une lune pâle, sapins givrés, atmosphère calme et poétique, palette bleu nuit et violet, style peinture
> numérique douce façon gouache, composition large 3:2, aucun texte, aucune lumière allumée.

Pour le village des devinettes, remplacer le début par « …village enneigé éclairé uniquement par des lanternes et des
lampadaires **éteints** le long des rues… ».

Astuce : les générateurs d'images allument souvent les fenêtres malgré la consigne. Régénérer, ou ajouter dans le
prompt « night, dark windows, unlit lanterns, no warm light », ou éteindre les fenêtres à la retouche.

## 3. Régler la position des lumières

Une fois l'image déposée :

1. Se connecter avec un compte **staff**, ouvrir `/avent2026/` : sous chaque village un lien « Régler la position des lumières ».
2. Cliquer sur l'illustration, **dans l'ordre des jours** (1, 2, 3 … 24), sur la fenêtre ou la lanterne à allumer.
   Cliquer sur un numéro dans la liste permet d'en re-placer un seul.
3. Copier le texte généré et **remplacer tout le contenu** de `avent2026/lights.json` (il contient les deux villages),
   puis recharger la page. Les positions sont en pourcentage de l'image, donc valables à toutes les tailles d'écran.

Faire l'opération pour les deux villages, mais un seul `lights.json` à mettre à jour.

## 4. Après avoir déposé les images

- Vérifier le poids : `du -sh static/avent2026/img`.
- `python manage.py collectstatic` au déploiement, puis Reload (voir `CLAUDE.md`).
