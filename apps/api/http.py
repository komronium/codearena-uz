"""What every API response shares: JSON in UTF-8, readable from any origin, cacheable for a short while, and a request
limit per address (the API is public and its standings are the costly part)."""
import functools

from django.http import Http404, JsonResponse
from django.views.decorators.http import require_GET

from apps.accounts import throttle

RATE_MAX, RATE_WINDOW = 120, 60  # requests per address per minute
CACHE_SECONDS = 30
MAX_PAGE_SIZE = 200


def respond(data, status=200, cache_seconds=CACHE_SECONDS):
    response = JsonResponse(data, status=status, json_dumps_params={"ensure_ascii": False}, safe=isinstance(data, dict))
    response["Access-Control-Allow-Origin"] = "*"
    response["Cache-Control"] = f"public, max-age={cache_seconds}" if cache_seconds and status == 200 else "no-store"
    return response


def error(status, message):
    return respond({"status": "error", "error": message}, status=status, cache_seconds=0)


def api(view):
    """A GET-only, rate-limited JSON endpoint."""
    @require_GET
    @functools.wraps(view)
    def wrapped(request, *args, **kwargs):
        if throttle.ip_blocked(request, "api", RATE_MAX, RATE_WINDOW):
            response = error(429, "too many requests")
            response["Retry-After"] = str(RATE_WINDOW)
            return response
        try:
            return view(request, *args, **kwargs)
        except Http404:
            return error(404, "not found")
    return wrapped


def page_of(request, queryset_or_list, serialize, default_size=50):
    """One page of a list as {"page", "pagesCount", "count", "pageSize", "data"}: the shape clist's other judges
    (samcoding.uz) already use, so a parser reads it the same way. ?page and ?page_size narrow it."""
    from django.core.paginator import Paginator

    def number(name, default, maximum):
        value = request.GET.get(name, "")
        return min(max(int(value), 1), maximum) if value.isdigit() else default

    size = number("page_size", default_size, MAX_PAGE_SIZE)
    paginator = Paginator(queryset_or_list, size)
    wanted = number("page", 1, 10**9)
    # past the last page the page is empty (not the last one again), so a crawler stops at pagesCount
    items = paginator.page(wanted) if wanted <= paginator.num_pages else []
    return {"status": "ok", "page": wanted, "pagesCount": paginator.num_pages, "pageSize": size,
            "count": paginator.count, "data": [serialize(item) for item in items]}
