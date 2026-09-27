"""One call per staff action that changes a result; see AuditEntry."""
from .models import AuditEntry

Action = AuditEntry.Action


def record(request, action: str, contest=None, subject=None, note: str = "") -> None:
    AuditEntry.objects.create(actor=request.user, action=action, contest=contest, subject=subject,
                              note=note[:300])
