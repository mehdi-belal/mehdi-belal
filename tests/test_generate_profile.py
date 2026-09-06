import json
import subprocess
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("profile_renderer", Path(__file__).resolve().parents[1] / "scripts/generate_profile.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class DataTests(unittest.TestCase):
    def test_pagination_filters_and_language_totals(self):
        config = {"username": "sample", "exclude_repositories": ["profile"]}
        def repo(name, **extra):
            return dict(name=name, fork=False, language="Python", description="Example", **extra)
        first = [repo("robot"), repo("profile"), repo("archived", archived=True), repo("secret", private=True)]
        first += [dict(name=f"fork{i}", fork=True) for i in range(96)]
        with patch.object(m, "api", side_effect=[first, [repo("vision")], {"Python": 30}, {"Python": 10, "C++": 60}]) as api:
            result = m.fetch_data(config)
        self.assertIn("page=2", api.call_args_list[1].args[0])
        self.assertEqual(result["languages"], {"C++": 60, "Python": 40})
        self.assertEqual(result["repository_count"], 2)

    def test_api_failure_does_not_publish(self):
        with patch.object(m, "fetch_data", side_effect=RuntimeError("API unavailable")), patch.object(m, "render") as render, patch("sys.argv", ["generate_profile.py"]):
            with self.assertRaises(RuntimeError):
                m.main()
            render.assert_not_called()

    def test_configured_logos_render(self):
        config = json.loads((m.PROFILE / "config.json").read_text())
        m.logo_image.cache_clear()
        for entry in config["work"] + config["academic"]:
            with self.subTest(logo=entry["logo"]):
                logo = m.logo_image(entry["logo"])
                self.assertIsNotNone(logo.getbbox())
                self.assertLessEqual(logo.width, 290)
                self.assertLessEqual(logo.height, 100)

    def test_logo_failure_exposes_stderr(self):
        failure = subprocess.CalledProcessError(
            1, ["rasterize_logo.py"], stderr=b"ImportError: missing Cairo integration"
        )
        with patch.object(m.subprocess, "run", side_effect=failure):
            with self.assertRaisesRegex(RuntimeError, "missing Cairo integration"):
                m.logo_image("missing-test-logo.svg")

    def test_empty_languages_render(self):
        config = {"username": "sample", "name": "Sample", "tagline": "Robotics", "skills": ["C++"], "learning": ["Rust"]}
        data = {"languages": {}, "repository_count": 0}
        for scene in range(6):
            self.assertEqual(m.frame(config, data, scene, 1).size, (960, 480))


if __name__ == "__main__":
    unittest.main()
