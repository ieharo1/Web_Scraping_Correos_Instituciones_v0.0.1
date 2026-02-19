from __future__ import annotations

import csv
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from common import ensure_dir, infer_institution_type, normalize_email, read_ndjson, valid_email


def _connect(db_path: Path) -> sqlite3.Connection:
    ensure_dir(db_path.parent)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _create_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS bronze_contacts (
            crawled_at TEXT,
            source_id TEXT,
            source_url TEXT,
            source_domain TEXT,
            contact_type TEXT,
            contact_value TEXT,
            depth INTEGER
        );

        CREATE TABLE IF NOT EXISTS silver_contacts (
            crawled_at TEXT,
            source_id TEXT,
            source_url TEXT,
            source_domain TEXT,
            contact_type TEXT,
            contact_value TEXT,
            institution_type TEXT,
            quality_score REAL,
            depth INTEGER
        );

        CREATE TABLE IF NOT EXISTS gold_domain_kpis (
            source_domain TEXT,
            total_contacts INTEGER,
            unique_emails INTEGER,
            institutions INTEGER,
            avg_quality_score REAL
        );

        CREATE TABLE IF NOT EXISTS gold_institution_kpis (
            source_id TEXT,
            institution_type TEXT,
            total_contacts INTEGER,
            unique_emails INTEGER
        );

        CREATE TABLE IF NOT EXISTS gold_graph_kpis (
            domain TEXT,
            in_degree INTEGER,
            out_degree INTEGER,
            pagerank REAL
        );
        """
    )


def _quality_score(email: str, domain: str) -> float:
    score = 0.5
    if domain in email:
        score += 0.35
    if any(key in email for key in ["info", "contacto", "atencion", "mesa", "secretaria"]):
        score += 0.1
    if email.count(".") >= 2:
        score += 0.05
    return min(score, 1.0)


def _pagerank(edges: list[tuple[str, str]], iterations: int = 20, damping: float = 0.85) -> dict[str, float]:
    nodes = sorted({src for src, _ in edges} | {dst for _, dst in edges})
    if not nodes:
        return {}

    outgoing: dict[str, set[str]] = defaultdict(set)
    incoming: dict[str, set[str]] = defaultdict(set)
    for src, dst in edges:
        outgoing[src].add(dst)
        incoming[dst].add(src)

    n = len(nodes)
    ranks = {node: 1.0 / n for node in nodes}

    for _ in range(iterations):
        new_ranks: dict[str, float] = {}
        for node in nodes:
            rank_sum = 0.0
            for src in incoming.get(node, set()):
                out_degree = len(outgoing.get(src, set()))
                if out_degree > 0:
                    rank_sum += ranks[src] / out_degree
            new_ranks[node] = ((1.0 - damping) / n) + damping * rank_sum
        ranks = new_ranks

    return ranks


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    ensure_dir(path.parent)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    headers = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)


def build_lakehouse(
    contacts_path: Path,
    edges_path: Path,
    db_path: Path,
    bronze_csv: Path,
    silver_csv: Path,
    gold_domain_csv: Path,
    gold_institution_csv: Path,
    gold_graph_csv: Path,
) -> dict[str, Any]:
    contacts = read_ndjson(contacts_path)
    edges_rows = read_ndjson(edges_path)

    conn = _connect(db_path)
    _create_schema(conn)

    conn.execute("DELETE FROM bronze_contacts")
    conn.execute("DELETE FROM silver_contacts")
    conn.execute("DELETE FROM gold_domain_kpis")
    conn.execute("DELETE FROM gold_institution_kpis")
    conn.execute("DELETE FROM gold_graph_kpis")

    bronze_rows = contacts
    conn.executemany(
        """
        INSERT INTO bronze_contacts (crawled_at, source_id, source_url, source_domain, contact_type, contact_value, depth)
        VALUES (:crawled_at, :source_id, :source_url, :source_domain, :contact_type, :contact_value, :depth)
        """,
        bronze_rows,
    )

    seen: set[tuple[str, str]] = set()
    silver_rows: list[dict[str, Any]] = []

    for row in bronze_rows:
        ctype = row.get("contact_type", "")
        value = str(row.get("contact_value", "")).strip()
        if ctype != "email":
            continue
        email = normalize_email(value)
        key = (row.get("source_domain", ""), email)
        if key in seen or not valid_email(email):
            continue
        seen.add(key)

        domain = row.get("source_domain", "")
        enriched = {
            **row,
            "contact_value": email,
            "institution_type": infer_institution_type(domain),
            "quality_score": _quality_score(email, domain),
        }
        silver_rows.append(enriched)

    conn.executemany(
        """
        INSERT INTO silver_contacts (
            crawled_at, source_id, source_url, source_domain, contact_type,
            contact_value, institution_type, quality_score, depth
        ) VALUES (
            :crawled_at, :source_id, :source_url, :source_domain, :contact_type,
            :contact_value, :institution_type, :quality_score, :depth
        )
        """,
        silver_rows,
    )

    by_domain: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_source: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in silver_rows:
        by_domain[row["source_domain"]].append(row)
        by_source[row["source_id"]].append(row)

    domain_kpis: list[dict[str, Any]] = []
    for domain, rows in sorted(by_domain.items()):
        domain_kpis.append(
            {
                "source_domain": domain,
                "total_contacts": len(rows),
                "unique_emails": len({r['contact_value'] for r in rows}),
                "institutions": len({r['source_id'] for r in rows}),
                "avg_quality_score": round(sum(float(r['quality_score']) for r in rows) / len(rows), 4),
            }
        )

    institution_kpis: list[dict[str, Any]] = []
    for source_id, rows in sorted(by_source.items()):
        institution_kpis.append(
            {
                "source_id": source_id,
                "institution_type": rows[0]["institution_type"] if rows else "otros",
                "total_contacts": len(rows),
                "unique_emails": len({r['contact_value'] for r in rows}),
            }
        )

    edge_pairs = [(row.get("source_domain", ""), row.get("target_domain", "")) for row in edges_rows]
    pagerank = _pagerank(edge_pairs)

    out_degree_counter = Counter(src for src, _ in edge_pairs)
    in_degree_counter = Counter(dst for _, dst in edge_pairs)

    graph_kpis: list[dict[str, Any]] = []
    for domain in sorted(set(list(out_degree_counter.keys()) + list(in_degree_counter.keys()))):
        graph_kpis.append(
            {
                "domain": domain,
                "in_degree": int(in_degree_counter.get(domain, 0)),
                "out_degree": int(out_degree_counter.get(domain, 0)),
                "pagerank": round(float(pagerank.get(domain, 0.0)), 6),
            }
        )

    conn.executemany(
        """
        INSERT INTO gold_domain_kpis (source_domain, total_contacts, unique_emails, institutions, avg_quality_score)
        VALUES (:source_domain, :total_contacts, :unique_emails, :institutions, :avg_quality_score)
        """,
        domain_kpis,
    )
    conn.executemany(
        """
        INSERT INTO gold_institution_kpis (source_id, institution_type, total_contacts, unique_emails)
        VALUES (:source_id, :institution_type, :total_contacts, :unique_emails)
        """,
        institution_kpis,
    )
    conn.executemany(
        """
        INSERT INTO gold_graph_kpis (domain, in_degree, out_degree, pagerank)
        VALUES (:domain, :in_degree, :out_degree, :pagerank)
        """,
        graph_kpis,
    )

    conn.commit()
    conn.close()

    _write_csv(bronze_csv, bronze_rows)
    _write_csv(silver_csv, silver_rows)
    _write_csv(gold_domain_csv, domain_kpis)
    _write_csv(gold_institution_csv, institution_kpis)
    _write_csv(gold_graph_csv, graph_kpis)

    return {
        "bronze_rows": len(bronze_rows),
        "silver_rows": len(silver_rows),
        "gold_domain_rows": len(domain_kpis),
        "gold_institution_rows": len(institution_kpis),
        "gold_graph_rows": len(graph_kpis),
    }
