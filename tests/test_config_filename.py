# -*- coding: utf-8 -*-
"""Config filename sanitization (Phase 3) tests."""

from xpath_explorer.mixins.data.files import _safe_config_filename


def test_safe_config_filename_strips_path_characters():
    assert _safe_config_filename("a/b\\c:d*e?f\"g<h>i|j") == "a_b_c_d_e_f_g_h_i_j"


def test_safe_config_filename_falls_back_when_empty():
    assert _safe_config_filename("") == "xpath_config"
    assert _safe_config_filename("...") == "xpath_config"


def test_safe_config_filename_keeps_normal_names():
    assert _safe_config_filename("인터파크_20260101") == "인터파크_20260101"
