"""Create the role groups, the team accounts and the IRIS checklist.

    python manage.py setup_team

Prints a fresh random password for each new account once. Existing accounts
are left alone unless --reset-passwords is given.
"""

import json
import secrets
from pathlib import Path

from django.contrib.auth.models import Group, User
from django.core.management.base import BaseCommand

from workspace.models import ChecklistItem
from workspace.roles import ENGINEER, ROLES

TEAM = [
    ("admin", "Admin", "", None, True),
    ("engineer", "Engineer", "", ENGINEER, False),
]

CHECKLIST = [
    ("IRIS registration done and ₹5,000 fee paid", "Sweksha"),
    ("Category confirmed (Behavioral & Social Sciences)", "Sweksha"),
    ("Synopsis: problem, gap, method, headline number, impact, within the IRIS word limit", "Hanut"),
    ("Full research paper with pre-registration link, limitations, and future work (Parts 3–4)", "Hanut"),
    ("90-second video: gap 15 s, method 30 s, result 25 s, demo 20 s", "Hanut"),
    ("ISEF forms: 1, 1A, research plan, 1B, plus 2 if Prof. Viswanath agrees", "Sweksha"),
    ("Written confirmation that no human-subjects form is needed", "Sweksha"),
    ("Code and data archived with a DOI, and linked in the paper", "Engineer"),
    ("Contribution log matching the forms", "Sweksha"),
]


def _password() -> str:
    return "-".join(secrets.token_urlsafe(4) for _ in range(3))


class Command(BaseCommand):
    help = "Create role groups, team accounts and the IRIS checklist."

    def add_arguments(self, p):
        p.add_argument("--reset-passwords", action="store_true")
        p.add_argument("--apply-preset", action="store_true",
                       help="Set existing accounts to the passwords in web/.initial_passwords.json")

    def handle(self, *a, **o):
        preset_file = Path(__file__).resolve().parents[3] / ".initial_passwords.json"
        preset = json.loads(preset_file.read_text()) if preset_file.exists() else {}
        for r in ROLES:
            Group.objects.get_or_create(name=r)
        rows = []
        for username, first, last, role, superuser in TEAM:
            u, created = User.objects.get_or_create(username=username, defaults={"first_name": first, "last_name": last})
            if o["apply_preset"] and not created and preset.get(username):
                u.set_password(preset[username])
                rows.append((username, preset[username], role or "admin"))
            elif created or o["reset_passwords"]:
                pw = preset.get(username) if created and preset.get(username) else _password()
                u.set_password(pw)
                rows.append((username, pw, role or "admin"))
            u.is_superuser = u.is_staff = superuser
            u.save()
            if role:
                u.groups.add(Group.objects.get(name=role))
        if not ChecklistItem.objects.exists():
            for i, (text, owner) in enumerate(CHECKLIST):
                ChecklistItem.objects.create(order=i, text=text, owner=owner)
        if rows:
            self.stdout.write("\nNew logins (shown once; each person should change theirs with 'Change password'):\n")
            for username, pw, role in rows:
                self.stdout.write(f"  {username:<10} {pw:<20} {role}")
            self.stdout.write("")
        else:
            self.stdout.write("Team already set up. Use --reset-passwords to issue new passwords.")
