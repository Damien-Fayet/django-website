#!/usr/bin/env python
"""
Script de test pour vérifier le redimensionnement des images
Crée une image de test et vérifie le bon fonctionnement
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
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
from django.core.files.base import ContentFile


def create_test_image(width, height, text):
    """Crée une image de test avec texte"""
    img = Image.new('RGB', (width, height), color='lightblue')
    draw = ImageDraw.Draw(img)
    
    # Texte au centre
    text_bbox = draw.textbbox((0, 0), text)
    text_width = text_bbox[2] - text_bbox[0]
    text_height = text_bbox[3] - text_bbox[1]
    
    position = ((width - text_width) // 2, (height - text_height) // 2)
    draw.text(position, text, fill='darkblue')
    
    return img


def test_resize_system():
    """Teste le système de redimensionnement"""
    
    print("🧪 Test du système de redimensionnement\n")
    
    # Test 1 : Image portrait 1000x1500
    print("📐 Test 1 : Image portrait 1000x1500 → attendu 400x600")
    img_portrait = create_test_image(1000, 1500, "PORTRAIT\n1000x1500")
    
    # Sauvegarder en tant que photo temporaire
    buffer = BytesIO()
    img_portrait.save(buffer, format='JPEG')
    buffer.seek(0)
    
    photo_portrait = Photo(name="test_portrait")
    photo_portrait.image.save("test_portrait.jpg", ContentFile(buffer.read()), save=True)
    
    # Vérifier les dimensions
    if photo_portrait.image_400x400:
        resized_img = Image.open(photo_portrait.image_400x400.path)
        width, height = resized_img.size
        
        if width == 400 and height == 600:
            print(f"✅ Portrait : {width}x{height} ✓\n")
        else:
            print(f"❌ Portrait : {width}x{height} (attendu 400x600)\n")
    else:
        print("❌ Image redimensionnée non générée\n")
    
    # Test 2 : Image carrée 800x800
    print("📐 Test 2 : Image carrée 800x800 → attendu 400x400")
    img_square = create_test_image(800, 800, "CARRÉ\n800x800")
    
    buffer = BytesIO()
    img_square.save(buffer, format='JPEG')
    buffer.seek(0)
    
    photo_square = Photo(name="test_carre")
    photo_square.image.save("test_carre.jpg", ContentFile(buffer.read()), save=True)
    
    # Vérifier les dimensions
    if photo_square.image_400x400:
        resized_img = Image.open(photo_square.image_400x400.path)
        width, height = resized_img.size
        
        if width == 400 and height == 400:
            print(f"✅ Carré : {width}x{height} ✓\n")
        else:
            print(f"❌ Carré : {width}x{height} (attendu 400x400)\n")
    else:
        print("❌ Image redimensionnée non générée\n")
    
    # Test 3 : Image paysage 1200x800
    print("📐 Test 3 : Image paysage 1200x800 → attendu 400x400 (crop carré)")
    img_landscape = create_test_image(1200, 800, "PAYSAGE\n1200x800")
    
    buffer = BytesIO()
    img_landscape.save(buffer, format='JPEG')
    buffer.seek(0)
    
    photo_landscape = Photo(name="test_paysage")
    photo_landscape.image.save("test_paysage.jpg", ContentFile(buffer.read()), save=True)
    
    # Vérifier les dimensions
    if photo_landscape.image_400x400:
        resized_img = Image.open(photo_landscape.image_400x400.path)
        width, height = resized_img.size
        
        if width == 400 and height == 400:
            print(f"✅ Paysage : {width}x{height} ✓\n")
        else:
            print(f"❌ Paysage : {width}x{height} (attendu 400x400)\n")
    else:
        print("❌ Image redimensionnée non générée\n")
    
    print("="*60)
    print("🗑️  Nettoyage des photos de test...")
    Photo.objects.filter(name__startswith="test_").delete()
    print("✅ Tests terminés et nettoyés\n")


if __name__ == "__main__":
    test_resize_system()
