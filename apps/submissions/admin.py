from django.contrib import admin

from .models import Submission, UserProblemSolved


@admin.register(Submission)
class SubmissionAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "problem", "language", "verdict", "passed", "total", "created")
    list_filter = ("verdict", "language")
    readonly_fields = ("source", "compile_log")


admin.site.register(UserProblemSolved)
