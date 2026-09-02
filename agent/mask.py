# -*- coding: utf-8 -*-
"""밖으로 보내기 전에 비밀 정보를 가린다 (2026-08-31).

## 왜 필요한가

AI 도우미는 오류 문구·로그·코드를 외부 API 로 보낸다. 그런데 우리 로그에는
접속 정보가 통째로 찍히는 경우가 있다. 실제로 오늘 이런 오류를 봤다.

    psycopg.OperationalError: connection to server at "db.example.invalid" ...

CLAUDE.md 3절이 **"접속 정보는 .env 에. 코드나 문서에 절대 쓰지 말 것"** 이라고
못박고 있다. 밖으로 나가는 건 더 위험하다.

게다가 **Gemini 무료 등급은 보낸 내용을 모델 학습에 쓸 수 있다.**
한 번 나가면 되돌릴 수 없다.

## 원칙

  · **보내는 모든 문자열이 이 함수를 지나간다.** 예외를 두지 않는다
  · 못 지우면 통째로 버린다 — 애매하면 안 보내는 쪽
  · 가린 자리를 남긴다 (`***`). 무엇이 있었는지는 알 수 있어야 조사가 된다

## 시험

    python agent/mask.py        내장 시험 실행
"""
from __future__ import annotations

import re

# 순서가 중요하다. 넓은 것부터 지워야 조각이 안 남는다.
RULES: list[tuple[str, re.Pattern]] = [
    # postgresql://user:pass@host/db 처럼 **비밀번호가 든** 접속 문자열만 지운다.
    #   평범한 https 주소는 남긴다 — 어느 API 를 부르다 났는지 알아야 조사가 된다.
    ("접속문자열", re.compile(r"\b[a-z+]{3,12}://[^\s'\"/@]+:[^\s'\"/@]+@[^\s'\"]+", re.I)),
    # 사설 IP (우리 내부망) 과 그 뒤 포트
    ("내부IP", re.compile(r"\b(?:10|127|192\.168|172\.(?:1[6-9]|2\d|3[01]))"
                          r"(?:\.\d{1,3}){1,3}(?::\d{2,5})?\b")),
    # KEY / TOKEN / PASSWORD = 값
    ("키설정", re.compile(r"(?i)\b([A-Z0-9_]*(?:KEY|TOKEN|SECRET|PASSWORD|PWD)"
                          r"[A-Z0-9_]*)\s*[=:]\s*['\"]?([^\s'\"]+)")),
    # 공공데이터포털 serviceKey 처럼 URL 파라미터로 붙는 것
    ("URL키", re.compile(r"(?i)([?&](?:serviceKey|api[_-]?key|token)=)[^&\s]+")),
    # 40자 이상 이어지는 base64 스러운 덩어리 (키일 가능성)
    #   ※ `/` 를 넣으면 **파일 경로를 통째로 삼킨다.** 실제로
    #     `ML/20260824/ml_train_kit_2/exp_carryover.py` 가 키로 잡혔다.
    #     경로가 지워지면 조사가 불가능해지므로 `/` 는 뺀다.
    #   ※ 대문자·소문자·숫자가 **모두** 섞인 것만 본다. 그래야 긴 함수 이름이나
    #     한글 없는 문장이 잘못 걸리지 않는다.
    ("긴키덩어리", re.compile(
        r"\b(?=[A-Za-z0-9+%_-]*[A-Z])(?=[A-Za-z0-9+%_-]*[a-z])"
        r"(?=[A-Za-z0-9+%_-]*\d)[A-Za-z0-9+%_-]{40,}={0,2}\b")),
    # 이메일
    ("이메일", re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]+\b")),
]

# 가려도 되지만 조사에 필요한 것은 살린다.
#   파일 경로의 사용자 이름만 지우고 나머지 경로는 남긴다.
_USERPATH = re.compile(r"(?i)([A-Z]:\\Users\\)[^\\]+")


def mask(text: str) -> str:
    """문자열에서 비밀 정보를 지운다. 무엇을 지웠는지는 표시로 남긴다."""
    if not text:
        return text
    out = text
    for name, pat in RULES:
        if name == "키설정":
            out = pat.sub(lambda m: f"{m.group(1)}=***가림***", out)
        elif name == "URL키":
            out = pat.sub(lambda m: f"{m.group(1)}***가림***", out)
        else:
            out = pat.sub(f"***{name}가림***", out)
    out = _USERPATH.sub(r"\1***", out)
    return out


def mask_all(obj):
    """딕셔너리·리스트 안까지 훑어서 가린다."""
    if isinstance(obj, str):
        return mask(obj)
    if isinstance(obj, dict):
        return {k: mask_all(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return type(obj)(mask_all(v) for v in obj)
    return obj


# 이미 가려진 자리를 다시 위험으로 세지 않기 위한 표시.
#   `NAME=***가림***` 처럼 **이름까지 통째로** 지워야 한다. 표시만 지우면
#   `NAME=` 이 남고, 뒤따르는 글자가 다시 값처럼 잡혀 늘 위험으로 나온다.
_MASKED = re.compile(r"(?:[^\s=:]+\s*[=:]\s*)?\*\*\*[^*]*가림\*\*\*")


def looks_leaky(text: str) -> list[str]:
    """가린 뒤에도 남아 있는 위험 신호를 찾는다. 최종 확인용.

    가림 표시(`***…가림***`)를 먼저 지우고 검사한다. 안 그러면
    `KEY=***가림***` 이 다시 "키설정" 으로 잡혀 늘 위험으로 나온다.
    """
    probe = _MASKED.sub("", text)
    hits = []
    for name, pat in RULES:
        if pat.search(probe):
            hits.append(name)
    return hits


if __name__ == "__main__":
    cases = [
        ("접속문자열",
         'psycopg.OperationalError: connection to "postgresql://user:PASSWORD@db.example.invalid:5432/cost" failed'),
        ("환경변수",
         "DATA_GO_KR_KEY=abcd1234efgh5678 · GEMINI_API_KEY=AIzaSyD-xxxxxxxxxxxxxxxx"),
        ("URL 파라미터",
         "https://apis.data.go.kr/B552845/katOrigin/trades?serviceKey=Zm9vYmFy%2Bbaz&pageNo=1"),
        ("내부 IP",
         "http://223.255.205.198:24002/api/service 와 <개발PC> 에서 접속"),
        ("사용자 경로",
         r"C:\Users\403\AppData\Local\Temp\claude\...\train.py 449줄"),
        ("정상 로그 (안 지워져야 함)",
         "crop_price_train 198,937행 · 오차 16.0% · train.py:449 · _anchor_mix 없음"),
    ]
    print("=" * 70)
    print("가림 처리 시험")
    print("=" * 70)
    for name, src in cases:
        got = mask(src)
        left = looks_leaky(got)
        print(f"\n[{name}]")
        print(f"  전 : {src[:88]}")
        print(f"  후 : {got[:88]}")
        print(f"  남은 위험: {left if left else '없음'}")
