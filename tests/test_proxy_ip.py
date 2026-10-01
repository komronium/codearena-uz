from django.http import HttpResponse
from django.test import RequestFactory

from config.middleware import real_client_ip


def _ip_seen(peer="172.18.0.1", **meta):
    seen = {}

    def view(request):
        seen["ip"] = request.META["REMOTE_ADDR"]
        return HttpResponse()

    real_client_ip(view)(RequestFactory().get("/", REMOTE_ADDR=peer, **meta))
    return seen["ip"]


def test_takes_client_ip_from_proxy_header():
    assert _ip_seen(HTTP_X_FORWARDED_FOR="10.5.1.23") == "10.5.1.23"


def test_uses_rightmost_entry_so_client_cannot_spoof_it():
    # Caddy puts the address it saw last; anything to the left came from the client.
    assert _ip_seen(HTTP_X_FORWARDED_FOR="1.2.3.4, 10.5.1.23") == "10.5.1.23"


def test_keeps_remote_addr_without_header():
    assert _ip_seen() == "172.18.0.1"


def test_ignores_the_header_from_a_public_peer():
    # someone hitting the app port directly: their own address stays, the header is ignored
    assert _ip_seen(peer="8.8.8.8", HTTP_X_FORWARDED_FOR="10.0.0.5") == "8.8.8.8"
