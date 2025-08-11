from django.urls import path
from . import views

app_name = 'biblio'

urlpatterns = [
    path('', views.index, name='index'),
    path('livres/', views.book_list, name='book_list'),
    path('livre/<int:pk>/', views.book_detail, name='book_detail'),
    path('ajouter-isbn/', views.add_book_isbn, name='add_book_isbn'),
    path('scanner/', views.scan_barcode, name='scan_barcode'),
    path('ajouter-manuel/', views.add_book_manual, name='add_book_manual'),
    path('ajouter-manuel/<str:isbn>/', views.add_book_manual, name='add_book_manual_isbn'),
    path('modifier/<int:pk>/', views.edit_book, name='edit_book'),
    path('supprimer/<int:pk>/', views.delete_book, name='delete_book'),
]
