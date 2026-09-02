# -*- coding: utf-8 -*-
"""
DB 조회 — prediction_log 계열만 읽는다.

접속 정보는 루트 `.env` 의 DATABASE_URL 에서 읽는다.
코드나 문서에 절대 쓰지 않는다.

연결을 캐시하지 않고 조회할 때마다 짧게 열고 닫는다.
대시보드는 조회 빈도가 낮은데(캐시 TTL 10분), 캐시된 연결은 방치되면
서버가 끊어 다음 조회에서 알 수 없는 오류가 난다. 그 편이 손해다.
"""
from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
import psycopg
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent


def _load_dotenv() -> None:
    """루트 .env 를 읽어 환경변수에 채운다. 이미 있는 값은 덮지 않는다."""
    p = ROOT / ".env"
    if not p.exists():
        return
    for raw in p.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        v = v.strip()
        if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
            v = v[1:-1]
        os.environ.setdefault(k.strip(), v)


def dsn() -> str:
    # st.secrets 가 있으면 우선. 없으면 루트 .env
    try:
        if "DATABASE_URL" in st.secrets:
            return str(st.secrets["DATABASE_URL"])
    except Exception:
        pass
    _load_dotenv()
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        raise RuntimeError(
            "DATABASE_URL 이 없습니다. 프로젝트 루트 .env 에 넣어 주세요.\n"
            "  DATABASE_URL=postgresql://사용자:비밀번호@호스트:5432/cost_catcher_raw")
    return url


def _query(sql: str, params: tuple | None = None) -> pd.DataFrame:
    with psycopg.connect(dsn(), connect_timeout=10) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            cols = [d.name for d in cur.description]
            return pd.DataFrame(cur.fetchall(), columns=cols)


# ── 조회 ────────────────────────────────────────────────────────────
#   비싼 것은 캐시하고, 필터는 캐시 밖에서 건다.

@st.cache_data(ttl="10m", show_spinner="예측을 불러오는 중")
def load_predictions() -> pd.DataFrame:
    """prediction_log 전체 + 신뢰도 조인. 더미 포함 1,300행 남짓이라 통째로 읽는다."""
    df = _query("""
        SELECT p.base_dt, p.target_dt, p.item_nm, p.lead_biz_d, p.target_kind,
               p.unit, p.anchor_prc, p.pred_prc, p.pred_lo, p.pred_hi,
               p.seed_spread, p.gated, p.model_ver, p.actual_prc, p.abs_pct_err,
               q.use_recommended, q.improve_test_pct, q.note
          FROM prediction_log p
          LEFT JOIN ref_prediction_quality q
                 ON q.target_kind = p.target_kind AND q.item_nm = p.item_nm
         ORDER BY p.base_dt, p.item_nm, p.target_kind, p.lead_biz_d
    """)
    for c in ("base_dt", "target_dt"):
        df[c] = pd.to_datetime(df[c])
    for c in ("anchor_prc", "pred_prc", "pred_lo", "pred_hi",
              "seed_spread", "actual_prc", "abs_pct_err", "improve_test_pct"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


@st.cache_data(ttl="10m", show_spinner=False)
def load_quality() -> pd.DataFrame:
    df = _query("""
        SELECT target_kind, item_nm, improve_valid_pct, improve_test_pct,
               dir_acc_pct, use_recommended, note
          FROM ref_prediction_quality
         ORDER BY target_kind, item_nm
    """)
    for c in ("improve_valid_pct", "improve_test_pct", "dir_acc_pct"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


# ── 운영 상태 ───────────────────────────────────────────────────────
#   캐시를 짧게(1분) 둔다. 예측은 하루 한 번 바뀌지만 배치 상태는
#   "지금 도는 중인가" 를 봐야 하므로 10분은 너무 길다.

@st.cache_data(ttl="1m", show_spinner=False)
def load_batch_runs(limit: int = 14) -> pd.DataFrame:
    """최근 배치 실행. 없으면 빈 DataFrame (35_batch_run.sql 미실행 환경 대비)."""
    try:
        df = _query("SELECT * FROM v_batch_latest LIMIT %s", (limit,))
    except Exception:                                        # noqa: BLE001
        return pd.DataFrame()
    for c in ("started_at", "finished_at"):
        if c in df:
            df[c] = pd.to_datetime(df[c])
    return df


@st.cache_data(ttl="1m", show_spinner=False)
def load_freshness() -> pd.DataFrame:
    """원천별 신선도. 실시간 계산이라 배치가 멈춰도 정확하다."""
    try:
        return _query("SELECT * FROM v_data_freshness")
    except Exception:                                        # noqa: BLE001
        return pd.DataFrame()


@st.cache_data(ttl="1m", show_spinner=False)
def load_run_stages(run_id: int) -> pd.DataFrame:
    try:
        return _query("""SELECT seq, stage, ok, duration_s, message
                           FROM batch_run_stage WHERE run_id = %s
                          ORDER BY seq""", (run_id,))
    except Exception:                                        # noqa: BLE001
        return pd.DataFrame()


@st.cache_data(ttl="10m", show_spinner=False)
def load_band() -> pd.DataFrame:
    df = _query("""
        SELECT target_kind, item_nm, lead_biz_d, ratio_q10, ratio_q50, ratio_q90
          FROM ref_prediction_band
         ORDER BY target_kind, item_nm, lead_biz_d
    """)
    for c in ("ratio_q10", "ratio_q50", "ratio_q90"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df
