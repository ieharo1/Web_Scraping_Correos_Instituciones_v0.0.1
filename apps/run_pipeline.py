from __future__ import annotations

import argparse
import asyncio
from datetime import datetime
from pathlib import Path

from common import ensure_dir, project_root, write_ndjson
from report import write_report
from scraper import AsyncScraper, load_source_profile
from transform import build_lakehouse


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Pipeline de web scraping orientado a Big Data")
    parser.add_argument("--mode", choices=["auto", "live", "local"], default="auto")
    return parser.parse_args()


def output_paths(run_id: str) -> dict[str, Path]:
    root = project_root()
    return {
        "pages": root / "data" / "raw" / f"pages_{run_id}.ndjson",
        "contacts": root / "data" / "raw" / f"contacts_{run_id}.ndjson",
        "edges": root / "data" / "raw" / f"edges_{run_id}.ndjson",
        "db": root / "data" / "lakehouse" / "contact_lakehouse.db",
        "bronze_csv": root / "data" / "lakehouse" / "bronze" / f"contacts_{run_id}.csv",
        "silver_csv": root / "data" / "lakehouse" / "silver" / f"emails_{run_id}.csv",
        "gold_domain_csv": root / "data" / "lakehouse" / "gold" / f"domain_kpis_{run_id}.csv",
        "gold_institution_csv": root / "data" / "lakehouse" / "gold" / f"institution_kpis_{run_id}.csv",
        "gold_graph_csv": root / "data" / "lakehouse" / "gold" / f"graph_kpis_{run_id}.csv",
        "report_txt": root / "data" / "outputs" / "metrics_report.txt",
        "report_json": root / "data" / "outputs" / "metrics_report.json",
    }


async def execute_scraper(mode: str) -> tuple[dict[str, list[dict]], str, bool]:
    fallback_triggered = False

    if mode == "auto":
        selected_mode = "live"
    else:
        selected_mode = mode

    seeds, settings = load_source_profile(selected_mode)
    scraper = AsyncScraper(
        max_depth=int(settings.get("max_depth", 2)),
        max_pages=int(settings.get("max_pages", 120)),
        concurrency=int(settings.get("concurrency", 10)),
        timeout_seconds=int(settings.get("timeout_seconds", 15)),
        same_domain_only=bool(settings.get("same_domain_only", True)),
    )
    crawl_data = await scraper.crawl(seeds)

    if mode == "auto" and (len(crawl_data["pages"]) <= 2 or len(crawl_data["contacts"]) == 0):
        fallback_triggered = True
        local_seeds, _ = load_source_profile("local")
        crawl_data = await scraper.crawl(local_seeds)
        selected_mode = "local"

    return crawl_data, selected_mode, fallback_triggered


def main() -> None:
    args = parse_args()
    run_id = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    paths = output_paths(run_id)

    for key in ["pages", "contacts", "edges", "bronze_csv", "silver_csv", "gold_domain_csv", "gold_institution_csv", "gold_graph_csv", "report_txt", "report_json"]:
        ensure_dir(paths[key].parent)

    crawl_data, mode_used, fallback = asyncio.run(execute_scraper(args.mode))

    write_ndjson(paths["pages"], crawl_data["pages"])
    write_ndjson(paths["contacts"], crawl_data["contacts"])
    write_ndjson(paths["edges"], crawl_data["edges"])

    stats = build_lakehouse(
        contacts_path=paths["contacts"],
        edges_path=paths["edges"],
        db_path=paths["db"],
        bronze_csv=paths["bronze_csv"],
        silver_csv=paths["silver_csv"],
        gold_domain_csv=paths["gold_domain_csv"],
        gold_institution_csv=paths["gold_institution_csv"],
        gold_graph_csv=paths["gold_graph_csv"],
    )

    payload = {
        "run_id": run_id,
        "mode_used": mode_used,
        "fallback_triggered": fallback,
        "pages_crawled": len(crawl_data["pages"]),
        "contacts_raw": len(crawl_data["contacts"]),
        "edges_raw": len(crawl_data["edges"]),
        **stats,
    }
    write_report(paths["report_txt"], paths["report_json"], payload)

    print("Pipeline completado")
    print(payload)


if __name__ == "__main__":
    main()
