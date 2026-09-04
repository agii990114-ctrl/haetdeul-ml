"""기상청 지상(종관, ASOS) 일자료 -> CSV

전 지점(95개)의 지정 기간 일자료를 받아 하나의 CSV 로 저장한다.
명세는 기상청02_지상(종관,ASOS)일자료_조회서비스_오픈API활용가이드.md 참조.

인증키는 코드에 넣지 않는다. 아래 순서로 찾는다:
    1) 환경변수 ASOS_SERVICE_KEY
    2) 이 파일 옆의 service_key.txt

기본 기간은 팀에서 정한 대상 기간 2022-01-01 ~ 2025-12-31 이다.

사용:
    python fetch_asos.py                      # 대상 기간 전체
    python fetch_asos.py 20220101 20251231
    python fetch_asos.py 20220101 20251231 out.csv
"""

import collections
import csv
import math
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta

BASE = "https://apis.data.go.kr/1360000/AsosDalyInfoService/getWthrDataList"

MAX_ROWS = 999      # 1000 이상은 "한번에 최대 1,000건" 에러(코드 99)
MAX_TPS = 30        # 명세상 초당 최대 트랜잭션
WORKERS = 6
RETRY = 4

# 지점 번호 -> 지점명 (활용가이드 첨부. 지점 코드)
STATIONS = {
    90: "속초", 93: "북춘천", 95: "철원", 98: "동두천", 99: "파주",
    100: "대관령", 101: "춘천", 102: "백령도", 104: "북강릉", 105: "강릉",
    106: "동해", 108: "서울", 112: "인천", 114: "원주", 115: "울릉도",
    119: "수원", 121: "영월", 127: "충주", 129: "서산", 130: "울진",
    131: "청주", 133: "대전", 135: "추풍령", 136: "안동", 137: "상주",
    138: "포항", 140: "군산", 143: "대구", 146: "전주", 152: "울산",
    155: "창원", 156: "광주", 159: "부산", 162: "통영", 165: "목포",
    168: "여수", 169: "흑산도", 170: "완도", 172: "고창", 174: "순천",
    177: "홍성", 184: "제주", 185: "고산", 188: "성산", 189: "서귀포",
    192: "진주", 201: "강화", 202: "양평", 203: "이천", 211: "인제",
    212: "홍천", 216: "태백", 217: "정선군", 221: "제천", 226: "보은",
    232: "천안", 235: "보령", 236: "부여", 238: "금산", 239: "세종",
    243: "부안", 244: "임실", 245: "정읍", 247: "남원", 248: "장수",
    251: "고창군", 252: "영광군", 253: "김해시", 254: "순창군", 255: "북창원",
    257: "양산시", 258: "보성군", 259: "강진군", 260: "장흥", 261: "해남",
    262: "고흥", 263: "의령군", 264: "함양군", 266: "광양시", 268: "진도군",
    271: "봉화", 272: "영주", 273: "문경", 276: "청송군", 277: "영덕",
    278: "의성", 279: "구미", 281: "영천", 283: "경주시", 284: "거창",
    285: "합천", 288: "밀양", 289: "산청", 294: "거제", 295: "남해",
}

# ★열 순서 = 활용가이드 명세 순서 = DB 테이블 public.weather_asos_raw 순서★
# (앞에 stnNm 이 하나 끼는 것만 다르다. id · created_at 은 CSV 에 없다.)
# 셋이 같으므로 컬럼 목록 없는 COPY 도 어긋나지 않지만, load_to_pg.py 는 그래도
# 목록을 준다 — 셋 중 하나만 바뀌어도 조용히 깨지는 종류의 일치이기 때문이다.
COLUMNS = [
    "stnId", "stnNm", "tm",
    "avgTa", "minTa", "minTaHrmt", "maxTa", "maxTaHrmt",
    "sumRnDur", "mi10MaxRn", "mi10MaxRnHrmt", "hr1MaxRn", "hr1MaxRnHrmt", "sumRn",
    "maxInsWs", "maxInsWsWd", "maxInsWsHrmt", "maxWs", "maxWsWd", "maxWsHrmt",
    "avgWs", "hr24SumRws", "maxWd",
    "avgTd", "minRhm", "minRhmHrmt", "avgRhm", "avgPv",
    "avgPa", "maxPs", "maxPsHrmt", "minPs", "minPsHrmt", "avgPs",
    "ssDur", "sumSsHr", "hr1MaxIcsrHrmt", "hr1MaxIcsr", "sumGsr",
    "ddMefs", "ddMefsHrmt", "ddMes", "ddMesHrmt", "sumDpthFhsc",
    "avgTca", "avgLmac",
    "avgTs", "minTg",
    "avgCm5Te", "avgCm10Te", "avgCm20Te", "avgCm30Te",
    "avgM05Te", "avgM10Te", "avgM15Te", "avgM30Te", "avgM50Te",
    "sumLrgEv", "sumSmlEv", "n99Rn", "iscs", "sumFogDur",
]


def _read_env(path):
    """.env 를 읽어 환경변수에 채운다. 이미 있는 값은 덮지 않는다."""
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8-sig") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            v = v.strip()
            if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
                v = v[1:-1]
            os.environ.setdefault(k.strip(), v)


def load_key():
    # 이 폴더의 .env → 프로젝트 루트 .env 순으로 읽는다.
    # 프로젝트 관례가 .env 이고, 키가 네 군데로 흩어져 있어 루트로 모으는 중이다.
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.dirname(os.path.dirname(here))
    _read_env(os.path.join(here, ".env"))
    _read_env(os.path.join(root, ".env"))

    # 이름을 여러 개 받는다. 공공데이터포털은 계정당 인증키가 하나라서
    # 다른 수집기가 쓰는 키를 그대로 써도 된다 (ASOS 활용신청만 돼 있으면).
    key = (os.environ.get("ASOS_KEY")            # 쓰임 이름 (2026-09-04 · S-01)
           or os.environ.get("ASOS_SERVICE_KEY")
           or os.environ.get("DATA_GO_KR_KEY")
           or os.environ.get("DATA_GO_KR_SERVICE_KEY"))
    if not key:
        path = os.path.join(here, "service_key.txt")
        if os.path.exists(path):
            with open(path, encoding="utf-8-sig") as f:   # BOM 붙은 파일도 받아들인다
                key = f.read()
    if not key:
        sys.exit(
            "인증키가 없다.\n"
            "  데이터 수집/기상데이터/.env 의 ASOS_SERVICE_KEY 에 넣어라.\n"
            "  (루트 .env 의 DATA_GO_KR_KEY 도 읽는다. service_key.txt 도 가능)")
    key = key.strip().lstrip("﻿")     # BOM 한 글자가 섞이면 403 이 난다
    # 공공데이터포털 '일반 인증키(Encoding)' 를 그대로 붙여넣어도 되게, 이미 인코딩된
    # 키는 한 번 풀어서 아래에서 다시 인코딩한다 (이중 인코딩 방지).
    return urllib.parse.unquote(key)


class Throttle:
    """초당 호출 수를 MAX_TPS 아래로 유지한다."""

    def __init__(self, tps):
        self.interval = 1.0 / tps
        self.next_at = 0.0
        import threading
        self.lock = threading.Lock()

    def wait(self):
        with self.lock:
            now = time.monotonic()
            if now < self.next_at:
                delay = self.next_at - now
            else:
                delay = 0.0
                self.next_at = now
            self.next_at += self.interval
        if delay:
            time.sleep(delay)


throttle = Throttle(MAX_TPS)


def fetch(key, stn, start, end, page=1):
    """한 번 호출. (rows, note) 반환. note 가 있으면 정상 조회가 아니다."""
    qs = urllib.parse.urlencode({
        "serviceKey": key, "pageNo": page, "numOfRows": MAX_ROWS,
        "dataType": "XML", "dataCd": "ASOS", "dateCd": "DAY",
        "startDt": start, "endDt": end, "stnIds": stn,
    })
    url = f"{BASE}?{qs}"
    last = ""
    for attempt in range(RETRY):
        throttle.wait()
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "python-urllib"})
            with urllib.request.urlopen(req, timeout=120) as r:
                body = r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as ex:
            last = f"HTTP {ex.code}"
            if ex.code in (400, 401, 403, 404):   # 키·주소 문제는 재시도해도 같다
                return [], last
            time.sleep(2 * (attempt + 1))
            continue
        except Exception as ex:
            last = f"{type(ex).__name__}: {ex}"
            time.sleep(2 * (attempt + 1))
            continue

        code = re.search(r"<resultCode>\s*(\d+)\s*</resultCode>", body)
        code = code.group(1).zfill(2) if code else None
        if code == "03":                      # NODATA_ERROR — 그 기간에 관측이 없다
            return [], "NODATA"
        if code not in ("00", None):
            msg = re.search(r"<resultMsg>([^<]*)</resultMsg>", body)
            last = f"resultCode={code} {msg.group(1) if msg else ''}".strip()
            if code in ("01", "02", "04", "05", "99"):   # 일시적일 수 있는 것만 재시도
                time.sleep(2 * (attempt + 1))
                continue
            return [], last                   # 키/파라미터 문제는 재시도해도 같다

        try:
            root = ET.fromstring(body)
        except ET.ParseError as ex:
            last = f"ParseError: {ex}"
            time.sleep(2 * (attempt + 1))
            continue

        rows = [{c.tag: (c.text or "").strip() for c in item}
                for item in root.iter("item")]
        total = root.find(".//totalCount")
        total = int(total.text) if total is not None and total.text else len(rows)
        return rows, ("", total)

    return [], last or "unknown error"


def windows(start, end, span):
    """[start, end] 를 span 일짜리 구간으로 자른다."""
    cur = start
    while cur <= end:
        last = min(cur + timedelta(days=span - 1), end)
        yield cur.strftime("%Y%m%d"), last.strftime("%Y%m%d")
        cur = last + timedelta(days=1)


def verify_rows(recs, header):
    """계약 점검 — 파일이 아니라 **행 목록**에서 잰다.

    원래 CSV 를 쓴 뒤 파일을 다시 읽어 검사했다. 7개 중 파일이라서 되는 건
    둘(인코딩·BOM)뿐이고, 나머지 다섯은 내용 검사라 메모리에서 똑같이 된다.
    DB 직행이면 인코딩 문제 자체가 없어진다.
    """
    print("\n데이터 계약 점검 (메모리)")
    ok = True

    def say(no, rule, passed, detail):
        nonlocal ok
        ok = ok and passed
        print(f"  [{'OK' if passed else '실패'}] {no}. {rule} — {detail}")

    dup = [k for k, v in collections.Counter(header).items() if v > 1]
    say(2, "헤더 유지", not dup, f"{len(header)}열 · 중복 {dup or '없음'}")

    i_tm = header.index("tm")
    bad = sum(1 for r in recs if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(r[i_tm])))
    lead0 = sum(1 for r in recs for c in header if c.endswith("Hrmt")
                and len(str(r[header.index(c)])) > 1
                and str(r[header.index(c)]).startswith("0"))
    say(3, "날짜 문자열 유지", bad == 0,
        f"tm 형식 위반 {bad}행 · 시각 선행 0 보존 {lead0:,}개")

    odd = collections.Counter(); blank = 0
    for r in recs:
        for v in r:
            v = "" if v is None else str(v)
            if v == "":
                blank += 1
            elif v.strip() == "" or v.upper() in ("NULL", "NA", "N/A", "NAN", "NONE", "-"):
                odd[v] += 1
    say(4, "빈값 표기 통일", not odd,
        f"빈값 {blank:,}개 · 섞인 결측표기 {dict(odd) or '없음'}")

    zeros = sum(1 for r in recs for v in r if str(v) in ("0", "0.0", "0.00"))
    say(5, "원래 0 인 값 보존", zeros > 0, f"0 값 {zeros:,}개 그대로")

    extra = sorted(set(header) - set(COLUMNS))
    missing = sorted(set(COLUMNS) - set(header))
    say(6, "API 원본 컬럼명 유지", not extra and not missing,
        f"명세 밖 {extra or '없음'} · 빠짐 {missing or '없음'}")

    say(7, "DB 테이블 열 순서 일치", header[:len(COLUMNS)] == COLUMNS,
        "public.weather_asos_raw 순서 그대로" if header[:len(COLUMNS)] == COLUMNS
        else "★어긋남★")

    print(f"  => {'계약 충족' if ok else '★계약 위반★'}")
    return ok


def verify(path, header):
    """저장한 CSV 가 팀이 준 데이터 계약 6개를 지키는지 검사한다.

    계약은 문장으로 두면 조용히 깨진다. 뽑을 때마다 자동으로 재는 게 요점이다.
    """
    print("\n데이터 계약 점검")
    ok = True

    def say(no, rule, passed, detail):
        nonlocal ok
        ok = ok and passed
        print(f"  [{'OK' if passed else '실패'}] {no}. {rule} — {detail}")

    head = open(path, "rb").read(3)
    has_bom = head == b"\xef\xbb\xbf"
    say(1, "인코딩 UTF-8", True,
        f"BOM {'있음 (--bom · Excel 용)' if has_bom else '없음 (순수 UTF-8)'}")

    with open(path, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.reader(f))
    hdr, body = rows[0], rows[1:]

    dup = [k for k, v in collections.Counter(hdr).items() if v > 1]
    say(2, "헤더 유지", hdr == header and not dup,
        f"{len(hdr)}열 · 중복 {dup or '없음'}")

    i_tm = hdr.index("tm")
    bad = sum(1 for x in body if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", x[i_tm]))
    lead0 = sum(1 for x in body for c in hdr if c.endswith("Hrmt")
                and len(x[hdr.index(c)]) > 1 and x[hdr.index(c)].startswith("0"))
    say(3, "날짜 문자열 유지", bad == 0,
        f"tm 형식 위반 {bad}행 · 시각 선행 0 보존 {lead0:,}개")

    odd = collections.Counter()
    blank = 0
    for x in body:
        for v in x:
            if v == "":
                blank += 1
            elif v.strip() == "" or v.upper() in ("NULL", "NA", "N/A", "NAN", "NONE", "-"):
                odd[v] += 1
    say(4, "빈값 표기 통일", not odd,
        f"빈 문자열 {blank:,}개 · 섞인 결측표기 {dict(odd) or '없음'}")

    zeros = sum(1 for x in body for v in x if v in ("0", "0.0", "0.00"))
    say(5, "원래 0 인 값 보존", zeros > 0,
        f"0 값 {zeros:,}개 그대로 (빈칸으로 바꾸지 않았다)")

    extra = sorted(set(hdr) - set(COLUMNS))
    missing = sorted(set(COLUMNS) - set(hdr))
    say(6, "API 원본 컬럼명 유지", not extra and not missing,
        f"명세 밖 {extra or '없음'} · 빠짐 {missing or '없음'}")

    say(7, "DB 테이블 열 순서 일치", hdr[:len(COLUMNS)] == COLUMNS,
        "public.weather_asos_raw 순서 그대로" if hdr[:len(COLUMNS)] == COLUMNS
        else "★어긋남 — COPY 에 컬럼 목록을 반드시 줘라★")

    print(f"  => {'계약 충족' if ok else '★계약 위반 — 위 실패 항목을 보라★'}")
    return ok


def load_to_db(recs, header):
    """CSV 를 거치지 않고 weather_asos_raw 에 넣는다.

    빈 문자열은 NULL 로 바꾼다. **0 은 건드리지 않는다** — ASOS 는 무강수일에
    sumRn 을 빈 값으로 주고, 0 은 "쟀는데 0" 이다. 둘을 섞으면 안 된다.
    CSV 를 경유하면 이 구분이 문자열로 뭉개져 로더가 다시 복원해야 한다.
    """
    sys.path.insert(0, os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__)))))
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    try:
        import _dbload
    except ImportError as exc:
        print(f"[!] 공용 적재 모듈을 찾지 못했다: {exc}")
        return 1

    text_cols = {"stnId", "stnNm", "tm", "iscs"}
    typed = []
    for r in recs:
        v = []
        for c, x in zip(header, r):
            x = "" if x is None else str(x)
            v.append(x if (c in text_cols or x != "") else None)
        typed.append(v)

    print("\n[DB 적재] weather_asos_raw")
    try:
        _dbload.upsert("weather_asos_raw", header, typed,
                       conflict='("stnId", tm)', key_cols=["stnId", "tm"],
                       compare=["avgTa", "minTa", "maxTa"], label="asos")
    except Exception as exc:                                 # noqa: BLE001
        print(f"[!] DB 적재 실패: {exc}")
        return 1
    return 0


def main():
    args = sys.argv[1:]
    bom = "--bom" in args
    load_db = "--load-db" in args
    no_csv = "--no-csv" in args
    if no_csv and not load_db:
        sys.exit("--no-csv 는 --load-db 와 함께 써라.")
    args = [a for a in args if not a.startswith("--")]
    start_s = args[0] if len(args) > 0 else "20220101"   # 팀이 정한 대상 기간
    end_s = args[1] if len(args) > 1 else "20251231"
    out = args[2] if len(args) > 2 else f"asos_daily_{start_s}_{end_s}.csv"

    start = datetime.strptime(start_s, "%Y%m%d").date()
    end = datetime.strptime(end_s, "%Y%m%d").date()
    yesterday = date.today() - timedelta(days=1)
    if end > yesterday:                        # 전일(D-1) 까지만 제공
        print(f"[!] endDt 를 {end} -> {yesterday} 로 줄인다 (전일까지만 제공)")
        end = yesterday
    if start > end:
        sys.exit("startDt 가 endDt 보다 뒤다.")

    key = load_key()

    # 190회를 다 태우고 나서 "전부 실패" 를 알게 되지 않도록, 한 번 찔러보고 시작한다.
    _, note = fetch(key, 108, start.strftime("%Y%m%d"), start.strftime("%Y%m%d"))
    if isinstance(note, str) and note != "NODATA":
        sys.exit(f"첫 호출부터 실패한다 — 쿼터를 쓰기 전에 멈춘다: {note}")

    chunks = list(windows(start, end, MAX_ROWS))
    jobs = [(stn, s, e) for stn in sorted(STATIONS) for s, e in chunks]
    print(f"기간 {start}~{end} · 지점 {len(STATIONS)}개 · 구간 {len(chunks)}개 "
          f"-> 호출 {len(jobs)}회 (일일 한도 10,000)")

    results, problems = {}, []
    done = 0

    def work(job):
        stn, s, e = job
        rows, note = fetch(key, stn, s, e)
        return job, rows, note

    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        for (stn, s, e), rows, note in pool.map(work, jobs):
            done += 1
            if isinstance(note, tuple):
                _, total = note
                if total > len(rows):          # 999 로 못 담은 구간 (있으면 안 되지만 방어)
                    for page in range(2, math.ceil(total / MAX_ROWS) + 1):
                        more, _ = fetch(key, stn, s, e, page)
                        rows.extend(more)
            elif note == "NODATA":
                pass
            else:
                problems.append((stn, s, e, note))
            for r in rows:
                results[(str(stn), r.get("tm", ""))] = r
            print(f"\r  {done}/{len(jobs)}  누적 {len(results):,}행", end="", flush=True)
    print()

    # 모르는 필드가 오면 버리지 않고 뒤에 붙인다 — 다만 그러면 DB 열 순서와 어긋나므로
    # 경고를 찍는다. 테이블에도 열을 더하거나, 목록을 준 COPY 로 넣어야 한다.
    extras = sorted({k for r in results.values() for k in r} - set(COLUMNS))
    if extras:
        print(f"[!] 명세에 없는 응답 필드를 뒤에 붙인다: {', '.join(extras)}")
        print("    → DB 열 순서와 어긋난다. load_to_pg.py 는 컬럼 목록을 주므로 안전하다.")
    header = COLUMNS + extras

    # 행을 한 번만 만들어 CSV·DB 양쪽에 쓴다. 두 벌로 만들면 갈라진다.
    recs = []
    for (stn, tm), r in sorted(results.items(), key=lambda kv: (int(kv[0][0]), kv[0][1])):
        r = dict(r)
        # 지점명은 ★API 가 준 값을 쓴다★. 코드표는 API 가 안 줬을 때만 메운다 —
        # 열 이름만 원본이고 값은 우리 것이면 "API 원본" 이 아니다.
        if not r.get("stnNm"):
            r["stnNm"] = STATIONS.get(int(stn), "")
        recs.append([r.get(c, "") for c in header])

    if load_db:
        verify_rows(recs, header)
        rc = load_to_db(recs, header)
        if rc:
            sys.exit(rc)
        if no_csv:
            print("\n(CSV 미생성 — --no-csv)")
            return

    # 인코딩: 계약이 "UTF-8" 이므로 기본은 BOM 없는 순수 UTF-8 이다.
    # --bom 은 Excel 에서 더블클릭으로 열 때만 쓴다 (BOM 이 없으면 한글이 깨진다).
    with open(out, "w", newline="", encoding="utf-8-sig" if bom else "utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(recs)

    days = (end - start).days + 1
    print(f"\n저장: {os.path.abspath(out)}")
    print(f"  {len(results):,}행 · {len(header)}열 · "
          f"{os.path.getsize(out) / 1024 / 1024:.1f} MB")
    print(f"  지점 {len({k[0] for k in results}):,}개 / 최대 가능 {len(STATIONS) * days:,}행")
    if problems:
        print(f"\n[!] 실패한 구간 {len(problems)}건 — 다시 돌리면 이어서 채운다:")
        for stn, s, e, note in problems[:20]:
            print(f"    {stn} {s}~{e}  {note}")
        if len(problems) > 20:
            print(f"    ... 외 {len(problems) - 20}건")

    verify(out, header)


if __name__ == "__main__":
    main()
