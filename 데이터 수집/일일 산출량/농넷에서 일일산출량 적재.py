#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
농넷 수급일보 반입량 수집기 (인라인 차트 파싱)
==============================================

수급일보 화면의 반입량 값은 HTML 표가 아니라 응답에 심어진 인라인
자바스크립트에 들어 있다. 표가 '조회된 데이터가 없습니다' 여도 차트
데이터는 살아 있으므로, 이쪽을 읽으면 2015년까지 소급된다.

    function makeWeightChart() {
        var tmpObj = {};
        tmpObj["dayStr"]      = "01/20";
        tmpObj["rank1Weight"] = "719";
        tmpObj["rank2Weight"] = "28";
        tmpObj["etc"]         = "73";
        tmpObj["rank1Name"]   = "전남 해남군";
        tmpObj["rank2Name"]   = "전남 무안군";
        data.push(tmpObj);
        ...

JSON 이 아니라 대입문 나열이라 정규식으로 블록 단위로 뜬다.

한 응답에 8~9일치가 들어오므로 8일 간격으로 훑는다.

사용법
------
  uv run python nongnet_chart.py probe --item 배추 --date 2015-01-27
  uv run python nongnet_chart.py scan  --item 배추          # 소급 한계
  uv run python nongnet_chart.py verify --item 배추 --date 2023-06-15 --truth ./nongnet_supply/daily_volume.csv    # 기존 데이터와 대조
  uv run python nongnet_chart.py run --start 2015-01-01 --end 2025-12-31
  uv run python nongnet_chart.py merge
"""

import argparse
import csv
import json
import os
import re
import sys
import time
from datetime import date, timedelta
from html import unescape

import requests

BASE = "https://www.nongnet.or.kr"

# 배추 = M000000311 은 확인됨(페이지 title 로 확증).
# 나머지는 화면에서 각 품목 탭을 눌러 주소창의 M000000xxx 를 확인할 것.
# 311 배추 / 312 양파 / 315 고추 로 미루어 313·314 가 무·마늘일
# 가능성이 있으나 추정이다. probe 로 '응답 품목명' 을 반드시 확인하고
# 맞을 때만 이 표를 채운다.
ITEMS = {
    "배추": {"menu": "M000000311", "pumCd": "1001"},
    "양파": {"menu": "M000000312", "pumCd": "1201"},
    "무":   {"menu": "M000000313", "pumCd": "1101"},
    "마늘": {"menu": "M000000314", "pumCd": "1209"},
    "고추": {"menu": "M000000315", "pumCd": "1207"},
}

STEP_DAYS = 8          # 한 응답에 8~9일치가 들어옴
PAUSE = 1.5
TIMEOUT = 90           # 서버 렌더링이 8초 이상 걸린다
OUTDIR = "./nongnet_chart"

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/151.0 Safari/537.36"),
    "Content-Type": "application/x-www-form-urlencoded",
}


def kdate(d):
    return f"{d.year}년 {d.month:02d}월 {d.day:02d}일"


def session():
    s = requests.Session()
    s.headers.update(HEADERS)
    try:
        s.get(BASE, timeout=30)
    except Exception:                                   # noqa: BLE001
        pass
    return s


def fetch(s, cfg, d, retries=4):
    if not cfg.get("menu"):
        raise ValueError("menu 코드가 비어 있습니다. ITEMS 를 채우세요.")
    url = f"{BASE}/front/{cfg['menu']}/dailyReport/index.do"
    body = {"searchDate": kdate(d)}
    if cfg.get("pumCd"):
        body["pumCd"] = cfg["pumCd"]

    delay = 3
    for i in range(retries):
        try:
            r = s.post(url, data=body, headers={"Referer": url},
                       timeout=TIMEOUT)
            r.raise_for_status()
            if not r.encoding or r.encoding.lower() == "iso-8859-1":
                r.encoding = "utf-8"
            return r.text
        except Exception:                               # noqa: BLE001
            if i == retries - 1:
                raise
            time.sleep(delay)
            delay = min(delay * 2, 60)
    return ""


# ── 인라인 차트 파싱 ────────────────────────────────────────────────────

# tmpObj["key"] = "value";  (작은따옴표·공백 변형 허용)
ASSIGN = re.compile(
    r"""tmpObj\s*\[\s*['"](?P<k>\w+)['"]\s*\]\s*=\s*['"](?P<v>[^'"]*)['"]\s*;""")


def chart_functions(html):
    """make*Chart 함수 본문을 {함수명: 본문} 으로 뽑는다."""
    out = {}
    for m in re.finditer(r"function\s+(make\w*Chart)\s*\(", html):
        name = m.group(1)
        i = html.find("{", m.end())
        if i < 0:
            continue
        depth, j = 0, i
        while j < len(html):                # 중괄호 균형으로 본문 끝 찾기
            if html[j] == "{":
                depth += 1
            elif html[j] == "}":
                depth -= 1
                if depth == 0:
                    break
            j += 1
        out[name] = html[i:j + 1]
    return out


def parse_chart(body):
    """함수 본문 -> [{dayStr, rank1Weight, ...}, ...]

    tmpObj 선언을 경계로 블록을 나눠, 키가 겹쳐도 섞이지 않게 한다.
    """
    recs = []
    blocks = re.split(r"var\s+tmpObj\s*=\s*\{\s*\}\s*;", body)
    for blk in blocks[1:]:
        blk = blk.split("data.push")[0]
        obj = {m.group("k"): m.group("v").strip()
               for m in ASSIGN.finditer(blk)}
        if obj.get("dayStr"):
            recs.append(obj)
    return recs


def page_item(html):
    """응답이 실제로 어느 품목인지. title 에서 뽑는다.

    title 이 '배추 &gt; 수급일보 ...' 처럼 엔티티로 인코딩돼 있으므로
    먼저 unescape 한 뒤 첫 구분자까지를 취한다.
    """
    m = re.search(r"<title>(.*?)</title>", html, re.S | re.I)
    if m:
        t = unescape(m.group(1)).strip()
        first = re.split(r"[>|:\-]", t, maxsplit=1)[0].strip()
        if first:
            return first
    m = re.search(r"<em>([^<]{1,12})</em>\s*수급일보", html)
    return m.group(1).strip() if m else None


def to_num(v):
    if v is None:
        return None
    s = str(v).replace(",", "").strip()
    if not s or s == "-":
        return None
    try:
        return float(s)
    except ValueError:
        return None


def restore_ymd(day_str, req_date):
    """'01/20' + 요청일 -> date. 연말·연초 경계 보정."""
    m = re.match(r"(\d{1,2})\s*/\s*(\d{1,2})", str(day_str))
    if not m:
        return None
    mo, dd = int(m.group(1)), int(m.group(2))
    for y in (req_date.year, req_date.year - 1, req_date.year + 1):
        try:
            c = date(y, mo, dd)
        except ValueError:
            continue
        # 창은 요청일 기준 과거 ~2주 안쪽
        if -3 <= (req_date - c).days <= 20:
            return c
    return None


def extract(html, req_date, item):
    """응답 -> 정규화된 레코드 목록."""
    funcs = chart_functions(html)
    body = funcs.get("makeWeightChart")
    if body is None:
        for n, b in funcs.items():
            if "rank1Weight" in b or "Weight" in n:
                body = b
                break
    if body is None:
        return [], sorted(funcs)

    out = []
    for o in parse_chart(body):
        ymd = restore_ymd(o.get("dayStr"), req_date)
        if ymd is None:
            continue
        t1 = to_num(o.get("rank1Weight"))
        t2 = to_num(o.get("rank2Weight"))
        te = to_num(o.get("etc"))
        parts = [x for x in (t1, t2, te) if x is not None]
        out.append({
            "ymd": ymd.isoformat(),
            "item": item,
            "total_ton": sum(parts) if parts else None,
            "top1_region": (o.get("rank1Name") or "").strip() or None,
            "top1_ton": t1,
            "top2_region": (o.get("rank2Name") or "").strip() or None,
            "top2_ton": t2,
            "etc_ton": te,
            "req_date": req_date.isoformat(),
        })
    return out, sorted(funcs)


# ── probe ──────────────────────────────────────────────────────────────

def cmd_probe(args):
    s = session()
    cfg = ITEMS[args.item]
    d = date.fromisoformat(args.date)
    html = fetch(s, cfg, d)

    print(f"[{args.item}] menu={cfg['menu']} 요청일 {d}")
    print(f"  응답 크기   : {len(html):,}자")
    print(f"  응답 품목명 : {page_item(html)}")
    print(f"  표 상태     : "
          f"{'비어 있음' if '데이터가 없습니다' in html else '데이터 있음'}")

    recs, funcs = extract(html, d, args.item)
    print(f"  차트 함수   : {funcs}")
    print(f"\n  추출 {len(recs)}건")
    for r in recs:
        print(f"    {r['ymd']}  합계 {r['total_ton']:>6}  "
              f"1위 {r['top1_region']} {r['top1_ton']}  "
              f"2위 {r['top2_region']} {r['top2_ton']}  기타 {r['etc_ton']}")

    if page_item(html) and args.item not in str(page_item(html)):
        print(f"\n  ※ 응답 품목이 요청과 다릅니다. menu 코드를 확인하세요.")

    if args.save:
        open(args.save, "w", encoding="utf-8").write(html)
        print(f"\n  저장: {args.save}")


# ── scan ───────────────────────────────────────────────────────────────

def cmd_scan(args):
    s = session()
    cfg = ITEMS[args.item]
    print(f"[{args.item}] 소급 한계 탐색\n")
    for y in range(2026, 2004, -1):
        d = date(y, 6, 15)
        try:
            recs, _ = extract(fetch(s, cfg, d), d, args.item)
        except Exception as e:                          # noqa: BLE001
            print(f"  {y}  예외 {e}")
            continue
        vals = [r for r in recs if r["total_ton"]]
        print(f"  {d}  {'O ' + str(len(vals)) + '일치' if vals else 'X 없음'}")
        if not vals and y < 2024:
            print("    (연속 실패면 여기가 한계)")
        time.sleep(args.pause)


# ── verify ─────────────────────────────────────────────────────────────

def cmd_verify(args):
    """이미 확보한 구간을 다시 긁어 값이 일치하는지 확인한다.

    차트 경로와 기존 표 경로가 같은 계열인지 검증하는 단계.

    주의: 표의 '합계' 와 차트값은 반올림 지점이 달라 ±1 톤 차이가 정상이다.
      - 표   : 서버가 원값을 더한 뒤 반올림한 합계를 직접 제공
      - 차트 : 이미 반올림된 1위·2위·기타를 우리가 더함
    그래서 기준 파일에 구성요소 컬럼이 있으면 그 합과 비교하고(정확 일치
    기대), 없으면 합계와 비교하되 ±2 톤까지 허용한다.

    --truth 는 컬럼명이 달라도 된다. nongnet_supply.py 의 daily_volume.csv
    (ymd / item_label / 합계_톤) 와 backfill.py 의 nongnet_tidy.csv
    (ymd / item / total_ton) 를 모두 받는다.
    """
    ALIASES = {
        "ymd":   ["ymd", "base_date", "날짜_ymd", "일자"],
        "item":  ["item", "item_label", "품목", "품목명"],
        "total": ["total_ton", "합계_톤", "합계", "total"],
        "t1":    ["top1_ton", "1위_톤"],
        "t2":    ["top2_ton", "2위_톤"],
        "te":    ["etc_ton", "other_ton", "기타_톤"],
    }
    REQUIRED = ("ymd", "item", "total")
    TOL = 2.0                      # 합계끼리 비교할 때 허용 오차 (톤)

    def num(v):
        v = str(v or "").replace(",", "").strip()
        if not v or v == "-":
            return None
        try:
            return float(v)
        except ValueError:
            return None

    with open(args.truth, encoding="utf-8-sig") as f:
        rdr = csv.DictReader(f)
        cols = [c.strip() for c in (rdr.fieldnames or [])]
        pick = {}
        for role, names in ALIASES.items():
            for n in names:
                if n in cols:
                    pick[role] = n
                    break
        missing = [r for r in REQUIRED if r not in pick]
        if missing:
            sys.exit(f"{args.truth} 에서 컬럼을 찾지 못했습니다: {missing}\n"
                     f"  실제 컬럼: {cols}")

        has_parts = all(k in pick for k in ("t1", "t2", "te"))
        print(f"컬럼 매칭: {pick}")
        print("비교 기준: "
              + ("구성요소 합 (1위+2위+기타) — 정확 일치 기대"
                 if has_parts else f"합계 — ±{TOL:.0f}톤 허용"))

        truth = {}
        for row in rdr:
            if str(row.get(pick["item"], "")).strip() != args.item:
                continue
            key = str(row[pick["ymd"]]).strip()[:10]
            tot = num(row.get(pick["total"]))
            parts = None
            if has_parts:
                ps = [num(row.get(pick[k])) for k in ("t1", "t2", "te")]
                if all(p is not None for p in ps):
                    parts = sum(ps)
            if tot is None and parts is None:
                continue
            truth[key] = (tot, parts)

    if not truth:
        sys.exit(f"{args.truth} 에서 {args.item} 데이터를 찾지 못했습니다.")
    print(f"기준 데이터 {len(truth):,}일\n")

    s = session()
    cfg = ITEMS[args.item]
    d = date.fromisoformat(args.date)
    recs, _ = extract(fetch(s, cfg, d), d, args.item)

    print(f"대조 ({args.date} 기준 창)\n")
    head = f"  {'날짜':<12}{'차트':>8}{'기존합계':>10}{'구성요소합':>12}{'판정':>8}"
    print(head)
    n = same = 0
    diffs = []
    for r in recs:
        got = r["total_ton"]
        t = truth.get(r["ymd"])
        if t is None:
            print(f"  {r['ymd']:<12}{got:>8.0f}{'없음':>10}{'':>12}{'-':>8}")
            continue
        tot, parts = t
        base = parts if parts is not None else tot
        diff = (got or 0) - base
        okay = abs(diff) < 0.5 if parts is not None else abs(diff) <= TOL
        n += 1
        same += bool(okay)
        diffs.append(abs(diff))
        print(f"  {r['ymd']:<12}{got:>8.0f}"
              f"{(tot if tot is not None else float('nan')):>10.0f}"
              f"{(parts if parts is not None else float('nan')):>12.0f}"
              f"{('일치' if okay else f'{diff:+.0f}'):>8}")

    if not n:
        print("\n  겹치는 날짜가 없습니다. --date 를 기존 데이터 구간 안쪽으로 잡으세요.")
        return

    print(f"\n  비교 {n}건 중 일치 {same}건 ({same/n*100:.0f}%) · "
          f"최대 절대차 {max(diffs):.0f}톤")
    if same == n:
        print("  => 동일 계열입니다. 과거 구간을 이어붙여도 됩니다.")
        if has_parts:
            print("     (표의 '합계' 와는 반올림 때문에 ±1 톤 차이가 날 수 있으나 정상)")
    elif max(diffs) <= TOL:
        print("  => 차이가 반올림 범위입니다. 동일 계열로 봐도 무방합니다.")
    else:
        print("  => 불일치. 집계 범위가 다를 수 있으니 접합 전에 원인을 확인하세요.")


# ── run / merge ────────────────────────────────────────────────────────

def cmd_run(args):
    os.makedirs(args.outdir, exist_ok=True)
    s = session()
    start = date.fromisoformat(args.start)
    end = date.fromisoformat(args.end)

    items = [args.item] if args.item else [
        k for k, v in ITEMS.items() if v.get("menu")]
    skipped = [k for k, v in ITEMS.items() if not v.get("menu")]
    if skipped and not args.item:
        print(f"menu 코드가 비어 건너뜁니다: {skipped}\n")

    raw_path = os.path.join(args.outdir, "raw.jsonl")
    done_path = os.path.join(args.outdir, "_done.txt")
    done = set()
    if os.path.exists(done_path):
        done = {l.strip() for l in open(done_path, encoding="utf-8") if l.strip()}
        print(f"이어받기: {len(done):,}건 건너뜀")

    days = []
    d = end
    while d >= start:
        days.append(d)
        d -= timedelta(days=args.step)
    total = len(days) * len(items)
    print(f"총 {total:,}회 요청 예정 "
          f"(약 {total * (args.pause + 8) / 3600:.1f}시간)\n")

    rf = open(raw_path, "a", encoding="utf-8")
    dfh = open(done_path, "a", encoding="utf-8")
    i = ok = miss = 0
    try:
        for d in days:
            for label in items:
                i += 1
                tag = f"{d}|{label}"
                if tag in done:
                    continue
                try:
                    recs, _ = extract(fetch(s, ITEMS[label], d), d, label)
                except Exception as e:                  # noqa: BLE001
                    print(f"  ! {tag}: {e}", file=sys.stderr)
                    continue

                recs = [r for r in recs if r["total_ton"] is not None]
                if recs:
                    ok += 1
                    for r in recs:
                        rf.write(json.dumps(r, ensure_ascii=False) + "\n")
                    rf.flush()
                else:
                    miss += 1

                dfh.write(tag + "\n")
                dfh.flush()
                if i % 20 == 0:
                    print(f"  [{i:,}/{total:,}] {d} · 성공 {ok:,} · 빈응답 {miss:,}")
                time.sleep(args.pause)

                if miss > 40 and ok == 0:
                    print("\n계속 빈 응답입니다. probe 로 확인하세요.")
                    raise KeyboardInterrupt
    except KeyboardInterrupt:
        print("\n중단됨. 다시 실행하면 이어서 받습니다.")
    finally:
        rf.close()
        dfh.close()

    print(f"\n성공 {ok:,} · 빈응답 {miss:,}")
    merge(raw_path, os.path.join(args.outdir, "daily_volume.csv"),
          getattr(args, "load_db", False), getattr(args, "no_csv", False))


def load_to_db(recs):
    """CSV 를 거치지 않고 daily_volume 에 넣는다.

    raw.jsonl 은 남긴다 — 25분짜리 스크래핑을 이어받는 데 필요하다(_done.txt 와 짝).
    없애는 것은 **파이프라인 중간 산출물인 merge CSV** 뿐이다.

    스크래퍼가 톤을 실수로 준다(1718.0). 컬럼은 integer 이므로 반올림한다.
    CSV 를 경유하면 이 변환이 로더로 넘어가 규칙이 두 곳에 생긴다.
    """
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    try:
        import _dbload
    except ImportError as exc:
        print(f"[!] 공용 적재 모듈을 찾지 못했다: {exc}")
        return 1

    cols = ["base_date", "item_label", "total_ton", "top1_region", "top1_ton",
            "top2_region", "top2_ton", "etc_ton", "req_date"]
    num = {"total_ton", "top1_ton", "top2_ton", "etc_ton"}
    typed, bad = [], []
    for r in recs:
        try:
            v = [date.fromisoformat(r["ymd"]), r["item"]]
            for c in ("total_ton", "top1_region", "top1_ton",
                      "top2_region", "top2_ton", "etc_ton"):
                x = r.get(c)
                v.append(int(round(float(x))) if c in num and x is not None
                         else (x or None))
            v.append(date.fromisoformat(r["req_date"]))
        except (ValueError, TypeError, KeyError) as e:
            bad.append((r.get("ymd"), r.get("item"), str(e)))
            continue
        # DB CHECK 과 같은 조건을 미리 건다. 어느 행이 왜 걸렸는지 알려면 필요하다.
        i = {c: k for k, c in enumerate(cols)}
        if any(v[i[c]] is None or v[i[c]] < 0 for c in num):
            bad.append((r["ymd"], r["item"], "톤이 NULL 이거나 음수"))
        elif v[i["top1_ton"]] < v[i["top2_ton"]]:
            bad.append((r["ymd"], r["item"], "top1 < top2"))
        elif v[i["req_date"]] < v[i["base_date"]]:
            bad.append((r["ymd"], r["item"], "req_date < base_date"))
        else:
            typed.append(v)

    if bad:
        print(f"  제외 {len(bad)}행")
        for x in bad[:5]:
            print(f"    {x[0]} {x[1]} — {x[2]}")

    # 농넷은 **수급일보**라 최근 물량이 뒤늦게 반영된다.
    #   실측(2026-08-25): 8/18~8/22 17건이 전부 늘어났다.
    #   8/18 양파 1,407 → 1,658톤 · 8/20 무 677 → 700톤
    #   반영하지 않으면 모델이 낡은 물량으로 학습한다.
    #
    # 그렇다고 전 구간을 덮어쓰면 스크래퍼가 깨졌을 때 이상한 값이 그대로 들어간다.
    # **정정은 최근 며칠 안에서만 일어난다** — 오래된 값이 갑자기 바뀌면 그건 사고다.
    # 그래서 최근 REVISE_DAYS 만 덮어쓰고 나머지는 건드리지 않는다.
    REVISE_DAYS = 14
    cutoff = date.today() - timedelta(days=REVISE_DAYS)
    recent = [v for v in typed if v[0] >= cutoff]
    older = [v for v in typed if v[0] < cutoff]

    print("\n[DB 적재] daily_volume")
    try:
        if older:
            _dbload.upsert("daily_volume", cols, older,
                           conflict="(base_date, item_label)",
                           key_cols=["base_date", "item_label"],
                           compare=["total_ton", "top1_ton", "top2_ton", "etc_ton"],
                           do_update=False, label=f"volume ~{cutoff} (기존 유지)")
        if recent:
            _dbload.upsert("daily_volume", cols, recent,
                           conflict="(base_date, item_label)",
                           key_cols=["base_date", "item_label"],
                           compare=["total_ton", "top1_ton", "top2_ton", "etc_ton"],
                           do_update=True, label=f"volume {cutoff}~ (정정 반영)")
    except Exception as exc:                                 # noqa: BLE001
        print(f"[!] DB 적재 실패: {exc}")
        return 1
    return 0


def merge(raw_path, out_path, load_db=False, no_csv=False):
    if not os.path.exists(raw_path) or os.path.getsize(raw_path) < 5:
        print("병합할 원자료가 없습니다.")
        return

    rows = {}
    with open(raw_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            rows[(r["ymd"], r["item"])] = r

    recs = sorted(rows.values(), key=lambda r: (r["item"], r["ymd"]))
    cols = ["ymd", "item", "total_ton", "top1_region", "top1_ton",
            "top2_region", "top2_ton", "etc_ton", "req_date"]
    if no_csv:
        print(f"\n병합 {len(recs):,}행 (CSV 미생성)")
    else:
        with open(out_path, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
            w.writeheader()
            w.writerows(recs)
        print(f"\n저장: {out_path}  ({len(recs):,}행)")
    by = {}
    for r in recs:
        by.setdefault(r["item"], []).append(r["ymd"])
    for item, ds in sorted(by.items()):
        d0, d1 = min(ds), max(ds)
        span = (date.fromisoformat(d1) - date.fromisoformat(d0)).days + 1
        print(f"  {item}: {d0} ~ {d1} · {len(set(ds)):,}일 "
              f"(구간 {span:,}일, 결측 {span - len(set(ds)):,})")

    # 산지 칸에 들어온 비산지 값
    bad = {}
    for r in recs:
        for k in ("top1_region", "top2_region"):
            v = (r.get(k) or "").strip()
            if v in ("기타", "서울", "미상"):
                bad[v] = bad.get(v, 0) + 1
    if bad:
        print(f"  ! 산지 칸의 비산지 값: {bad}")

    if load_db:
        return load_to_db(recs)
    return 0


def main():
    p = argparse.ArgumentParser(description="농넷 수급일보 반입량 수집")
    sub = p.add_subparsers(dest="cmd", required=True)

    pr = sub.add_parser("probe")
    pr.add_argument("--item", default="배추")
    pr.add_argument("--date", default="2015-01-27")
    pr.add_argument("--save", default=None)
    pr.set_defaults(func=cmd_probe)

    sc = sub.add_parser("scan")
    sc.add_argument("--item", default="배추")
    sc.add_argument("--pause", type=float, default=PAUSE)
    sc.set_defaults(func=cmd_scan)

    vf = sub.add_parser("verify")
    vf.add_argument("--item", default="배추")
    vf.add_argument("--date", default="2023-06-15")
    vf.add_argument("--truth", default="nongnet_tidy.csv")
    vf.set_defaults(func=cmd_verify)

    rn = sub.add_parser("run")
    rn.add_argument("--start", default="2015-01-01")
    rn.add_argument("--end", default="2025-12-31")
    rn.add_argument("--item", default=None)
    rn.add_argument("--step", type=int, default=STEP_DAYS)
    rn.add_argument("--pause", type=float, default=PAUSE)
    rn.add_argument("--outdir", default=OUTDIR)
    rn.set_defaults(func=cmd_run)

    rn.add_argument("--load-db", action="store_true",
                    help="CSV 를 거치지 않고 daily_volume 에 바로 적재")
    rn.add_argument("--no-csv", action="store_true",
                    help="merge CSV 를 만들지 않는다 (--load-db 와 함께)")

    mg = sub.add_parser("merge")
    mg.add_argument("--raw", default=os.path.join(OUTDIR, "raw.jsonl"))
    mg.add_argument("--out", default=os.path.join(OUTDIR, "daily_volume.csv"))
    mg.add_argument("--load-db", action="store_true")
    mg.add_argument("--no-csv", action="store_true")
    mg.set_defaults(func=lambda a: merge(a.raw, a.out, a.load_db, a.no_csv))

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
