from django.contrib.auth.decorators import user_passes_test

# The site has no Django admin; staff pages use this instead of staff_member_required
# (which would redirect to the removed admin login). Anonymous users go to LOGIN_URL.
staff_required = user_passes_test(lambda u: u.is_active and u.is_staff)
