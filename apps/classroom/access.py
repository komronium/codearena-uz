from apps.accounts.models import Group


def teaches(user, student_id: int) -> bool:
    """True when `user` is the teacher of a group `student_id` belongs to."""
    return user.is_authenticated and Group.objects.filter(teacher=user, members=student_id).exists()


def can_review(user, submission) -> bool:
    return user.is_authenticated and (
        submission.user_id == user.pk or user.is_staff or teaches(user, submission.user_id))
