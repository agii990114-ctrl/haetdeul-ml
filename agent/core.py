# -*- coding: utf-8 -*-
"""agent 공통 뼈대 (2026-08-31).

## 설계 원칙 — 왜 이렇게 만드는가

**규칙이 판단하고, agent 는 설명한다.**

08-28 에 정리한 결론이다. 판단을 LLM 에 맡기면 세 가지가 나빠진다.
  · 같은 상황에 다른 답을 낼 수 있다 (날짜 비교 하나에 그럴 필요가 없다)
  · 호출 비용과 지연이 붙는다
  · **agent 가 조용히 죽으면 "이상 없음" 처럼 보인다** — 08-27 에 경보 파일이
    안 지워져 "매일 실패 중" 으로 보이던 것과 같은 함정이다

그래서 이 모듈의 모든 점검은 **LLM 없이 끝까지 돈다.** 결론·근거·수치가
전부 규칙으로 나오고, LLM 은 그 위에 사람 말 요약을 얹는 선택지일 뿐이다.
LLM 이 없거나 실패해도 보고서는 그대로 나온다.

## 세 agent 가 공유하는 것

  Finding    점검 하나의 결과 (수준 · 제목 · 근거 · 수치)
  Report     Finding 묶음 + 사람이 읽는 출력
  db()       원본/서비스 DB 연결
  narrate()  선택적 LLM 요약. 없으면 조용히 건너뛴다
"""
from __future__ import annotations

import datetime
import io
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

#   ★ 자기 출력을 UTF-8 로 고정한다. **여기 한 곳에서 한다.**
#
#     윈도우 한국어 콘솔은 cp949 라 긴 붙임표 `—` 같은 글자를 못 찍는다.
#     찍으려 들면 그 자리에서 UnicodeEncodeError 로 죽는다. 09-07 에 뉴스
#     도우미가, 09-07~09 사흘 동안 배치 조사 도우미가 이걸로 죽었다.
#
#     `PYTHONIOENCODING=utf-8` 을 붙여 부르면 되지만, **화면에서 부르거나
#     작업 스케줄러가 부르면 그게 안 넘어온다.** 부르는 쪽마다 챙기는 방식은
#     이미 실패했다 — 네 파일에만 넣고 다섯 파일을 빠뜨렸다.
#
#     모든 도우미가 이 모듈을 첫 줄에서 들여온다. 그러니 여기서 한 번 하면
#     새로 만드는 도우미도 저절로 안전하다. `errors="replace"` 라 정말 못 쓰는
#     글자가 있어도 **그 글자만 물음표가 되고 프로그램은 안 죽는다.**
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
    except (AttributeError, ValueError):
        pass                     # 파이프로 묶여 reconfigure 가 없는 경우

ROOT = Path(__file__).resolve().parent.parent

OK, WARN, BAD = "정상", "주의", "이상"
_MARK = {OK: "OK ", WARN: "▲  ", BAD: "*** "}


def _env(path: Path) -> dict:
    out = {}
    if not path.exists():
        return out
    for line in io.open(path, encoding="utf-8", errors="ignore"):
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip()
    return out


#: 접속이 안 되면 이만큼 기다리고 포기한다 (초).  (2026-09-16)
#:
#:   libpq 기본은 0 = **무제한**이다. DB 가 «안 됩니다» 라고 거절하면 바로
#:   오류가 나지만, **아무 답도 안 하면** 계속 기다린다. 방화벽이 패킷을
#:   조용히 버리는 경우가 그렇다.
#:
#:   실측 (2026-09-16 · 응답 없는 주소로 `log_cutover` 호출)
#:       없음              2분이 지나도 안 끝남 — 교체 절차가 그만큼 멈춘다
#:       connect_timeout=5 5초 만에 False
#:
#:   5는 채팅 서버(`mainproject/backend/app/ml/db.py` 의
#:   `CONNECT_TIMEOUT_SECONDS`)·매입(`purchase_agent/db.py`)과 맞춘 값이다.
#:   파트마다 다르면 어느 쪽이 먼저 끊겼는지 화면만 보고 알 수 없다.
CONNECT_TIMEOUT_SECONDS = 5


def db(service: bool = False):
    """DB 연결. service=True 면 예측 전달표가 있는 쪽."""
    import psycopg
    env = _env(ROOT / ".env")
    key = "TEST_DATABASE_URL" if service else "DATABASE_URL"
    url = os.environ.get(key) or env.get(key)
    if not url:
        raise RuntimeError(f"{key} 가 .env 에 없습니다.")
    return psycopg.connect(url, connect_timeout=CONNECT_TIMEOUT_SECONDS)


def to_db(name: str, verdict: str | None, ran_at, payload, body: str,
          source_file: str = "", kind: str | None = None) -> bool:
    """보고서 한 벌을 `agent_report` 에 남긴다. **실패해도 조용히 넘어간다.**

    ★ **여기서 절대 예외를 올리지 않는다.** 이 함수는 배치 한복판에서 불린다.
      보고서를 «알리다가» 배치를 죽이면 본말전도다. 그래서 DB 가 없든,
      표가 없든, 열쇠가 틀렸든 False 를 돌려주고 끝낸다. 파일은 이미 남았다.

    ★ **시각은 한국 시간 그대로 넣는다.** `ran_at` 은 파일 이름에 박힌 값과
      같은 값이다. DB 시계가 UTC 라(9절) 시간대 있는 칸에 넣으면 9시간
      밀린다. 표의 `ran_at` 을 시간대 없는 칸으로 둔 이유다.

    같은 (이름 · 시각 · 가격 종류)가 이미 있으면 덮지 않고 넘어간다 — 과거
    파일을 다시 밀어 넣어도 두 벌이 되지 않는다.

    ★ **열쇠에 가격 종류가 들어간다** (2026-09-16 고침). 전에는 (이름 · 시각)
      뿐이었다. 그런데 재학습판정은 **가격 종류마다 한 건씩** 나오고, 종류
      하나가 0초 만에 끝나면 **다음 것과 같은 초에** 저장된다.
      2026-09-16 09:09:08 에 whsl 과 rtl 이 그렇게 겹쳐, 뒤엣것이
      `ON CONFLICT DO NOTHING` 에 걸려 **조용히 버려졌다.**
      09-11 은 1초 차이라 운으로 둘 다 남았다.

      `kind` 가 없는 보고서(수집검사 · 데이터품질 …)는 `COALESCE(kind,'')`
      로 빈 문자열이 되어 예전과 똑같이 (이름 · 시각)으로만 갈린다.
    """
    try:
        import json as _json                                 # noqa: PLC0415
        #   ★ **초 아래를 자른다** (2026-09-16 고침). 파일 이름에는 초까지만
        #     박히는데(`%H%M%S`) 여기에는 `datetime.now()` 의 마이크로초가
        #     그대로 들어가고 있었다. 그래서 **같은 보고서가 두 행**이 됐다 —
        #     저장할 때 `15:12:32.843535`, 파일에서 밀어넣을 때 `15:12:32`.
        #     실측으로 4행이 그렇게 겹쳐 있었다 (전부 2026-09-16).
        #     두 경로가 **같은 열쇠**를 내야 한다.
        if isinstance(ran_at, datetime.datetime):
            ran_at = ran_at.replace(microsecond=0)
        with db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO agent_report"
                    " (name, kind, verdict, ran_at, payload, body, source_file)"
                    " VALUES (%s, %s, %s, %s, %s::jsonb, %s, %s)"
                    " ON CONFLICT (name, ran_at, (COALESCE(kind, ''))) DO NOTHING",
                    (name, kind or None, verdict, ran_at,
                     _json.dumps(payload, ensure_ascii=False) if payload is not None else None,
                     body, source_file or None))
            conn.commit()
        return True
    except Exception:                                        # noqa: BLE001
        return False


#: 가격 종류 이름표. 코드 쪽은 소문자, 표 쪽은 대문자를 쓴다.
KIND_UP = {"auc": "AUC", "whsl": "WHSL", "rtl": "RTL"}


def bundle_info(d) -> tuple:
    """번들 폴더에서 (폴더이름, 학습끝, 만든날)을 읽는다.

    못 읽으면 그 칸만 None 이다. **여기서 예외를 올리지 않는다** —
    이력을 남기는 일이 교체 자체를 망치면 안 된다.

    ★ 이미 읽어 둔 3칸짜리 묶음을 주면 그대로 돌려준다. 되돌리기처럼
      **폴더를 지운 뒤에 기록해야 하는 자리**에서, 지우기 전에 읽어 둔
      값을 그대로 넘기기 위해서다.
    """
    import json as _json                                     # noqa: PLC0415
    if not d:
        return (None, None, None)
    if isinstance(d, tuple) and len(d) == 3:
        return d
    p = Path(d)
    try:
        m = _json.loads((p / "meta.json").read_text(encoding="utf-8"))
    except Exception:                                        # noqa: BLE001
        return (p.name, None, None)
    te = m.get("train_end")
    try:
        te = datetime.date.fromisoformat(str(te)) if te else None
    except ValueError:
        te = None
    ca = m.get("created_at")
    try:
        ca = datetime.datetime.fromisoformat(str(ca)) if ca else None
    except ValueError:
        ca = None
    if isinstance(ca, datetime.datetime) and ca.tzinfo is not None:
        ca = ca.replace(tzinfo=None)
    return (p.name, te, ca)


def log_cutover(kind: str, model_ver: str, old_dir, new_dir,
                swapped_at=None, actor: str = "", note: str = "",
                time_known: bool = True) -> bool:
    """운영 모델을 바꾼 일을 `model_cutover` 에 한 행 남긴다.

    ★ **여기서 절대 예외를 올리지 않는다.** `to_db()` 와 같은 원칙이다.
      이 함수는 «번들을 이미 바꾼 직후» 에 불린다. 이력을 «알리다가»
      교체 절차를 죽이면 본말전도다. 표가 없든, DB 가 멀든, meta.json 이
      깨졌든 False 를 돌려주고 끝낸다.

    ★ **시각은 한국 시간 그대로 넣는다.** DB 시계가 UTC 라(CLAUDE.md 9절)
      시간대 있는 값으로 넣으면 9시간 밀린다. 표의 `swapped_at` 을
      시간대 없는 칸으로 둔 이유다 — `agent_report.ran_at` 과 같다.

    ★ 모델 «이름»(`model_ver`)은 교체해도 안 바뀐다. 지금이 어느 모델인지는
      `new_train_end` · `new_created_at` 으로 가린다.

    kind        auc / whsl / rtl (대문자도 받는다)
    model_ver   ops_auc · ops_whsl · ops_rtl
    old_dir     바뀌기 전 번들이 옮겨 간 백업 폴더 (Path 또는 문자열)
    new_dir     새로 꽂은 번들이 원래 있던 폴더
    swapped_at  교체 시각. 안 주면 지금
    actor       배치 · 사람 · 되돌리기 · 시뮬레이션 · 추정(백업 폴더)
    time_known  시각까지 아는가. **기본은 참** — 지금 일어나는 교체는
                시계를 그대로 읽으므로 확실하다. 백필처럼 «날짜만 알고
                시각은 모르는» 자리에서만 거짓을 준다. 거짓이면
                `swapped_at` 은 그 날 00:00:00 이고, 화면은 시각을
                감춰야 한다. **모르는 것을 아는 척하지 않기 위한 칸이다.**

    같은 (종류 · 시각)이 이미 있으면 덮지 않고 넘어간다 — 과거 교체를
    두 번 밀어 넣어도 두 벌이 되지 않는다.
    """
    try:
        k = KIND_UP.get(str(kind).strip().lower(), str(kind).strip().upper())
        if k not in ("AUC", "WHSL", "RTL"):
            return False
        at = swapped_at or datetime.datetime.now()
        if isinstance(at, str):
            at = datetime.datetime.fromisoformat(at)
        if at.tzinfo is not None:
            at = at.replace(tzinfo=None)
        at = at.replace(microsecond=0)

        o_name, o_te, o_ca = bundle_info(old_dir)
        n_name, n_te, n_ca = bundle_info(new_dir)
        with db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO model_cutover"
                    " (kind, model_ver, old_bundle, new_bundle,"
                    "  old_train_end, new_train_end,"
                    "  old_created_at, new_created_at,"
                    "  swapped_at, time_known, actor, note)"
                    " VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"
                    " ON CONFLICT (kind, swapped_at) DO NOTHING",
                    (k, model_ver, o_name, n_name, o_te, n_te, o_ca, n_ca,
                     at, bool(time_known), actor or None, note or None))
            conn.commit()
        return True
    except Exception:                                        # noqa: BLE001
        return False


@dataclass
class Finding:
    """점검 하나의 결과.

    level     정상 / 주의 / 이상
    title     한 줄 제목. 사람이 먼저 읽는 문장
    detail    왜 그렇게 판정했나
    numbers   근거 수치. (이름, 값) 목록. **조건 없는 수치는 넣지 않는다**
    advice    무엇을 하면 되나. 없으면 생략
    """
    level: str
    title: str
    detail: str = ""
    numbers: list = field(default_factory=list)
    advice: str = ""


@dataclass
class Report:
    """보고서 한 벌.

    kind  가격 종류 (auc · whsl · rtl). **선택이다** — 종류가 없는 보고서도
          있다 (데이터품질 · 수집검사 …). 있는 것은 반드시 넣는다.

          ★ 왜 필요한가 (2026-09-16). 재학습판정·재학습검증은 **하루에
            가격 종류마다 한 건씩** 나온다. 그런데 `payload` 만으로는 그게
            경락가 것인지 소매가 것인지 가릴 수 없었다. 그래서 채팅 쪽이
            보고서를 읽어도 이름을 못 달았다.
    """
    name: str
    findings: list = field(default_factory=list)
    started: datetime.datetime = field(default_factory=datetime.datetime.now)
    kind: str | None = None

    def add(self, f: Finding) -> None:
        self.findings.append(f)

    @property
    def worst(self) -> str:
        for lv in (BAD, WARN, OK):
            if any(f.level == lv for f in self.findings):
                return lv
        return OK

    def text(self) -> str:
        nl = chr(10)
        bar = "=" * 70
        out = [bar,
               f"{self.name}  ·  {self.started.strftime('%Y-%m-%d %H:%M:%S')}",
               f"판정: {self.worst}",
               bar, ""]
        for f in self.findings:
            out.append(f"{_MARK[f.level]}{f.title}")
            if f.detail:
                for line in f.detail.splitlines():
                    out.append(f"      {line}")
            for k, v in f.numbers:
                out.append(f"        {k:<28} {v}")
            if f.advice:
                out.append(f"      → {f.advice}")
            out.append("")
        return nl.join(out)

    def save(self, subdir: str = "agent_logs") -> Path:
        """보고서를 남긴다. **글과 구조를 나란히 남긴다.**

        ★ `.txt` 는 사람이 읽는 것이다. 수치가 세로로 줄 맞춰져 있다.
        ★ `.json` 은 화면이 읽는 것이다. 판정 배지와 근거 수치를 표로
          그리려면 글이 아니라 구조가 필요하다.

        왜 둘 다인가 — 전에는 `.txt` 만 남겼다. 그래서 화면이 저장된
        보고서를 **글자 덩어리로만** 보일 수 있었고, 방금 돌린 것과
        모양이 달랐다. 같은 내용인데 두 가지로 보이면 사람이 헷갈린다.

        ★ **DB 에도 한 벌 넣는다** (2026-09-16 · `agent_report`).
          파일은 우리 PC 에만 있어서 팀 채팅 쪽 서버가 못 읽는다.
          «오늘 데이터 처리 잘 됐어?» 에 답하려면 저쪽이 같은 내용을
          읽을 수 있어야 한다. **파일이 원본이고 DB 는 사본이다** —
          DB 가 죽어도 여기서 예외가 새어 나가지 않는다.
        """
        from dataclasses import asdict                       # noqa: PLC0415
        import json as _json                                 # noqa: PLC0415

        d = ROOT / "진행기록" / subdir
        d.mkdir(parents=True, exist_ok=True)
        #   ★ **파일 이름에 가격 종류를 붙인다** (2026-09-16 고침).
        #
        #     전에는 `날짜_시각_이름` 뿐이었다. 재학습판정은 가격 종류마다
        #     한 건씩 나오는데, 한 종류가 **0초 만에** 끝나면 다음 것과 같은
        #     초에 저장된다. 그러면 이름이 통째로 같아 **뒤엣것이 앞엣것을
        #     덮었다.** 2026-09-16 09:09:08 에 whsl 이 rtl 에 먹혔다.
        #
        #     종류가 없는 보고서(수집검사 · 데이터품질 …)는 **이름 그대로**다.
        #     그쪽은 하루 한 건이라 겹칠 일이 없고, 이름을 바꾸면 화면·DB 의
        #     기존 기록과 갈린다.
        tail = f"_{self.kind}" if self.kind else ""
        stem = f"{self.started.strftime('%Y-%m-%d_%H%M%S')}_{self.name}{tail}"
        p = d / f"{stem}.txt"
        body = self.text()
        io.open(p, "w", encoding="utf-8").write(body)
        payload = {
            "name": self.name,
            "verdict": self.worst,
            #   ★ 종류가 없는 보고서도 있으므로 None 을 그대로 둔다.
            #     빈 문자열로 바꾸면 «안 넣은 것» 과 «없는 것» 이 섞인다.
            "kind": self.kind,
            "at": self.started.strftime("%Y-%m-%d %H:%M:%S"),
            "findings": [asdict(f) for f in self.findings],
        }
        #   ★ 구조 저장이 실패해도 `.txt` 는 이미 남았다. 여기서 죽어서
        #     보고서를 통째로 잃으면 본말전도다.
        try:
            io.open(d / f"{stem}.json", "w", encoding="utf-8").write(
                _json.dumps(payload, ensure_ascii=False, indent=1))
        except Exception:                                    # noqa: BLE001
            pass
        to_db(self.name, self.worst, self.started, payload, body, p.name,
              kind=self.kind)
        return p


def narrate(report: Report) -> str | None:
    """선택적 LLM 요약. 키가 없으면 None 을 돌려주고 조용히 넘어간다.

    **이 함수가 실패해도 보고서는 이미 완성돼 있다.** 그게 요점이다.
    """
    key = os.environ.get("ANTHROPIC_API_KEY") or _env(ROOT / ".env").get("ANTHROPIC_API_KEY")
    if not key:
        return None
    try:
        import anthropic
        c = anthropic.Anthropic(api_key=key)
        msg = c.messages.create(
            model="claude-sonnet-5",
            max_tokens=600,
            messages=[{"role": "user", "content":
                       "아래는 농산물 가격 예측 시스템의 점검 보고서다. "
                       "초등학생도 알아듣게 세 문장으로 요약하라. "
                       "숫자는 그대로 쓰고, 나쁜 소식은 순화하지 마라." + chr(10) * 2
                       + report.text()}])
        return msg.content[0].text
    except Exception:                                        # noqa: BLE001
        return None
