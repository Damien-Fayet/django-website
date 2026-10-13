# Illustrations du village des devinettes

> **Statut : fait.** Le village des devinettes est dessiné étape par étape, il n'y a plus rien à fournir ni à calibrer.
> L'ancien village des énigmes (24 lumières posées sur une seule image, page de calibrage) a été **remplacé** par la
> cellule du Père Noël : voir `ILLUSTRATIONS_ENIGMES.md`.

## Les 25 images

Le village des devinettes n'utilise pas une image unique mais 25 images « étape »
(`static/avent2026/img/carte-devinettes/village-iso-etape-00.webp` à `-24.webp`, 1600 × 1080), une par nombre de
devinettes résolues par le joueur : l'étape 0 est le village sous la tempête, l'étape 24 le village entièrement allumé.
Les 24 jours sont des boutons sous l'image.

Pour les remplacer : mêmes noms, mêmes dimensions, et exporter en webp
(`Pillow` : `Image.open(png).save(webp, "WEBP", quality=80, method=6)`, ~80 Ko chacune).
Les PNG d'origine ne sont pas versionnés (`.gitignore`).

## Après avoir déposé des images

- Vérifier le poids : `du -sh static/avent2026/img`.
- `python manage.py collectstatic` au déploiement, puis Reload (voir `CLAUDE.md`).
