from django.contrib import admin

from .models import ChecklistItem, ContributionEntry, PipelineRun


@admin.register(PipelineRun)
class PipelineRunAdmin(admin.ModelAdmin):
    list_display = ("started", "step", "user", "ok", "seconds")
    list_filter = ("step", "ok")


@admin.register(ChecklistItem)
class ChecklistAdmin(admin.ModelAdmin):
    list_display = ("order", "text", "owner", "done", "done_by", "done_at")


@admin.register(ContributionEntry)
class ContributionAdmin(admin.ModelAdmin):
    list_display = ("date", "person", "role", "text", "automatic")
    list_filter = ("role", "automatic")
