from xpath_explorer.tools.csv_safety import sanitize_csv_value


def test_sanitize_csv_value_prefixes_formula_injection_characters():
    assert sanitize_csv_value("=cmd|'/c calc'!A0") == "'=cmd|'/c calc'!A0"
    assert sanitize_csv_value("+1+1") == "'+1+1"
    assert sanitize_csv_value("-1+1") == "'-1+1"
    assert sanitize_csv_value("@SUM(A1)") == "'@SUM(A1)"
    assert sanitize_csv_value("\t=1+1") == "'\t=1+1"


def test_sanitize_csv_value_leaves_normal_text_unchanged():
    assert sanitize_csv_value("login_button") == "login_button"
    assert sanitize_csv_value("//button[@id='x']") == "//button[@id='x']"
    assert sanitize_csv_value("") == ""
    assert sanitize_csv_value(None) == ""
