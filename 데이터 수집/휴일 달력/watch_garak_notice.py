# -*- coding: utf-8 -*-
"""
가락시장 휴업 공고 감시 — ref_calendar_override 후보 뽑기
=========================================================
서울시농수산식품공사 공지 게시판에서 '휴업' 공고를 긁어 날짜 후보를 뽑고,
`25_ref_calendar.sql` 의 override 목록과 대조한다.

    python watch_garak_notice.py                 # 대조 리포트
    python watch_garak_notice.py --future-only   # 오늘 이후만 (운영용)
    python watch_garak_notice.py --dump          # 추출 원문까지 보기

이 스크립트를 믿지 말 것 — 보조 수단이다
-----------------------------------------
**과거 휴장의 정답은 게시판이 아니라 `auction_prices_daily` 실거래일이다.**
"규칙상 개장인데 거래 0건" 을 뽑으면 그게 비정기 휴장이고, 그 방법으로
override 14건을 채워 오탐 0 · 미탐 0 을 달성했다 (25_ref_calendar.sql).

게시판이 필요한 건 **아직 지나지 않은 날**뿐이다. 리드타임이 18영업일이니
3~4주 앞까지만 알면 되고, 비정기 휴장은 연 1.3회다. 월 1회 이 스크립트를
돌려 후보를 보고, 사람이 확인해 override 에 넣으면 충분하다.

왜 완전 자동이 안 되나
----------------------
공고 본문이 대부분 **이미지**다. 다행히 접근성용 `alt` 속성에 내용을 적어두는
경우가 있어 거기서 날짜를 건질 수 있는데, 공고마다 품질이 다르다.

    시범휴업·하계·추석 공고   alt 에 날짜가 다 들어 있다      → 추출 가능
    정기·설·신년 공고        "자세한 내용은 이미지를 확인해 주세요"  → 사람이 봐야 함

그래서 이 스크립트는 **못 뽑은 공고를 숨기지 않고 따로 표시한다.**
조용히 0건을 반환하는 것이 가장 나쁘다.

날짜 표기도 제각각이라 세 가지 패턴을 모두 훑는다.
    ’26.6.3.(수)      시범휴업 개요 — 이게 휴업일 자체다
    2026년 6월 3일     본문 문장
    7. 31.(목)        하계휴업 표 — 연도가 없어 제목에서 가져온다
"""
import argparse
import datetime
import html
import os
import re
import sys
import urllib.request

BASE = "https://www.garak.co.kr/homepage/M0000227/board"
LIST_URL = BASE + "/list.do?searchCondition=0&searchKeyword=%s&pageIndex=%d"
VIEW_URL = BASE + "/view.do?atcSn=%s"
UA = "Mozilla/5.0 (compatible; cost-catcher/1.0)"

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
OVERRIDE_SQL = os.path.join(ROOT, "SQL", "25_ref_calendar.sql")

DOW = "월화수목금토일"


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def strip_tags(s):
    s = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", s, flags=re.S | re.I)
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", html.unescape(s)).strip()


def list_posts(keyword, pages):
    """게시판 목록에서 (atcSn, 제목) 을 모은다."""
    out, seen = [], set()
    kw = urllib.request.quote(keyword)
    for p in range(1, pages + 1):
        try:
            s = get(LIST_URL % (kw, p))
        except Exception as e:
            print("  [경고] 목록 %d쪽 실패: %s" % (p, e), file=sys.stderr)
            continue
        for sn, raw in re.findall(r"atcSn=(\d+)[^>]*>(.*?)</a>", s, re.S):
            t = strip_tags(raw)
            if t and sn not in seen:
                seen.add(sn)
                out.append((sn, t))
    return out


def extract_text(page):
    """본문 텍스트 + 이미지 alt. alt 가 진짜 내용을 담는 경우가 많다."""
    alts = [html.unescape(m.group(1))
            for m in re.finditer(r'<img[^>]*alt="([^"]{30,})"', page)]
    body = strip_tags(page)
    return alts, body


def find_dates(text, title_year):
    """날짜 후보를 뽑는다. (date, 원문조각) 목록."""
    found = []

    def add(y, mo, d, frag):
        try:
            found.append((datetime.date(int(y), int(mo), int(d)), frag))
        except ValueError:
            pass

    # ’26.6.3. / '26.6.3 / ‘26.6.3.  ← 시범휴업 개요. 휴업일 자체다
    for m in re.finditer(r"[’'‘`](\d{2})\.\s*(\d{1,2})\.\s*(\d{1,2})\.?", text):
        add(2000 + int(m.group(1)), m.group(2), m.group(3), m.group(0))

    # 2026년 6월 3일
    for m in re.finditer(r"(\d{4})\s*년\s*(\d{1,2})\s*월\s*(\d{1,2})\s*일", text):
        add(m.group(1), m.group(2), m.group(3), m.group(0))

    # 6월 3일  ← 연도 없음. 추석·하계 공고가 이렇게 쓴다. 제목 연도를 빌린다
    if title_year:
        for m in re.finditer(r"(?<!\d년\s)(?<!\d년)(\d{1,2})\s*월\s*(\d{1,2})\s*일", text):
            add(title_year, m.group(1), m.group(2), m.group(0))

    # 7. 31.(목)  ← 연도 없음. 제목 연도를 빌린다
    if title_year:
        for m in re.finditer(r"(?<![\d.])(\d{1,2})\.\s*(\d{1,2})\.\s*\(([월화수목금토일])\)", text):
            mo, d, w = m.group(1), m.group(2), m.group(3)
            for y in (title_year, title_year + 1):     # 연말 공고가 다음 해를 가리키기도 한다
                try:
                    dt = datetime.date(y, int(mo), int(d))
                except ValueError:
                    continue
                if DOW[dt.weekday()] == w:             # 요일이 맞아야 채택 — 연도 판별에 쓴다
                    found.append((dt, m.group(0)))
                    break

    uniq = {}
    for d, frag in found:
        uniq.setdefault(d, frag)
    return sorted(uniq.items())


def load_overrides():
    """25_ref_calendar.sql 에서 경매 축 override 날짜를 읽는다."""
    if not os.path.exists(OVERRIDE_SQL):
        print("  [경고] %s 없음 — 대조를 건너뜁니다." % OVERRIDE_SQL, file=sys.stderr)
        return {}
    s = open(OVERRIDE_SQL, encoding="utf-8").read()
    out = {}
    for m in re.finditer(r"\('(\d{4}-\d{2}-\d{2})','open',(true|false),'([^']*)'\)", s):
        out[datetime.date.fromisoformat(m.group(1))] = (m.group(2) == "true", m.group(3))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--keyword", default="휴업")
    ap.add_argument("--pages", type=int, default=2)
    ap.add_argument("--future-only", action="store_true",
                    help="오늘 이후 날짜만 본다. 과거는 실거래일이 정답이므로 운영에서는 이걸 쓴다")
    ap.add_argument("--dump", action="store_true", help="추출한 원문도 출력")
    ap.add_argument("--today", help="기준일 (테스트용, YYYY-MM-DD)")
    a = ap.parse_args()

    today = datetime.date.fromisoformat(a.today) if a.today else datetime.date.today()
    ov = load_overrides()
    print("[감시] 가락시장 공지 · 검색어 '%s' · %d쪽" % (a.keyword, a.pages))
    print("[대조] ref_calendar_override 경매 축 %d건 · 기준일 %s" % (len(ov), today))
    print("[주의] 과거 휴장의 정답은 실거래일이다. 이 목록은 미래분 후보로만 쓸 것")
    print()

    posts = list_posts(a.keyword, a.pages)
    print("공고 %d건" % len(posts))
    print()

    blind, cand = [], {}
    for sn, title in posts:
        ty = re.search(r"(\d{4})\s*년", title)
        ty = int(ty.group(1)) if ty else None
        try:
            page = get(VIEW_URL % sn)
        except Exception as e:
            print("  [경고] %s 본문 실패: %s" % (sn, e), file=sys.stderr)
            continue
        alts, body = extract_text(page)
        dates = find_dates(" ".join(alts) + " " + body, ty)
        if a.future_only:
            dates = [(d, f) for d, f in dates if d >= today]

        print("─" * 78)
        print("[%s] %s" % (sn, title))
        print("      %s" % (VIEW_URL % sn))
        if a.dump and alts:
            for x in alts:
                print("      alt: %s" % x[:200])
        if not dates:
            reason = "본문이 이미지뿐이고 alt 에 날짜가 없음" if alts else "날짜를 못 찾음"
            print("      ** 추출 실패 — %s. 사람이 확인할 것 **" % reason)
            blind.append((sn, title))
            continue

        # 시범휴업 공고는 개요에 휴업일 자체가 나열된다 → 후보로 올릴 수 있다.
        # 하계·설·추석·정기 공고는 "채소 7.31 저녁 경매 종료, 8.3 저녁 시작" 처럼
        # **경계일**을 적는다. 그 사이 어느 날이 휴장인지는 부류별 경매 시간까지
        # 따져야 알 수 있어 기계가 판정할 수 없다. 후보로 올리지 않고 참고만 한다.
        trial = "시범" in title
        if not trial:
            print("      (범위형 공고 — 아래는 경매 종료/시작 경계일이다. 휴업일이 아님)")
            blind.append((sn, title + "  ※ 범위형, 경계일만 추출됨"))

        for d, frag in dates:
            tag = DOW[d.weekday()]
            if d in ov:
                mark = "이미 override"
            elif d.weekday() == 6:
                mark = "일요일 — 규칙상 휴장"
            elif d < today:
                mark = "과거 — 실거래일로 확인"
            elif not trial:
                mark = "참고 (경계일)"
            else:
                mark = "★ override 없음"
                cand.setdefault(d, (sn, title, frag))
            print("      %s(%s)  %-22s  「%s」" % (d, tag, mark, frag))

    print("─" * 78)
    print()
    if cand:
        print("★ override 에 없는 미래 날짜 %d건" % len(cand))
        print("  25_ref_calendar.sql 에 아래를 넣고 재실행하세요.")
        print("  (학습 테이블은 2026-02 까지라 v5 재실행은 대개 필요 없습니다)")
        print()
        for d, (sn, title, frag) in sorted(cand.items()):
            print(" ('%s','open',false,'%s (공고 atcSn=%s·미검증)')," % (d, title[:30], sn))
        print()
        print("  ※ 공고 날짜는 미검증입니다. 날짜가 지나면 실거래일로 확정하세요.")
    else:
        print("override 에 없는 미래 날짜: 없음")

    if blind:
        print()
        print("사람이 봐야 하는 공고 %d건 — 본문이 이미지고 alt 에 날짜가 없습니다" % len(blind))
        for sn, title in blind:
            print("  %s  %s" % (VIEW_URL % sn, title))


if __name__ == "__main__":
    main()
