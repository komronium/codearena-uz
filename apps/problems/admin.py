from django.contrib import admin

from .models import Language, Problem, Tag, TestCase


class TestCaseInline(admin.TabularInline):
    model = TestCase
    extra = 2


@admin.register(Problem)
class ProblemAdmin(admin.ModelAdmin):
    list_display = ("title", "slug", "difficulty", "points", "is_public", "status", "author")
    list_filter = ("status", "is_public", "difficulty")
    prepopulated_fields = {"slug": ("title",)}
    inlines = [TestCaseInline]

    def save_model(self, request, obj, form, change):
        if not obj.author_id:
            obj.author = request.user
        super().save_model(request, obj, form, change)


admin.site.register(Tag)
admin.site.register(Language)
