# -*- coding: utf-8 -*-
"""
aT 일별 도·소매 가격 증분 수집 → veg_daily_price_raw
=====================================================
`일별_도,소매_가격정보.py` 는 2015~2026 을 통째로 다시 받아 CSV 로만 떨굽니다.
배치에 쓰려고 **마지막 적재일 다음 날부터만 받아 DB 에 바로 넣는** 쪽으로
다시 썼습니다. 경락가 쪽 `auction_collector update` 와 같은 방식입니다.

    python collect_kamis.py                          # DB 최신일 다음날 ~ 어제
    python collect_kamis.py --start 2026-01-01 --end 2026-08-24
    python collect_kamis.py --items 배추 양파 무 마늘
    python collect_kamis.py --check                  # 받기만 하고 적재 안 함

적재
    UNIQUE (exmn_ymd, item_cd, vrty_cd, grd_cd, se_cd, sgg_cd, mrkt_cd, unit, unit_sz)
    가 걸려 있어 ON CONFLICT DO NOTHING 으로 넣습니다. 같은 구간을 다시 받아도
    중복이 쌓이지 않으므로 겹치게 받아도 안전합니다.

인증키
    환경변수 → 루트 `.env` → 이 폴더 `.env` 순으로 찾습니다.
    **하드코딩 폴백은 제거했습니다 (2026-08-25).** 키가 없으면 조용히
    다른 값으로 돌지 말고 멈춰야 합니다 — 배치가 무인으로 도는 지금은
    "경고를 띄우고 계속" 이 곧 "아무도 못 보는 경고" 입니다.
"""
import argparse
import calendar
import datetime
import json
import os
import re
import sys
import time
import urllib.request
from pathlib import Path
from urllib.parse import urlencode

import psycopg

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
URL = "https://apis.data.go.kr/B552845/perDay/price"
ROWS = 1000
SLEEP = 0.3
TIMEOUT = 90

# ctgry_cd 200 = 채소류
#   item_cd 는 DB 실측으로 확인한 값이다 (2026-08-25).
#   **244 와 258 을 헷갈리지 말 것.** 피마늘과 깐마늘은 다른 물건이고
#   유통 마진이 달라(경락 3,398 → 피마늘 5,778 / 깐마늘 7,385) 섞으면 안 된다.
#
#   그리고 item_nm 은 원천이 바꾼다 — 241 이 2026 부터 '고추'→'건고추' 로 바뀌었다.
#   품목을 셀 때는 item_nm 이 아니라 **item_cd 로 세야 한다** (CLAUDE.md 9절).
ITEMS = {
    "배추": "211",
    "무": "231",
    "고추": "241",      # item_nm: 2025 까지 '고추' · 2026~ '건고추'
    "마늘": "244",      # 피마늘. 소매 없음(전량 se_cd=02 중도매)
    "양파": "245",
    "깐마늘": "258",    # 소매는 이쪽에만 있다
}

# API 필드 → 컬럼. exmn_ymd 와 orgnl_reg_dt 만 형 변환이 필요합니다.
COLS = ["exmn_ymd", "ctgry_cd", "ctgry_nm", "item_cd", "item_nm",
        "vrty_cd", "vrty_nm", "grd_cd", "grd_nm", "se_cd", "se_nm",
        "sgg_cd", "sgg_nm", "mrkt_cd", "mrkt_nm", "unit", "unit_sz",
        "exmn_dd_prc", "exmn_dd_cnvs_prc", "orgnl_reg_dt"]


def env():
    """환경변수를 채운다. 루트 `.env` 가 정본이고 폴더 `.env` 는 폴백이다.

    `setdefault` 라 먼저 읽은 쪽이 이긴다 — 루트를 먼저 읽는 이유다.
    폴더 `.env` 를 계속 읽는 것은 아직 루트로 옮기지 않은 작업 PC 때문이다.
    """
    for path in (ROOT / ".env", HERE / ".env"):
        if not path.exists():
            continue
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                v = v.strip()
                if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
                    v = v[1:-1]
                os.environ.setdefault(k.strip(), v)


def service_key():
    k = os.environ.get("DATA_GO_KR_KEY") or os.environ.get("DATA_GO_KR_SERVICE_KEY")
    if k:
        return k.strip().lstrip("﻿")     # BOM 한 글자가 섞이면 403 이 난다
    sys.exit("인증키가 없습니다. 루트 .env 에 DATA_GO_KR_KEY 를 넣으세요.")


def fetch_range(key, item_cd, gte, lte):
    """한 품목·기간의 전체 레코드. 페이지를 끝까지 넘긴다."""
    out, page = [], 1
    while True:
        q = urlencode({
            "serviceKey": key, "returnType": "JSON",
            "pageNo": page, "numOfRows": ROWS,
            "cond[exmn_ymd::GTE]": gte, "cond[exmn_ymd::LTE]": lte,
            "cond[ctgry_cd::EQ]": "200", "cond[item_cd::EQ]": item_cd,
        }, safe="[]:")
        with urllib.request.urlopen(URL + "?" + q, timeout=TIMEOUT) as r:
            body = r.read().decode("utf-8", "replace")
        try:
            data = json.loads(body)
        except ValueError:
            raise RuntimeError("비JSON 응답: %s" % body[:300])
        items = (data.get("response", {}).get("body", {})
                     .get("items", {}) or {}).get("item") or []
        if isinstance(items, dict):
            items = [items]
        out.extend(items)
        total = (data.get("response", {}).get("body", {}) or {}).get("totalCount")
        total = int(total) if total not in (None, "") else None
        if len(items) < ROWS or (total and page * ROWS >= total):
            break
        page += 1
        time.sleep(SLEEP)
    return out


def months(start, end):
    """월 단위로 자른다. 한 번에 너무 넓게 받으면 페이지가 깊어진다."""
    d = start
    while d <= end:
        last = datetime.date(d.year, d.month,
                             calendar.monthrange(d.year, d.month)[1])
        yield d, min(last, end)
        d = last + datetime.timedelta(days=1)


def to_row(r):
    v = []
    for c in COLS:
        x = r.get(c)
        if c == "exmn_ymd":
            s = str(x).strip()
            x = datetime.date(int(s[:4]), int(s[4:6]), int(s[6:8])) if len(s) == 8 else None
        elif c in ("unit_sz", "exmn_dd_prc", "exmn_dd_cnvs_prc"):
            s = str(x).replace(",", "").strip() if x is not None else ""
            x = float(s) if s not in ("", "None") else None
        elif isinstance(x, str):
            x = x.strip() or None
        v.append(x)
    return v


def main():
    ap = argparse.ArgumentParser()
    #   ★ 기본을 여섯으로 되돌린다 (2026-09-03).
    #     셋만 받고 있어서 건고추·피마늘·깐마늘이 2026-08-24 에서 멈춰 있었다.
    #     모델은 배추·무·양파만 쓰지만, 끊긴 자료는 나중에 되메우기 어렵다.
    ap.add_argument("--items", nargs="+", default=list(ITEMS))
    ap.add_argument("--start", help="기본: DB 최신일 다음 날")
    ap.add_argument("--end", help="기본: 어제")
    ap.add_argument("--check", action="store_true", help="받기만 하고 적재하지 않음")
    a = ap.parse_args()

    env()
    key = service_key()
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        sys.exit(".env 에 DATABASE_URL 이 없습니다.")

    bad = [i for i in a.items if i not in ITEMS]
    if bad:
        sys.exit("모르는 품목: %s (가능: %s)" % (bad, " ".join(ITEMS)))

    conn = psycopg.connect(dsn, connect_timeout=20)
    with conn.cursor() as cur:
        # item_nm 이 아니라 item_cd 로 찾는다.
        #   aT 가 2026 부터 이름을 바꿨다 — 마늘→피마늘 · 고추→건고추.
        #   item_nm 으로 세면 "이미 최신" 으로 잘못 판단하거나 신규를 0으로 보고한다.
        codes = [ITEMS[i] for i in a.items]
        #   ★★ 품목마다 따로 본다 (2026-09-03 고침).
        #
        #   전에는 여섯 품목의 MAX 를 **하나로 뭉쳐** 봤다. 그러면 배추가
        #   최신일 때 db_max 가 최신이 되고, **뒤처진 품목의 빈 구간을
        #   아무도 요청하지 않는다.** 뒤처진 품목이 하나라도 있으면
        #   영영 못 따라잡는다.
        #
        #   품목별 최신일을 각각 본다.
        cur.execute("SELECT item_cd, MAX(exmn_ymd) FROM veg_daily_price_raw "
                    "WHERE item_cd = ANY(%s) GROUP BY 1", (codes,))
        db_max_by = {cd: mx for cd, mx in cur.fetchall()}
        db_max = max(db_max_by.values()) if db_max_by else None

    end = datetime.date.fromisoformat(a.end) if a.end else         datetime.date.today() - datetime.timedelta(days=1)

    def start_for(name):
        """그 품목의 시작일. --start 를 주면 그게 이긴다."""
        if a.start:
            return datetime.date.fromisoformat(a.start)
        mx = db_max_by.get(ITEMS[name])
        return mx + datetime.timedelta(days=1) if mx else datetime.date(2015, 1, 1)

    print("[수집] ~ %s · %s" % (end, " ".join(a.items)))
    for name in a.items:
        st, mx = start_for(name), db_max_by.get(ITEMS[name])
        #   ★ 다른 품목보다 크게 뒤처진 것을 눈에 띄게 찍는다.
        #     2026-09-03 에 건고추·피마늘·깐마늘이 10일 뒤처진 것을
        #     아무도 몰랐다. 조용하면 또 그렇게 된다.
        flag = ""
        if db_max and mx and (db_max - mx).days > 3:
            flag = "   ★ 다른 품목보다 %d일 뒤처짐" % (db_max - mx).days
        print("  %-8s DB 최신 %s -> %s%s"
              % (name, mx or "(없음)", st if st <= end else "받을 것 없음", flag))
    if all(start_for(n) > end for n in a.items):
        print("  이미 최신입니다. 받을 구간이 없습니다.")
        return

    total_new = 0
    for name in a.items:
        start = start_for(name)
        if start > end:
            print("  %-4s 이미 최신" % name)
            continue
        got = []
        for s, e in months(start, end):
            try:
                recs = fetch_range(key, ITEMS[name], s.strftime("%Y%m%d"),
                                   e.strftime("%Y%m%d"))
            except Exception as ex:                      # noqa: BLE001
                print("  ! %s %s~%s 실패: %s" % (name, s, e, ex), file=sys.stderr)
                continue
            got.extend(recs)
            print("  %-4s %s~%s  %d건" % (name, s, e, len(recs)))
            time.sleep(SLEEP)
        if not got:
            print("  %-4s 수집 0건" % name)
            continue
        rows = [to_row(r) for r in got]
        rows = [r for r in rows if r[0] is not None]
        if a.check:
            ds = sorted({r[0] for r in rows})
            print("  %-4s 총 %d건 · 조사일 %s ~ %s (--check, 적재 안 함)"
                  % (name, len(rows), ds[0], ds[-1]))
            continue
        sql = ("INSERT INTO veg_daily_price_raw (%s) VALUES (%s) "
               "ON CONFLICT ON CONSTRAINT veg_daily_price_raw_uk DO NOTHING"
               % (", ".join(COLS), ", ".join(["%s"] * len(COLS))))
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM veg_daily_price_raw WHERE item_cd=%s",
                        (ITEMS[name],))
            n0 = cur.fetchone()[0]
            cur.executemany(sql, rows)
            conn.commit()
            cur.execute("SELECT COUNT(*) FROM veg_daily_price_raw WHERE item_cd=%s",
                        (ITEMS[name],))
            n1 = cur.fetchone()[0]
        print("  %-4s 받은 %d건 · 신규 적재 %d행" % (name, len(rows), n1 - n0))
        total_new += n1 - n0

    if not a.check:
        with conn.cursor() as cur:
            cur.execute("SELECT item_cd, item_nm, COUNT(*), MIN(exmn_ymd), MAX(exmn_ymd) "
                        "FROM veg_daily_price_raw WHERE item_cd = ANY(%s) "
                        "GROUP BY 1,2 ORDER BY 1, MIN(exmn_ymd)", (codes,))
            print("\n[적재 후] 신규 %d행" % total_new)
            for r in cur.fetchall():
                print("  %-5s %-12s %8d행 %s ~ %s" % r)
    conn.close()


if __name__ == "__main__":
    main()
