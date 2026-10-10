"""Web workspace tests: python manage.py test workspace"""

import shutil
import tempfile
from pathlib import Path

from django.contrib.auth.models import Group, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings

from hcm import paths

from .models import ChecklistItem, ContributionEntry, PipelineRun

REPO = Path(__file__).resolve().parents[2]
NAMES = ["ROOT", "CONFIG", "DATA", "RAW", "INTERIM", "PROCESSED", "MANUAL", "GEO", "SEALED",
         "UNSEALED", "OUTPUTS", "DOCS", "SEAL_LOG"]


class Base(TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        root = self.tmp / "proj"
        for sub in ("config", "data/manual", "demo", "scripts"):
            shutil.copytree(REPO / sub, root / sub)
        (root / "data/geo").mkdir(parents=True)
        for n in ("odisha_districts_2011.geojson",):
            shutil.copy(REPO / "data/geo" / n, root / "data/geo" / n)
        shutil.copy(root / "data/geo/odisha_districts_2011.geojson", root / "data/geo/india_districts_2011.geojson")
        self._old = {n: getattr(paths, n) for n in NAMES}
        new = {"ROOT": root, "CONFIG": root / "config", "DATA": root / "data", "RAW": root / "data/raw",
               "INTERIM": root / "data/interim", "PROCESSED": root / "data/processed", "MANUAL": root / "data/manual",
               "GEO": root / "data/geo", "SEALED": root / "data/sealed", "UNSEALED": root / "data/unsealed",
               "OUTPUTS": root / "outputs", "DOCS": root / "docs", "SEAL_LOG": root / "docs/seal_log.jsonl"}
        for n, v in new.items():
            setattr(paths, n, v)
        paths.sources.cache_clear()
        paths.ensure_dirs()
        self.root = root
        self.key = self.tmp / "nfhs6.key"
        call_command("setup_team", stdout=open("/dev/null", "w"))
        self.users = {}
        for name in ("engineer",):
            u = User.objects.get(username=name)
            u.set_password("pass-for-tests-123")
            u.save()
            self.users[name] = u

    def tearDown(self):
        for n, v in self._old.items():
            setattr(paths, n, v)
        paths.sources.cache_clear()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def login(self, name):
        self.client.force_login(self.users[name])


class AccessTests(Base):
    def test_pages_need_login_but_fair_map_does_not(self):
        for url in ("/", "/data/", "/pipeline/", "/review/", "/panel/", "/map/", "/log/"):
            self.assertEqual(self.client.get(url).status_code, 302, url)
        self.assertEqual(self.client.get("/fair/").status_code, 200)
        self.assertEqual(self.client.get("/fair/map/").status_code, 200)

    def test_every_page_renders_for_each_role(self):
        for name in ("engineer",):
            self.login(name)
            for url in ("/", "/data/", "/pipeline/", "/review/", "/panel/", "/map/", "/log/"):
                self.assertEqual(self.client.get(url).status_code, 200, f"{name} {url}")

    def test_setup_team_creates_roles_and_checklist(self):
        self.assertEqual(set(Group.objects.values_list("name", flat=True)), {"engineer"})
        self.assertFalse(User.objects.filter(username__in=["hanut", "sweksha"]).exists())
        self.assertEqual(ChecklistItem.objects.count(), 9)

    def test_seal_pages_are_gone(self):
        self.login("engineer")
        self.assertEqual(self.client.get("/seal/").status_code, 404)

    def test_user_without_role_cannot_upload_data(self):
        u = User.objects.create_user("viewer", password="pass-for-tests-123")
        self.client.force_login(u)
        f = SimpleUploadedFile("lgd.csv", b"lgd_code,state,district,census2011_code\n")
        self.client.post("/data/lgd/upload/", {"files": f})
        self.assertEqual(len(list((self.root / "data/manual").glob("_previous/*"))), 0)
        self.assertFalse(ContributionEntry.objects.filter(text__startswith="Uploaded").exists())


class PipelineTests(Base):
    def test_upload_ncrb_then_build_panel_and_review(self):
        self.login("engineer")
        csv = b"State/UT,District,Year,Prohibition of Child Marriage Act\nOdisha,Khurda,2021,3\nOdisha,Atlantis,2021,1\n"
        r = self.client.post("/data/ncrb/upload/", {"files": SimpleUploadedFile("ncrb_2021.csv", csv)})
        self.assertEqual(r.status_code, 302)
        self.assertTrue((self.root / "data/raw/ncrb/ncrb_2021.csv").exists())
        self.client.post("/pipeline/run/extract/")
        self.client.post("/pipeline/run/panel/")
        run = PipelineRun.objects.filter(step="panel").first()
        self.assertTrue(run.ok, run.log)
        self.assertIn("unmatched_names  1", run.log)
        page = self.client.get("/review/").content.decode()
        self.assertIn("Atlantis", page)
        # engineer fixes the bad name; rebuild clears it
        self.client.post("/review/override/", {"state": "Odisha", "district": "Atlantis", "unit_id": "U0387"})
        self.client.post("/pipeline/run/panel/")
        self.assertIn("unmatched_names  0", PipelineRun.objects.filter(step="panel").first().log)
        self.assertIn("ncrb_pcma_cases", self.client.get("/panel/?var=ncrb_pcma_cases&year=2021").content.decode())

    def test_wrong_file_type_is_refused(self):
        self.login("engineer")
        r = self.client.post("/data/ncrb/upload/", {"files": SimpleUploadedFile("x.exe", b"MZ")}, follow=True)
        self.assertIn("Wrong file type", r.content.decode())


class NFHS6UploadTests(Base):
    def test_nfhs6_upload_is_a_plain_file_now(self):
        self.login("engineer")
        self.client.post("/data/nfhs6/upload/", {"files": SimpleUploadedFile("Puri.pdf", b"%PDF nfhs6")})
        self.assertEqual((self.root / "data/raw/nfhs/round6/Puri.pdf").read_bytes(), b"%PDF nfhs6")
        self.assertFalse((self.root / "data/sealed").exists() and any((self.root / "data/sealed").iterdir()))


class MapTests(Base):
    def test_mock_outputs_then_public_map_and_reason_edit(self):
        self.login("engineer")
        with self.settings(HCM_ALLOW_MOCK=True):
            self.client.post("/map/mock/")
            self.assertIn("MOCK", self.client.get("/map/embed/").content.decode())
        self.assertNotIn('"mock":true', self.client.get("/fair/map/").content.decode())
        self.login("engineer")
        self.client.post("/map/reasons/", {"text_or_0": "ପରୀକ୍ଷା", "odia_0": "on"})
        txt = (self.root / "outputs/reason_codes.csv").read_text(encoding="utf-8")
        self.assertIn("ପରୀକ୍ଷା", txt)

    def test_bad_outputs_are_rejected_and_old_ones_kept(self):
        self.login("engineer")
        est = SimpleUploadedFile("e.csv", b"census2011_code,district\n387,Puri\n")
        rc = SimpleUploadedFile("r.csv", b"reason_code,text_en,text_hi,text_or,odia_checked\n")
        r = self.client.post("/map/outputs/", {"estimates": est, "reasons": rc}, follow=True)
        self.assertIn("Not saved", r.content.decode())
        self.assertFalse((self.root / "outputs/district_estimates.csv").exists())


class LogTests(Base):
    def test_manual_entry_and_export(self):
        self.login("engineer")
        self.client.post("/log/", {"date": "2026-10-03", "text": "Registered on IRIS"})
        self.client.post("/log/export/")
        md = (self.root / "docs/contribution_log.md").read_text(encoding="utf-8")
        self.assertIn("Registered on IRIS", md)


class LoginPageTests(Base):
    def test_logins_listed_only_locally_in_debug_with_file(self):
        import json
        from unittest import mock
        from django.test import override_settings
        from . import login_view
        f = self.tmp / "initial_passwords.json"  # never the real file
        f.write_text(json.dumps({"admin": "pw-admin-1234", "engineer": "pw-engineer-1234"}))
        with mock.patch.object(login_view, "PRESET", f):
            with override_settings(DEBUG=True):
                page = self.client.get("/login/", REMOTE_ADDR="127.0.0.1").content.decode()
                self.assertIn("pw-engineer-1234", page)
                self.assertIn("Engineer", page)
                other = self.client.get("/login/", REMOTE_ADDR="192.168.1.20").content.decode()
                self.assertNotIn("pw-engineer-1234", other)
            with override_settings(DEBUG=False, ALLOWED_HOSTS=["testserver"]):
                self.assertNotIn("pw-engineer-1234", self.client.get("/login/", REMOTE_ADDR="127.0.0.1").content.decode())
        with mock.patch.object(login_view, "PRESET", self.tmp / "missing.json"), override_settings(DEBUG=True):
            self.assertNotIn("Team logins", self.client.get("/login/", REMOTE_ADDR="127.0.0.1").content.decode())


class SurveyMapTests(Base):
    def test_survey_map_shown_until_model_outputs_exist(self):
        import pandas as pd
        (self.root / "data/processed").mkdir(parents=True, exist_ok=True)
        rows = [{"unit_id": "U0397", "year": 2016, "state": "Odisha", "unit_name": "Nabarangapur", "cm_20_24_before18": 41.0},
                {"unit_id": "U0397", "year": 2020, "state": "Odisha", "unit_name": "Nabarangapur", "cm_20_24_before18": 39.4}]
        pd.DataFrame(rows).to_parquet(self.root / "data/processed/panel_wide.parquet", index=False)
        html = self.client.get("/fair/map/").content.decode()
        self.assertIn('"mode":"survey"', html)
        self.assertIn('"n5":39.4', html)
        self.assertIn('"chg":-1.6', html)
        self.login("engineer")
        self.assertIn("published NFHS survey figures", self.client.get("/map/").content.decode())
        self.login("engineer")
        with self.settings(HCM_ALLOW_MOCK=True):
            self.client.post("/map/mock/")
            self.assertIn('"mock":true', self.client.get("/map/embed/").content.decode())
            # the public fair view never shows MOCK, even where mock is allowed
            self.assertIn('"mode":"survey"', self.client.get("/fair/map/").content.decode())
        # production (mock not allowed): workspace map falls back to the survey too
        with self.settings(HCM_ALLOW_MOCK=False):
            self.assertIn('"mode":"survey"', self.client.get("/map/embed/").content.decode())
            self.assertIn("hidden on this server", self.client.get("/map/").content.decode())

    def test_mock_button_disabled_in_production(self):
        self.login("engineer")
        with self.settings(HCM_ALLOW_MOCK=False):
            self.client.post("/map/mock/")
        self.assertFalse((self.root / "outputs/district_estimates.csv").exists())


class InsightsTests(Base):
    def _panel(self):
        import pandas as pd
        (self.root / "data/processed").mkdir(parents=True, exist_ok=True)
        rows = []
        for y in range(2015, 2025):
            rows.append({"unit_id": "U0397", "year": y, "state": "Odisha", "unit_name": "Nabarangapur",
                         "cm_20_24_before18": {2016: 41.0, 2020: 39.4}.get(y), "ncrb_pcma_cases": 1.0 if y <= 2022 else None,
                         "rain_mm": 1400.0, "rain_shock_z": 0.1, "udise_transition_g9_g10": 0.95 if y >= 2017 else None,
                         "teen_pregnancy_15_19": {2016: 9.0, 2020: 8.3}.get(y)})
        pd.DataFrame(rows).to_parquet(self.root / "data/processed/panel_wide.parquet", index=False)

    def test_insights_page_and_public_view(self):
        self.assertEqual(self.client.get("/insights/").status_code, 302)       # workspace page needs sign-in
        self.assertIn("isn", self.client.get("/fair/").content.decode() + "isn")  # renders without a panel
        self._panel()
        self.login("engineer")
        page = self.client.get("/insights/").content.decode()
        self.assertIn('id="insights-data"', page)
        self.assertIn("Nabarangapur", page)
        self.assertEqual(self.client.get("/fair/insights/").status_code, 301)
        pub = self.client.get("/fair/")
        self.assertEqual(pub.status_code, 200)
        self.assertIn("not model estimates", pub.content.decode())

    def test_insights_data_shape(self):
        from . import services as S
        self._panel()
        d = S.insights_data()
        r = d["odisha_districts"][0]
        self.assertEqual((r["nfhs5_pct"], r["change_pts"], r["cases_2016_2021"]), (39.4, -1.6, 6))
        self.assertEqual(len(d["district_year"]), 10)
        self.assertEqual(d["pcma_by_year"][0], {"year": 2015, "odisha": 1, "india": 1})
