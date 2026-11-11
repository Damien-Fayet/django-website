# Illustrations de la cellule du Père Noël (piste des énigmes)

Les énigmes ne se jouent plus dans un village mais dans **la cellule où le Père Noël est enchaîné**. Chaque énigme résolue
brise un verrou ; huit énigmes, huit verrous, et à la dernière le Père Noël est libre.
Ce document dit quoi fournir, comment le fournir et ce que doit montrer chacune des 9 images.

> Le village des devinettes est déjà fait (voir `ILLUSTRATIONS_VILLAGES.md`). Rien à régler en pourcentage, pas de
> calibrage : la piste des énigmes fonctionne comme lui, avec **une image par nombre d'énigmes résolues par le joueur**.

## 1. Le calendrier des verrous

| Étape | Verrou | Date | Image affichée quand le joueur en a résolu… |
|---|---|---|---|
| 0 | | | aucune (cellule fermée, tout est rouge) |
| 1 | 1 | mar. 1er déc. (échauffement) | 1 énigme |
| 2 | 2 | mer. 2 déc. | 2 énigmes |
| 3 | 3 | sam. 5 déc. | 3 énigmes |
| 4 | 4 | mer. 9 déc. | 4 énigmes |
| 5 | 5 | sam. 12 déc. | 5 énigmes |
| 6 | 6 | mer. 16 déc. | 6 énigmes |
| 7 | 7 | sam. 19 déc. | 7 énigmes |
| 8 | 8 | mer. 23 déc. | 8 énigmes (Père Noël libre) |

Chaque joueur avance à son rythme : l'image dépend du nombre d'énigmes **qu'il** a résolues, pas de la date. Les énigmes
sortent à **6 h du matin** (heure de Paris), le jour indiqué.

## 2. Les 9 fichiers

À déposer dans `static/avent2026/img/carte-enigmes/` :

```
cellule-etape-00.webp  …  cellule-etape-08.webp
```

**Contraintes techniques**
- Même cadrage pour les 9 images (c'est la même scène qui évolue), au **format 3:2** : 1600 × 1080 px de préférence, mais une taille proche (ex. 1264 × 848) convient (le cadre rogne légèrement).
- Format **webp**, qualité 80 (export avec Pillow : `Image.open(png).save(webp, "WEBP", quality=80, method=6)`).
  **Le poids n'est pas une contrainte** (hébergement sur SSD) : 1 à 2 Mo par image conviennent. Il pèse seulement sur le
  temps de chargement de la page (la nouvelle image et l'ancienne sont chargées pour le fondu), inutile donc de dépasser
  ~2 Mo.
- **Aucun texte** dans l'image (les libellés sont dans la page).
- Ne pas versionner les PNG d'origine (ils sont ignorés par `.gitignore`).
- Tant qu'une image manque, le jeu reste jouable sur un fond sombre dessiné en CSS (un message « image manquante »
  s'affiche pour le staff).

## 3. Direction artistique

**Un thriller, pas un conte.** Public plus jeune, compétiteur, moderne : on est plus près d'un film de braquage ou d'un
escape game que d'un livre pour enfants. Le Père Noël reste digne (prisonnier de marque, pas humilié ni maltraité).

- **Lieu** : une cellule ultra-sécurisée, entre coffre-fort de banque et laboratoire de haute sécurité : parois métalliques
  ou glace noire, grille de lasers, caméras, panneaux de contrôle, huit énormes cadenas / verrous numériques alignés
  autour de la pièce ou sur la porte. Le Père Noël est assis ou debout au centre, **retenu par huit chaînes**, une par
  verrou.
- **Style** : rendu 3D stylisé ou illustration numérique cinématographique, contrastée, bien éclairée, texture lisse.
  Même type de point de vue (légèrement en plongée, isométrique ou presque) que le village des devinettes pour que les
  deux cartes se répondent. Pas de gouache ni de style « livre pour enfants ».
- **Palette** : nuit bleu-noir + **rouge alarme** (verrous fermés, lasers, voyants) qui vire au **vert doré** au fil des
  verrous brisés. À l'étape 8, la pièce est baignée de lumière chaude (rouge totalement éteint).
- **Lisibilité** : les 8 verrous doivent être **bien distincts et toujours au même endroit** d'une image à l'autre : c'est
  ce qui fait voir la progression. Éviter les détails importants sur les bords (recadrage sur téléphone).
- **Rappel du thème** : la tempête de neige n'était qu'un écran de fumée. On peut voir un peu de neige par un conduit ou
  une lucarne, un fil électrique sectionné, la valise-outil du ravisseur… sans montrer de visage.
- **Interface** : l'interface du site reste sobre (vert sapin). Le rouge et le vert vivent **seulement dans l'illustration**,
  comme la lueur des fenêtres du village.

## 4. Ce que montre chaque étape

| Étape | Ce qu'on voit |
|---|---|
| 0 | Cellule en alerte : **8 verrous rouges fermés**, 8 chaînes tendues, lasers actifs, voyants rouges. Père Noël prisonnier. |
| 1 | **Un verrou passe au vert** et sa chaîne tombe au sol. Le reste est inchangé. |
| 2 à 7 | À chaque étape, **un verrou de plus** est vert et sa chaîne est tombée. Les lasers disparaissent par paliers (à l'étape 4 environ : la grille est à moitié éteinte). L'éclairage rougeâtre recule peu à peu. |
| 7 | Un seul verrou rouge reste. Le Père Noël se redresse, la porte tremble. |
| 8 | **Tous les verrous sont brisés.** Chaînes au sol, porte grande ouverte sur la neige, lumière chaude, le Père Noël est debout et libre (traîneau ou silhouette qui part vers la place du réveillon). |

> **Important** : les 9 images doivent être la même scène, même caméra, même cadrage. Générer d'abord l'image 0, puis
> demander à l'outil des **variantes de cette image** (« même scène, le verrou n°1 est brisé… ») ou retoucher l'image
> précédente. Numéroter les verrous de gauche à droite (ou dans l'ordre horaire) pour qu'ils s'ouvrent toujours dans le
> même ordre.

## 5. Prompts à adapter (Midjourney, DALL·E, Firefly, Leonardo…)

**Image de départ (étape 0)**

> Cinematic isometric view of a high-security vault cell at night, Santa Claus seated in the center held by eight heavy
> glowing chains, each chain attached to one of eight large red digital padlocks arranged evenly around the room, laser
> grid across the floor, security cameras, red alarm lights, dark metallic walls, a small skylight with falling snow,
> moody thriller atmosphere, stylized 3D render, high contrast, no text, 3:2 composition.

**Étapes 1 à 7**, en partant de l'image précédente :

> Same scene, same camera, same composition. Padlock number N is now unlocked and glowing green, its chain has fallen on
> the floor. The other padlocks stay red. [Étape 4 : half of the laser grid is switched off. Étape 7: only one red padlock
> remains.] No text.

**Image finale (étape 8)**

> Same scene, same camera. All eight padlocks are open and green, all chains lie broken on the floor, the vault door is
> wide open onto a snowy night, warm golden light fills the room, Santa Claus stands free, hopeful mood, no lasers, no
> red light, no text.

Astuce : les générateurs ont du mal à garder la même scène d'une image à l'autre. Utiliser la fonction « variation /
référence d'image » de l'outil, ou retoucher l'image d'origine et la décliner à la main, plutôt que de regénérer à partir
de zéro.

## 6. Après avoir déposé les images

- Vérifier que les 9 fichiers existent (`cellule-etape-00` à `cellule-etape-08`) et regarder la page `/avent2026/` avec le
  compte staff (qui voit tous les jours).
- `python manage.py collectstatic` au déploiement, puis Reload (voir `CLAUDE.md`).
