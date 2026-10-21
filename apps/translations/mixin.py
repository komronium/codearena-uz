"""Content that reads in the page language. A model that lists its fields in `TRANSLATABLE` (the short ones, shown in lists,
in `SHORT`) and has a `source_lang` returns the confirmed translation of a field instead of the stored text, but only while a
template is being rendered: forms, views, saves and JSON built in Python keep seeing the author's own text, so an edit can
never write a translation over the original. With no confirmed translation the author's text is shown (see `pending`)."""
import threading

from django.core.cache import cache
from django.db.models.signals import post_delete, post_save
from django.utils.translation import get_language

_state = threading.local()
TTL = 120


def rendering() -> bool:
    return getattr(_state, "depth", 0) > 0


def install():
    """Mark the span of every template render (Template.render: the test runner swaps _render for its own, so that one is
    not safe to patch), and keep the short-text cache fresh."""
    from django.template.base import Template

    if getattr(Template.render, "_translations", False):
        return
    original = Template.render

    def render(self, context):
        _state.depth = getattr(_state, "depth", 0) + 1
        try:
            return original(self, context)
        finally:
            _state.depth -= 1

    render._translations = True
    Template.render = render
    from .models import ContentTranslation
    post_save.connect(_drop_cache, sender=ContentTranslation, dispatch_uid="translations-cache-save")
    post_delete.connect(_drop_cache, sender=ContentTranslation, dispatch_uid="translations-cache-delete")


def _key(ct_id: int, lang: str) -> str:
    return f"ct-short:{ct_id}:{lang}"


def _drop_cache(sender, instance, **kwargs):
    cache.delete(_key(instance.content_type_id, instance.lang))


def _short(model, lang: str) -> dict:
    """{object_id: {field: text}} of the confirmed short texts of a model in a language, cached."""
    from django.contrib.contenttypes.models import ContentType

    from .models import ContentTranslation
    ct = ContentType.objects.get_for_model(model)
    data = cache.get(_key(ct.pk, lang))
    if data is None:
        data = {}
        rows = ContentTranslation.objects.filter(content_type=ct, lang=lang, confirmed=True, field__in=model.SHORT).exclude(text="")
        for oid, field, text in rows.values_list("object_id", "field", "text"):
            data.setdefault(oid, {})[field] = text
        cache.set(_key(ct.pk, lang), data, TTL)
    return data


def confirmed_text(obj, name: str, lang: str):
    """The confirmed translation of one field in `lang`, or None."""
    model = type(obj)
    if name in model.SHORT:
        return _short(model, lang).get(obj.pk, {}).get(name)
    from django.contrib.contenttypes.models import ContentType

    from .models import ContentTranslation
    memo = obj.__dict__.setdefault("_tr_long", {})
    if lang not in memo:
        ct = ContentType.objects.get_for_model(model)
        memo[lang] = dict(ContentTranslation.objects.filter(content_type=ct, object_id=obj.pk, lang=lang, confirmed=True)
                          .exclude(text="").values_list("field", "text"))
    return memo[lang].get(name)


class Translatable:
    TRANSLATABLE: tuple = ()
    SHORT: tuple = ()  # the ones lists show: one cached query per model and language instead of one per row

    def __getattribute__(self, name):
        value = object.__getattribute__(self, name)
        if name in type(self).TRANSLATABLE and _state.__dict__.get("depth", 0) > 0 and value:
            lang = get_language()
            if lang and lang != object.__getattribute__(self, "source_lang") and object.__getattribute__(self, "pk"):
                return confirmed_text(self, name, lang) or value
        return value

    def pending(self) -> bool:
        """True when the page language isn't the original one and nothing confirmed exists for the main text yet."""
        lang = get_language()
        if not lang or lang == self.source_lang:
            return False
        main = type(self).TRANSLATABLE[0] if "statement_md" not in type(self).TRANSLATABLE else "statement_md"
        _state.depth = getattr(_state, "depth", 0)  # the lookup is explicit here, whatever the render state
        return not confirmed_text(self, main, lang)


def localized(obj, name: str):
    """The text of a field in the page language, wherever it is asked for (a view building HTML, not only a template): the
    confirmed translation when the page isn't in the author's language, else the author's own text."""
    value = object.__getattribute__(obj, name)
    lang = get_language()
    if value and lang and lang != obj.source_lang and obj.pk:
        return confirmed_text(obj, name, lang) or value
    return value
