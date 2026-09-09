"""가격 예측이 왜 예시값으로 떨어지나 — 한 방에 찍어 보는 검사기.

    cd mainproject/backend
    python ../../mainproject_jh_workplace/ops/check_ml_env.py

  (mainproject 저장소만 있는 컴퓨터면 이 파일 하나만 backend/ 에 복사해서
   `python check_ml_env.py` 로 돌려도 됩니다.)

★ **값은 한 글자도 안 찍습니다.** 있는지/없는지, 몇 글자인지, 붙는지만 말합니다.
  비밀번호가 화면이나 로그에 남으면 안 됩니다.

★ **왜 필요한가.** 화면은 DB 에 못 붙어도 죽지 않고 예시값으로 떨어집니다.
  그래서 브라우저 콘솔에 **에러가 안 뜹니다.** 어디서 막혔는지 알려면
  서버 쪽에서 봐야 합니다.

★ `.env` 를 나란히 놓고 비교해도 못 잡는 것들이 있습니다 —
  파일 이름이 `.env.txt` 이거나, BOM 이 붙어 첫 줄 이름이 깨졌거나,
  셸에 낡은 환경변수가 이미 있어서 `.env` 를 **덮어쓰고** 있거나,
  브랜치가 옛것이거나, 사내망 밖이거나. 아래가 그걸 하나씩 봅니다.
"""

from __future__ import annotations

import os
import socket
import sys
from pathlib import Path

OK, BAD, WARN = "  [OK]  ", "  [막힘]", "  [주의]"

NEEDED = ("DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD", "DB_SCHEMA")
SOURCE = "ML_SOURCE_DB_NAME"


def head(title: str) -> None:
    print(f"\n── {title} " + "─" * max(0, 58 - len(title)))


def main() -> int:  # noqa: C901  검사기라 분기가 많은 게 자연스럽다
    fails: list[str] = []

    # ── 1. 어디서 도는가 ────────────────────────────────────────────
    head("1. 자리")
    here = Path.cwd()
    print(f"  지금 폴더   {here}")
    print(f"  파이썬      {sys.version.split()[0]}  ({sys.executable})")

    # `app/ml/db.py` 가 보는 자리와 똑같이 계산한다
    guesses = [here / ".env", here / "backend" / ".env"]
    env_file = next((p for p in guesses if p.exists()), None)
    for p in guesses:
        print(f"  .env 후보   {p}  {'있음' if p.exists() else '없음'}")

    # 흔한 실수: 확장자가 붙은 파일
    for p in guesses:
        for wrong in (p.with_suffix(".env.txt"), p.parent / ".env.txt"):
            if wrong.exists():
                print(f"{WARN} ★ {wrong.name} 이 있습니다 — 윈도우가 확장자를 숨겨서")
                print("        `.env` 로 만든 줄 알았는데 `.env.txt` 인 경우가 많습니다.")

    if env_file is None:
        print(f"{BAD} .env 를 못 찾았습니다. backend/.env 자리에 두세요.")
        return 1
    print(f"{OK} 읽을 파일   {env_file}")

    # ── 2. 파일이 제대로 읽히는가 ───────────────────────────────────
    head("2. 파일 모양")
    raw = env_file.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        print(f"{WARN} ★ BOM 이 붙어 있습니다. 첫 줄 이름이 깨져 안 읽힐 수 있습니다.")
        print("        메모장 대신 VS Code 에서 «UTF-8 (BOM 없음)» 으로 저장하세요.")
        fails.append("BOM")
    text = raw.decode("utf-8-sig", errors="replace")
    if "\r\n" in text:
        print("  줄바꿈      CRLF (윈도우) — 보통 괜찮습니다")

    parsed: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        parsed[k.strip()] = v.strip().strip('"').strip("'")
    print(f"  읽은 줄     {len(parsed)}개")

    for key in NEEDED + (SOURCE,):
        v = parsed.get(key)
        if not v:
            print(f"{BAD} {key:<22} 없거나 비었음")
            fails.append(key)
        else:
            print(f"{OK} {key:<22} 있음 ({len(v)}글자)")

    # ── 3. ★ 셸 환경변수가 .env 를 덮고 있지 않은가 ─────────────────
    head("3. 셸에 이미 값이 있나  ← .env 가 같아도 여기서 갈립니다")
    #   python-dotenv 의 load_dotenv 는 **이미 있는 환경변수를 안 덮어씁니다.**
    #   그래서 셸이나 시스템에 낡은 DB_HOST 가 있으면 .env 를 아무리 고쳐도
    #   그 값이 계속 이깁니다. 이게 "파일은 같은데 결과가 다른" 대표 원인입니다.
    clash = []
    for key in NEEDED + (SOURCE,):
        shell = os.environ.get(key)
        if shell is None:
            continue
        same = shell == parsed.get(key)
        mark = OK if same else BAD
        print(f"{mark} {key:<22} 셸에도 있음 · .env 와 {'같음' if same else '★ 다름'}")
        if not same:
            clash.append(key)
    if clash:
        print(f"{BAD} ★ 셸 값이 .env 를 이깁니다. 이게 원인일 가능성이 큽니다.")
        print("        새 터미널을 열거나, 아래로 지우고 다시 띄우세요:")
        print("          PowerShell:  Remove-Item Env:DB_HOST, Env:DB_PASSWORD")
        fails.append("셸 충돌")
    elif not any(k in os.environ for k in NEEDED):
        print("  셸에 DB_* 없음 — .env 가 그대로 쓰입니다 (좋음)")

    # ── 4. 필요한 꾸러미 ────────────────────────────────────────────
    head("4. 파이썬 꾸러미")
    for mod in ("dotenv", "psycopg"):
        try:
            __import__(mod)
            print(f"{OK} {mod}")
        except Exception as e:  # noqa: BLE001
            print(f"{BAD} {mod} 없음 — {e}")
            print("        이게 없으면 DB 를 못 읽고 조용히 예시값으로 떨어집니다.")
            fails.append(mod)

    # ── 5. 사내망에 닿는가 ──────────────────────────────────────────
    head("5. DB 서버에 닿는가")
    host, port = parsed.get("DB_HOST", ""), int(parsed.get("DB_PORT") or 5432)
    if not host:
        print(f"{BAD} DB_HOST 가 없어 건너뜁니다")
    else:
        try:
            with socket.create_connection((host, port), timeout=5):
                print(f"{OK} {port} 포트 열림 — 사내망 안입니다")
        except Exception as e:  # noqa: BLE001
            print(f"{BAD} 못 닿습니다 ({type(e).__name__})")
            print("        사내망 밖이거나 VPN 이 꺼져 있습니다. .env 문제가 아닙니다.")
            fails.append("망")

    # ── 6. 실제로 로그인되는가 · 표가 보이는가 ──────────────────────
    head("6. 두 창고에 붙어 표가 보이는가")
    try:
        import psycopg
        from psycopg.rows import dict_row

        def probe(dbname: str, label: str, checks: list[tuple[str, str]]) -> None:
            try:
                with psycopg.connect(
                    host=parsed["DB_HOST"], port=parsed["DB_PORT"], dbname=dbname,
                    user=parsed["DB_USER"], password=parsed["DB_PASSWORD"],
                    row_factory=dict_row, connect_timeout=5,
                ) as cn, cn.cursor() as cur:
                    print(f"{OK} {label} 로그인 됨 (db={dbname})")
                    for sql, what in checks:
                        try:
                            cur.execute(sql)
                            print(f"{OK}   {what}: {cur.fetchone()}")
                        except Exception as e:  # noqa: BLE001
                            print(f"{BAD}   {what} 실패 — {str(e).splitlines()[0][:90]}")
                            fails.append(what)
            except Exception as e:  # noqa: BLE001
                print(f"{BAD} {label} 로그인 실패 — {str(e).splitlines()[0][:90]}")
                fails.append(label)

        schema = parsed.get("DB_SCHEMA", "haetdeul")
        probe(parsed.get("DB_NAME", ""), "서비스 창고", [
            (f"SELECT COUNT(*) AS n, MAX(base_dt) AS mx FROM {schema}.ml_price_forecasts",
             "ml_price_forecasts"),
        ])
        probe(parsed.get(SOURCE, ""), "원본 창고", [
            ("SELECT COUNT(*) AS n, MAX(base_dt) AS mx FROM prediction_log "
             "WHERE model_ver = ANY(ARRAY['ops_auc','ops_whsl','ops_rtl'])",
             "prediction_log (운영기록)"),
        ])
    except ImportError:
        print(f"{BAD} psycopg 가 없어 건너뜁니다")

    # ── 7. 코드가 최신인가 ──────────────────────────────────────────
    head("7. 코드가 최신인가")
    #   dev 에 실제값 판이 들어간 게 2026-09-08 (PR #424) 이다.
    #   옛 코드면 DB 가 붙어도 예시값이 나온다 — 이것도 «에러 없이 안 됨» 이다.
    q = Path("app/api/forecast/query.py")
    if not q.exists():
        q = Path("backend/app/api/forecast/query.py")
    if q.exists():
        body = q.read_text(encoding="utf-8", errors="replace")
        if "prediction_log" in body:
            print(f"{OK} forecast/query.py 가 prediction_log 를 읽는 최신 판입니다")
        else:
            print(f"{BAD} ★ 옛 코드입니다 — 예시값만 냅니다. `git pull` 하세요.")
            fails.append("옛 코드")
    else:
        print(f"{WARN} app/api/forecast/query.py 를 못 찾았습니다 (자리를 확인하세요)")

    # ── 마무리 ──────────────────────────────────────────────────────
    head("결론")
    if fails:
        print(f"{BAD} 막힌 곳: {', '.join(dict.fromkeys(fails))}")
        print("\n  ★ 위에서 [막힘] 이 처음 나온 곳부터 고치세요.")
        return 1
    print(f"{OK} 다 통과했습니다.")
    print("\n  그래도 화면이 예시값이면 **백엔드를 껐다 켜세요.**")
    print("  환경변수는 서버가 시작할 때 한 번만 읽습니다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
