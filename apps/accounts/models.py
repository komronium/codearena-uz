from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    class Role(models.TextChoices):
        STUDENT = "student"
        TEACHER = "teacher"
        ADMIN = "admin"

    rating = models.IntegerField(default=1500, db_index=True)
    practice_points = models.IntegerField(default=0, db_index=True)
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.STUDENT)


class Group(models.Model):
    name = models.CharField(max_length=100)
    teacher = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="taught_groups")
    members = models.ManyToManyField(settings.AUTH_USER_MODEL, blank=True, related_name="student_groups")

    def __str__(self):
        return self.name
