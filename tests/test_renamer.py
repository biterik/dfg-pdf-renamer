"""
Tests for dfg_pdf_renamer.py.  Run with:

    python -m unittest discover tests

No extra test framework is needed.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

# Make the main module importable when the tests are run from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import dfg_pdf_renamer as r  # noqa: E402
from make_test_pdfs import EXAMPLES, write_examples, write_simple_pdf  # noqa: E402


class PatternTests(unittest.TestCase):
    def test_examples_from_erik(self):
        self.assertEqual(r.find_reference("Votum zu AB 1234/5-1 Bitzek"), "AB 1234/5-1")
        self.assertEqual(r.find_reference("Geschäftszeichen: CD 5678/12-2"), "CD 5678/12-2")

    def test_other_letter_counts_and_trailing_letter(self):
        self.assertEqual(r.find_reference("SFB 999/1-3"), "SFB 999/1-3")
        self.assertEqual(r.find_reference("TRR 777/2-1"), "TRR 777/2-1")
        self.assertEqual(r.find_reference("Zeichen BI 1234/5-1A Ende"), "BI 1234/5-1A")
        self.assertEqual(r.find_reference("AB1234/5-1"), "AB 1234/5-1")   # no space
        self.assertEqual(r.find_reference("AB\n1234/5-1"), "AB 1234/5-1")  # line break

    def test_first_of_two_is_taken(self):
        text = "Geschäftszeichen: CD 5678/12-2 \n verwandt: MU 1234/5-2"
        self.assertEqual(r.find_reference(text), "CD 5678/12-2")

    def test_no_match(self):
        self.assertIsNone(r.find_reference("Rechnung Nr. 4711 vom 12/03-2026"))
        self.assertIsNone(r.find_reference("ISO 9001/2-1x"))  # glued letter

    def test_filename_form(self):
        self.assertEqual(r.reference_for_filename("AB 1234/5-1"), "AB1234-5-1")
        self.assertEqual(r.reference_for_filename("CD 5678/12-2"), "CD5678-12-2")

    def test_clean_stem(self):
        self.assertEqual(r.clean_stem("Entscheidungsvorlage (39)"), "Entscheidungsvorlage")
        self.assertEqual(r.clean_stem("Entscheidungsvorlage(39)"), "Entscheidungsvorlage")
        self.assertEqual(r.clean_stem("2026_07_30_Votum_Bitzek_Duesseldorf"),
                         "2026_07_30_Votum_Bitzek_Duesseldorf")
        self.assertEqual(r.clean_stem("Bericht (Teil 2)"), "Bericht (Teil 2)")  # not a number


class EndToEndTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.src = Path(self.tmp.name) / "quelle"
        self.dst = Path(self.tmp.name) / "ziel"
        write_examples(self.src)

    def tearDown(self):
        self.tmp.cleanup()

    def test_plan(self):
        plan = r.make_plan(self.src, self.dst)
        by_name = {e.source.name: e for e in plan.entries}

        self.assertEqual(by_name["2026_07_30_Votum_Bitzek_Duesseldorf.pdf"].new_name,
                         "AB1234-5-1_2026_07_30_Votum_Bitzek_Duesseldorf.pdf")
        self.assertEqual(by_name["Entscheidungsvorlage (39).pdf"].new_name,
                         "CD5678-12-2_Entscheidungsvorlage.pdf")
        self.assertEqual(by_name["Entscheidungsvorlage (40).pdf"].new_name,
                         "SFB999-1-3_Entscheidungsvorlage.pdf")

        self.assertFalse(by_name["Rechnung_Hotel.pdf"].ok)
        self.assertIn("kein DFG-Dokument", by_name["Rechnung_Hotel.pdf"].message)
        self.assertFalse(by_name["DFG_ohne_Zeichen.pdf"].ok)
        self.assertIn("kein Geschäftszeichen", by_name["DFG_ohne_Zeichen.pdf"].message)
        self.assertFalse(by_name["leer.pdf"].ok)
        self.assertIn("keinen Text", by_name["leer.pdf"].message)
        self.assertNotIn("notiz.txt", by_name)  # non-PDFs are ignored

        self.assertEqual(len(plan.to_copy), 3)
        self.assertEqual(len(plan.skipped), 3)

    def test_collision_gets_suffix(self):
        # A second copy of the same document with a different duplicate number.
        write_simple_pdf(self.src / "Entscheidungsvorlage (41).pdf",
                         ["Antragstyp: Sachbeihilfe", "Geschäftszeichen: CD 5678/12-2"])
        plan = r.make_plan(self.src, self.dst)
        names = sorted(e.new_name for e in plan.to_copy if e.new_name.startswith("CD5678"))
        self.assertEqual(names, ["CD5678-12-2_Entscheidungsvorlage.pdf",
                                 "CD5678-12-2_Entscheidungsvorlage_2.pdf"])

    def test_collision_with_existing_target_file(self):
        self.dst.mkdir()
        (self.dst / "CD5678-12-2_Entscheidungsvorlage.pdf").write_bytes(b"alt")
        plan = r.make_plan(self.src, self.dst)
        entry = next(e for e in plan.entries if e.source.name == "Entscheidungsvorlage (39).pdf")
        self.assertEqual(entry.new_name, "CD5678-12-2_Entscheidungsvorlage_2.pdf")

    def test_execute_copies_and_logs(self):
        plan = r.make_plan(self.src, self.dst)
        log = r.execute_plan(plan)
        copied = sorted(p.name for p in self.dst.glob("*.pdf"))
        self.assertEqual(copied, [
            "AB1234-5-1_2026_07_30_Votum_Bitzek_Duesseldorf.pdf",
            "CD5678-12-2_Entscheidungsvorlage.pdf",
            "SFB999-1-3_Entscheidungsvorlage.pdf",
        ])
        # originals untouched
        self.assertEqual(sorted(p.name for p in self.src.glob("*.pdf")),
                         sorted(EXAMPLES) + ["leer.pdf"])
        # copy is byte-identical
        self.assertEqual((self.dst / "CD5678-12-2_Entscheidungsvorlage.pdf").read_bytes(),
                         (self.src / "Entscheidungsvorlage (39).pdf").read_bytes())
        text = log.read_text(encoding="utf-8")
        self.assertIn("[OK]    Entscheidungsvorlage (39).pdf", text)
        self.assertIn("[---]   Rechnung_Hotel.pdf", text)


if __name__ == "__main__":
    unittest.main()
