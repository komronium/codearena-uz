from django.contrib import admin

from .models import Contest, ContestProblem, Participation


class ContestProblemInline(admin.TabularInline):
    model = ContestProblem
    extra = 1


@admin.register(Contest)
class ContestAdmin(admin.ModelAdmin):
    list_display = ("title", "start", "end", "type", "is_rated", "rating_applied")
    inlines = [ContestProblemInline]


@admin.register(Participation)
class ParticipationAdmin(admin.ModelAdmin):
    list_display = ("user", "contest", "score", "penalty", "rank", "rating_before", "rating_after")
    list_filter = ("contest",)
