import re
import pytest
from django.urls import reverse
from apps.accounts.models import User
from apps.problems.models import Problem
from apps.translations import service

@pytest.mark.django_db
def test_dbg(client):
    a = User.objects.create_user("a", password="x", is_staff=True)
    p = Problem.objects.create(slug="sum", title="Yig", statement_md="x", author=a, is_public=True, status="approved")
    service.save_draft(p, "title", "en", "Sum", by_ai=True)
    service.save_draft(p, "statement_md", "en", "Find the sum", by_ai=True)
    client.cookies["ca_lang"] = "en"
    t = client.get(reverse("problems:detail", args=["sum"])).content.decode()
    print("A", re.search(r"<title>(.*?)</title>", t, re.S).group(1).strip()[:60])
    service.confirm_all(p, a)
    t = client.get(reverse("problems:detail", args=["sum"])).content.decode()
    print("B", re.search(r"<title>(.*?)</title>", t, re.S).group(1).strip()[:60])
    t = client.get(reverse("problems:list")).content.decode()
    print("C", "Sum" in t, "Yig" in t)
