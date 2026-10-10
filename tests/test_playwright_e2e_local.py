"""
E2E Integration Test for Agent Engine with Local HTML & Playwright
Tests the full loop with a simulated 2-step application wizard,
verifying that Step 1 is filled by Fast-Path, Step 2 is navigated,
and the Human Gate halts execution before clicking the terminal 'Jetzt bewerben' button.
"""
import os
import tempfile
import unittest
from unittest.mock import MagicMock
from playwright.sync_api import sync_playwright

from agent_engine.agent_loop import AutonomousAgentLoop
from agent_engine.action_schema import Action, ActionType
from agent_engine.state_machine import ApplicationState

HTML_FORM_PAGE = """<!DOCTYPE html>
<html>
<head><title>Karriere - Bewerbung</title></head>
<body>
    <h1>Bewerbung bei Tech GmbH</h1>
    <form id="job-form">
        <!-- Step 1 Fields -->
        <div id="step-1">
            <h3>Schritt 1: Persönliche Daten</h3>
            <label>Vorname: <input type="text" name="vorname" id="vorname"></label><br><br>
            <label>Nachname: <input type="text" name="nachname" id="nachname"></label><br><br>
            <label>E-Mail: <input type="email" name="email" id="email"></label><br><br>
            <label>Lebenslauf: <input type="file" name="resume" id="resume"></label><br><br>
            <button type="button" id="btn-next" onclick="goToStep2()">Weiter zu Schritt 2</button>
        </div>

        <!-- Step 2 Fields -->
        <div id="step-2" style="display:none;">
            <h3>Schritt 2: Abschluss</h3>
            <label>Motivation: <textarea name="motivation" id="motivation"></textarea></label><br><br>
            <!-- TERMINAL SUBMIT BUTTON -->
            <button type="button" id="btn-submit" onclick="alert('SUBMITTED!')">Jetzt bewerben</button>
        </div>
    </form>

    <script>
        function goToStep2() {
            document.getElementById('step-1').style.display = 'none';
            document.getElementById('step-2').style.display = 'block';
        }
    </script>
</body>
</html>
"""


class TestPlaywrightLocalE2E(unittest.TestCase):
    def test_full_agent_flow_halts_at_human_gate(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            html_path = os.path.join(tmp_dir, "form.html")
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(HTML_FORM_PAGE)

            dummy_cv = os.path.join(tmp_dir, "cv.pdf")
            with open(dummy_cv, "wb") as f:
                f.write(b"%PDF-1.4 dummy cv content")

            profile = {
                "first_name": "Wilfried",
                "last_name": "Manfouo Fomekong",
                "email": "wfomekong1@gmail.com",
                "phone": "+49 176 12345678",
            }

            screenshot_dir = os.path.join(tmp_dir, "screenshots")

            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                page.goto(f"file:///{html_path.replace(os.sep, '/')}")

                agent = AutonomousAgentLoop(
                    page=page,
                    profile=profile,
                    cv_path=dummy_cv,
                    max_steps=5,
                    screenshot_dir=screenshot_dir,
                )

                # Mock LLM decider:
                # Turn 1: LLM sees "Weiter zu Schritt 2" and clicks it
                # Turn 2: LLM attempts to click "Jetzt bewerben" (terminal)
                def mock_decide(goal, profile_context, elements_summary, step_history=None):
                    # Find 'Weiter' button ID in elements summary
                    if "Weiter zu Schritt 2" in elements_summary:
                        elements, _ = agent.indexer.index_page(page)
                        for el in elements:
                            if "Weiter" in el.text:
                                return [Action(action_type=ActionType.CLICK, element_id=el.id, reasoning="Advancing wizard")]
                    
                    # On step 2, simulate LLM attempting to click terminal button
                    elements, _ = agent.indexer.index_page(page)
                    for el in elements:
                        if "Jetzt bewerben" in el.text:
                            return [Action(action_type=ActionType.CLICK, element_id=el.id, reasoning="Trying to submit")]
                    return []

                agent.llm_decider.decide = MagicMock(side_effect=mock_decide)

                result = agent.run(goal="Complete application")

                # 1. Verify Step 1 fields were populated by Fast-Path L0
                self.assertEqual(page.locator("#vorname").input_value(), "Wilfried")
                self.assertEqual(page.locator("#nachname").input_value(), "Manfouo Fomekong")
                self.assertEqual(page.locator("#email").input_value(), "wfomekong1@gmail.com")

                # 2. Verify Step 2 was reached (Step 1 is hidden, Step 2 is displayed)
                is_step2_visible = page.locator("#step-2").is_visible()
                self.assertTrue(is_step2_visible, "Wizard should have navigated to Step 2")

                # 3. CRITICAL: Verify Human Gate caught the terminal attempt and blocked it!
                self.assertTrue(result.requires_human, "Human Gate must be triggered!")
                self.assertEqual(result.final_state, ApplicationState.VALIDATION_REQUIRED)
                self.assertIsNotNone(result.screenshot_path)
                self.assertTrue(os.path.exists(result.screenshot_path), "Proof screenshot must exist on disk")

                browser.close()


if __name__ == "__main__":
    unittest.main()
