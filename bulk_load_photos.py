#!/usr/bin/env python
"""
Script de chargement en masse de photos pour Max Challenge
Usage: python bulk_load_photos.py <chemin_vers_dossier_photos>

Le script:
- Lit toutes les images JPG/JPEG/PNG d'un dossier
- Extrait le nom depuis le nom de fichier (sans extension)
- Crée les objets Photo avec redimensionnement automatique
- Gère les doublons et erreurs
"""

import os
import sys
import django
from pathlib import Path

# Configuration Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mysite.settings')
django.setup()

from max_challenge.models import Photo
from django.core.files import File
from django.db import IntegrityError


def bulk_load_photos(directory_path):
    """Charge toutes les photos d'un dossier"""
    
    directory = Path(directory_path)
    
    if not directory.exists():
        print(f"❌ Le dossier {directory_path} n'existe pas")
        return
    
    if not directory.is_dir():
        print(f"❌ {directory_path} n'est pas un dossier")
        return
    
    # Extensions supportées
    extensions = ('.jpg', '.jpeg', '.png', '.JPG', '.JPEG', '.PNG')
    
    # Trouver toutes les images
    image_files = [f for f in directory.iterdir() if f.suffix in extensions]
    
    if not image_files:
        print(f"⚠️  Aucune image trouvée dans {directory_path}")
        return
    
    print(f"📁 {len(image_files)} images trouvées dans {directory_path}")
    print(f"🚀 Début du chargement...\n")
    
    success_count = 0
    skip_count = 0
    error_count = 0
    
    for image_file in sorted(image_files):
        # Extraire le nom (sans extension)
        name = image_file.stem
        
        try:
            # Vérifier si la photo existe déjà
            if Photo.objects.filter(name=name).exists():
                print(f"⏭️  {name}: déjà existante, ignorée")
                skip_count += 1
                continue
            
            # Créer la photo
            photo = Photo(name=name)
            
            # Ouvrir et attacher le fichier
            with open(image_file, 'rb') as f:
                photo.image.save(image_file.name, File(f), save=True)
            
            print(f"✅ {name}: chargée et redimensionnée")
            success_count += 1
            
        except IntegrityError as e:
            print(f"⚠️  {name}: doublon détecté - {e}")
            skip_count += 1
            
        except Exception as e:
            print(f"❌ {name}: erreur - {e}")
            error_count += 1
    
    # Résumé
    print(f"\n{'='*60}")
    print(f"📊 RÉSUMÉ DU CHARGEMENT")
    print(f"{'='*60}")
    print(f"✅ Succès:  {success_count} photos")
    print(f"⏭️  Ignorées: {skip_count} photos (déjà existantes)")
    print(f"❌ Erreurs:  {error_count} photos")
    print(f"📁 Total:    {len(image_files)} fichiers traités")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python bulk_load_photos.py <chemin_vers_dossier_photos>")
        print("\nExemple:")
        print("  python bulk_load_photos.py /Users/damien/Photos/max_challenge")
        sys.exit(1)
    
    directory_path = sys.argv[1]
    bulk_load_photos(directory_path)
