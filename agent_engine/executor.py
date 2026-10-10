"""
Action Executor
Executes validated browser actions using Playwright locators targeting data-agent-id.
Maintains defense-in-depth: refuses to click terminal elements even if validator was bypassed.
"""
import time
from typing import Optional
from .action_schema import Action, ActionType, IndexedElement
from .terminal_guard import HumanApprovalRequired, is_terminal_element


class ExecutionError(Exception):
    pass


class ActionExecutor:
    def __init__(self, page):
        self.page = page

    def execute(self, action: Action, element: Optional[IndexedElement] = None) -> bool:
        """
        Executes a validated action on the Playwright page.
        """
        action_type = action.action_type

        # Global actions
        if action_type == ActionType.NAVIGATE:
            if not action.value:
                raise ExecutionError("Navigate requires a URL value.")
            self.page.goto(action.value, wait_until="networkidle", timeout=30000)
            return True

        if action_type == ActionType.SCROLL:
            pixels = int(action.value) if (action.value and action.value.isdigit()) else 500
            self.page.mouse.wheel(0, pixels)
            self.page.wait_for_timeout(500)
            return True

        if action_type == ActionType.WAIT:
            ms = int(action.value) if (action.value and action.value.isdigit()) else 1500
            self.page.wait_for_timeout(ms)
            return True

        # Element actions
        if action.element_id is None:
            raise ExecutionError(f"Action '{action_type}' requires element_id.")

        locator = self.page.locator(f"[data-agent-id='{action.element_id}']").first

        if locator.count() == 0:
            raise ExecutionError(f"Element with data-agent-id='{action.element_id}' not found on page.")

        # Defense-in-depth terminal check
        if element and is_terminal_element(element):
            raise HumanApprovalRequired(
                f"DEFENSE-IN-DEPTH: Element [{element.id}] is terminal. Execution halted.",
                element,
            )

        try:
            if action_type == ActionType.TYPE:
                try:
                    locator.scroll_into_view_if_needed(timeout=1000)
                except Exception:
                    pass
                val = action.value or ""
                try:
                    locator.fill(val, timeout=2000, force=True)
                except Exception:
                    # JavaScript direct fill fallback (bypasses sticky headers / intercepts)
                    locator.evaluate(
                        "(el, v) => { el.focus(); el.value = v; el.dispatchEvent(new Event('input', {bubbles: true})); el.dispatchEvent(new Event('change', {bubbles: true})); el.blur(); }",
                        val
                    )
                return True

            elif action_type == ActionType.UPLOAD:
                if not action.value:
                    raise ExecutionError("Upload action requires a file path.")
                try:
                    locator.set_input_files(action.value)
                    return True
                except Exception as ex:
                    # If setting directly on input failed, try expect_file_chooser via click
                    try:
                        with self.page.expect_file_chooser(timeout=3000) as fc_info:
                            locator.click()
                        fc_info.value.set_files(action.value)
                        return True
                    except Exception:
                        raise ex

            elif action_type == ActionType.SELECT:
                locator.scroll_into_view_if_needed(timeout=2000)
                target = (action.value or "").strip()
                selected = False

                # 1. Exact label match
                try:
                    locator.select_option(label=target, timeout=800)
                    selected = True
                except Exception:
                    pass

                # 2. Exact value match
                if not selected:
                    try:
                        locator.select_option(value=target, timeout=800)
                        selected = True
                    except Exception:
                        pass

                # 3. Fuzzy match by partial text or dial code in options
                if not selected:
                    try:
                        best_val = locator.evaluate(
                            """(sel, targetStr) => {
                                const t = targetStr.toLowerCase();
                                // Direct text substring
                                for (const opt of sel.options) {
                                    const txt = (opt.text || '').toLowerCase();
                                    if (txt.includes(t)) return opt.value;
                                }
                                // Dial code fallback (49 or +49)
                                if (t.includes('49') || t.includes('deutschland')) {
                                    for (const opt of sel.options) {
                                        if (opt.value === '49' || (opt.text && opt.text.includes('(49)'))) return opt.value;
                                    }
                                }
                                return null;
                            }""",
                            target
                        )
                        if best_val is not None:
                            locator.select_option(value=best_val, timeout=1200)
                            selected = True
                    except Exception:
                        pass

                if not selected:
                    raise ExecutionError(f"Could not find matching option for '{target}' in select element [{action.element_id}].")
                return True

            elif action_type in (ActionType.CLICK, ActionType.CLICK_NON_TERMINAL):
                locator.scroll_into_view_if_needed(timeout=3000)
                # Re-check button text directly from DOM at execution time
                dom_text = (locator.inner_text() or "").strip()
                if any(w in dom_text.lower() for w in ["absenden", "jetzt bewerben", "kostenpflichtig", "submit application"]):
                    raise HumanApprovalRequired(
                        f"DEFENSE-IN-DEPTH: Live DOM button text '{dom_text}' is TERMINAL. Clic blocked.",
                        element,
                    )
                try:
                    locator.click(timeout=3000)
                except Exception:
                    try:
                        locator.click(force=True, timeout=1500)
                    except Exception:
                        locator.evaluate("el => el.click()")
                self.page.wait_for_timeout(1000)
                return True

            else:
                raise ExecutionError(f"Unsupported action type: {action_type}")

        except HumanApprovalRequired:
            raise
        except Exception as e:
            raise ExecutionError(f"Failed executing {action_type} on element [{action.element_id}]: {str(e)}") from e
