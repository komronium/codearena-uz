import secrets

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    class Role(models.TextChoices):
        STUDENT = "student"
        TEACHER = "teacher"
        ADMIN = "admin"

    rating = models.IntegerField(default=1200, db_index=True)
    practice_points = models.IntegerField(default=0, db_index=True)
    duel_rating = models.IntegerField(default=1200)  # 1v1 duels only (apps.classroom.duels)
    # From supervised contests only (apps.contests.rating.recalc_official); None until the first one.
    official_rating = models.IntegerField(null=True, blank=True, db_index=True)
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.STUDENT)
    avatar = models.ImageField(upload_to="avatars/", blank=True, null=True)
    location = models.CharField(max_length=100, blank=True)
    school = models.CharField(max_length=150, blank=True)
    invited_by = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="invited_users",
    )
    # "I'm a teacher" at sign-up or from the profile; staff approve it by giving the teacher role
    teacher_requested = models.BooleanField(default=False, db_index=True)
    # the tier the user was last shown; a higher one on the next page view gets a congratulation
    seen_tier = models.CharField(max_length=30, blank=True)
    # when the user promised to submit only their own work (accounts:honor); asked once
    honor_pledged_at = models.DateTimeField(null=True, blank=True)
    # A teacher or admin confirmed this is the real student; only verified users get an official rating
    verified_at = models.DateTimeField(null=True, blank=True)
    verified_by = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="verified_users",
    )
    verified_note = models.CharField(max_length=200, blank=True)


_CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"


def new_join_code() -> str:
    while True:
        code = "".join(secrets.choice(_CODE_ALPHABET) for _ in range(6))
        if not Group.objects.filter(join_code=code).exists():
            return code


class Group(models.Model):
    name = models.CharField(max_length=100)
    teacher = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="taught_groups")
    members = models.ManyToManyField(settings.AUTH_USER_MODEL, blank=True, related_name="student_groups")
    # students join with this code; no ambiguous letters (0/O, 1/I/L) so it reads out loud in class
    join_code = models.CharField(max_length=8, unique=True, null=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.join_code:
            self.join_code = new_join_code()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name
