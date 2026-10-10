"""
DOM Indexer
Injects deterministic numeric IDs (data-agent-id="1", "2"...) into visible interactive elements
in the Playwright page and detects active validation errors ("Diese Angabe ist erforderlich").
"""
from typing import List, Optional, Tuple
from .action_schema import IndexedElement
from .terminal_guard import is_terminal_element

JS_INDEXER_SCRIPT = """
() => {
    // Clean any prior agent index marks
    const prior = document.querySelectorAll('[data-agent-id]');
    prior.forEach(el => el.removeAttribute('data-agent-id'));

    const interactiveSelectors = [
        'input',
        'textarea',
        'select',
        'button',
        'a[href]',
        '[role="button"]',
        '[role="checkbox"]',
        '[role="radio"]',
        '[role="combobox"]',
        '[role="listbox"]',
        '[role="option"]',
        '[role="switch"]',
        '[role="tab"]',
        '[contenteditable="true"]',
        'label'
    ];

    const candidates = Array.from(document.querySelectorAll(interactiveSelectors.join(',')));
    const results = [];
    let counter = 1;

    for (const el of candidates) {
        const tag = el.tagName.toLowerCase();
        const type = (el.getAttribute('type') || '').toLowerCase();
        
        // Skip hidden inputs (except file inputs, which frameworks often hide visually behind custom buttons)
        if (tag === 'input' && type === 'hidden') continue;

        const rect = el.getBoundingClientRect();
        const style = window.getComputedStyle(el);
        const isFile = (tag === 'input' && type === 'file');

        const isDisplayed = style.display !== 'none' && style.visibility !== 'hidden' && parseFloat(style.opacity || '1') > 0;
        const hasSize = (rect.width > 2 && rect.height > 2) || isFile;
        const isVisible = (isDisplayed && hasSize) || isFile;

        if (!isVisible && !isFile) continue;

        // Skip labels that wrap an input (to avoid duplicates) unless they represent styled switches/radios
        if (tag === 'label' && el.querySelector('input')) {
            continue;
        }

        const agentId = counter++;
        el.setAttribute('data-agent-id', String(agentId));

        let text = (el.innerText || el.textContent || '').trim();
        let options = [];

        if (isFile) {
            // Find nearby dropzone heading or label
            const container = el.closest('div, section, fieldset, li') || el.parentElement;
            if (container) {
                const heading = container.querySelector('h1, h2, h3, h4, h5, h6, label, p, strong, [class*="title"], [class*="label"], [class*="header"]');
                if (heading && heading.innerText) {
                    text = heading.innerText.trim();
                } else {
                    text = (container.innerText || '').substring(0, 80).trim();
                }
            }
        } else if (tag === 'input' || tag === 'textarea' || tag === 'select') {
            // Find associated label or question
            let fieldLabel = '';
            if (el.id) {
                try {
                    const lbl = document.querySelector('label[for="' + CSS.escape(el.id) + '"]');
                    if (lbl && lbl.innerText) fieldLabel = lbl.innerText.trim();
                } catch(e) {}
            }
            if (!fieldLabel) {
                const parentLbl = el.closest('label');
                if (parentLbl && parentLbl.innerText) fieldLabel = parentLbl.innerText.trim();
            }
            if (!fieldLabel && el.getAttribute('aria-labelledby')) {
                try {
                    const lbl = document.getElementById(el.getAttribute('aria-labelledby'));
                    if (lbl && lbl.innerText) fieldLabel = lbl.innerText.trim();
                } catch(e) {}
            }

            // For radios and checkboxes, combine question title + option text
            if (type === 'radio' || type === 'checkbox') {
                let groupQuestion = '';
                const container = el.closest('fieldset, .form-group, .field, [class*="radio-group"], [class*="form-row"], [class*="group"], tr, div');
                if (container) {
                    const legend = container.querySelector('legend, [class*="label"], [class*="title"], h3, h4, h5, strong');
                    if (legend && legend.innerText && !legend.contains(el)) {
                        groupQuestion = legend.innerText.trim();
                    }
                }
                if (groupQuestion && fieldLabel && groupQuestion !== fieldLabel) {
                    text = groupQuestion + ' -> ' + fieldLabel;
                } else if (fieldLabel) {
                    text = fieldLabel;
                } else if (groupQuestion) {
                    text = groupQuestion;
                }
            } else {
                if (!text && fieldLabel) {
                    text = fieldLabel;
                }
                if (!text) {
                    const container = el.closest('.form-group, .field, [class*="form-row"], tr, div');
                    if (container) {
                        const heading = container.querySelector('label, [class*="label"], [class*="title"], strong');
                        if (heading && heading.innerText && !heading.contains(el)) {
                            text = heading.innerText.trim();
                        }
                    }
                }
            }

            // For select dropdowns, capture available options
            if (tag === 'select') {
                try {
                    options = Array.from(el.querySelectorAll('option'))
                        .map(o => (o.innerText || o.textContent || '').trim())
                        .filter(t => t.length > 0 && !t.startsWith('--'));
                } catch(e) {}
            }
        }

        if (text.length > 140) {
            text = text.substring(0, 140) + '...';
        }

        const classStr = String(el.className || '').toLowerCase();
        const isSelected = el.getAttribute('aria-pressed') === 'true' ||
                           el.getAttribute('aria-selected') === 'true' ||
                           el.checked === true ||
                           classStr.includes('active') ||
                           classStr.includes('selected') ||
                           classStr.includes('checked') ||
                           classStr.includes('btn-primary');

        results.push({
            id: agentId,
            tag: tag,
            element_type: type || null,
            name: el.getAttribute('name') || null,
            placeholder: el.getAttribute('placeholder') || null,
            text: text,
            role: el.getAttribute('role') || null,
            aria_label: el.getAttribute('aria-label') || null,
            value: (el.value !== undefined && el.value !== null) ? String(el.value) : null,
            options: options,
            is_visible: isVisible,
            is_interactive: true,
            is_selected: Boolean(isSelected),
            attributes: {
                id: el.id || null,
                class: el.className ? String(el.className).substring(0, 60) : null,
                title: el.getAttribute('title') || null,
                required: el.hasAttribute('required')
            }
        });
    }

    // Detect active validation error messages (DE, EN, FR)
    const errorCandidates = Array.from(document.querySelectorAll('[class*="error"], [class*="invalid"], [role="alert"], span, p, div, small'));
    const validationErrors = [];
    for (const node of errorCandidates) {
        const txt = (node.innerText || '').trim();
        if (txt.length >= 4 && txt.length <= 150) {
            const low = txt.toLowerCase();
            if (
                low.includes('diese angabe ist erforderlich') ||
                low.includes('ist erforderlich') ||
                low.includes('pflichtfeld') ||
                low.includes('bitte füllen') ||
                low.includes('field is required') ||
                low.includes('champ obligatoire')
            ) {
                const st = window.getComputedStyle(node);
                if (st.display !== 'none' && st.visibility !== 'hidden' && !validationErrors.includes(txt)) {
                    validationErrors.push(txt);
                }
            }
        }
    }

    return {
        elements: results,
        validation_errors: validationErrors
    };
}
"""


class DOMIndexer:
    def __init__(self):
        pass

    def index_page(self, page) -> Tuple[List[IndexedElement], List[str]]:
        """
        Executes JavaScript in Playwright page to index interactive elements
        and detect active validation errors.
        """
        payload = page.evaluate(JS_INDEXER_SCRIPT)
        raw_elements = payload.get("elements", [])
        validation_errors = payload.get("validation_errors", [])
        indexed: List[IndexedElement] = []

        for item in raw_elements:
            elem = IndexedElement(
                id=item["id"],
                tag=item["tag"],
                element_type=item.get("element_type"),
                name=item.get("name"),
                placeholder=item.get("placeholder"),
                text=item.get("text", ""),
                role=item.get("role"),
                aria_label=item.get("aria_label"),
                value=item.get("value"),
                is_visible=item.get("is_visible", True),
                is_interactive=item.get("is_interactive", True),
                is_selected=item.get("is_selected", False),
                options=item.get("options", []),
                attributes=item.get("attributes", {}),
            )
            # Evaluate architectural terminal status
            elem.is_terminal = is_terminal_element(elem)
            indexed.append(elem)

        return indexed, validation_errors

    @staticmethod
    def serialize_for_observation(elements: List[IndexedElement], validation_errors: Optional[List[str]] = None) -> str:
        """
        Formats indexed elements as a clean, concise list for LLM consumption,
        prepending active validation errors if present.
        """
        lines = []
        if validation_errors:
            lines.append("⚠️ ACTIVE VALIDATION ERRORS DETECTED ON SCREEN (MUST BE RESOLVED):")
            for err in validation_errors:
                lines.append(f"  ❌ {err}")
            lines.append("--------------------------------------------------")

        for el in elements:
            lines.append(el.summary())
        return "\n".join(lines)
