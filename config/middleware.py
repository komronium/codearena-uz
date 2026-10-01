import ipaddress


def _from_local_proxy(addr: str) -> bool:
    try:
        ip = ipaddress.ip_address(addr)
    except ValueError:
        return False
    return ip.is_private or ip.is_loopback


def real_client_ip(get_response):
    """Behind nginx, REMOTE_ADDR is the Docker gateway; the client's address is the last
    X-Forwarded-For entry (the one nginx itself added). Contest IP locks and integrity logs
    read REMOTE_ADDR, so it is fixed here once. The header is trusted only when the request
    came from a private/loopback peer (the local proxy): a client reaching the app port
    directly arrives with its public address and cannot spoof it. Keep the app port bound to
    127.0.0.1 as well."""
    def middleware(request):
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
        if forwarded and _from_local_proxy(request.META.get("REMOTE_ADDR", "")):
            request.META["REMOTE_ADDR"] = forwarded.rsplit(",", 1)[-1].strip()
        return get_response(request)
    return middleware
