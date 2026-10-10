"""Delete the former student (hanut) and mentor (sweksha) accounts and their role groups.

    python manage.py remove_former_members

Their contribution-log entries are kept (with the person's name) as part of the record.
Safe to run more than once.
"""

from django.contrib.auth.models import Group, User
from django.core.management.base import BaseCommand

FORMER = ("hanut", "sweksha")
FORMER_GROUPS = ("student", "mentor")


class Command(BaseCommand):
    help = "Remove the hanut and sweksha accounts and the student/mentor groups."

    def handle(self, *a, **o):
        from workspace.models import ContributionEntry
        # keep their notebook entries: detach them from the user rows before deleting
        field = ContributionEntry._meta.get_field("user")
        if field.null:
            ContributionEntry.objects.filter(user__username__in=FORMER).update(user=None)
        n_users = User.objects.filter(username__in=FORMER).count()
        if not field.null and ContributionEntry.objects.filter(user__username__in=FORMER).exists():
            admin = User.objects.filter(is_superuser=True).order_by("id").first()
            ContributionEntry.objects.filter(user__username__in=FORMER).update(user=admin)
        User.objects.filter(username__in=FORMER).delete()
        n_groups = Group.objects.filter(name__in=FORMER_GROUPS).count()
        Group.objects.filter(name__in=FORMER_GROUPS).delete()
        self.stdout.write(f"Removed {n_users} account(s) and {n_groups} group(s). Contribution-log entries kept.")
