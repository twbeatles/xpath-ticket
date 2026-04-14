# -*- coding: utf-8 -*-
"""DOM snapshot export helpers for Selenium/Playwright flows."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from html import escape
import difflib


@dataclass
class DomSnapshot:
    """Captured DOM metadata for a single window/frame document."""

    engine: str
    window_id: str
    window_title: str
    window_url: str
    is_popup: bool
    frame_path: str
    frame_label: str
    document_url: str
    html: str
    error: str = ""
    error_type: str = ""


@dataclass(frozen=True)
class DomDiffEntry:
    """DOM snapshot comparison result per document key."""

    key: str
    change_type: str  # added, removed, changed
    window_title: str
    frame_path: str
    document_url: str
    old_size: int = 0
    new_size: int = 0
    similarity: float = 0.0
    old_error: str = ""
    new_error: str = ""


def _safe(value: str) -> str:
    return escape(value or "")


def render_dom_report_htm(
    snapshots: list[DomSnapshot],
    source_label: str,
    generated_at_iso: str | None = None,
    scope: str = "all",
    selected_window_title: str = "",
    selected_window_url: str = "",
) -> str:
    """Render a standalone HTM report with all captured DOM documents."""

    if generated_at_iso is None:
        generated_at_iso = datetime.now().isoformat(timespec="seconds")

    total_count = len(snapshots)
    fail_count = sum(1 for s in snapshots if s.error)
    engines = sorted({s.engine for s in snapshots if s.engine})
    engine_text = ", ".join(engines) if engines else "-"
    error_types: dict[str, int] = {}
    for snapshot in snapshots:
        if not snapshot.error_type:
            continue
        error_types[snapshot.error_type] = error_types.get(snapshot.error_type, 0) + 1

    parts: list[str] = []
    parts.append("<!DOCTYPE html>")
    parts.append("<html lang='ko'>")
    parts.append("<head>")
    parts.append("  <meta charset='utf-8'>")
    parts.append("  <meta name='viewport' content='width=device-width, initial-scale=1'>")
    parts.append(f"  <title>{_safe(source_label)} DOM Export Report</title>")
    parts.append("  <style>")
    parts.append("    :root { color-scheme: light; }")
    parts.append("    body { font-family: 'Segoe UI', sans-serif; margin: 20px; line-height: 1.45; }")
    parts.append("    h1, h2, h3 { margin: 0 0 10px 0; }")
    parts.append("    .meta { margin: 4px 0; color: #333; }")
    parts.append("    .summary { margin: 12px 0 20px; padding: 10px; background: #f6f8fa; border: 1px solid #d0d7de; border-radius: 6px; }")
    parts.append("    .toc { margin: 0 0 24px; padding: 12px; background: #fafbfc; border: 1px solid #d8dee4; border-radius: 6px; }")
    parts.append("    .toc li { margin: 4px 0; }")
    parts.append("    .snapshot { margin: 20px 0; padding: 12px; border: 1px solid #d0d7de; border-radius: 8px; }")
    parts.append("    .label { display: inline-block; padding: 2px 8px; border-radius: 999px; background: #eaeef2; font-size: 12px; margin-right: 6px; }")
    parts.append("    .popup { background: #fff2cc; }")
    parts.append("    .main { background: #ddeeff; }")
    parts.append("    .error { margin: 10px 0; padding: 10px; background: #fff1f0; border: 1px solid #ffccc7; border-radius: 6px; color: #a8071a; }")
    parts.append("    details { margin-top: 12px; }")
    parts.append("    pre { margin: 8px 0 0; padding: 12px; background: #0f1720; color: #e5e7eb; border-radius: 6px; overflow: auto; white-space: pre-wrap; word-break: break-word; }")
    parts.append("    a { color: #0969da; text-decoration: none; }")
    parts.append("    a:hover { text-decoration: underline; }")
    parts.append("  </style>")
    parts.append("</head>")
    parts.append("<body>")
    parts.append(f"  <h1>{_safe(source_label)} DOM Export Report</h1>")
    parts.append("  <div class='summary'>")
    parts.append(f"    <div class='meta'><strong>Generated At:</strong> {_safe(generated_at_iso)}</div>")
    parts.append(f"    <div class='meta'><strong>Engine:</strong> {_safe(engine_text)}</div>")
    parts.append(f"    <div class='meta'><strong>Scope:</strong> {_safe(scope)}</div>")
    if selected_window_title:
        parts.append(f"    <div class='meta'><strong>Selected Window:</strong> {_safe(selected_window_title)}</div>")
    if selected_window_url:
        parts.append(f"    <div class='meta'><strong>Selected URL:</strong> {_safe(selected_window_url)}</div>")
    parts.append(f"    <div class='meta'><strong>Total Documents:</strong> {total_count}</div>")
    parts.append(f"    <div class='meta'><strong>Failed Documents:</strong> {fail_count}</div>")
    if error_types:
        summary = ", ".join(f"{key}={value}" for key, value in sorted(error_types.items()))
        parts.append(f"    <div class='meta'><strong>Error Types:</strong> {_safe(summary)}</div>")
    parts.append("  </div>")

    parts.append("  <div class='toc'>")
    parts.append("    <h2>목차</h2>")
    parts.append("    <ol>")
    for idx, snap in enumerate(snapshots, start=1):
        popup_text = "[팝업] " if snap.is_popup else ""
        title = snap.window_title or "(untitled)"
        frame = snap.frame_label or snap.frame_path or "main"
        marker = " (실패)" if snap.error else ""
        parts.append(
            f"      <li><a href='#doc-{idx}'>{_safe(popup_text + title)} / {_safe(frame)}{_safe(marker)}</a></li>"
        )
    if not snapshots:
        parts.append("      <li>수집된 DOM이 없습니다.</li>")
    parts.append("    </ol>")
    parts.append("  </div>")

    for idx, snap in enumerate(snapshots, start=1):
        popup_cls = "popup" if snap.is_popup else "main"
        popup_text = "팝업" if snap.is_popup else "메인"
        frame_text = snap.frame_label or snap.frame_path or "main"
        dom_html = _safe(snap.html)
        parts.append(f"  <section class='snapshot' id='doc-{idx}'>")
        parts.append(f"    <h3>{idx}. {_safe(snap.window_title or '(untitled)')}</h3>")
        parts.append("    <div>")
        parts.append(f"      <span class='label {popup_cls}'>{popup_text}</span>")
        parts.append(f"      <span class='label'>{_safe(snap.engine)}</span>")
        parts.append(f"      <span class='label'>{_safe(frame_text)}</span>")
        parts.append("    </div>")
        parts.append(f"    <div class='meta'><strong>Window ID:</strong> {_safe(snap.window_id)}</div>")
        parts.append(f"    <div class='meta'><strong>Window URL:</strong> {_safe(snap.window_url)}</div>")
        parts.append(f"    <div class='meta'><strong>Document URL:</strong> {_safe(snap.document_url)}</div>")
        if snap.error:
            error_type = f" ({snap.error_type})" if snap.error_type else ""
            parts.append(f"    <div class='error'><strong>수집 실패{_safe(error_type)}:</strong> {_safe(snap.error)}</div>")
        parts.append("    <details open>")
        parts.append("      <summary><strong>DOM 원문</strong></summary>")
        parts.append(f"      <pre>{dom_html}</pre>")
        parts.append("    </details>")
        parts.append("  </section>")

    parts.append("</body>")
    parts.append("</html>")
    return "\n".join(parts)


def _snapshot_key(snapshot: DomSnapshot) -> str:
    base_url = snapshot.document_url or snapshot.window_url
    frame_path = snapshot.frame_path or "main"
    return f"{snapshot.window_id}|{frame_path}|{base_url}"


def diff_dom_snapshots(
    old_snapshots: list[DomSnapshot],
    new_snapshots: list[DomSnapshot],
) -> list[DomDiffEntry]:
    """Compare old/new snapshots and return added/removed/changed entries."""
    old_map = {_snapshot_key(s): s for s in old_snapshots}
    new_map = {_snapshot_key(s): s for s in new_snapshots}
    entries: list[DomDiffEntry] = []

    for key in sorted(new_map.keys() - old_map.keys()):
        snap = new_map[key]
        entries.append(
            DomDiffEntry(
                key=key,
                change_type="added",
                window_title=snap.window_title,
                frame_path=snap.frame_path or "main",
                document_url=snap.document_url or snap.window_url,
                old_size=0,
                new_size=len(snap.html or ""),
                similarity=0.0,
                old_error="",
                new_error=snap.error or "",
            )
        )

    for key in sorted(old_map.keys() - new_map.keys()):
        snap = old_map[key]
        entries.append(
            DomDiffEntry(
                key=key,
                change_type="removed",
                window_title=snap.window_title,
                frame_path=snap.frame_path or "main",
                document_url=snap.document_url or snap.window_url,
                old_size=len(snap.html or ""),
                new_size=0,
                similarity=0.0,
                old_error=snap.error or "",
                new_error="",
            )
        )

    for key in sorted(old_map.keys() & new_map.keys()):
        old = old_map[key]
        new = new_map[key]
        if (
            (old.html or "") == (new.html or "")
            and (old.error or "") == (new.error or "")
            and (old.document_url or "") == (new.document_url or "")
        ):
            continue

        old_html = old.html or ""
        new_html = new.html or ""
        if old_html and new_html:
            sample_size = 50000
            similarity = difflib.SequenceMatcher(
                None,
                old_html[:sample_size],
                new_html[:sample_size],
            ).ratio()
        else:
            similarity = 0.0

        entries.append(
            DomDiffEntry(
                key=key,
                change_type="changed",
                window_title=new.window_title or old.window_title,
                frame_path=new.frame_path or old.frame_path or "main",
                document_url=new.document_url or old.document_url or new.window_url or old.window_url,
                old_size=len(old_html),
                new_size=len(new_html),
                similarity=similarity,
                old_error=old.error or "",
                new_error=new.error or "",
            )
        )

    return entries


def render_dom_diff_report_htm(
    old_snapshots: list[DomSnapshot],
    new_snapshots: list[DomSnapshot],
    source_label: str,
    generated_at_iso: str | None = None,
) -> str:
    """Render HTM report that summarizes diff between old/new DOM snapshots."""
    if generated_at_iso is None:
        generated_at_iso = datetime.now().isoformat(timespec="seconds")

    entries = diff_dom_snapshots(old_snapshots, new_snapshots)
    added = sum(1 for e in entries if e.change_type == "added")
    removed = sum(1 for e in entries if e.change_type == "removed")
    changed = sum(1 for e in entries if e.change_type == "changed")
    unchanged = max(0, min(len(old_snapshots), len(new_snapshots)) - changed)

    parts: list[str] = []
    parts.append("<!DOCTYPE html>")
    parts.append("<html lang='ko'>")
    parts.append("<head>")
    parts.append("  <meta charset='utf-8'>")
    parts.append("  <meta name='viewport' content='width=device-width, initial-scale=1'>")
    parts.append(f"  <title>{_safe(source_label)} DOM Diff Report</title>")
    parts.append("  <style>")
    parts.append("    body { font-family: 'Segoe UI', sans-serif; margin: 20px; line-height: 1.45; }")
    parts.append("    .summary { margin: 12px 0 20px; padding: 10px; background: #f6f8fa; border: 1px solid #d0d7de; border-radius: 6px; }")
    parts.append("    .chip { display: inline-block; margin-right: 8px; padding: 3px 8px; border-radius: 999px; font-size: 12px; }")
    parts.append("    .added { background: #dcfce7; }")
    parts.append("    .removed { background: #fee2e2; }")
    parts.append("    .changed { background: #fef3c7; }")
    parts.append("    .table { width: 100%; border-collapse: collapse; }")
    parts.append("    .table th, .table td { border: 1px solid #d0d7de; padding: 8px; text-align: left; vertical-align: top; }")
    parts.append("    .table th { background: #f3f4f6; }")
    parts.append("    .mono { font-family: 'Consolas', monospace; word-break: break-all; }")
    parts.append("  </style>")
    parts.append("</head>")
    parts.append("<body>")
    parts.append(f"  <h1>{_safe(source_label)} DOM Diff Report</h1>")
    parts.append("  <div class='summary'>")
    parts.append(f"    <div><strong>Generated At:</strong> {_safe(generated_at_iso)}</div>")
    parts.append(f"    <div><strong>Baseline Documents:</strong> {len(old_snapshots)}</div>")
    parts.append(f"    <div><strong>Current Documents:</strong> {len(new_snapshots)}</div>")
    parts.append("    <div style='margin-top:8px;'>")
    parts.append(f"      <span class='chip added'>추가 {added}</span>")
    parts.append(f"      <span class='chip removed'>삭제 {removed}</span>")
    parts.append(f"      <span class='chip changed'>변경 {changed}</span>")
    parts.append(f"      <span class='chip'>변경없음 {unchanged}</span>")
    parts.append("    </div>")
    parts.append("  </div>")

    parts.append("  <table class='table'>")
    parts.append("    <thead>")
    parts.append("      <tr><th>변경</th><th>창/프레임</th><th>문서 URL</th><th>크기(이전→현재)</th><th>유사도</th><th>오류 변화</th></tr>")
    parts.append("    </thead>")
    parts.append("    <tbody>")
    if entries:
        for entry in entries:
            kind = {"added": "추가", "removed": "삭제", "changed": "변경"}.get(entry.change_type, entry.change_type)
            size_text = f"{entry.old_size} → {entry.new_size}"
            similarity_text = "-" if entry.change_type != "changed" else f"{entry.similarity * 100:.1f}%"
            error_text = ""
            if entry.old_error or entry.new_error:
                error_text = f"{entry.old_error or '-'} → {entry.new_error or '-'}"
            parts.append("      <tr>")
            parts.append(f"        <td>{_safe(kind)}</td>")
            parts.append(f"        <td>{_safe(entry.window_title)} / {_safe(entry.frame_path)}</td>")
            parts.append(f"        <td class='mono'>{_safe(entry.document_url)}</td>")
            parts.append(f"        <td>{size_text}</td>")
            parts.append(f"        <td>{similarity_text}</td>")
            parts.append(f"        <td>{_safe(error_text)}</td>")
            parts.append("      </tr>")
    else:
        parts.append("      <tr><td colspan='6'>변경된 DOM 문서가 없습니다.</td></tr>")
    parts.append("    </tbody>")
    parts.append("  </table>")
    parts.append("</body>")
    parts.append("</html>")
    return "\n".join(parts)
