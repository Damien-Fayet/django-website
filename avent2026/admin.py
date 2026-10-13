from django.contrib import admin

from .models import Attempt, Hint, Puzzle, Submission


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
    list_display = ("user", "puzzle", "errors", "points", "rank", "first_seen_at", "solved_at")
    list_filter = ("puzzle__kind", "puzzle__day")
    raw_id_fields = ("user", "puzzle")


@admin.register(Submission)
class SubmissionAdmin(admin.ModelAdmin):
    """Journal des réponses en lecture seule ; la vue de synthèse est dans « Suivi » (/avent2026/suivi/)."""

    list_display = ("created_at", "user", "puzzle", "answer", "correct", "ip")
    list_filter = ("correct", "puzzle__kind", "puzzle__day")
    search_fields = ("user__username", "answer")
    date_hierarchy = "created_at"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
