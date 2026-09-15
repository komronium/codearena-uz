import pytest
from django.urls import reverse

from .models import User


@pytest.mark.django_db
def test_register_creates_user_and_logs_in(client):
    r = client.post(reverse("register"), {
        "username": "ali", "password1": "StrongPass123!", "password2": "StrongPass123!",
    })
    assert r.status_code == 302
    u = User.objects.get(username="ali")
    assert u.rating == 1500 and u.practice_points == 0 and u.role == "student"
    assert client.session["_auth_user_id"] == str(u.pk)


@pytest.mark.django_db
def test_login_page_renders(client):
    assert client.get(reverse("login")).status_code == 200
