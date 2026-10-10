from django.conf import settings
from django.db import models


class PipelineRun(models.Model):
    STEPS = [("extract", "Extract raw data"), ("crosswalk", "Build crosswalk"), ("panel", "Build panel"),
             ("extract_rasters", "Extract rainfall and night lights"), ("demo", "Rebuild map")]
    step = models.CharField(max_length=32, choices=STEPS)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    started = models.DateTimeField(auto_now_add=True)
    seconds = models.FloatField(default=0)
    ok = models.BooleanField(default=False)
    log = models.TextField(blank=True)

    class Meta:
        ordering = ["-started"]


class ChecklistItem(models.Model):
    """IRIS submission checklist (from the sprint plan)."""
    order = models.PositiveSmallIntegerField(default=0)
    text = models.CharField(max_length=300)
    owner = models.CharField(max_length=40, blank=True)
    done = models.BooleanField(default=False)
    done_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    done_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["order", "id"]


class ContributionEntry(models.Model):
    """Dated lab notebook for the ISEF forms. Some entries are added automatically."""
    date = models.DateField()
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    person = models.CharField(max_length=80)
    role = models.CharField(max_length=40)
    text = models.TextField()
    automatic = models.BooleanField(default=False)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "-created"]
