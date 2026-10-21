"""Admin pages for the other-language text of problems, courses and contests (apps.translations): what is missing, the AI
draft, editing side by side with the original, and confirming (only confirmed text is shown to readers)."""
from django.conf import settings
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.translation import gettext as _t
from django.views.decorators.http import require_POST

from apps.accounts.decorators import staff_required
from apps.translations import jobs, service
from apps.translations.models import LANGS
from django.utils.translation import gettext as _t

KIND_LABELS = {"problems": "Masalalar", "courses": "Kurslar", "contests": "Musobaqalar"}


def _kind(kind: str) -> str:
    if kind not in service.KINDS:
        raise Http404
    return kind


@staff_required
def index(request):
    kind = _kind(request.GET.get("kind", "problems"))
    model = service.model_of(kind)
    q = request.GET.get("q", "").strip()
    want = request.GET.get("status", "")
    qs = model.objects.all().order_by("-pk")
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(pk__in=[int(q)] if q.isdigit() else []))
    rows = []
    counts = {"none": 0, "draft": 0, "confirmed": 0}
    for obj in qs:
        st = service.status(obj)
        counts[st] += 1
        if not want or want == st:
            rows.append({"obj": obj, "status": st, "target": service.other(obj.source_lang)})
    page = Paginator(rows, 40).get_page(request.GET.get("page"))
    return render(request, "moderation/translations.html", {
        "kind": kind, "kinds": [(k, KIND_LABELS[k]) for k in service.KINDS], "page": page, "counts": counts,
        "q": q, "want": want, "langs": dict(LANGS)})


@staff_required
def edit(request, kind, pk):
    obj = get_object_or_404(service.model_of(_kind(kind)), pk=pk)
    target = service.other(obj.source_lang)
    us = service.units(obj)
    have = service.existing(obj, target)
    from django.contrib.contenttypes.models import ContentType
    rows = []
    for i, (row, field, text) in enumerate(us):
        ct = ContentType.objects.get_for_model(row)
        t = have.get((ct.pk, row.pk, field))
        rows.append({"i": i, "row": row, "field": field, "source": text, "text": t.text if t else "",
                     "confirmed": bool(t and t.confirmed), "by_ai": bool(t and t.by_ai),
                     "label": f"{type(row).__name__} · {field}", "long": len(text) > 120 or "\n" in text})
    if request.method == "POST":
        confirm = "confirm" in request.POST
        saved = 0
        for r in rows:
            value = request.POST.get(f"t{r['i']}", "").strip()
            if value != r["text"].strip() or (confirm and value and not r["confirmed"]):
                service.save_draft(r["row"], r["field"], target, value, by_ai=False, user=request.user,
                                   confirm=confirm and bool(value))
                saved += 1
        messages.success(request, _t("Tarjima tasdiqlandi.") if confirm else _t("Qoralama saqlandi."))
        return redirect("moderation:translation_edit", kind=kind, pk=pk)
    return render(request, "moderation/translation_edit.html", {
        "kind": kind, "obj": obj, "rows": rows, "target": dict(LANGS)[target], "source": dict(LANGS)[obj.source_lang],
        "status": service.status(obj)})


@staff_required
@require_POST
def ai_one(request, kind, pk):
    obj = get_object_or_404(service.model_of(_kind(kind)), pk=pk)
    if not _ai_ready():
        messages.error(request, _t("AI kaliti sozlanmagan (ANTHROPIC_API_KEY)."))
    else:
        jobs.enqueue_one(kind, obj.pk)
        messages.success(request, _t("AI tarjima qilmoqda: bir necha soniyadan keyin sahifani yangilang.") if settings.RQ_ASYNC
                         else _t("AI tarjimasi tayyor."))
    return redirect("moderation:translation_edit", kind=kind, pk=pk)


@staff_required
@require_POST
def ai_all(request, kind):
    if not _ai_ready():
        messages.error(request, _t("AI kaliti sozlanmagan (ANTHROPIC_API_KEY)."))
    else:
        n = jobs.enqueue_missing(_kind(kind))
        messages.success(request, _t("{n} ta tarjima navbatga qo‘yildi.").format(n=n))
    return redirect(f"{reverse('moderation:translations')}?kind={kind}")


@staff_required
@require_POST
def confirm_one(request, kind, pk):
    obj = get_object_or_404(service.model_of(_kind(kind)), pk=pk)
    n = service.confirm_all(obj, request.user)
    messages.success(request, _t("{n} ta matn tasdiqlandi.").format(n=n))
    return redirect(f"{reverse('moderation:translations')}?kind={kind}")


@staff_required
@require_POST
def confirm_all(request, kind):
    n = 0
    for obj in service.model_of(_kind(kind)).objects.all():
        if service.status(obj) == "draft":
            n += service.confirm_all(obj, request.user)
    messages.success(request, _t("{n} ta matn tasdiqlandi.").format(n=n))
    return redirect(f"{reverse('moderation:translations')}?kind={kind}")


def _ai_ready() -> bool:
    import os
    return bool(os.environ.get("ANTHROPIC_API_KEY") or getattr(settings, "ANTHROPIC_API_KEY", ""))
