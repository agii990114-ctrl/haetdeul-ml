# -*- coding: utf-8 -*-
"""프롬프트를 여러 파일로 나눈다 (2026-09-02)

## 왜 필요한가

2026-09-02 에 배추 27블록을 한 번에 시켰더니 **답이 망가졌습니다.**
블록마다 새로 답한 게 아니라 **하나의 긴 숫자 줄을 2칸씩 밀어가며** 잘라
썼습니다.

    B01  471, 544, 570, 579, 555, 574, 414, 380, …
    B02            570, 579, 555, 574, 414, 380, …   ← B01 을 2칸 민 것
    B03                      555, 574, 414, 380, …   ← 또 2칸

B01→B05 가 전부 "앞 2칸을 밀면 완전히 같음" 이었습니다. 우연이 아닙니다.
뒤쪽 블록(B24~B27)은 한 칸에 3~4원씩 오르는 직선으로 바뀌었습니다.

**원인은 블록이 많고 다 비슷하게 생긴 것**입니다. 그전까지 잘 되던
프롬프트는 배추·무·양파가 번갈아 나와 구분이 됐는데, 배추만 27개를
연속으로 놓으니 어느 블록인지 놓쳤습니다.

## 그래서

    · 한 번에 30블록쯤으로 나눈다 (5회 잘 돌아간 크기)
    · 품목은 섞어 둔다 (번갈아 나오면 구분이 된다)
    · 블록 번호는 그대로 둔다 — 답을 모아 채점해야 하기 때문

## ★ 자를 때 조심할 것

"## " 로 자르면 안 된다. 머리말의 `## 규칙` · `## 출력 형식` 까지 블록으로
세어 **뒤쪽 조각에 지시문이 통째로 빠진다** (실제로 한 번 그렇게 만들었다).
**번호가 붙은 `## B01` 만** 블록으로 본다.

## 쓰는 법

    python split_prompt.py ../../../실험결과/llm_p20.md --parts 2
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

#   블록 제목만 정확히 잡는다. 머리말의 "## 규칙" 등은 안 걸린다.
BLOCK_RE = re.compile(r"^## (B\d+)\b", re.M)


def main() -> int:
    ap = argparse.ArgumentParser(description="프롬프트를 여러 파일로 나눈다")
    ap.add_argument("path")
    ap.add_argument("--parts", type=int, default=2)
    a = ap.parse_args()

    src = Path(a.path)
    txt = src.read_text(encoding="utf-8")

    pos = [m.start() for m in BLOCK_RE.finditer(txt)]
    if not pos:
        raise SystemExit("블록을 못 찾았습니다. '## B01' 형식인지 보세요.")
    head = txt[:pos[0]]                       # 제목 + 규칙 + 출력 형식 + 참고
    ends = pos[1:] + [len(txt)]
    blocks = [txt[s:e] for s, e in zip(pos, ends)]

    #   마지막 블록 뒤 꼬리말(--- 이후)을 떼어 모든 조각에 붙인다.
    tail = ""
    if "\n---\n" in blocks[-1]:
        i = blocks[-1].rindex("\n---\n")
        blocks[-1], tail = blocks[-1][:i], blocks[-1][i:]

    n = -(-len(blocks) // a.parts)             # 올림 나눗셈
    print(f"[나누기] 블록 {len(blocks)}개 → {a.parts}개 파일 (한 파일 최대 {n}개)")
    for i in range(a.parts):
        chunk = blocks[i * n:(i + 1) * n]
        if not chunk:
            continue
        ids = [BLOCK_RE.match(c).group(1) for c in chunk]
        body = head + "".join(chunk) + tail
        #   "51개 블록 전부에 대해 51줄" 을 이 조각의 개수로 고친다.
        body = re.sub(r"\d+개 블록 전부에 대해 \d+줄",
                      f"{len(chunk)}개 블록 전부에 대해 {len(chunk)}줄", body)
        body = re.sub(r"이제 \d+줄을 출력", f"이제 {len(chunk)}줄을 출력", body)
        body = re.sub(r"for all \d+ blocks", f"for all {len(chunk)} blocks", body)
        body = re.sub(r"Give \d+ lines", f"Give {len(chunk)} lines", body)
        body = re.sub(r"output \d+ lines", f"output {len(chunk)} lines", body)
        fn = src.with_name(src.stem + f"_{i + 1}of{a.parts}.md")
        fn.write_text(body, encoding="utf-8")
        print(f"  {i+1}/{a.parts}  {fn.name}  블록 {len(chunk)}개 "
              f"({ids[0]}~{ids[-1]}) · {fn.stat().st_size/1024:.0f} KB")

    print("\n  ※ 조각마다 **다른 새 대화창**에서 하세요.")
    print("    같은 창에서 이어 하면 앞 답을 기억해 밀어 씁니다.")
    print("  ※ 블록 번호는 그대로 두었습니다. 답을 한 파일에 모아 채점하면 됩니다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
