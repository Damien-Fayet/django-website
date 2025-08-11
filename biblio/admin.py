from django.contrib import admin
from .models import Book

@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = ('title', 'authors', 'publisher', 'published_date', 'rating', 'themes', 'added_date')
    list_filter = ('rating', 'published_date', 'added_date', 'age_range')
    search_fields = ('title', 'authors', 'isbn', 'publisher', 'themes')
    readonly_fields = ('added_date', 'updated_date', 'google_books_id')
    
    fieldsets = (
        ('Informations principales', {
            'fields': ('isbn', 'title', 'authors', 'publisher', 'published_date')
        }),
        ('Description', {
            'fields': ('description', 'page_count', 'cover_image_url')
        }),
        ('Informations pédagogiques', {
            'fields': ('age_range', 'reading_level', 'themes', 'rating', 'comments')
        }),
        ('Métadonnées', {
            'fields': ('google_books_id', 'added_date', 'updated_date'),
            'classes': ('collapse',)
        }),
    )
