def real_client_ip(get_response):
    """Behind Caddy, REMOTE_ADDR is the Docker gateway; the client's address is the last
    X-Forwarded-For entry (the one Caddy itself added). Contest IP locks and integrity logs
    read REMOTE_ADDR, so it is fixed here once. Only safe while the app port is bound to
    127.0.0.1 — otherwise anyone could send the header directly."""
    def middleware(request):
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
        if forwarded:
            request.META["REMOTE_ADDR"] = forwarded.rsplit(",", 1)[-1].strip()
        return get_response(request)
    return middleware
