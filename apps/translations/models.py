"""The other-language text of content that lives in the database (problems, hints, courses, contests). The author writes
a piece in ONE language (its `source_lang`); the other language is added later, by an admin or by the AI, and stays
closed to readers until an admin confirms it."""
from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _tl

LANGS = [("uz", _tl("O‘zbekcha")), ("en", "English")]


class ContentTranslation(models.Model):
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, related_name="+")
    object_id = models.PositiveIntegerField()
    obj = GenericForeignKey("content_type", "object_id")
    lang = models.CharField(max_length=2)  # the language of `text` (never the object's source language)
    field = models.CharField(max_length=40)
    text = models.TextField(blank=True)
    confirmed = models.BooleanField(default=False)  # only confirmed text is shown to readers
    by_ai = models.BooleanField(default=False)  # a draft the AI wrote (an admin may have edited it since)
    updated = models.DateTimeField(auto_now=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["content_type", "object_id", "lang", "field"], name="one_translation_per_field")]
        indexes = [models.Index(fields=["content_type", "lang", "confirmed"])]

    def __str__(self):
        return f"{self.content_type.model}#{self.object_id} {self.lang}.{self.field}"

    def confirm(self, user):
        self.confirmed, self.reviewed_by, self.reviewed_at = True, user, timezone.now()
        self.save(update_fields=["confirmed", "reviewed_by", "reviewed_at", "updated"])
