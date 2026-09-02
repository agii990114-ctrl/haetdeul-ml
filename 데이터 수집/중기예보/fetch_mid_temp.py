# -*- coding: utf-8 -*-
"""중기 기온예보 수집 — 기상청 API허브  (2026-08-31)

## 왜 모으나

우리 예측이 18일 내내 거의 일직선입니다. 실측:

    한 기준일 안에서 리드타임 3~18 이 움직이는 폭
      경락가 배추   예측 13.7%  vs  실제 137.8%   (0.10배)

원인을 재보니 **모델 입력 28개 중 17개가 한 기준일 안에서 전부 같은 값**
이었습니다. "1월 2일"과 "1월 27일"에 거의 같은 이야기를 하고 있습니다.

지금 모델은 **어제까지의 날씨는 알지만 그날 날씨는 모릅니다.**
예보는 우리가 가진 것 중 **유일하게 "그날"을 말해주는 자료**입니다.

`crop_price_train.prod_area_fcst_temp_avg10` 컬럼이 이걸 기다리며 만들어져
있습니다 (지금 198,937행 전부 NULL).

## 무엇을 받나

    API     기상청 API허브 · fct_afs_wc.php (중기 기온예보)
    기간    2015년부터 (실측 확인)
    발표    하루 2번 — 06시 · 18시
    앞날    발표+3일 ~ +10일 (8일치)
    값      아침 최저기온 · 낮 최고기온 (℃)

## ★ 예보구역은 이름으로 고르지 않았습니다

예보구역 563개 중 **시군(C등급) 208개만 기온을 줍니다.** 나머지는 바다·도로
구역입니다. 이름만 보고 골랐으면 이렇게 틀렸을 것입니다.

    목포   → '영광-목포' · '목포구내' · '목포-홍도'   전부 바다 (기온 없음)
    대관령 → '장평-대관령'                          도로 구간 (기온 없음)

그래서 **코드마다 실제로 불러 기온이 나오는 것만** 아래 표에 넣었습니다.

## 누수 방지

`tm_fc`(발표시각)를 그대로 저장합니다. 학습에서 쓸 때 **기준일보다 앞서
발표된 것만** 골라 쓰면 됩니다. 예보는 그 시각에 실제로 나와 있던 값이라
"그때 알 수 있었나" 가 자료 자체에 남습니다.

## 쓰는 법

    python fetch_mid_temp.py --from 2015-01-01 --to 2026-08-31    # 전 구간
    python fetch_mid_temp.py --recent 30                          # 최근 30일
    python fetch_mid_temp.py --recent 7 --check                   # 대조만
"""
from __future__ import annotations

import argparse
import datetime
import io
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import _dbload                                               # noqa: E402

HUB = "https://apihub.kma.go.kr/api/typ01/url/fct_afs_wc.php"

#   주산지 관측소 → 중기예보구역.
#   ★ 2026-08-31 에 563개 구역을 전부 시험해 **기온이 실제로 나온 코드**만 적었다.
#     이름이 비슷하다고 넣지 말 것. 바다 구역이 섞이면 산지 기온 자리에
#     바다 예보가 들어간다.
REGIONS = {
    "제주":   "11G00201",
    "목포":   "21F20801",
    "강릉":   "11D20501",
    "홍성":   "11C20104",
    "홍천":   "11D10302",
    "해남":   "11F20302",
    "대관령": "11D20201",
    "고창군": "21F10601",     # 예보구역 이름은 '고창'
}

#   한 번에 며칠치를 받을지. 30일이면 구역당 약 135회, 8구역 1,100회로
#   하루 한도(2만)의 6% 다. 더 키우면 응답이 커져 끊길 수 있다.
CHUNK_DAYS = 30

DDL = """
CREATE TABLE IF NOT EXISTS kma_mid_temp_raw (
    reg_id      TEXT        NOT NULL,   -- 예보구역 코드
    stn_nm      TEXT        NOT NULL,   -- 우리 주산지 관측소 이름
    tm_fc       TIMESTAMP   NOT NULL,   -- 발표시각 (KST). 누수 판정의 기준
    tm_ef       TIMESTAMP   NOT NULL,   -- 대상시각 (KST)
    min_ta      NUMERIC(5,1),           -- 아침 최저기온 (℃)
    max_ta      NUMERIC(5,1),           -- 낮 최고기온 (℃)
    lead_days   SMALLINT,               -- 대상일 - 발표일 (달력일)
    created_at  TIMESTAMPTZ DEFAULT now(),
    CONSTRAINT uq_kma_mid_temp UNIQUE (reg_id, tm_fc, tm_ef)
);
COMMENT ON TABLE kma_mid_temp_raw IS
  '중기 기온예보 원본. 기상청 API허브 fct_afs_wc. 발표시각(tm_fc)이 남아 있어 '
  '"그 시점에 알 수 있었나" 를 자료로 판정할 수 있다. 2026-08-31 수집 시작';
CREATE INDEX IF NOT EXISTS ix_kma_mid_temp_ef ON kma_mid_temp_raw(stn_nm, tm_ef, tm_fc);
"""


def api_key() -> str:
    for p in (HERE / ".env", HERE.parent.parent / ".env"):
        if not p.exists():
            continue
        for line in io.open(p, encoding="utf-8-sig", errors="ignore"):
            line = line.strip()
            if line.startswith("API_HUB_KEY="):
                v = line.split("=", 1)[1].strip().strip('"').strip("'")
                if v:
                    return v
    v = os.environ.get("API_HUB_KEY")
    if v:
        return v
    raise SystemExit("API_HUB_KEY 가 .env 에 없습니다.")


KEY = api_key()


def fetch(reg: str, t1: str, t2: str, tries: int = 3) -> str:
    """한 구역의 [t1, t2] 발표분을 받는다. 실패하면 잠깐 쉬고 다시."""
    q = urllib.parse.urlencode({"reg": reg, "tmfc1": t1, "tmfc2": t2,
                                "disp": "0", "help": "0", "authKey": KEY})
    for i in range(tries):
        try:
            with urllib.request.urlopen(HUB + "?" + q, timeout=40) as r:
                #   응답이 EUC-KR 이다. utf-8 로 읽으면 한글이 깨진다.
                return r.read().decode("euc-kr", errors="replace")
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            if i == tries - 1:
                print(f"    ! {reg} {t1}~{t2} 실패: {type(e).__name__}")
                return ""
            time.sleep(2 * (i + 1))
    return ""


def parse(txt: str, stn: str) -> list:
    """고정폭 텍스트를 행으로. 형식이 다르면 조용히 버리지 않고 센다.

    # REG_ID TM_FC        TM_EF        MOD STN C MIN MAX MIN_L MIN_H MAX_L MAX_H
    11B10101 202312010600 202312040000 A01 109 2  -2   8    1    1    1    1
    """
    rows, bad, n_odd = [], 0, 0
    for line in txt.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        p = line.split()
        if len(p) < 8 or len(p[1]) != 12 or len(p[2]) != 12:
            bad += 1
            continue
        try:
            fc = datetime.datetime.strptime(p[1], "%Y%m%d%H%M")
            ef = datetime.datetime.strptime(p[2], "%Y%m%d%H%M")
            #   -99 · -999 는 결측 표시다. 0 으로 바꾸지 않는다.
            mn = float(p[6]) if p[6] not in ("-99", "-999", "") else None
            mx = float(p[7]) if p[7] not in ("-99", "-999", "") else None
            #   ★ 원천에 물리적으로 불가능한 값이 섞여 있다 (2026-08-31 실측).
            #     42만 행 중 8건 · 전부 2016-12-21~22 에 몰려 있다.
            #       홍천  최저 -170.0℃ / 최고   1.0℃
            #       홍천  최저 -157.0℃ / 최고 -126.0℃
            #     우리나라 관측 최저는 -32.6℃(1981 양평), 최고는 41.0℃(2018 홍천)다.
            #     그 밖은 값이 아니라 오류로 본다. **버리지 않고 NULL 로 둔다** —
            #     0 으로 바꾸면 한겨울에 0℃ 예보가 있던 것처럼 보인다.
            if mn is not None and not (-40 <= mn <= 45):
                mn, n_odd = None, n_odd + 1
            if mx is not None and not (-40 <= mx <= 50):
                mx, n_odd = None, n_odd + 1
        except (ValueError, IndexError):
            bad += 1
            continue
        if mn is None and mx is None:
            continue
        rows.append([p[0], stn, fc, ef, mn, mx, (ef.date() - fc.date()).days])
    if bad:
        print(f"    (형식이 다른 줄 {bad}개 건너뜀)")
    if n_odd:
        print(f"    (기온이 -40~45℃ 밖인 값 {n_odd}개를 NULL 로 둠)")
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description="중기 기온예보 수집")
    ap.add_argument("--from", dest="d_from", default=None, help="YYYY-MM-DD")
    ap.add_argument("--to", dest="d_to", default=None, help="YYYY-MM-DD")
    ap.add_argument("--recent", type=int, default=None, help="최근 N일")
    ap.add_argument("--check", action="store_true", help="대조만 하고 넣지 않음")
    a = ap.parse_args()

    today = datetime.date.today()
    if a.recent:
        d1, d2 = today - datetime.timedelta(days=a.recent), today
    else:
        d1 = datetime.date.fromisoformat(a.d_from) if a.d_from else datetime.date(2015, 1, 1)
        d2 = datetime.date.fromisoformat(a.d_to) if a.d_to else today
    if d1 > d2:
        raise SystemExit("시작일이 끝일보다 뒤입니다.")

    import psycopg
    with psycopg.connect(_dbload.dsn(), connect_timeout=30) as cn:
        cn.execute(DDL)
        cn.commit()
    print(f"[표] kma_mid_temp_raw 준비 완료")
    print(f"[구역] {len(REGIONS)}개 · {d1} ~ {d2}\n")

    cols = ["reg_id", "stn_nm", "tm_fc", "tm_ef", "min_ta", "max_ta", "lead_days"]
    total, calls = 0, 0
    for stn, reg in REGIONS.items():
        got: list = []
        cur = d1
        while cur <= d2:
            end = min(cur + datetime.timedelta(days=CHUNK_DAYS - 1), d2)
            txt = fetch(reg, cur.strftime("%Y%m%d") + "0000",
                        end.strftime("%Y%m%d") + "2359")
            calls += 1
            got += parse(txt, stn)
            cur = end + datetime.timedelta(days=1)
        print(f"  {stn:<5} {reg}  {len(got):>7,}행")
        if got:
            _dbload.upsert("kma_mid_temp_raw", cols, got,
                           conflict="ON CONSTRAINT uq_kma_mid_temp",
                           key_cols=["reg_id", "tm_fc", "tm_ef"],
                           compare=["min_ta", "max_ta"],
                           check=a.check, label=f"중기기온:{stn}")
        total += len(got)

    print(f"\n[합계] {total:,}행 · 호출 {calls:,}회 "
          f"(하루 한도 20,000 의 {calls/200:.1f}%)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
