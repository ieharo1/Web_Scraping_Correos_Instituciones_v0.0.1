from __future__ import annotations

import asyncio
from collections import deque
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import aiohttp
import yaml
from bs4 import BeautifulSoup

from common import EMAIL_RE, PHONE_RE, domain_from_url, project_root, utc_now_iso


class AsyncScraper:
    def __init__(
        self,
        *,
        max_depth: int,
        max_pages: int,
        concurrency: int,
        timeout_seconds: int,
        same_domain_only: bool,
    ) -> None:
        self.max_depth = max_depth
        self.max_pages = max_pages
        self.same_domain_only = same_domain_only
        self.timeout = aiohttp.ClientTimeout(total=timeout_seconds)
        self.semaphore = asyncio.Semaphore(concurrency)

    async def _fetch_http(self, session: aiohttp.ClientSession, url: str) -> tuple[int, str]:
        async with self.semaphore:
            async with session.get(url, allow_redirects=True) as response:
                text = await response.text(errors="ignore")
                return response.status, text

    async def _fetch_file(self, url: str) -> tuple[int, str]:
        parsed = urlparse(url)
        candidate_parts = [parsed.netloc, parsed.path.lstrip("/")]
        candidate = "/".join([part for part in candidate_parts if part])
        file_path = project_root() / candidate

        def _read_text(path: Path) -> str:
            return path.read_text(encoding="utf-8", errors="ignore")

        if not file_path.exists():
            return 404, ""
        text = await asyncio.to_thread(_read_text, file_path)
        return 200, text

    async def _fetch(self, session: aiohttp.ClientSession, url: str) -> tuple[int, str]:
        parsed = urlparse(url)
        if parsed.scheme == "file":
            return await self._fetch_file(url)
        return await self._fetch_http(session, url)

    def _extract_links(self, base_url: str, soup: BeautifulSoup) -> list[str]:
        links: list[str] = []
        for anchor in soup.find_all("a", href=True):
            href = anchor.get("href", "").strip()
            if not href or href.startswith("#") or href.startswith("mailto:") or href.startswith("tel:"):
                continue
            next_url = urljoin(base_url, href)
            if next_url.startswith("javascript:"):
                continue
            links.append(next_url)
        return links

    def _should_enqueue(self, source_url: str, next_url: str) -> bool:
        if not self.same_domain_only:
            return True
        return domain_from_url(source_url) == domain_from_url(next_url)

    async def crawl(self, seeds: list[dict[str, str]]) -> dict[str, list[dict[str, Any]]]:
        pages: list[dict[str, Any]] = []
        contacts: list[dict[str, Any]] = []
        edges: list[dict[str, Any]] = []

        visited: set[str] = set()
        queue: deque[tuple[str, int, str]] = deque((seed["url"], 0, seed["id"]) for seed in seeds)

        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; BigDataScraper/1.0; +https://github.com/ieharo1)"
        }

        async with aiohttp.ClientSession(timeout=self.timeout, headers=headers) as session:
            while queue and len(pages) < self.max_pages:
                url, depth, source_id = queue.popleft()
                if url in visited or depth > self.max_depth:
                    continue
                visited.add(url)

                status = 0
                html = ""
                error = ""
                try:
                    status, html = await self._fetch(session, url)
                except Exception as exc:  # pragma: no cover - network dependent
                    error = str(exc)

                soup = BeautifulSoup(html, "html.parser") if html else BeautifulSoup("", "html.parser")
                title = soup.title.string.strip() if soup.title and soup.title.string else ""
                text_blob = soup.get_text(" ", strip=True)
                emails = sorted(set(EMAIL_RE.findall(text_blob)))
                phones = sorted(set(PHONE_RE.findall(text_blob)))
                links = self._extract_links(url, soup)

                pages.append(
                    {
                        "crawled_at": utc_now_iso(),
                        "source_id": source_id,
                        "url": url,
                        "domain": domain_from_url(url),
                        "depth": depth,
                        "status_code": status,
                        "title": title,
                        "html_bytes": len(html.encode("utf-8")) if html else 0,
                        "link_count": len(links),
                        "error": error,
                    }
                )

                for email in emails:
                    contacts.append(
                        {
                            "crawled_at": utc_now_iso(),
                            "source_id": source_id,
                            "source_url": url,
                            "source_domain": domain_from_url(url),
                            "contact_type": "email",
                            "contact_value": email,
                            "depth": depth,
                        }
                    )

                for phone in phones:
                    contacts.append(
                        {
                            "crawled_at": utc_now_iso(),
                            "source_id": source_id,
                            "source_url": url,
                            "source_domain": domain_from_url(url),
                            "contact_type": "phone",
                            "contact_value": phone,
                            "depth": depth,
                        }
                    )

                for next_url in links:
                    edges.append(
                        {
                            "crawled_at": utc_now_iso(),
                            "source_url": url,
                            "source_domain": domain_from_url(url),
                            "target_url": next_url,
                            "target_domain": domain_from_url(next_url),
                        }
                    )
                    if self._should_enqueue(url, next_url):
                        queue.append((next_url, depth + 1, source_id))

        return {"pages": pages, "contacts": contacts, "edges": edges}


def load_source_profile(mode: str) -> tuple[list[dict[str, str]], dict[str, Any]]:
    conf_path = project_root() / "configs" / "sources.yml"
    payload = yaml.safe_load(conf_path.read_text(encoding="utf-8"))
    profiles = payload.get("profiles", {})
    if mode not in profiles:
        raise ValueError(f"Profile no soportado: {mode}")
    return profiles[mode], payload.get("settings", {})
