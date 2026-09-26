from .models import ReviewComment


def unread_reviews(request):
    """Review comments others left on your submissions that you haven't opened yet."""
    if not request.user.is_authenticated:
        return {"unread_reviews": 0}
    n = (ReviewComment.objects.filter(submission__user=request.user, read=False)
         .exclude(author=request.user).count())
    return {"unread_reviews": n}
