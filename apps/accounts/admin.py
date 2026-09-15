from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (("CodeArena", {"fields": ("rating", "practice_points", "role")}),)
    list_display = ("username", "email", "role", "rating", "practice_points")
