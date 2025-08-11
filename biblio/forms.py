from django import forms
from .models import Book
import requests
import json

class ISBNSearchForm(forms.Form):
    isbn = forms.CharField(
        max_length=13,
        label="Code ISBN",
        help_text="Entrez le code ISBN (10 ou 13 chiffres)",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '978-2-1234-5678-9'
        })
    )

class BookForm(forms.ModelForm):
    class Meta:
        model = Book
        fields = [
            'isbn', 'title', 'authors', 'publisher', 'published_date',
            'description', 'page_count', 'age_range', 'reading_level', 'themes',
            'comments', 'rating', 'cover_image_url'
        ]
        widgets = {
            'isbn': forms.TextInput(attrs={'class': 'form-control'}),
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'authors': forms.TextInput(attrs={'class': 'form-control'}),
            'publisher': forms.TextInput(attrs={'class': 'form-control'}),
            'published_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'page_count': forms.NumberInput(attrs={'class': 'form-control'}),
            'age_range': forms.TextInput(attrs={'class': 'form-control'}),
            'reading_level': forms.TextInput(attrs={'class': 'form-control'}),
            'themes': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: aventure, amitié, nature'}),
            'comments': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'rating': forms.Select(attrs={'class': 'form-control'}),
            'cover_image_url': forms.URLInput(attrs={'class': 'form-control'}),
        }

class BookFilterForm(forms.Form):
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Rechercher par titre, auteur...'
        })
    )
    rating = forms.ChoiceField(
        choices=[('', 'Toutes les notes')] + [(i, f'{i} étoiles') for i in range(1, 6)],
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    themes = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Thème(s)'
        })
    )
    age_range = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Tranche d\'âge'
        })
    )

def search_book_by_isbn(isbn):
    """
    Recherche un livre via l'API Google Books en utilisant l'ISBN
    """
    url = f"https://www.googleapis.com/books/v1/volumes?q=isbn:{isbn}"
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        
        if data.get('totalItems', 0) > 0:
            book_info = data['items'][0]['volumeInfo']
            
            # Extraction des données
            authors = ', '.join(book_info.get('authors', []))
            published_date = book_info.get('publishedDate', '')
            
            # Conversion de la date si possible
            try:
                if len(published_date) == 4:  # Année seulement
                    published_date = f"{published_date}-01-01"
                elif len(published_date) == 7:  # Année-mois
                    published_date = f"{published_date}-01"
            except Exception:
                published_date = None
            
            # Récupération de l'URL de l'image
            cover_url = ""
            if 'imageLinks' in book_info:
                cover_url = book_info['imageLinks'].get('thumbnail', '')
            
            return {
                'title': book_info.get('title', ''),
                'authors': authors,
                'publisher': book_info.get('publisher', ''),
                'published_date': published_date,
                'description': book_info.get('description', ''),
                'page_count': book_info.get('pageCount'),
                'cover_image_url': cover_url,
                'google_books_id': data['items'][0].get('id', ''),
            }
            
    except Exception as e:
        print(f"Erreur lors de la recherche ISBN: {e}")
    
    return None
