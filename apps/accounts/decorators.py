from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied


def setter_required(view):
    """Staff and the trusted writers (User.is_setter): the problem editor. Guests go to the login page, anybody else
    signed in gets a 403."""
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        user = request.user
        if not user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        if not (user.is_active and (user.is_staff or user.is_setter)):
            raise PermissionDenied
        return view(request, *args, **kwargs)
    return wrapper


def staff_required(view):
    """The site has no Django admin; staff pages use this instead of staff_member_required
    (which would redirect to the removed admin login). Guests go to LOGIN_URL; a signed-in user
    who isn't staff gets 403, since a login form would only puzzle someone already signed in."""
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        user = request.user
        if not user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        if not (user.is_active and user.is_staff):
            raise PermissionDenied
        return view(request, *args, **kwargs)
    return wrapper
