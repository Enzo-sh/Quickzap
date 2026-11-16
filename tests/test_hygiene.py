import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("check_secrets", ROOT / "scripts" / "check_secrets.py")
check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check)


class HygieneTests(unittest.TestCase):
    def test_repository_has_no_secrets_or_personal_data(self):
        self.assertEqual(check.scan(ROOT), [])

    def test_scanner_detects_planted_secrets(self):
        planted = {
            "a.py": 'API_KEY = "abcd1234efgh5678"\n',
            "b.txt": "clave: sk-" + "A1b2C3d4E5f6G7h8I9j0K1l2" + "\n",
            "c.md": "mi carpeta es C:\\Users\\maria\\proyecto\n",
            "d.md": "escribime a persona@gmail.com\n",
            "e.pem": "-----BEGIN PRIVATE KEY-----\n",
            "f.md": "/home/pedro/notas\n",
        }
        with tempfile.TemporaryDirectory() as tmp:
            for name, text in planted.items():
                (Path(tmp) / name).write_text(text, encoding="utf-8")
            found = {f[0] for f in check.scan(tmp)}
        self.assertEqual(found, set(planted))

    def test_scanner_ignores_placeholders_and_embedded_images(self):
        ok = {"a.md": "Ruta de ejemplo: C:\\Users\\<tu-usuario>\\Downloads y /home/<usuario>/x\n",
              "b.html": '<img src="data:image/png;base64,' + "sk-AKIA" * 400 + '">\n',
              "c.md": "contacto: nadie@example.com\n"}
        with tempfile.TemporaryDirectory() as tmp:
            for name, text in ok.items():
                (Path(tmp) / name).write_text(text, encoding="utf-8")
            self.assertEqual(check.scan(tmp), [])


if __name__ == "__main__":
    unittest.main()
