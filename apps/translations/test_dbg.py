import pytest
from apps.accounts.models import User
from apps.problems.models import Problem
from apps.translations import service, mixin
from django.core.cache import cache

@pytest.mark.django_db
def test_dbg():
    a = User.objects.create_user("a", password="x", is_staff=True)
    p = Problem.objects.create(slug="s", title="Yig", statement_md="x", author=a, is_public=True, status="approved")
    service.save_draft(p, "title", "en", "Sum", by_ai=True)
    print("first", mixin._short(Problem, "en"))
    service.confirm_all(p, a)
    from apps.translations.models import ContentTranslation
    print("rows", list(ContentTranslation.objects.values("field", "confirmed", "lang")))
    print("second", mixin._short(Problem, "en"))
