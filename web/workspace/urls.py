from django.urls import path

from . import views as v

urlpatterns = [
    path("", v.dashboard, name="dashboard"),
    path("checklist/<int:pk>/", v.checklist_toggle, name="checklist_toggle"),
    path("data/", v.data, name="data"),
    path("data/<str:key>/upload/", v.upload, name="upload"),
    path("data/<str:key>/view/", v.manual_view, name="manual_view"),
    path("pipeline/", v.pipeline, name="pipeline"),
    path("pipeline/run/<str:step>/", v.pipeline_run, name="pipeline_run"),
    path("pipeline/<int:pk>/", v.pipeline_detail, name="pipeline_detail"),
    path("review/", v.review, name="review"),
    path("review/override/", v.override_add, name="override_add"),
    path("review/spot/", v.spot_save, name="spot_save"),
    path("panel/", v.panel, name="panel"),
    path("panel/panel_wide.csv", v.panel_csv, name="panel_csv"),
    path("map/", v.map_page, name="map"),
    path("map/embed/", v.map_embed, name="map_embed"),
    path("map/download/", v.map_download, name="map_download"),
    path("map/outputs/", v.outputs_upload, name="outputs_upload"),
    path("map/mock/", v.outputs_mock, name="outputs_mock"),
    path("map/reasons/", v.reasons_save, name="reasons_save"),
    path("fair/", v.insights_public, name="insights_public"),
    path("fair/map/", v.map_public, name="map_public"),
    path("fair/insights/", v.fair_insights_redirect),
    path("insights/", v.insights, name="insights"),
    path("log/", v.log, name="log"),
    path("log/export/", v.log_export, name="log_export"),
]
