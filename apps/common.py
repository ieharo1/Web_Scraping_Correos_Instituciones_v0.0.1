from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"(?:\+?\d{1,3}[\s.-]?)?(?:\(?\d{2,4}\)?[\s.-]?)\d{3,4}[\s.-]?\d{3,4}")


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def write_ndjson(path: Path, rows: list[dict[str, Any]]) -> None:
    ensure_dir(path.parent)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=True) + "\n")


def read_ndjson(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def normalize_email(value: str) -> str:
    return value.strip().lower()


def valid_email(value: str) -> bool:
    return bool(EMAIL_RE.fullmatch(value.strip()))


def domain_from_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme == "file":
        parts = [p for p in parsed.path.split("/") if p]
        if len(parts) >= 2:
            return parts[-2]
        return "local"
    return (parsed.netloc or "unknown").lower()


def infer_institution_type(domain: str) -> str:
    if ".edu" in domain or "univers" in domain:
        return "academia"
    if ".gob" in domain or ".gov" in domain:
        return "gobierno"
    if "municip" in domain or "alcald" in domain or "quito" in domain:
        return "municipal"
    return "otros"
