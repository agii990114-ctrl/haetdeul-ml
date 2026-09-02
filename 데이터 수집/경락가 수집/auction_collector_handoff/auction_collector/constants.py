from __future__ import annotations

from dataclasses import dataclass


API_URL = "https://apis.data.go.kr/B552845/katOrigin/trades"
SOURCE = "공공데이터포털_전국 공영도매시장 경매원천정보"

# ★ 2026-08-27 — 규격 차원 추가
#   기존 집계 키는 (날짜×시장×품목×등급) 이라 **포장 규격이 전부 섞였다.**
#   가락 배추 특등급 2026-08-03 실측: 15개 규격이 한 행에 뭉쳐 있었고
#   물량 79% 를 차지하는 그물망 10kg 은 711원/kg 인데 소포장(1kg 상자
#   11,224원/kg)이 섞여 평균이 939원/kg 으로 32% 부풀려졌다.
#   등급 역전(특<상)·max 19,900원/kg 도 전부 이 혼합 때문이었다.
#   규격을 키에 넣으면 min/max 분산이 132.7배 → 9.7배로 줄어든다.
#
#   subclass 도 함께 받는다 — "배추" 안에 쌈배추·수입배추·생채용이 섞여 있었다.
CSV_HEADERS = (
    "auction_date",
    "market_category",
    "wholesale_market_code",
    "wholesale_market_name",
    "item_code",
    "item_name",
    "subclass_code",
    "subclass_name",
    "grade_code",
    "grade_name",
    "package_code",
    "package_name",
    "unit_weight_kg",
    "avg_auction_price_krw_per_kg",
    "min_auction_price_krw_per_kg",
    "max_auction_price_krw_per_kg",
    "trade_volume_kg",
    "trade_amount_krw",
    "package_trade_quantity",
    "source_trade_count",
    "source",
)

NUMERIC_COLUMNS = (
    "unit_weight_kg",
    "avg_auction_price_krw_per_kg",
    "min_auction_price_krw_per_kg",
    "max_auction_price_krw_per_kg",
    "trade_volume_kg",
    "trade_amount_krw",
    "package_trade_quantity",
    "source_trade_count",
)

NATURAL_KEY_COLUMNS = (
    "auction_date",
    "wholesale_market_code",
    "item_code",
    "subclass_code",
    "grade_code",
    "grade_name",
    "package_code",
    "unit_weight_kg",
)


@dataclass(frozen=True, slots=True)
class ItemSpec:
    large_code: str
    middle_code: str
    item_code: str
    item_name: str

    @property
    def api_key(self) -> str:
        return f"{self.large_code}-{self.middle_code}"


DEFAULT_ITEMS = (
    ItemSpec("10", "01", "1001", "배추"),
    ItemSpec("11", "01", "1101", "무"),
    ItemSpec("12", "01", "1201", "양파"),
    ItemSpec("12", "07", "1207", "건고추"),
    ItemSpec("12", "09", "1209", "마늘"),
)

