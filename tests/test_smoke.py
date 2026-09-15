import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_root_redirects_to_problems(client):
    r = client.get("/")
    assert r.status_code == 302
    assert r.url == reverse("problems:list")
