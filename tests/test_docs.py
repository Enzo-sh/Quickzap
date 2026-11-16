import re
import unittest
from pathlib import Path

from quickzap import __version__, reports

ROOT = Path(__file__).resolve().parent.parent
DOCS = [ROOT / "README.md", ROOT / "CHANGELOG.md", ROOT / "CONTRIBUTING.md", ROOT / "THIRD_PARTY.md",
        ROOT / "benchmarks" / "README.md"] + sorted((ROOT / "docs").glob("*.md"))


class DocsTests(unittest.TestCase):
    def test_models_table_is_up_to_date(self):
        self.assertIn(reports.models_markdown(), (ROOT / "docs" / "MODELS.md").read_text(encoding="utf-8"),
                      "docs/MODELS.md está desactualizado: regeneralo con `python -m quickzap models --markdown`")

    def test_relative_links_and_images_exist(self):
        broken = []
        for doc in DOCS:
            for target in re.findall(r"\]\(([^)\s]+)\)", doc.read_text(encoding="utf-8")):
                if re.match(r"(https?:|mailto:|#)", target):
                    continue
                path = (doc.parent / target.split("#")[0]).resolve()
                if not path.exists():
                    broken.append("%s -> %s" % (doc.name, target))
        self.assertEqual(broken, [])

    def test_required_open_source_files_exist(self):
        for name in ("README.md", "LICENSE", "CHANGELOG.md", "CONTRIBUTING.md", "THIRD_PARTY.md", ".gitignore",
                     "docs/TROUBLESHOOTING.md", "docs/BENCHMARKS.md", "docs/MODELS.md"):
            self.assertTrue((ROOT / name).is_file(), name)
        self.assertIn("MIT License", (ROOT / "LICENSE").read_text(encoding="utf-8"))

    def test_changelog_mentions_current_version(self):
        self.assertIn("## [%s]" % __version__, (ROOT / "CHANGELOG.md").read_text(encoding="utf-8"))

    def test_readme_has_the_project_description_and_screenshots(self):
        text = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("QuickZap is a local-first AI chatbot powered by Ollama, featuring selective RAG, persistent memory, "
                      "automatic hardware detection and offline support.", text)
        for shot in ("wizard-model", "wizard-benchmark", "stats"):
            self.assertTrue((ROOT / "docs" / "screenshots" / (shot + ".png")).is_file(), shot)

    def test_every_documented_command_exists(self):
        from quickzap.__main__ import main
        text = (ROOT / "README.md").read_text(encoding="utf-8") + (ROOT / "docs" / "TROUBLESHOOTING.md").read_text(encoding="utf-8")
        used = set(re.findall(r"python -m quickzap (hardware|recommend|pull|doctor|bench-compare|bench|models)", text))
        self.assertTrue({"hardware", "doctor", "bench", "bench-compare", "models", "pull", "recommend"} <= used)
        for cmd in used:
            with self.assertRaises(SystemExit) as ctx:     # `--help` termina con código 0 si el subcomando existe
                main([cmd, "--help"])
            self.assertEqual(ctx.exception.code, 0, cmd)


if __name__ == "__main__":
    unittest.main()
