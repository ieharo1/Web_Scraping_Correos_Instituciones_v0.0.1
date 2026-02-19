from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from common import ensure_dir, utc_now_iso


def write_report(path_txt: Path, path_json: Path, payload: dict[str, Any]) -> None:
    ensure_dir(path_txt.parent)
    ensure_dir(path_json.parent)

    lines = [
        "WEB SCRAPING BIG DATA REPORT",
        "============================",
        f"generated_at: {utc_now_iso()}",
        f"mode_used: {payload.get('mode_used')}",
        f"pages_crawled: {payload.get('pages_crawled')}",
        f"contacts_raw: {payload.get('contacts_raw')}",
        f"edges_raw: {payload.get('edges_raw')}",
        f"bronze_rows: {payload.get('bronze_rows')}",
        f"silver_rows: {payload.get('silver_rows')}",
        f"gold_domain_rows: {payload.get('gold_domain_rows')}",
        f"gold_institution_rows: {payload.get('gold_institution_rows')}",
        f"gold_graph_rows: {payload.get('gold_graph_rows')}",
        f"fallback_triggered: {payload.get('fallback_triggered')}",
    ]

    path_txt.write_text("\n".join(lines) + "\n", encoding="utf-8")
    path_json.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")
