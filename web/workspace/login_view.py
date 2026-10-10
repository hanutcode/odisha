"""Sign-in page that also lists the starting team logins.

The list appears only while all three are true:
  * DEBUG is on (local use, not a server),
  * the browser is on this same computer (127.0.0.1 / ::1),
  * web/.initial_passwords.json still exists.
Delete that file once everyone has changed their password and the list disappears.
"""

import json
from pathlib import Path

from django.conf import settings
from django.contrib.auth import views as auth_views

from .management.commands.setup_team import TEAM

PRESET = Path(settings.BASE_DIR) / ".initial_passwords.json"
LOCAL = {"127.0.0.1", "::1"}
ROLE_LABEL = {None: "Admin", "student": "Student", "engineer": "Engineer", "mentor": "Mentor"}


def demo_logins(request) -> list[dict]:
    if not settings.DEBUG or request.META.get("REMOTE_ADDR") not in LOCAL or not PRESET.exists():
        return []
    try:
        pw = json.loads(PRESET.read_text())
    except (OSError, ValueError):
        return []
    return [{"username": u, "password": pw[u], "role": ROLE_LABEL.get(role, role)}
            for u, _f, _l, role, _s in TEAM if pw.get(u)]


class TeamLoginView(auth_views.LoginView):
    template_name = "workspace/login.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["demo_logins"] = demo_logins(self.request)
        return ctx
