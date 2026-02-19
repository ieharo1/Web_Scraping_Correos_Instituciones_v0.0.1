from __future__ import annotations

import json
import subprocess
from pathlib import Path

from common import project_root


def main() -> None:
    root = project_root()
    result = subprocess.run(
        ["python", "apps/run_pipeline.py", "--mode", "local"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise SystemExit(f"Pipeline fallo:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}")

    report_path = root / "data" / "outputs" / "metrics_report.json"
    if not report_path.exists():
        raise SystemExit("No existe metrics_report.json")

    data = json.loads(report_path.read_text(encoding="utf-8"))
    checks = {
        "pages_crawled": data.get("pages_crawled", 0) > 0,
        "contacts_raw": data.get("contacts_raw", 0) > 0,
        "silver_rows": data.get("silver_rows", 0) > 0,
        "gold_domain_rows": data.get("gold_domain_rows", 0) > 0,
    }

    failed = [key for key, ok in checks.items() if not ok]
    if failed:
        raise SystemExit(f"Validacion fallida en: {failed}\nReporte: {data}")

    print("Validacion OK")
    print(data)


if __name__ == "__main__":
    main()
