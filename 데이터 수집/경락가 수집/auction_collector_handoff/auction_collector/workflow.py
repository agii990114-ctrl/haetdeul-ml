from __future__ import annotations

import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta
from pathlib import Path
from typing import Callable

from .aggregate import aggregate_date
from .api import DataGoClient
from .constants import ItemSpec


ProgressCallback = Callable[[dict[str, object]], None]


def collection_dates(start: date, end: date, include_sundays: bool = False) -> list[date]:
    if start > end:
        return []
    dates: list[date] = []
    cursor = start
    while cursor <= end:
        if include_sundays or cursor.weekday() != 6:
            dates.append(cursor)
        cursor += timedelta(days=1)
    return dates


class Collector:
    def __init__(
        self,
        client: DataGoClient,
        items: tuple[ItemSpec, ...],
        cache_dir: Path,
        *,
        concurrency: int = 2,
        progress: ProgressCallback | None = None,
    ) -> None:
        if concurrency < 1:
            raise ValueError("concurrency는 1 이상이어야 합니다.")
        self.client = client
        self.items = items
        self.cache_dir = cache_dir
        self.concurrency = concurrency
        self.progress = progress or (lambda _event: None)

    def _cache_path(self, date_text: str) -> Path:
        return self.cache_dir / f"{date_text}.json"

    def _load_cache(self, path: Path) -> dict[str, object]:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or not isinstance(payload.get("rows"), list):
            raise ValueError(f"잘못된 캐시 파일: {path}")
        return payload

    def _write_cache(self, path: Path, payload: dict[str, object]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.parent / f".{path.name}.{os.getpid()}.tmp"
        temp.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        os.replace(temp, path)

    def collect_one(self, target_date: date, *, force: bool = False) -> dict[str, object]:
        date_text = target_date.isoformat()
        cache_path = self._cache_path(date_text)
        if cache_path.exists() and not force:
            payload = self._load_cache(cache_path)
            self.progress({"event": "cache_hit", "date": date_text, "rows": len(payload["rows"])})
            return payload
        fetched = self.client.fetch_date(date_text, self.items)
        rows, quality = aggregate_date(date_text, fetched, self.items)
        payload: dict[str, object] = {
            "date": date_text,
            "rows": rows,
            "quality": quality.to_dict(),
        }
        self._write_cache(cache_path, payload)
        self.progress({"event": "collected", "date": date_text, "rows": len(rows)})
        return payload

    def collect_range(
        self,
        start: date,
        end: date,
        *,
        include_sundays: bool = False,
        force: bool = False,
    ) -> tuple[list[dict[str, str]], dict[str, int]]:
        dates = collection_dates(start, end, include_sundays)
        results: dict[str, dict[str, object]] = {}
        with ThreadPoolExecutor(max_workers=self.concurrency) as executor:
            futures = {executor.submit(self.collect_one, value, force=force): value for value in dates}
            for future in as_completed(futures):
                payload = future.result()
                results[str(payload["date"])] = payload

        rows: list[dict[str, str]] = []
        quality_totals: dict[str, int] = {}
        for date_text in sorted(results):
            payload = results[date_text]
            rows.extend(payload["rows"])  # type: ignore[arg-type]
            for key, value in payload["quality"].items():  # type: ignore[union-attr]
                quality_totals[key] = quality_totals.get(key, 0) + int(value)
        return rows, quality_totals

