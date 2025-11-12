from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.contrib import messages
from django.db.models import Q, Avg
from django.core.paginator import Paginator
from django.utils import timezone

from .models import Book
from .forms import ISBNSearchForm, BookForm, BookFilterForm, search_book_by_isbn

def index(request):
    """Page d'accueil améliorée avec plus de statistiques"""
    total_books = Book.objects.count()
    recent_books = Book.objects.order_by('-added_date')[:5]
    
    # Livres les mieux notés
    top_rated_books = Book.objects.filter(rating__gte=4).order_by('-rating', '-added_date')[:5]
    
    # Statistiques supplémentaires
    avg_rating = Book.objects.filter(rating__isnull=False).aggregate(avg=Avg('rating'))['avg'] or 0
    this_month = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    this_month_count = Book.objects.filter(added_date__gte=this_month).count()
    
    context = {
        'total_books': total_books,
        'recent_books': recent_books,
        'top_rated_books': top_rated_books,
        'avg_rating': avg_rating,
        'this_month_count': this_month_count,
    }
    return render(request, 'biblio/index.html', context)

def book_list(request):
    """Liste des livres avec filtres améliorés"""
    books = Book.objects.all()
    form = BookFilterForm(request.GET)
    
    # Tri
    sort = request.GET.get('sort', 'title')
    if sort == '-added_date':
        books = books.order_by('-added_date')
    elif sort == '-rating':
        books = books.order_by('-rating', 'title')
    elif sort == 'author':
        books = books.order_by('authors')
    else:
        books = books.order_by('title')
    
    if form.is_valid():
        search = form.cleaned_data.get('search')
        rating = form.cleaned_data.get('rating')
        themes = form.cleaned_data.get('themes')
        age_range = form.cleaned_data.get('age_range')
        
        if search:
            books = books.filter(
                Q(title__icontains=search) |
                Q(authors__icontains=search) |
                Q(description__icontains=search) |
                Q(isbn__icontains=search)
            )
        
        if rating:
            books = books.filter(rating=rating)
        
        if themes:
            books = books.filter(themes__icontains=themes)
        
        if age_range:
            books = books.filter(age_range__icontains=age_range)
    
    # Pagination améliorée
    paginator = Paginator(books, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'books': page_obj,
        'form': form,
        'total_count': books.count(),
        'sort': sort,
        'paginator': paginator,
    }
    return render(request, 'biblio/book_list.html', context)

def book_detail(request, pk):
    """Détails d'un livre avec navigation entre livres"""
    book = get_object_or_404(Book, pk=pk)
    
    # Navigation entre livres (basée sur l'ordre alphabétique par défaut)
    all_books = Book.objects.order_by('title')
    book_ids = list(all_books.values_list('pk', flat=True))
    
    try:
        current_index = book_ids.index(book.pk)
        previous_book = all_books[book_ids[current_index - 1]] if current_index > 0 else None
        next_book = all_books[book_ids[current_index + 1]] if current_index < len(book_ids) - 1 else None
        current_position = current_index + 1
        total_books = len(book_ids)
    except (ValueError, IndexError):
        previous_book = next_book = None
        current_position = 1
        total_books = all_books.count()
    
    context = {
        'book': book,
        'previous_book': previous_book,
        'next_book': next_book,
        'current_position': current_position,
        'total_books': total_books,
    }
    return render(request, 'biblio/book_detail.html', context)

def add_book_isbn(request):
    """Ajouter un livre via ISBN"""
    if request.method == 'POST':
        form = ISBNSearchForm(request.POST)
        
        if form.is_valid():
            isbn = form.cleaned_data['isbn'].replace('-', '').replace(' ', '')
            
            # Vérifier si le livre existe déjà
            if Book.objects.filter(isbn=isbn).exists():
                messages.error(request, 'Ce livre existe déjà dans la bibliothèque.')
                return render(request, 'biblio/add_book_isbn.html', {'form': form})
            
            # Rechercher via API Google Books
            book_data = search_book_by_isbn(isbn)
            
            if book_data:
                # Pré-remplir le formulaire avec les données trouvées
                book_data['isbn'] = isbn
                # Stocker les données en session pour les récupérer dans add_book_manual
                request.session['book_data_from_isbn'] = book_data
                return redirect('biblio:add_book_manual')
            else:
                messages.warning(request, 'Livre non trouvé via ISBN. Veuillez saisir les informations manuellement.')
                return redirect('biblio:add_book_manual_isbn', isbn=isbn)
        else:
            # Afficher les erreurs du formulaire
            messages.error(request, 'Veuillez corriger les erreurs dans le formulaire.')
    else:
        form = ISBNSearchForm()
    
    return render(request, 'biblio/add_book_isbn.html', {'form': form})

def scan_barcode(request):
    """Scanner un code-barres via webcam"""
    return render(request, 'biblio/scan_barcode.html')

def add_book_manual(request, isbn=None):
    """Ajouter un livre manuellement"""
    if request.method == 'POST':
        form = BookForm(request.POST)
        if form.is_valid():
            book = form.save()
            # Nettoyer les données de session si elles existent
            if 'book_data_from_isbn' in request.session:
                del request.session['book_data_from_isbn']
            messages.success(request, f'Le livre "{book.title}" a été ajouté avec succès.')
            return redirect('biblio:book_detail', pk=book.pk)
        else:
            # Ajouter un message d'erreur pour le débogage
            messages.error(request, 'Erreurs dans le formulaire. Veuillez vérifier les champs.')
    else:
        initial_data = {}
        from_isbn = False
        
        # Récupérer les données de la session si elles existent (venant de la recherche ISBN)
        if 'book_data_from_isbn' in request.session:
            initial_data = request.session['book_data_from_isbn']
            from_isbn = True
        elif isbn:
            initial_data['isbn'] = isbn
            
        form = BookForm(initial=initial_data)
    
    return render(request, 'biblio/add_book_manual.html', {
        'form': form, 
        'from_isbn': from_isbn if 'from_isbn' in locals() else False
    })

def edit_book(request, pk):
    """Modifier un livre"""
    book = get_object_or_404(Book, pk=pk)
    
    if request.method == 'POST':
        form = BookForm(request.POST, instance=book)
        if form.is_valid():
            book = form.save()
            messages.success(request, f'Le livre "{book.title}" a été modifié avec succès.')
            return redirect('biblio:book_detail', pk=book.pk)
    else:
        form = BookForm(instance=book)
    
    return render(request, 'biblio/edit_book.html', {'form': form, 'book': book})

def delete_book(request, pk):
    """Supprimer un livre"""
    book = get_object_or_404(Book, pk=pk)
    
    if request.method == 'POST':
        title = book.title
        book.delete()
        messages.success(request, f'Le livre "{title}" a été supprimé.')
        return redirect('biblio:book_list')
    
    return render(request, 'biblio/delete_book.html', {'book': book})

def ajax_search(request):
    """Recherche AJAX rapide"""
    query = request.GET.get('q', '').strip()
    
    if len(query) < 2:
        return JsonResponse({'books': []})
    
    books = Book.objects.filter(
        Q(title__icontains=query) |
        Q(authors__icontains=query) |
        Q(isbn__icontains=query)
    )[:10]  # Limite à 10 résultats pour la recherche rapide
    
    books_data = []
    for book in books:
        books_data.append({
            'id': book.pk,
            'title': book.title,
            'authors': book.authors,
            'cover_image_url': book.cover_image_url,
        })
    
    return JsonResponse({'books': books_data})
