# -*- coding: utf-8 -*-
"""
가격 예측 대시보드
==================
prediction_log 를 읽어 예측 곡선·구간·정확도를 본다.
다른 파트가 소비할 값이 실제로 어떻게 생겼는지 확인하는 용도다.

    streamlit run 대시보드/streamlit_app.py
"""
import altair as alt
import pandas as pd
import streamlit as st

from db import (load_band, load_batch_runs, load_freshness, load_predictions,
                load_quality, load_run_stages)

KIND_LABEL = {"auc": "경락가 (매입)", "whsl": "중도매가", "rtl": "소매가 (매도)"}
ITEM_ORDER = ["배추", "양파", "무"]

st.set_page_config(page_title="가격 예측 대시보드", page_icon=":material/insights:",
                   layout="wide")

st.title("가격 예측 대시보드")

# ── 운영 상태 ───────────────────────────────────────────────────────
#   배치가 자동으로 돌기 시작하면 아무도 로그를 안 본다.
#   **"자동화했는데 실은 3일째 안 돌고 있었다"** 가 가장 흔한 사고다.
#   그래서 예측보다 먼저, 접었다 펼 수 있는 형태로 맨 위에 둔다.
_runs = load_batch_runs()
_fresh = load_freshness()

if not _runs.empty:
    _last = _runs.iloc[0]
    _age_h = (pd.Timestamp.now(tz=_last.started_at.tz) - _last.started_at).total_seconds() / 3600
    _stale = _age_h > 30          # 하루 한 번 도는 배치가 30시간 넘게 조용하면 이상하다
    _icon = {"ok": ":material/check_circle:", "partial": ":material/warning:",
             "fail": ":material/error:", "running": ":material/hourglass:"}.get(_last.status, "")
    _title = "운영 상태 — 마지막 실행 %s · %s" % (
        _last.started_at.strftime("%m-%d %H:%M"), _last.status)
    if _stale:
        _title += "  ⚠ %d시간째 실행 없음" % _age_h

    with st.expander(_title, expanded=bool(_stale or _last.status != "ok")):
        c1, c2 = st.columns([1, 1])

        with c1:
            st.caption("최근 실행")
            _r = _runs[["started_at", "status", "소요_초", "n_ok", "n_fail", "실패단계"]].copy()
            _r["started_at"] = _r.started_at.dt.strftime("%m-%d %H:%M")
            st.dataframe(_r, hide_index=True, width='stretch', height=220)

            _sg = load_run_stages(int(_last.run_id))
            if not _sg.empty:
                st.caption("마지막 실행 단계별")
                st.dataframe(_sg[["stage", "ok", "duration_s"]],
                             hide_index=True, width='stretch', height=180)

        with c2:
            st.caption("데이터 신선도")
            if _fresh.empty:
                st.info("`SQL/35_batch_run.sql` 을 실행하면 신선도가 표시됩니다.")
            else:
                f = _fresh.sort_values("지연일", ascending=False).copy()
                # 지연은 **달력일**이다. 주말·연휴가 끼면 커 보이므로 판정 임계로 쓰지 말 것.
                # 배치의 신선도 가드는 조사일 기준으로 따로 잰다.
                f["상태"] = f.지연일.map(
                    lambda d: "정상" if d is None or d <= 3
                    else ("주의" if d <= 14 else "정지"))
                st.dataframe(f[["원천", "최신", "지연일", "상태", "행수"]],
                             hide_index=True, width='stretch', height=280)
                st.caption("지연은 달력일입니다. 주말·연휴가 끼면 커 보입니다 — "
                           "배치의 신선도 가드는 조사일 기준으로 따로 잽니다. "
                           "경제지표는 M2 가 2개월 늦게 나와 50일대가 정상입니다.")
else:
    st.info("배치 실행 이력이 없습니다. `SQL/35_batch_run.sql` 실행 후 "
            "`python run_batch.py` 를 돌리면 여기에 표시됩니다.", icon=":material/schedule:")

# ── 데이터 ──────────────────────────────────────────────────────────
try:
    pred = load_predictions()
    quality = load_quality()
    band = load_band()
except Exception as e:      # 접속 실패를 그대로 보여준다. 빈 화면보다 낫다
    st.error("DB 에 연결하지 못했습니다.")
    st.exception(e)
    st.stop()

if pred.empty:
    st.warning("prediction_log 가 비어 있습니다. `SQL/28_prediction_log.sql` 을 실행하세요.")
    st.stop()

# 더미가 섞여 있으면 반드시 알린다. 이 숫자로 판단하면 안 된다
dummy_n = int((pred.model_ver == "dummy-v0").sum())
if dummy_n:
    st.warning(
        f"**더미 데이터 {dummy_n:,}행**이 포함돼 있습니다 (`model_ver = dummy-v0`). "
        "앵커·대상일·정답은 실제 값이지만 **예측가는 만들어낸 값**입니다. "
        "연동 확인용이며 사업 판단에 쓰지 마세요.",
        icon=":material/science:")

# ── 필터 ────────────────────────────────────────────────────────────
with st.sidebar:
    st.subheader("보기 설정")

    kind = st.segmented_control(
        "예측 단계", options=list(KIND_LABEL),
        format_func=lambda k: KIND_LABEL[k], default="rtl")
    if kind is None:
        kind = "rtl"

    kdf = pred[pred.target_kind == kind]

    items = [i for i in ITEM_ORDER if i in set(kdf.item_nm)]
    picked = st.pills("품목", items, selection_mode="multi", default=items)
    if not picked:
        picked = items

    bases = sorted(kdf.base_dt.dt.date.unique(), reverse=True)
    base_dt = st.selectbox(
        "기준일", bases, index=0,
        help="예측을 수행한 날. 같은 대상일이라도 기준일이 다르면 예측이 다르다")

    st.divider()
    st.caption(
        "타겟마다 단위가 다릅니다. 소매가의 배추는 kg 이 아니라 **포기** 단위입니다. "
        "세 단계를 한 축에 겹쳐 보지 마세요.")

view = kdf[(kdf.item_nm.isin(picked)) & (kdf.base_dt.dt.date == base_dt)].copy()
unit = view.unit.iloc[0] if not view.empty else ""

# ── KPI ─────────────────────────────────────────────────────────────
# 오차율은 출처를 반드시 구분한다.
#   더미 예측 × 실제 정답으로 계산한 값은 모델 성능이 아니다. 그런데 숫자만
#   보면 성능처럼 읽히고, 하필 실제 모델보다 좋아 보인다(더미는 앵커 주변만
#   흔들리고 앵커 자체가 강한 baseline 이므로). 라벨에 '더미' 를 박아 둔다.
scored = kdf[kdf.actual_prc.notna()]
real_scored = scored[scored.model_ver != "dummy-v0"]
if not real_scored.empty:
    err_label, err_value = "채점된 평균 오차율", f"{real_scored.abs_pct_err.mean():.1f}%"
elif not scored.empty:
    err_label, err_value = "오차율 (더미)", f"{scored.abs_pct_err.mean():.1f}%"
else:
    err_label, err_value = "채점된 평균 오차율", "—"

with st.container(horizontal=True):
    st.metric("기준일", str(base_dt), border=True,
              help="이 날 시점의 정보로 앞으로 18영업일을 예측한 것")
    st.metric("예측 행", f"{len(view):,}", border=True)
    st.metric(err_label, err_value, border=True,
              help="실제값이 나온 예측만. 리드타임 전체 평균. "
                   "더미 라벨이 붙으면 모델 성능이 아니라 더미 예측의 오차이며, "
                   "실제 모델 성능은 오른쪽 '권장 품목' 과 아래 '품목별 신뢰도' 를 보세요.")
    n_ok = int(quality[(quality.target_kind == kind) & quality.use_recommended].shape[0])
    st.metric("권장 품목", f"{n_ok} / {quality[quality.target_kind == kind].shape[0]}",
              border=True, help="모델이 baseline 보다 나은 품목 수 (실측)")

if real_scored.empty and not scored.empty:
    st.caption(
        ":material/warning: 오차율은 **더미 예측**으로 계산된 값이라 모델 성능이 아닙니다. "
        "실제 모델 성능은 아래 **품목별 신뢰도**(검증·테스트 실측)를 보세요.")

if view.empty:
    st.info("선택한 조건에 예측이 없습니다.")
    st.stop()

# ── 1. 예측 곡선 + 구간 ─────────────────────────────────────────────
with st.container(border=True):
    st.subheader(f"{KIND_LABEL[kind]} 예측 곡선")
    st.caption(
        f"단위 {unit} · 음영은 예측 구간(q10~q90) — 과거 실적상 10건 중 8건이 이 안에 들어왔습니다. "
        "점선은 앵커(기준일 시점 최신 실제가)이고, 모델이 앵커를 이기지 못하면 그 선이 답입니다.")

    v = view.sort_values(["item_nm", "target_dt"])
    x = alt.X("target_dt:T", title="대상일")

    band_layer = alt.Chart(v).mark_area(opacity=0.15).encode(
        x=x, y=alt.Y("pred_lo:Q", title=f"가격 ({unit})", scale=alt.Scale(zero=False)),
        y2="pred_hi:Q", color=alt.Color("item_nm:N", title="품목"))

    anchor_layer = alt.Chart(v).mark_rule(strokeDash=[5, 4], opacity=0.7).encode(
        x=alt.value(0), y="mean(anchor_prc):Q", color="item_nm:N")

    line_layer = alt.Chart(v).mark_line(strokeWidth=2).encode(
        x=x, y="pred_prc:Q", color="item_nm:N",
        strokeDash=alt.StrokeDash("gated:N", title="게이트",
                                  legend=alt.Legend(orient="bottom")))

    pts = alt.Chart(v).mark_point(size=55, filled=True).encode(
        x=x, y="pred_prc:Q", color="item_nm:N",
        tooltip=[alt.Tooltip("target_dt:T", title="대상일"),
                 alt.Tooltip("item_nm:N", title="품목"),
                 alt.Tooltip("lead_biz_d:Q", title="리드타임"),
                 alt.Tooltip("anchor_prc:Q", title="앵커", format=",.0f"),
                 alt.Tooltip("pred_prc:Q", title="예측", format=",.0f"),
                 alt.Tooltip("pred_lo:Q", title="구간 하단", format=",.0f"),
                 alt.Tooltip("pred_hi:Q", title="구간 상단", format=",.0f"),
                 alt.Tooltip("gated:N", title="게이트"),
                 alt.Tooltip("actual_prc:Q", title="실제", format=",.0f")])

    layers = [band_layer, anchor_layer, line_layer, pts]
    if v.actual_prc.notna().any():
        layers.append(
            alt.Chart(v[v.actual_prc.notna()]).mark_point(
                shape="cross", size=90, strokeWidth=2.2, filled=False).encode(
                x=x, y="actual_prc:Q", color="item_nm:N"))

    st.altair_chart(alt.layer(*layers).resolve_scale(y="shared").interactive())

    if v.gated.any():
        st.caption(
            f":material/info: 리드타임 1~{int(v[v.gated].lead_biz_d.max())} 는 "
            "모델을 쓰지 않고 앵커를 그대로 내보냅니다(점선). "
            "가까운 미래는 어제 가격이 이미 정답에 가까워 모델이 개입할수록 손해였습니다.")

# ── 2·3. 정확도 · 신뢰도 ────────────────────────────────────────────
left, right = st.columns(2)

with left:
    with st.container(border=True):
        st.subheader("리드타임별 오차")
        st.caption("실제값이 나온 예측만. 멀리 볼수록 커지는 것이 정상입니다.")
        s = kdf[kdf.actual_prc.notna() & kdf.item_nm.isin(picked)]
        if s.empty:
            st.info("아직 채점된 예측이 없습니다.")
        else:
            g = (s.groupby(["lead_biz_d", "item_nm"], as_index=False)
                   .abs_pct_err.mean())
            st.altair_chart(
                alt.Chart(g).mark_line(point=True, strokeWidth=2).encode(
                    x=alt.X("lead_biz_d:Q", title="리드타임 (영업일)"),
                    y=alt.Y("abs_pct_err:Q", title="평균 절대오차율 (%)"),
                    color=alt.Color("item_nm:N", title="품목"),
                    tooltip=["lead_biz_d", "item_nm",
                             alt.Tooltip("abs_pct_err:Q", format=".2f")]))

with right:
    with st.container(border=True):
        st.subheader("품목별 신뢰도")
        st.caption("baseline(어제 가격) 대비 개선율. 0 보다 작으면 모델을 쓰면 안 됩니다.")
        q = quality[quality.target_kind == kind].melt(
            id_vars=["item_nm", "use_recommended"],
            value_vars=["improve_valid_pct", "improve_test_pct"],
            var_name="구간", value_name="개선율")
        q["구간"] = q["구간"].map({"improve_valid_pct": "검증 2023",
                                   "improve_test_pct": "테스트 2024~25"})
        st.altair_chart(
            alt.Chart(q).mark_bar().encode(
                x=alt.X("개선율:Q", title="baseline 대비 개선율 (%)"),
                y=alt.Y("item_nm:N", title=None, sort=ITEM_ORDER),
                yOffset="구간:N",
                color=alt.Color("구간:N", title=None,
                                legend=alt.Legend(orient="bottom")),
                tooltip=["item_nm", "구간",
                         alt.Tooltip("개선율:Q", format="+.1f")]))
        bad = quality[(quality.target_kind == kind) & (~quality.use_recommended)]
        for _, r in bad.iterrows():
            st.caption(f":material/warning: **{r.item_nm}** — {r.note}")

# ── 표 ──────────────────────────────────────────────────────────────
with st.expander("예측 원본 보기"):
    st.dataframe(
        view[["target_dt", "item_nm", "lead_biz_d", "anchor_prc", "pred_prc",
              "pred_lo", "pred_hi", "gated", "actual_prc", "abs_pct_err",
              "model_ver"]].sort_values(["item_nm", "lead_biz_d"]),
        hide_index=True,
        column_config={
            "target_dt": st.column_config.DateColumn("대상일", format="YYYY-MM-DD"),
            "item_nm": "품목",
            "lead_biz_d": st.column_config.NumberColumn("LT"),
            "anchor_prc": st.column_config.NumberColumn("앵커", format="%.0f"),
            "pred_prc": st.column_config.NumberColumn("예측", format="%.0f"),
            "pred_lo": st.column_config.NumberColumn("구간 하단", format="%.0f"),
            "pred_hi": st.column_config.NumberColumn("구간 상단", format="%.0f"),
            "gated": st.column_config.CheckboxColumn("게이트"),
            "actual_prc": st.column_config.NumberColumn("실제", format="%.0f"),
            "abs_pct_err": st.column_config.NumberColumn("오차율(%)", format="%.2f"),
            "model_ver": "모델",
        })

with st.expander("예측 구간의 근거"):
    st.caption(
        "구간은 검증 구간에서 잰 `actual / pred` 비율의 q10~q90 입니다. "
        "시드 편차가 아닙니다 — 시드 편차는 1.6~1.8% 인데 실제 오차는 10~17% 로 "
        "자릿수가 달라, 그걸 구간으로 쓰면 불확실성을 크게 과소평가합니다.")
    b = band[(band.target_kind == kind) & band.item_nm.isin(picked)].copy()
    b["폭"] = (b.ratio_q90 - b.ratio_q10) * 100
    st.altair_chart(
        alt.Chart(b).mark_line(point=True, strokeWidth=2).encode(
            x=alt.X("lead_biz_d:Q", title="리드타임 (영업일)"),
            y=alt.Y("폭:Q", title="구간 폭 (%)"),
            color=alt.Color("item_nm:N", title="품목"),
            tooltip=["item_nm", "lead_biz_d",
                     alt.Tooltip("ratio_q10:Q", format=".3f"),
                     alt.Tooltip("ratio_q90:Q", format=".3f")]))
