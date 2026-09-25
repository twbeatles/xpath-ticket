# -*- coding: utf-8 -*-
"""Shipped-JS regression guards (codepoint-precise, no browser needed).

Background: the XPath-literal quote token and the CSS-escape backslash were
mangled by Python string-escape processing on their way into the browser
(`"'\\"'"` collapsing into an unterminated JS string, `'\\\\'` collapsing
into `'\''`), so `scan_elements` threw V8 SyntaxError on every frame and the
picker injection never compiled. Mocks never caught it because they stub out
`eval_on_selector_all`/`execute_script`; only real-engine execution did
(see /tmp/e2e_verify logs). These tests pin the RUNTIME strings at codepoint
level -- displays and editors render backslash runs ambiguously, chr() does not.
"""

import sys

sys.path.insert(0, ".")  # noqa: E402  (repo root for direct import)

from xpath_explorer.browser.playwright_scan import (  # noqa: E402
    PlaywrightScanMixin,
)
from xpath_explorer.core.browser_assets.picker import (  # noqa: E402
    PICKER_SCRIPT,
)


def _scan_expr():
    consts = [
        c
        for c in PlaywrightScanMixin.scan_elements.__code__.co_consts
        if isinstance(c, str) and "buildXPath" in c
    ]
    assert len(consts) == 1
    return consts[0]


# Runtime JS for the 1-char double-quote token: tokens.push('"');
FIXED_PUSH = "tokens.push(" + chr(39) + chr(34) + chr(39) + ");"
# Broken runtime (unterminated string): tokens.push("'"'");
BROKEN_PUSH = (
    "tokens.push("
    + chr(34)
    + chr(39)
    + chr(34)
    + chr(39)
    + chr(34)
    + ");"
)
# Runtime JS for prepending one backslash: return '\\' + ch;
FIXED_ESCAPE = "return " + chr(39) + chr(92) * 2 + chr(39) + " + ch;"
# Broken runtime (unterminated string): return '\'' + ch;
BROKEN_ESCAPE = "return " + chr(39) + chr(92) + chr(39) + " + ch;"


def test_scan_expression_has_valid_quote_token():
    expr = _scan_expr()
    assert BROKEN_PUSH not in expr
    assert FIXED_PUSH in expr
    # Hardened generator still present (id/placeholder/aria/class relays).
    assert "data-testid" in expr


def test_picker_script_has_valid_quote_token():
    assert BROKEN_PUSH not in PICKER_SCRIPT
    assert FIXED_PUSH in PICKER_SCRIPT


def test_picker_escape_prepends_single_backslash():
    assert BROKEN_ESCAPE not in PICKER_SCRIPT
    assert FIXED_ESCAPE in PICKER_SCRIPT
