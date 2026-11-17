import unittest
from pathlib import Path
from scripts.package_sources import entries
import linked_task

class BrandCleanupTests(unittest.TestCase):
    def test_old_brand_only_in_upgrade_code(self):
        old = "cut" + "sync"
        migration = {"link_resolve.ps1", "scripts/install_mac.py"}
        for file, rel in entries():
            self.assertNotIn(old, rel.as_posix().lower())
            if file.suffix.lower() in {".png", ".ico"}: continue
            if rel.as_posix() not in migration:
                self.assertNotIn(old, file.read_text(encoding="utf-8").lower(), str(rel))
    def test_new_task_name(self):
        self.assertEqual(linked_task.TASK_PREFIX, "Stintory Linked - ")
    def test_no_old_slogan_or_description(self):
        for file, rel in entries():
            if file.suffix.lower() in {".png", ".ico"} or rel.name == "test_brand_cleanup.py": continue
            text = file.read_text(encoding="utf-8").lower()
            self.assertNotIn("your time tells a story.", text, str(rel))
            self.assertNotIn("local-first", text, str(rel))
            for phrase in ("the hours behind " + "every frame.", "let your timelines " + "keep time."):
                self.assertNotIn(phrase, text, str(rel))
