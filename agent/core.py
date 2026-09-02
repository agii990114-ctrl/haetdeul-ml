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
from dataclasses import dataclass, field
from pathlib import Path

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


def db(service: bool = False):
    """DB 연결. service=True 면 예측 전달표가 있는 쪽."""
    import psycopg
    env = _env(ROOT / ".env")
    key = "TEST_DATABASE_URL" if service else "DATABASE_URL"
    url = os.environ.get(key) or env.get(key)
    if not url:
        raise RuntimeError(f"{key} 가 .env 에 없습니다.")
    return psycopg.connect(url)


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
    name: str
    findings: list = field(default_factory=list)
    started: datetime.datetime = field(default_factory=datetime.datetime.now)

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
        d = ROOT / "진행기록" / subdir
        d.mkdir(parents=True, exist_ok=True)
        p = d / f"{self.started.strftime('%Y-%m-%d_%H%M%S')}_{self.name}.txt"
        io.open(p, "w", encoding="utf-8").write(self.text())
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
