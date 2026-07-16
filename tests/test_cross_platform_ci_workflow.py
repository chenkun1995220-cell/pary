from pathlib import Path
import unittest

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = PROJECT_ROOT / ".github" / "workflows" / "test.yml"


class CrossPlatformCIWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(WORKFLOW_PATH.exists(), "cross-platform workflow is missing")
        self.workflow_text = WORKFLOW_PATH.read_text(encoding="utf-8")
        self.workflow = yaml.load(self.workflow_text, Loader=yaml.BaseLoader)

    def test_triggers_only_target_main_and_manual_dispatch(self):
        triggers = self.workflow["on"]
        self.assertEqual(triggers["push"]["branches"], ["main"])
        self.assertEqual(triggers["pull_request"]["branches"], ["main"])
        self.assertEqual(triggers["workflow_dispatch"], {})

    def test_uses_read_only_permissions_and_cancels_superseded_runs(self):
        self.assertEqual(self.workflow["permissions"], {"contents": "read"})
        self.assertEqual(self.workflow["concurrency"]["cancel-in-progress"], "true")

    def test_runs_full_windows_and_focused_posix_suites_with_python_312(self):
        job = self.workflow["jobs"]["test"]
        self.assertEqual(
            job["strategy"]["matrix"].get("include"),
            [
                {"os": "windows-latest", "suite": "full"},
                {"os": "ubuntu-latest", "suite": "posix"},
            ],
        )
        self.assertEqual(job["runs-on"], "${{ matrix.os }}")
        self.assertEqual(self.workflow["env"]["PYTHONUTF8"], "1")
        self.assertEqual(self.workflow["env"]["PYTHONIOENCODING"], "utf-8")
        steps = job["steps"]
        setup = next(step for step in steps if step.get("uses") == "actions/setup-python@v5")
        self.assertEqual(setup["with"]["python-version"], "3.12")
        commands = "\n".join(step.get("run", "") for step in steps)
        self.assertIn("pip install -r requirements.txt -r requirements-dev.txt", commands)
        self.assertIn("python -m compileall -q", commands)
        self.assertIn("node_modules", commands)
        self.assertIn("New-Item -ItemType Junction", commands)
        self.assertIn("python -m unittest discover -s tests", commands)
        self.assertIn(
            "python -m unittest tests.test_one_week_forecast_shadow_disposition "
            "tests.test_cross_platform_ci_workflow",
            commands,
        )

    def test_excludes_production_automation_and_write_capabilities(self):
        forbidden = (
            "run_us_universe_weekly",
            "run_cn_weekly",
            "run_hk_weekly",
            "SEC_USER_AGENT",
            "secrets.",
            "contents: write",
        )
        for value in forbidden:
            self.assertNotIn(value, self.workflow_text)


if __name__ == "__main__":
    unittest.main()
