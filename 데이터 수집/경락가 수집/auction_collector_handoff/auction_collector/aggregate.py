from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from .constants import CSV_HEADERS, SOURCE, ItemSpec


@dataclass(slots=True)
class Quality:
    fetched_rows: int = 0
    target_rows: int = 0
    auction_rows: int = 0
    kg_rows: int = 0
    excluded_non_auction: int = 0
    excluded_non_kg: int = 0
    excluded_invalid: int = 0

    def to_dict(self) -> dict[str, int]:
        return asdict(self)


def _decimal(value: object) -> Decimal | None:
    try:
        number = Decimal(str(value).strip())
    except (InvalidOperation, AttributeError):
        return None
    return number if number.is_finite() else None


def _format_decimal(value: Decimal, digits: int) -> str:
    quantum = Decimal(1).scaleb(-digits)
    text = format(value.quantize(quantum, rounding=ROUND_HALF_UP), "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def aggregate_date(
    date: str,
    fetched: list[dict[str, object]],
    items: tuple[ItemSpec, ...],
) -> tuple[list[dict[str, str]], Quality]:
    item_map = {item.api_key: item for item in items}
    # 키에 subclass·package·unit_weight 를 넣는다 (2026-08-27).
    # 이걸 안 넣으면 서로 다른 상품이 한 평균에 뭉친다 — 상세 근거는 constants.py.
    groups: dict[tuple[str, ...], dict[str, object]] = {}
    quality = Quality(fetched_rows=len(fetched))

    for raw in fetched:
        api_item_key = f"{raw.get('gds_lclsf_cd', '')}-{raw.get('gds_mclsf_cd', '')}"
        item = item_map.get(api_item_key)
        if item is None:
            continue
        quality.target_rows += 1
        if str(raw.get("trd_se", "")).strip() != "경매":
            quality.excluded_non_auction += 1
            continue
        quality.auction_rows += 1
        if str(raw.get("unit_nm", "")).strip().lower() != "kg":
            quality.excluded_non_kg += 1
            continue

        unit_qty = _decimal(raw.get("unit_qty"))
        total_kg = _decimal(raw.get("unit_tot_qty"))
        package_qty = _decimal(raw.get("qty"))
        bid_price = _decimal(raw.get("scsbd_prc"))
        total_won = _decimal(raw.get("totprc"))
        numbers = (unit_qty, total_kg, package_qty, bid_price, total_won)
        if any(value is None or value <= 0 for value in numbers):
            quality.excluded_invalid += 1
            continue
        assert total_kg is not None and package_qty is not None and total_won is not None
        quality.kg_rows += 1

        market_code = str(raw.get("whsl_mrkt_cd", "")).strip()
        market_name = str(raw.get("whsl_mrkt_nm", "")).strip() or "미상"
        grade_code = str(raw.get("grd_cd", "")).strip()
        grade_name = str(raw.get("grd_nm", "")).strip() or "미상"
        subclass_code = str(raw.get("gds_sclsf_cd", "")).strip()
        subclass_name = str(raw.get("gds_sclsf_nm", "")).strip() or "미상"
        package_code = str(raw.get("pkg_cd", "")).strip()
        package_name = str(raw.get("pkg_nm", "")).strip() or "미상"
        # unit_qty 는 포장당 중량(kg). 규격을 가르는 핵심 값이라 키에 넣는다.
        unit_weight = _format_decimal(unit_qty, 3)  # type: ignore[arg-type]
        if not market_code:
            quality.excluded_invalid += 1
            quality.kg_rows -= 1
            continue
        key = (date, market_code, item.item_code, subclass_code,
               grade_code, grade_name, package_code, unit_weight)
        won_per_kg = total_won / total_kg

        group = groups.get(key)
        if group is None:
            group = {
                "auction_date": date,
                "market_category": "가락" if market_code == "110001" else "지방",
                "wholesale_market_code": market_code,
                "wholesale_market_name": market_name,
                "item_code": item.item_code,
                "item_name": item.item_name,
                "subclass_code": subclass_code,
                "subclass_name": subclass_name,
                "grade_code": grade_code,
                "grade_name": grade_name,
                "package_code": package_code,
                "package_name": package_name,
                "unit_weight_kg": unit_weight,
                "total_kg": Decimal(0),
                "total_won": Decimal(0),
                "min_won_per_kg": won_per_kg,
                "max_won_per_kg": won_per_kg,
                "package_qty": Decimal(0),
                "source_rows": 0,
            }
            groups[key] = group
        group["total_kg"] = group["total_kg"] + total_kg  # type: ignore[operator]
        group["total_won"] = group["total_won"] + total_won  # type: ignore[operator]
        group["min_won_per_kg"] = min(group["min_won_per_kg"], won_per_kg)  # type: ignore[type-var]
        group["max_won_per_kg"] = max(group["max_won_per_kg"], won_per_kg)  # type: ignore[type-var]
        group["package_qty"] = group["package_qty"] + package_qty  # type: ignore[operator]
        group["source_rows"] = int(group["source_rows"]) + 1

    output: list[dict[str, str]] = []
    for key in sorted(groups):
        group = groups[key]
        total_kg = group["total_kg"]
        total_won = group["total_won"]
        assert isinstance(total_kg, Decimal) and isinstance(total_won, Decimal)
        row = {
            "auction_date": str(group["auction_date"]),
            "market_category": str(group["market_category"]),
            "wholesale_market_code": str(group["wholesale_market_code"]),
            "wholesale_market_name": str(group["wholesale_market_name"]),
            "item_code": str(group["item_code"]),
            "item_name": str(group["item_name"]),
            "subclass_code": str(group["subclass_code"]),
            "subclass_name": str(group["subclass_name"]),
            "grade_code": str(group["grade_code"]),
            "grade_name": str(group["grade_name"]),
            "package_code": str(group["package_code"]),
            "package_name": str(group["package_name"]),
            "unit_weight_kg": str(group["unit_weight_kg"]),
            "avg_auction_price_krw_per_kg": _format_decimal(total_won / total_kg, 2),
            "min_auction_price_krw_per_kg": _format_decimal(group["min_won_per_kg"], 2),  # type: ignore[arg-type]
            "max_auction_price_krw_per_kg": _format_decimal(group["max_won_per_kg"], 2),  # type: ignore[arg-type]
            "trade_volume_kg": _format_decimal(total_kg, 3),
            "trade_amount_krw": _format_decimal(total_won, 0),
            "package_trade_quantity": _format_decimal(group["package_qty"], 3),  # type: ignore[arg-type]
            "source_trade_count": str(group["source_rows"]),
            "source": SOURCE,
        }
        output.append({header: row[header] for header in CSV_HEADERS})
    return output, quality

