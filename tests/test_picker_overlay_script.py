from xpath_explorer.core.browser_assets.picker import PICKER_SCRIPT, picker_overlay_bootstrap


def test_picker_overlay_bootstrap_sets_boolean_flag():
    assert "window.__pickerOverlay = true;" in picker_overlay_bootstrap(True)
    assert "window.__pickerOverlay = false;" in picker_overlay_bootstrap(False)


def test_picker_script_honors_overlay_flag_and_escapes_html():
    assert "window.__pickerOverlay" in PICKER_SCRIPT
    assert "function escapeHtml(" in PICKER_SCRIPT
    assert "escapeHtml(xpath)" in PICKER_SCRIPT
    assert "escapeHtml(text)" in PICKER_SCRIPT
    assert "preventDefault()" in PICKER_SCRIPT
