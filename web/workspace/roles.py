"""Team roles.

Since 10 Oct 2026 there is one working role, engineer (plus admin = superuser).
The former student (Hanut) and mentor (Sweksha) roles and accounts were removed at the
project lead's request; their pages (spot checks, model outputs, reason wording,
checklist) are done by the engineer or admin. STUDENT and MENTOR are kept as names
for the same role so older code paths keep working.
"""

from __future__ import annotations

from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect

ENGINEER = "engineer"
STUDENT = MENTOR = ENGINEER          # former roles, now the engineer's
ROLES = (ENGINEER,)
LABELS = {ENGINEER: "Engineer"}


def roles_of(user) -> set[str]:
    if not user.is_authenticated:
        return set()
    if user.is_superuser:
        return set(ROLES)
    return set(user.groups.values_list("name", flat=True)) & set(ROLES)


def primary_role(user) -> str:
    if user.is_superuser:
        return "Admin"
    r = roles_of(user)
    return next((LABELS[x] for x in ROLES if x in r), "Viewer")


def has_role(user, *roles) -> bool:
    return bool(roles_of(user) & set(roles))


def require_role(*roles):
    def deco(view):
        @login_required
        @wraps(view)
        def inner(request, *a, **kw):
            if not has_role(request.user, *roles):
                need = " or ".join(sorted({LABELS[r] for r in roles}))
                messages.error(request, f"Only the {need} role can do that.")
                return redirect(request.META.get("HTTP_REFERER") or "dashboard")
            return view(request, *a, **kw)
        return inner
    return deco


def context(request):
    u = request.user
    r = roles_of(u)
    return {
        "role_label": primary_role(u) if u.is_authenticated else "",
        "is_student": STUDENT in r, "is_engineer": ENGINEER in r, "is_mentor": MENTOR in r,
    }
