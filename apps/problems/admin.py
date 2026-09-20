from django.contrib import admin

from .models import Language, Problem, SQLDataset, Tag, TestCase


class TestCaseInline(admin.TabularInline):
    model = TestCase
    extra = 2


class SQLDatasetInline(admin.StackedInline):
    model = SQLDataset
    extra = 0
    max_num = 1


@admin.register(Problem)
class ProblemAdmin(admin.ModelAdmin):
    list_display = ("title", "slug", "kind", "difficulty", "points", "is_public", "status", "author")
    list_filter = ("kind", "status", "is_public", "difficulty")
    prepopulated_fields = {"slug": ("title",)}
    inlines = [TestCaseInline, SQLDatasetInline]

    def save_model(self, request, obj, form, change):
        if not obj.author_id:
            obj.author = request.user
        super().save_model(request, obj, form, change)


admin.site.register(Tag)
admin.site.register(Language)
