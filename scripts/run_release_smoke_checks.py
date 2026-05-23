# -*- coding: utf-8 -*-
"""Release-oriented smoke checks."""

from __future__ import annotations

import argparse
import importlib
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple
from urllib.error import URLError
from urllib.request import Request, urlopen

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from xpath_explorer.browser.dom_export import (
    DomSnapshot,
    diff_dom_snapshots,
    render_dom_diff_report_htm,
    render_dom_report_htm,
)


@dataclass(frozen=True)
class SmokeResult:
    name: str
    success: bool
    detail: str


def load_spec_text(spec_path: Path) -> str:
    return spec_path.read_text(encoding="utf-8")


def check_tls_excludes(spec_text: str) -> Tuple[bool, List[str]]:
    block_match = re.search(r"qt_excludes\s*=\s*\[(?P<body>.*?)\]", spec_text, flags=re.DOTALL)
    if block_match:
        body = block_match.group("body")
        entries = [m.group(1).lower() for m in re.finditer(r"['\"]([^'\"]+)['\"]", body)]
        blocked = [token for token in ("libcrypto", "libssl") if token in entries]
    else:
        # Fallback: conservative full text scan (legacy format compatibility).
        lowered = spec_text.lower()
        blocked = [token for token in ("libcrypto", "libssl") if token in lowered]
    return len(blocked) == 0, blocked


def run_https_smoke(url: str = "https://example.com", timeout: float = 5.0) -> Tuple[bool, str]:
    request = Request(url, headers={"User-Agent": "XPathExplorerReleaseSmoke/1.0"})
    try:
        with urlopen(request, timeout=timeout) as response:
            code = int(getattr(response, "status", 200))
            if 200 <= code < 400:
                return True, f"HTTP {code}"
            return False, f"Unexpected HTTP status: {code}"
    except URLError as e:
        return False, f"HTTPS request failed: {e}"
    except Exception as e:
        return False, f"HTTPS smoke error: {e}"


def run_dom_report_smoke() -> Tuple[bool, str]:
    baseline = [
        DomSnapshot(
            engine="selenium",
            window_id="w1",
            window_title="Example",
            window_url="https://example.com",
            is_popup=False,
            frame_path="main",
            frame_label="main",
            document_url="https://example.com",
            html="<html><body><h1>Old</h1></body></html>",
        )
    ]
    current = [
        DomSnapshot(
            engine="selenium",
            window_id="w1",
            window_title="Example",
            window_url="https://example.com",
            is_popup=False,
            frame_path="main",
            frame_label="main",
            document_url="https://example.com",
            html="<html><body><h1>New</h1></body></html>",
        )
    ]
    try:
        report = render_dom_report_htm(current, source_label="Selenium")
        diff_report = render_dom_diff_report_htm(baseline, current, source_label="Selenium DOM")
        entries = diff_dom_snapshots(baseline, current)
        if "<html" not in report.lower() or "DOM Export Report" not in report:
            return False, "DOM export renderer output is invalid."
        if "<html" not in diff_report.lower() or "DOM Diff Report" not in diff_report:
            return False, "DOM diff renderer output is invalid."
        if not entries:
            return False, "DOM diff smoke expected at least one changed entry."
        return True, f"rendered {len(current)} snapshots / {len(entries)} diff entries"
    except Exception as e:
        return False, f"DOM report smoke failed: {e}"


def check_optional_imports() -> Dict[str, bool]:
    modules = {
        "openai": "openai",
        "google-genai": "google.genai",
        "playwright": "playwright",
    }
    results: Dict[str, bool] = {}
    for label, module_name in modules.items():
        try:
            importlib.import_module(module_name)
            results[label] = True
        except Exception:
            results[label] = False
    return results


def run_pyinstaller_build_smoke(repo_root: Path, timeout_seconds: float = 900.0) -> SmokeResult:
    spec_path = repo_root / "packaging" / "pyinstaller" / "xpath_explorer.spec"
    cmd = [sys.executable, "-m", "PyInstaller", str(spec_path)]
    try:
        completed = subprocess.run(
            cmd,
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired:
        return SmokeResult("pyinstaller_build", False, "PyInstaller build timed out.")
    except Exception as e:
        return SmokeResult("pyinstaller_build", False, f"PyInstaller build failed to start: {e}")

    if completed.returncode == 0:
        return SmokeResult("pyinstaller_build", True, "PyInstaller build completed.")
    detail = (completed.stderr or completed.stdout or "").strip().splitlines()
    tail = " | ".join(detail[-5:]) if detail else f"exit code {completed.returncode}"
    return SmokeResult("pyinstaller_build", False, tail)


def run_checks(
    repo_root: Path,
    strict_optional_imports: bool = False,
    build_exe: bool = False,
) -> List[SmokeResult]:
    results: List[SmokeResult] = []

    spec_path = repo_root / "packaging" / "pyinstaller" / "xpath_explorer.spec"
    try:
        spec_text = load_spec_text(spec_path)
        ok, blocked = check_tls_excludes(spec_text)
        if ok:
            results.append(SmokeResult("pyinstaller_tls_excludes", True, "TLS libraries are not excluded."))
        else:
            results.append(
                SmokeResult(
                    "pyinstaller_tls_excludes",
                    False,
                    f"Found blocked tokens in exclude list: {', '.join(blocked)}",
                )
            )
    except Exception as e:
        results.append(SmokeResult("pyinstaller_tls_excludes", False, f"Spec check failed: {e}"))

    https_ok, https_detail = run_https_smoke()
    results.append(SmokeResult("https_smoke", https_ok, https_detail))

    dom_ok, dom_detail = run_dom_report_smoke()
    results.append(SmokeResult("dom_report_smoke", dom_ok, dom_detail))

    import_status = check_optional_imports()
    missing = sorted(name for name, ok in import_status.items() if not ok)
    if missing and strict_optional_imports:
        results.append(
            SmokeResult(
                "optional_imports",
                False,
                f"Missing optional dependencies: {', '.join(missing)}",
            )
        )
    else:
        detail = "all optional dependencies importable"
        if missing:
            detail = f"missing optional dependencies (non-fatal): {', '.join(missing)}"
        results.append(SmokeResult("optional_imports", True, detail))

    if build_exe:
        results.append(run_pyinstaller_build_smoke(repo_root))

    return results


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run release smoke checks.")
    parser.add_argument(
        "--strict-optional-imports",
        action="store_true",
        help="Treat optional dependency import misses as failures.",
    )
    parser.add_argument(
        "--build-exe",
        action="store_true",
        help="Run a real PyInstaller build smoke. This is slower and writes build/dist artifacts.",
    )
    args = parser.parse_args(argv)

    repo_root = Path(__file__).resolve().parents[1]
    results = run_checks(
        repo_root,
        strict_optional_imports=args.strict_optional_imports,
        build_exe=args.build_exe,
    )

    failed = [r for r in results if not r.success]
    for result in results:
        status = "PASS" if result.success else "FAIL"
        print(f"[{status}] {result.name}: {result.detail}")

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
