"""tools/translate.py: export a language as TSV files, change a few lines, import them back – on a copy of the
project, never the real dictionaries. Needs node (the build needs it anyway) to read the JS dictionaries."""
from tests.python import env  # noqa: F401  (before app.*)

import importlib.util
import io
import shutil
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


@unittest.skipUnless(shutil.which("node"), "needs node")
class TranslateToolTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(tempfile.mkdtemp(dir=env.ROOT))
        for part in ("app", "frontend/src", "tools"):
            shutil.copytree(REPO / part, cls.root / part, ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copy(REPO / "tuttiphon.py", cls.root / "tuttiphon.py")
        spec = importlib.util.spec_from_file_location("translate_copy", cls.root / "tools" / "translate.py")
        cls.tool = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.tool)
        cls.tsv = cls.root / "translations"

    def run_tool(self, fn, *args):
        with redirect_stdout(io.StringIO()) as out:
            code = fn(*args, root=self.root)
        return code, out.getvalue()

    def rows(self, lang, area):
        return [line.split("\t") for line in (self.tsv / lang / f"{area}.tsv").read_text(encoding="utf-8").splitlines()]

    def write_rows(self, lang, area, rows):
        (self.tsv / lang / f"{area}.tsv").write_text("".join("\t".join(r) + "\n" for r in rows), encoding="utf-8")

    def test_a_correction_goes_back_and_nothing_else_changes(self):
        self.run_tool(self.tool.export, "fr", self.tsv)
        rows = self.rows("fr", "ui-common")
        target = self.root / "frontend/src/locales/fr/common.js"
        before = self.tool.ui_dict(target)
        en = rows[0][1]
        self.write_rows("fr", "ui-common", [["", en, rows[0][2], "Correction"]])   # a file with just one line
        code, out = self.run_tool(self.tool.import_, "fr", self.tsv)
        self.assertEqual(code, 0, out)
        after = self.tool.ui_dict(target)
        self.assertEqual(after[en], "Correction")
        self.assertEqual({k: v for k, v in after.items() if k != en}, {k: v for k, v in before.items() if k != en})

    def test_wrong_placeholders_and_markup_are_refused(self):
        self.run_tool(self.tool.export, "es", self.tsv)
        area = next(p.stem for p in (self.tsv / "es").glob("srv-*.tsv")
                    if any("{" in r[1] for r in self.rows("es", p.stem)))
        row = next(r for r in self.rows("es", area) if "{" in r[1])
        self.write_rows("es", area, [["", row[1], row[2], "sin marcador"]])
        code, out = self.run_tool(self.tool.import_, "es", self.tsv)
        self.assertEqual(code, 1)
        self.assertIn("placeholders", out)
        ui = next(r for r in self.rows("es", "ui-help-user") if "<b>" in r[1])
        self.write_rows("es", "ui-help-user", [["", ui[1], ui[2], "sin negrita"]])
        self.assertIn("markup", self.run_tool(self.tool.import_, "es", self.tsv)[1])

    def test_polish_plurals_need_both_forms(self):
        self.run_tool(self.tool.export, "pl", self.tsv)
        rows = self.rows("pl", "ui-common")
        few = next(r for r in rows if r[0] == "few")
        self.assertTrue(any(r[0] == "many" and r[1] == few[1] for r in rows))   # one line per form
        self.write_rows("pl", "ui-common", [few[:3] + ["piosenki?"]])   # only "few" given: "many" stays as it was
        code, out = self.run_tool(self.tool.import_, "pl", self.tsv)
        self.assertEqual(code, 0, out)
        entry = self.tool.ui_dict(self.root / "frontend/src/locales/pl/common.js")[few[1]]
        self.assertEqual(entry["few"], "piosenki?")
        self.assertTrue(entry["many"])

    def test_missing_only_and_a_new_language(self):
        code, _out = self.run_tool(self.tool.export, "fr", self.tsv, True)
        self.assertEqual(code, 0)   # French is complete: nothing missing
        self.run_tool(self.tool.export, "sv", self.tsv)   # Swedish: everything to do
        rows = self.rows("sv", "ui-common")
        self.assertTrue(rows and all(r[3] == "" for r in rows))
        self.write_rows("sv", "ui-common", [["", rows[0][1], rows[0][2], "Just nu"]])
        code, out = self.run_tool(self.tool.import_, "sv", self.tsv)
        self.assertEqual(code, 0, out)
        self.assertIn("A new language", out)   # reminds of the language lists
        self.assertTrue((self.root / "frontend/src/locales/sv/index.js").exists())
        self.assertEqual(self.tool.ui_dict(self.root / "frontend/src/locales/sv/common.js"), {rows[0][1]: "Just nu"})
        self.assertFalse((self.root / "app/locales/sv").exists())   # nothing written where nothing was given


if __name__ == "__main__":
    unittest.main()
