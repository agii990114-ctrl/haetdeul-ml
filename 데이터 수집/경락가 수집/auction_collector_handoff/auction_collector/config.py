from __future__ import annotations

import json
import os
from pathlib import Path

from .constants import DEFAULT_ITEMS, ItemSpec


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        os.environ.setdefault(key, value)


def load_items(path: Path | None) -> tuple[ItemSpec, ...]:
    if path is None:
        return DEFAULT_ITEMS
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list) or not raw:
        raise ValueError("품목 설정은 하나 이상의 객체를 담은 JSON 배열이어야 합니다.")
    items: list[ItemSpec] = []
    for index, value in enumerate(raw, start=1):
        if not isinstance(value, dict):
            raise ValueError(f"품목 설정 {index}번 항목이 객체가 아닙니다.")
        try:
            item = ItemSpec(
                str(value["large_code"]).strip(),
                str(value["middle_code"]).strip(),
                str(value["item_code"]).strip(),
                str(value["item_name"]).strip(),
            )
        except KeyError as error:
            raise ValueError(f"품목 설정 {index}번에 {error.args[0]}가 없습니다.") from error
        if not all((item.large_code, item.middle_code, item.item_code, item.item_name)):
            raise ValueError(f"품목 설정 {index}번에 빈 값이 있습니다.")
        items.append(item)
    keys = [(item.api_key, item.item_code) for item in items]
    if len(keys) != len(set(keys)):
        raise ValueError("품목 설정에 중복 코드가 있습니다.")
    return tuple(items)

