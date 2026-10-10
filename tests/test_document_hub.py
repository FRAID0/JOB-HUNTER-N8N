"""
Unit tests for DocumentHub
Verifies that DocumentHub categorizes the candidate's files and accurately resolves
appropriate files for web dropzones (e.g. Zeugnisse vs CV).
"""
import os
import tempfile
import unittest
from pathlib import Path
from agent_engine.document_hub import DocumentHub, DocumentCategory


class TestDocumentHub(unittest.TestCase):
    def test_document_hub_categorization_and_resolution(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            # Create simulated candidate files
            cv_path = Path(tmp_dir) / "cv.pdf"
            cv_path.write_text("Dummy CV")

            trans_path = Path(tmp_dir) / "notenspiegel_aktuell.pdf"
            trans_path.write_text("Dummy Transcript")

            immat_path = Path(tmp_dir) / "studienbescheinigung_ss26.pdf"
            immat_path.write_text("Dummy Enrollment")

            ref_path = Path(tmp_dir) / "arbeitszeugnis_pwo.pdf"
            ref_path.write_text("Dummy Reference")

            hub = DocumentHub(docs_dir=tmp_dir)

            # 1. Verify CV resolution
            resolved_cv = hub.resolve_document("Lebenslauf (wenn möglich mit Foto)")
            self.assertIsNotNone(resolved_cv)
            self.assertEqual(resolved_cv.name, "cv.pdf")

            # 2. Verify Zeugnisse resolution (MUST NOT return CV!)
            resolved_zeugnis = hub.resolve_document("Zeugnisse (alle relevanten Zeugnisse, die deine Qualifikationen belegen)")
            self.assertIsNotNone(resolved_zeugnis)
            self.assertNotEqual(resolved_zeugnis.name, "cv.pdf")
            self.assertEqual(resolved_zeugnis.name, "notenspiegel_aktuell.pdf")

            # 3. Verify Immatrikulation resolution
            resolved_immat = hub.resolve_document("Aktuelle Immatrikulationsbescheinigung")
            self.assertIsNotNone(resolved_immat)
            self.assertEqual(resolved_immat.name, "studienbescheinigung_ss26.pdf")

            # 4. Verify 'Andere (Optional)' resolution (MUST NEVER return CV!)
            resolved_andere = hub.resolve_document("Andere (Optional)")
            if resolved_andere is not None:
                self.assertNotEqual(resolved_andere.name, "cv.pdf")


if __name__ == "__main__":
    unittest.main()
