import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_root_is_the_home_page(client):
    assert client.get("/").status_code == 200


@pytest.mark.django_db
def test_phone_menu_reaches_every_page(client):
    """The sidebar is hidden on phones; the menu sheet must offer the same destinations."""
    from apps.accounts.models import User

    client.force_login(User.objects.create_user("ali", password="x"))
    page = client.get(reverse("problems:list")).content.decode()
    sheet = page[page.index('id="ca-menu"'):]
    for name in ("classroom:list", "classroom:duels", "top", "rating", "submissions:mine"):
        assert f'href="{reverse(name)}"' in sheet, name
    assert reverse("moderation:dashboard") not in sheet

    client.force_login(User.objects.create_user("boss", password="x", is_staff=True))
    sheet = client.get(reverse("problems:list")).content.decode().split('id="ca-menu"', 1)[1]
    assert reverse("moderation:dashboard") in sheet and reverse("integrity:audit") in sheet
