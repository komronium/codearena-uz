from django.contrib import admin

from .models import FocusEvent, SimilarityFlag


@admin.register(FocusEvent)
class FocusEventAdmin(admin.ModelAdmin):
    list_display = ("user", "contest", "kind", "at")
    list_filter = ("contest", "kind")


@admin.register(SimilarityFlag)
class SimilarityFlagAdmin(admin.ModelAdmin):
    list_display = ("submission_a", "submission_b", "score", "reviewed")
    list_filter = ("reviewed",)
