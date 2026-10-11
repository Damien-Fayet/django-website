from django.contrib import admin

from .models import Attempt, Hint, Puzzle


class HintInline(admin.TabularInline):
    model = Hint
    extra = 1


@admin.register(Puzzle)
class PuzzleAdmin(admin.ModelAdmin):
    list_display = ("day", "kind", "title")
    list_filter = ("kind", "day")
    inlines = [HintInline]


@admin.register(Attempt)
class AttemptAdmin(admin.ModelAdmin):
    list_display = ("user", "puzzle", "errors", "points", "solved_at")
    list_filter = ("puzzle__kind", "puzzle__day")
    raw_id_fields = ("user", "puzzle")
