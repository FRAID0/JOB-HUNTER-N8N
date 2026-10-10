"""
Unit and Integration Tests for Barriers Dismissal and Job Aggregator Resolution
"""
import os
import tempfile
import unittest
import urllib.parse
from playwright.sync_api import sync_playwright

from copilot_apply import dismiss_barriers_and_modals, resolve_application_page

HTML_LINKEDIN_MOCK = """<!DOCTYPE html>
<html>
<head><title>LinkedIn Job Mock</title></head>
<body>
    <!-- Cookie Banner -->
    <div class="artdeco-global-alert">
        <p>LinkedIn nimmt den Schutz Ihrer Privatsphäre sehr ernst.</p>
        <button data-tracking-control-name="ga-cookie-consent-accept">Akzeptieren</button>
    </div>

    <!-- Contextual Sign-In Modal (Authwall) -->
    <div class="contextual-sign-in-modal" role="dialog" id="authwall-modal">
        <h3>Einloggen, um zu sehen, wen Sie bei Würth Deutschland bereits kennen!</h3>
        <button aria-label="Schließen" class="modal__dismiss" onclick="document.getElementById('authwall-modal').style.display='none'">✕</button>
    </div>

    <!-- Job Header with Offsite Apply Link -->
    <div class="top-card">
        <h1>Praktikum Forschung und Entwicklung - Würth</h1>
        <a data-tracking-control-name="public_jobs_apply-link-offsite_sign-up-modal" 
           href="https://www.linkedin.com/jobs/view/externalApply/4176313755?url=https%3A%2F%2Fjobs.wuerth.de%2Fjob%2F123&urlHash=abc">
           Auf Unternehmens-Website bewerben
        </a>
    </div>
</body>
</html>
"""

class TestBarriersAndAggregators(unittest.TestCase):
    def test_dismiss_barriers_removes_modal_and_cookies(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            html_file = os.path.join(tmp_dir, "linkedin_mock.html")
            with open(html_file, "w", encoding="utf-8") as f:
                f.write(HTML_LINKEDIN_MOCK)

            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                page.goto(f"file:///{html_file.replace(os.sep, '/')}")

                # Verify modal is initially present
                modal = page.locator("#authwall-modal")
                self.assertTrue(modal.is_visible())

                # Run dismissal
                dismiss_barriers_and_modals(page)

                # Modal should now be dismissed / hidden
                self.assertFalse(modal.is_visible())
                browser.close()

    def test_resolve_application_page_extracts_encoded_offsite_url(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            # Create a target destination page (employer portal)
            employer_file = os.path.join(tmp_dir, "employer_portal.html")
            with open(employer_file, "w", encoding="utf-8") as f:
                f.write("<!DOCTYPE html><html><head><title>Wuerth Career Portal</title></head><body><h1>Bewerbungsformular Wuerth</h1></body></html>")

            encoded_dest = urllib.parse.quote(f"file:///{employer_file.replace(os.sep, '/')}")
            
            # Create the linkedin mock with current url mimicking linkedin.com
            html_content = f"""<!DOCTYPE html>
            <html>
            <head><title>LinkedIn</title></head>
            <body>
                <a data-tracking-control-name="public_jobs_apply-link-offsite_sign-up-modal" 
                   href="https://www.linkedin.com/jobs/view/externalApply/123?url={encoded_dest}">
                   Auf Unternehmens-Website bewerben
                </a>
            </body>
            </html>"""
            
            html_file = os.path.join(tmp_dir, "mock_job.html")
            with open(html_file, "w", encoding="utf-8") as f:
                f.write(html_content)

            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                page.goto(f"file:///{html_file.replace(os.sep, '/')}")

                resolved_page = resolve_application_page(page)
                self.assertIn("employer_portal.html", resolved_page.url)
                browser.close()

if __name__ == "__main__":
    unittest.main()
