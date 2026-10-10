from __future__ import annotations

from datetime import datetime

import io

import pandas as pd
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.views.decorators.http import require_POST

from hcm import contract, paths
from hcm import seal as sealmod

from . import services as S
from .models import ChecklistItem, ContributionEntry, PipelineRun
from .roles import ENGINEER, MENTOR, STUDENT, has_role, primary_role, require_role


def _df_rows(df: pd.DataFrame, limit: int = 500):
    return list(df.columns), df.head(limit).values.tolist()


# ----------------------------------------------------------------- dashboard
@login_required
def dashboard(request):
    return render(request, "workspace/dashboard.html", {
        "s": S.status_summary(), "days": S.sprint_days(),
        "checklist": ChecklistItem.objects.select_related("done_by"),
        "runs": PipelineRun.objects.select_related("user")[:5],
        "nav": "dashboard",
    })


@login_required
@require_POST
def checklist_toggle(request, pk):
    item = get_object_or_404(ChecklistItem, pk=pk)
    item.done = not item.done
    item.done_by = request.user if item.done else None
    item.done_at = timezone.now() if item.done else None
    item.save()
    S.note(request.user, f"Checklist: {'done' if item.done else 'reopened'} — {item.text}")
    return redirect("dashboard")


# --------------------------------------------------------------------- data
@login_required
def data(request):
    rows = [{"t": t, "files": S.target_files(t)} for t in S.TARGETS]
    return render(request, "workspace/data.html", {
        "rows": rows, "nav": "data"})


@require_role(ENGINEER)
@require_POST
def upload(request, key):
    t = S.TARGET_BY_KEY.get(key)
    if t is None:
        raise Http404()
    files = request.FILES.getlist("files")
    if not files:
        messages.error(request, "Choose at least one file.")
    else:
        try:
            messages.success(request, S.save_upload(t, files, request.user))
        except (ValueError, sealmod.SealError) as e:
            messages.error(request, str(e))
    return redirect(reverse("data") + f"#{key}")


@login_required
def manual_view(request, key):
    t = S.TARGET_BY_KEY.get(key)
    if not t or not t.replace_name or not t.replace_name.endswith(".csv"):
        raise Http404()
    df = S.read_csv(paths.ROOT / t.folder / t.replace_name)
    cols, rows = _df_rows(df)
    return render(request, "workspace/table.html", {"title": t.label, "cols": cols, "rows": rows,
                                                    "back": reverse("data"), "nav": "data"})


# ----------------------------------------------------------------- pipeline
@login_required
def pipeline(request):
    return render(request, "workspace/pipeline.html", {
        "steps": PipelineRun.STEPS, "runs": PipelineRun.objects.select_related("user")[:30], "nav": "pipeline"})


@require_role(ENGINEER, STUDENT)
@require_POST
def pipeline_run(request, step):
    if step not in dict(PipelineRun.STEPS):
        raise Http404()
    run = S.run_step(step, request.user)
    (messages.success if run.ok else messages.error)(
        request, f"{run.get_step_display()} {'finished' if run.ok else 'failed'} in {run.seconds:.1f} s.")
    return redirect("pipeline_detail", pk=run.pk)


@login_required
def pipeline_detail(request, pk):
    return render(request, "workspace/run.html", {"run": get_object_or_404(PipelineRun, pk=pk), "nav": "pipeline"})


# ------------------------------------------------------------------- review
@login_required
def review(request):
    review = S.read_csv(paths.INTERIM / "match_review.csv")
    problems = S.read_csv(paths.INTERIM / "crosswalk_problems.csv")
    spot = S.read_csv(paths.DOCS / "crosswalk_spot_checks.csv")
    overrides = S.read_csv(paths.MANUAL / "match_overrides.csv")
    u = S.units()
    unit_choices = [] if u.empty else sorted(
        zip(u["unit_id"], u["state"] + " — " + u["unit_name"]), key=lambda x: x[1])
    return render(request, "workspace/review.html", {
        "review": review.to_dict("records"), "problems": problems.to_dict("records"),
        "spot": spot.to_dict("records"), "overrides": overrides.to_dict("records"),
        "unit_choices": unit_choices, "nav": "review"})


@require_role(ENGINEER)
@require_POST
def override_add(request):
    state, district, unit = (request.POST.get(k, "").strip() for k in ("state", "district", "unit_id"))
    if not (state and district and unit):
        messages.error(request, "State, district and unit are all needed.")
    else:
        S.append_override(state, district, unit)
        S.note(request.user, f"Name match override: {district} ({state}) → {unit}")
        messages.success(request, f"Saved. {district} will match {unit} the next time the panel is built.")
    return redirect("review")


@require_role(STUDENT)
@require_POST
def spot_save(request):
    f = paths.DOCS / "crosswalk_spot_checks.csv"
    df = S.read_csv(f)
    if df.empty:
        raise Http404()
    for i in range(len(df)):
        df.loc[i, "hanut_ok"] = request.POST.get(f"ok_{i}", "")
        df.loc[i, "hanut_note"] = request.POST.get(f"note_{i}", "").strip()
    df.to_csv(f, index=False)
    done = int((df["hanut_ok"] != "").sum())
    S.note(request.user, f"Crosswalk spot checks: {done}/{len(df)} checked, "
                         f"{int((df['hanut_ok'] == 'no').sum())} marked wrong")
    messages.success(request, f"Saved {done} of {len(df)} spot checks.")
    return redirect(reverse("review") + "#spot")


# -------------------------------------------------------------------- panel
@login_required
def panel(request):
    w = S.panel_wide()
    ctx = {"nav": "panel", "built": not w.empty}
    if w.empty:
        return render(request, "workspace/panel.html", ctx)
    meta = {"unit_id", "year", "state", "unit_name", "stable", "in_training_window"}
    variables = sorted(c for c in w.columns if c not in meta)
    states = sorted(w["state"].dropna().unique())
    var = request.GET.get("var") or (variables[0] if variables else "")
    year = int(request.GET.get("year") or 2021)
    state = request.GET.get("state", "Odisha" if "Odisha" in states else "")
    cov = (w.groupby("year")[variables].count().T if variables else pd.DataFrame())
    sel = w[w["year"] == year]
    if state:
        sel = sel[sel["state"] == state]
    table = sel[["unit_id", "unit_name", "state"] + ([var] if var else [])].sort_values(var or "unit_name",
                                                                                      ascending=False)
    ctx.update({
        "variables": variables, "states": states, "years": list(range(2015, 2025)),
        "var": var, "year": year, "state": state,
        "cov_years": list(cov.columns), "cov_rows": [(v, list(r)) for v, r in cov.iterrows()],
        "n_units": w["unit_id"].nunique(),
        "table": [{"unit_id": r["unit_id"], "unit_name": r["unit_name"], "state": r["state"],
                   "value": None if not var or pd.isna(r[var]) else float(r[var])}
                  for r in table.to_dict("records")],
        "training": year <= paths.training_cutoff_year(), "cutoff": paths.training_cutoff_year(),
    })
    return render(request, "workspace/panel.html", ctx)


@login_required
def panel_csv(request):
    w = S.panel_wide()
    if w.empty:
        raise Http404()
    buf = io.StringIO()
    w.to_csv(buf, index=False)
    resp = HttpResponse(buf.getvalue(), content_type="text/csv")
    resp["Content-Disposition"] = 'attachment; filename="panel_wide.csv"'
    return resp


# ---------------------------------------------------------------------- map
@login_required
def map_page(request):
    st = S.outputs_state()
    rc = S.read_csv(paths.OUTPUTS / "reason_codes.csv")
    survey = (not st.get("present") or st.get("error") or st.get("mock_hidden")) and S.survey_html() is not None
    return render(request, "workspace/map.html", {"o": st, "reasons": rc.to_dict("records"), "survey": survey, "allow_mock": S.mock_allowed(), "nav": "map"})


@xframe_options_sameorigin
def map_embed(request):
    p = S.demo_html()
    if not p:
        return HttpResponse("<p style='font-family:system-ui;padding:24px'>No map yet: load NFHS data and build the panel, or upload model outputs.</p>")
    return HttpResponse(p.read_text(encoding="utf-8"), content_type="text/html; charset=utf-8")


def map_public(request):
    """The fair view: the map only, no login, no workspace navigation. Never MOCK."""
    p = S.demo_html(allow_mock=False)
    if not p:
        return HttpResponse("<p style='font-family:system-ui;padding:24px'>The map is not available yet.</p>")
    return HttpResponse(p.read_text(encoding="utf-8"), content_type="text/html; charset=utf-8")


@login_required
def map_download(request):
    p = S.demo_html()
    if not p:
        raise Http404()
    return FileResponse(open(p, "rb"), as_attachment=True, filename="odisha_demo.html")


@require_role(STUDENT)
@require_POST
def outputs_upload(request):
    est, rc = request.FILES.get("estimates"), request.FILES.get("reasons")
    if not (est and rc):
        messages.error(request, "Upload both district_estimates.csv and reason_codes.csv.")
        return redirect("map")
    try:
        messages.success(request, S.save_outputs(est, rc, request.user))
    except (contract.ContractError, ValueError, KeyError, pd.errors.ParserError) as e:
        messages.error(request, f"Not saved. {e}")
    return redirect("map")


@require_role(ENGINEER, STUDENT)
@require_POST
def outputs_mock(request):
    if not S.mock_allowed():
        messages.error(request, "Mock outputs are disabled on this server (they are for local demo building only).")
        return redirect("map")
    import make_mock_outputs
    make_mock_outputs.main()
    S.run_step("demo", request.user)
    messages.warning(request, "MOCK outputs written. They are random and must never be used as results.")
    return redirect("map")


@require_role(STUDENT, MENTOR)
@require_POST
def reasons_save(request):
    f = paths.OUTPUTS / "reason_codes.csv"
    df = S.read_csv(f)
    if df.empty:
        raise Http404()
    is_student = has_role(request.user, STUDENT)
    for i in range(len(df)):
        if is_student:
            for col in ("text_en", "text_hi"):
                df.loc[i, col] = request.POST.get(f"{col}_{i}", df.loc[i, col])
        df.loc[i, "text_or"] = request.POST.get(f"text_or_{i}", df.loc[i, "text_or"])
        df.loc[i, "odia_checked"] = f"odia_{i}" in request.POST
    df.to_csv(f, index=False)
    S.run_step("demo", request.user)
    S.note(request.user, f"Edited reason-code wording ({int(df['odia_checked'].sum())}/{len(df)} Odia checked)")
    messages.success(request, "Wording saved and the map rebuilt.")
    return redirect(reverse("map") + "#reasons")


# ---------------------------------------------------------------------- log
@login_required
def log(request):
    if request.method == "POST":
        text = request.POST.get("text", "").strip()
        date = request.POST.get("date") or timezone.localdate()
        if text:
            ContributionEntry.objects.create(date=date, user=request.user,
                                             person=request.user.get_full_name() or request.user.username,
                                             role=primary_role(request.user), text=text)
            messages.success(request, "Entry added.")
        return redirect("log")
    show = request.GET.get("show", "all")
    qs = ContributionEntry.objects.all()
    if show == "manual":
        qs = qs.filter(automatic=False)
    return render(request, "workspace/log.html", {"entries": qs[:400], "show": show,
                                                  "today": timezone.localdate(), "nav": "log"})


@require_role(MENTOR, STUDENT, ENGINEER)
@require_POST
def log_export(request):
    p = S.export_log()
    messages.success(request, f"Exported to {p.relative_to(paths.ROOT)}. Commit it with the code.")
    return redirect("log")


# ----------------------------------------------------------------- insights
def _insights_context():
    data = S.insights_data()
    pw = paths.PROCESSED / "panel_wide.parquet"
    return {"dash_data": data, "built": datetime.fromtimestamp(pw.stat().st_mtime) if pw.exists() else None}


@login_required
def insights(request):
    return render(request, "workspace/insights.html", {**_insights_context(), "nav": "insights"})


def fair_insights_redirect(request):
    return redirect("insights_public", permanent=True)


def insights_public(request):
    """The fair page (/fair/): the Insights dashboard for visitors, published figures only, no sign-in."""
    return render(request, "workspace/insights_public.html", _insights_context())
