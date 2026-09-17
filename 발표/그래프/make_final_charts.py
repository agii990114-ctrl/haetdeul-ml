# -*- coding: utf-8 -*-
"""Final presentation charts (2026-09-17). English + Korean.

Error values are copied from the result logs named in each chart's source line.
Feature importance is computed live from the operating model bundles.
"""
import collections
import glob
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

plt.rcParams["font.family"] = "Malgun Gothic"
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams["figure.dpi"] = 160
plt.rcParams["savefig.bbox"] = "tight"
plt.rcParams["savefig.facecolor"] = "white"

ROOT = Path(r"C:\IDE\workplace\mainproject_jh_workplace")
KIT = ROOT / "ML" / "20260824" / "ml_train_kit_2"
BASE_OUT = ROOT / "발표" / "그래프"

C_MODEL, C_SIMPLE = "#2E8B57", "#9E9E9E"
C_A, C_B = "#2E6FBA", "#D9534F"
C_BAD = "#C0392B"
INK, MUTED = "#222222", "#777777"

T = {
    "en": {
        "items": ["Cabbage", "Radish", "Onion"],
        "prices": {"rtl": "Retail (sell)", "auc": "Auction (buy)", "whsl": "Wholesale"},
        "model": "Our model", "simple": "Baseline",
        "err": "Error rate (%) · lower is better",
        "t_err": "Forecast error: our model vs baseline",
        "t_err3": "Forecast error by price type",
        "src_err": "Holdout 2024–2025 · 486 base days · lead time ≥ 3 days · WMAPE · baseline = strongest of 8 candidates per crop\n"
                   "Source: 실험결과/2026-09-01_133352_train_auc · 2026-08-31_173513_whsl · 173522_rtl",
        "loses": "baseline wins",
        "t_alg": "Same data, different algorithms — auction price",
        "algs": ["No model\n(anchor)", "LightGBM\n(operating)", "XGBoost", "CatBoost", "Neural net\n(MLP 256·128·64)"],
        "foldA": "Validation 2023", "foldB": "Validation 2022 (typhoon year)",
        "src_alg": "76 trees · lr 0.03 · 31 inputs · lead time ≥ 3 · 3 seeds\n"
                   "Source: 진행기록/부스팅모델비교_XGBoost_CatBoost_20260901.md · 신경망_사전확인_MLP_20260901.md",
        "t_lt": "Farther ahead, larger error — and a larger gap",
        "lt_x": "Business days ahead", "lt_gate": "Days 1–2:\nanchor used as is",
        "src_lt": "Auction price · holdout 2024–2025 · Source: 실험결과/2026-09-01_133352_train_auc_valid2025.txt",
        "t_mix": "The biggest fix was the data, not the model",
        "mix_left": "Cabbage auction price by package\n(Garak, top grade, 2026-08-03)",
        "mix_x": "Price per kg (won, log scale)",
        "pk": ["Net 10 kg (79% volume)", "Pallet 10 kg (6%)", "Box 4 kg", "Box 1 kg", "Mixed average (old target)", "Fixed target (net+pallet 10 kg)"],
        "mix_right": "Does yesterday predict today?\n(autocorrelation, cabbage)",
        "mixed": "Mixed", "fixed": "Package fixed", "random": "(almost random)",
        "src_mix": "Source: 진행기록/경락가_규격분리_20260827.md · CLAUDE.md §2",
        "t_qa": "QA agent: how well it understands questions",
        "qa_y": "Correct slots (%)", "qa_note": "17 questions × 4 slots × 2 rounds · 132 judgeable slots · base date 2026-09-14",
        "qa_names": ["Gemini flash-lite\n(operating)", "gemma4:e2b\n(local PC)", "exaone3.5:2.4b\n(local PC)"],
        "qa_time": "{} per question",
        "src_qa": "Source: 진행기록/QA해석기_로컬LLM_비교_20260917.md",
        "t_imp": "What each model looks at (feature importance by group)",
        "groups": ["Origin weather", "Wholesale price history", "Calendar (holidays, lead time)", "Arrival volume",
                   "Auction price history", "Retail price", "Anchor", "Seoul weather", "Crop"],
        "models": {"auc": "Auction", "whsl": "Wholesale", "rtl": "Retail"},
        "imp_x": "Share of total gain (%)",
        "src_imp": "Operating bundles ops_auc / ops_whsl / ops_rtl · mean gain over 5 seeds · computed 2026-09-17",
        "rtl_noweather": "weather removed\n(made it worse)",
    },
    "kr": {
        "items": ["배추", "무", "양파"],
        "prices": {"rtl": "소매가 (팔 때)", "auc": "경락가 (살 때)", "whsl": "중도매가"},
        "model": "우리 모델", "simple": "baseline",
        "err": "오차율 (%) · 낮을수록 좋음",
        "t_err": "예측 오차율 — 우리 모델 vs baseline",
        "t_err3": "가격 종류별 예측 오차율",
        "src_err": "홀드아웃 2024~2025 · 486 기준일 · 리드타임 3일 이상 · WMAPE · baseline = 후보 8개 중 품목마다 가장 센 것\n"
                   "출처: 실험결과/2026-09-01_133352_train_auc · 2026-08-31_173513_whsl · 173522_rtl",
        "loses": "baseline 이 나음",
        "t_alg": "같은 데이터, 다른 알고리즘 — 경락가",
        "algs": ["모델 없음\n(기준값)", "LightGBM\n(운영)", "XGBoost", "CatBoost", "신경망\n(MLP 256·128·64)"],
        "foldA": "검증 2023", "foldB": "검증 2022 (태풍 든 해)",
        "src_alg": "나무 76 · 학습률 0.03 · 입력 31 · 리드타임 3일 이상 · 시드 3\n"
                   "출처: 진행기록/부스팅모델비교_XGBoost_CatBoost_20260901.md · 신경망_사전확인_MLP_20260901.md",
        "t_lt": "멀리 볼수록 오차가 커지고, 격차도 벌어진다",
        "lt_x": "며칠 앞 (영업일)", "lt_gate": "1~2일 앞은\n기준값 그대로",
        "src_lt": "경락가 · 홀드아웃 2024~2025 · 출처: 실험결과/2026-09-01_133352_train_auc_valid2025.txt",
        "t_mix": "가장 큰 개선은 모델이 아니라 데이터에서",
        "mix_left": "배추 경락가, 포장 규격별\n(가락 · 특등급 · 2026-08-03)",
        "mix_x": "kg당 가격 (원 · 로그 눈금)",
        "pk": ["그물망 10kg (물량 79%)", "파렛트 10kg (6%)", "상자 4kg", "상자 1kg", "전체 평균 (예전 타겟)", "고정 타겟 (그물망+파렛트 10kg)"],
        "mix_right": "어제 값이 오늘을 알려주나?\n(자기상관 · 배추)",
        "mixed": "섞인 상태", "fixed": "규격 고정", "random": "(사실상 무작위)",
        "src_mix": "출처: 진행기록/경락가_규격분리_20260827.md · CLAUDE.md §2",
        "t_qa": "QA 에이전트 — 질문을 얼마나 맞게 알아듣나",
        "qa_y": "맞은 칸 (%)", "qa_note": "질문 17개 × 4칸 × 2회차 · 판정 가능 132칸 · 기준일 2026-09-14",
        "qa_names": ["Gemini flash-lite\n(운영)", "gemma4:e2b\n(PC 로컬)", "exaone3.5:2.4b\n(PC 로컬)"],
        "qa_time": "문항당 {}",
        "src_qa": "출처: 진행기록/QA해석기_로컬LLM_비교_20260917.md",
        "t_imp": "모델이 무엇을 보고 맞히나 (입력 묶음별 중요도)",
        "groups": ["산지 날씨", "중도매가 과거값", "달력 (명절·리드타임)", "반입량",
                   "경락가 과거값", "소매가", "기준값", "서울 날씨", "품목"],
        "models": {"auc": "경락가", "whsl": "중도매가", "rtl": "소매가"},
        "imp_x": "전체 gain 중 비중 (%)",
        "src_imp": "운영 번들 ops_auc / ops_whsl / ops_rtl · 시드 5개 gain 평균 · 2026-09-17 계산",
        "rtl_noweather": "날씨 뺌\n(넣으면 나빠짐)",
    },
}

# holdout 2024-2025 WMAPE, order: cabbage, radish, onion
# auction cabbage uses the log's error-rate column (19.7%); the WMAPE column 0.1975 rounds to 19.8
ERR = {
    "auc":  {"model": [0.197, 0.1861, 0.0896], "simple": [0.2273, 0.1899, 0.0938]},
    "whsl": {"model": [0.1846, 0.1426, 0.0734], "simple": [0.2073, 0.1328, 0.0776]},
    "rtl":  {"model": [0.1274, 0.0966, 0.0826], "simple": [0.1463, 0.1062, 0.0936]},
}


def src(fig, text):
    fig.text(0.99, -0.01, text, ha="right", va="top", fontsize=7.5, color=MUTED)


def style(ax):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.grid(axis="y", alpha=.25, zorder=0)


def err_chart(t, kinds, name, title):
    fig, axes = plt.subplots(1, len(kinds), figsize=(4.3 * len(kinds), 4.6), sharey=True)
    w = .38
    for ax, k in zip(axes, kinds):
        m = [v * 100 for v in ERR[k]["model"]]
        s = [v * 100 for v in ERR[k]["simple"]]
        x = range(3)
        ax.bar([i - w / 2 for i in x], s, w, color=C_SIMPLE, label=t["simple"], zorder=3)
        ax.bar([i + w / 2 for i in x], m, w, color=C_MODEL, label=t["model"], zorder=3)
        for i in x:
            ax.text(i - w / 2, s[i] + .4, f"{s[i]:.1f}", ha="center", fontsize=8.5, color="#555")
            lose = m[i] > s[i]
            ax.text(i + w / 2, m[i] + .4, f"{m[i]:.1f}", ha="center", fontsize=9.5,
                    weight="bold", color=C_BAD if lose else INK)
            if lose:
                ax.text(i, max(m[i], s[i]) + 2.4, t["loses"], ha="center", fontsize=8, color=C_BAD)
        ax.set_xticks(list(x))
        ax.set_xticklabels(t["items"], fontsize=10.5)
        ax.set_title(t["prices"][k], fontsize=12, weight="bold", pad=8)
        ax.set_ylim(0, 27)
        style(ax)
    axes[0].set_ylabel(t["err"])
    axes[0].legend(loc="upper right", fontsize=9, frameon=False)
    fig.suptitle(title, fontsize=14, weight="bold", y=1.02)
    src(fig, t["src_err"])
    return fig


def alg_chart(t):
    a = [0.1730, 0.1670, 0.1688, 0.1687, 0.2468]
    b = [0.2096, 0.1968, 0.1971, 0.2103, 0.2651]
    fig, ax = plt.subplots(figsize=(9, 4.8))
    x = range(len(a))
    w = .38
    ax.bar([i - w / 2 for i in x], [v * 100 for v in a], w, color=C_A, label=t["foldA"], zorder=3)
    ax.bar([i + w / 2 for i in x], [v * 100 for v in b], w, color=C_B, label=t["foldB"], zorder=3, alpha=.85)
    for i in x:
        ax.text(i - w / 2, a[i] * 100 + .4, f"{a[i]*100:.1f}", ha="center", fontsize=9,
                weight="bold" if i == 1 else None)
        ax.text(i + w / 2, b[i] * 100 + .4, f"{b[i]*100:.1f}", ha="center", fontsize=9,
                weight="bold" if i == 1 else None)
    ax.axhline(a[0] * 100, color=C_A, lw=1, ls="--", alpha=.6, zorder=2)
    ax.axhline(b[0] * 100, color=C_B, lw=1, ls="--", alpha=.6, zorder=2)
    ax.axvspan(.5, 1.5, color=C_MODEL, alpha=.08, zorder=0)
    ax.set_xticks(list(x))
    ax.set_xticklabels(t["algs"], fontsize=10)
    ax.set_ylabel(t["err"])
    ax.set_ylim(0, 30)
    ax.legend(loc="upper left", fontsize=9.5, frameon=False)
    ax.set_title(t["t_alg"], fontsize=14, weight="bold", pad=10)
    style(ax)
    src(fig, t["src_alg"])
    return fig


def lt_chart(t):
    lt = list(range(3, 19))
    m = [.1253, .1322, .1378, .1428, .1470, .1499, .1537, .1573, .1612, .1645, .1672, .1701, .1735, .1777, .1814, .1854]
    s = [.1248, .1337, .1424, .1499, .1562, .1619, .1680, .1726, .1785, .1835, .1868, .1908, .1966, .2018, .2073, .2120]
    fig, ax = plt.subplots(figsize=(9, 4.6))
    ax.axvspan(.5, 2.5, color="#DDDDDD", alpha=.5, zorder=0)
    ax.text(1.5, 21.3, t["lt_gate"], ha="center", va="top", fontsize=8.5, color="#555")
    ax.plot(lt, [v * 100 for v in s], "o-", color=C_SIMPLE, lw=2, ms=5, label=t["simple"], zorder=3)
    ax.plot(lt, [v * 100 for v in m], "o-", color=C_MODEL, lw=2.4, ms=5, label=t["model"], zorder=3)
    ax.fill_between(lt, [v * 100 for v in m], [v * 100 for v in s], color=C_MODEL, alpha=.10, zorder=1)
    for i in (0, 6, 15):
        ax.annotate(f"{m[i]*100:.1f}", (lt[i], m[i] * 100), textcoords="offset points", xytext=(0, -15),
                    ha="center", fontsize=9, color=C_MODEL, weight="bold")
        ax.annotate(f"{s[i]*100:.1f}", (lt[i], s[i] * 100), textcoords="offset points", xytext=(0, 8),
                    ha="center", fontsize=9, color="#555")
    ax.set_xlim(.5, 18.5)
    ax.set_ylim(10, 22.5)
    ax.set_xticks(range(1, 19))
    ax.set_xlabel(t["lt_x"])
    ax.set_ylabel(t["err"])
    ax.legend(loc="lower right", fontsize=9.5, frameon=False)
    ax.set_title(t["t_lt"], fontsize=14, weight="bold", pad=10)
    style(ax)
    src(fig, t["src_lt"])
    return fig


def mix_chart(t):
    prices = [710.8, 870.0, 5841.3, 11223.7, 938.5, 721.9]
    colors = ["#7FB3A0", "#7FB3A0", "#E0A96D", C_BAD, "#555555", C_MODEL]
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.6), gridspec_kw={"width_ratios": [2.1, 1]})
    y = list(range(len(prices)))[::-1]
    ax1.barh(y, prices, color=colors, zorder=3, height=.62)
    ax1.set_xscale("log")
    ax1.set_xlim(300, 40000)
    for yy, p in zip(y, prices):
        ax1.text(p * 1.08, yy, f"{p:,.1f}", va="center", fontsize=9)
    ax1.set_yticks(y)
    ax1.set_yticklabels(t["pk"], fontsize=9.5)
    ax1.set_xlabel(t["mix_x"])
    ax1.set_title(t["mix_left"], fontsize=11, weight="bold")
    ax1.grid(axis="x", alpha=.25, zorder=0)
    for s in ("top", "right"):
        ax1.spines[s].set_visible(False)

    v = [0.085, 0.795]
    ax2.bar([0, 1], v, color=[C_SIMPLE, C_MODEL], width=.55, zorder=3)
    ax2.text(0, v[0] + .03, f"{v[0]:.3f}\n{t['random']}", ha="center", fontsize=10, color=C_BAD, weight="bold")
    ax2.text(1, v[1] + .03, f"{v[1]:.3f}", ha="center", fontsize=11, weight="bold")
    ax2.set_xticks([0, 1])
    ax2.set_xticklabels([t["mixed"], t["fixed"]], fontsize=10)
    ax2.set_ylim(0, 1)
    ax2.set_title(t["mix_right"], fontsize=11, weight="bold")
    style(ax2)
    fig.suptitle(t["t_mix"], fontsize=14, weight="bold", y=1.03)
    src(fig, t["src_mix"])
    fig.tight_layout()
    return fig


def qa_chart(t):
    acc = [98.5, 87.9, 72.7]
    tm = ["1.5–1.8 s", "12.3 s", "1.9 s"] if t is T["en"] else ["1.5~1.8초", "12.3초", "1.9초"]
    fig, ax = plt.subplots(figsize=(8, 4.6))
    cols = [C_MODEL, C_SIMPLE, C_SIMPLE]
    ax.bar(range(3), acc, color=cols, width=.55, zorder=3)
    for i in range(3):
        ax.text(i, acc[i] + 1.2, f"{acc[i]:.1f}%", ha="center", fontsize=13, weight="bold",
                color=INK if i == 0 else "#555")
        label = t["qa_time"].format(tm[i]).replace(" per", "\nper").replace("문항당 ", "문항당\n")
        ax.text(i, 6, label, ha="center", fontsize=9.5, color="white", weight="bold")
    ax.set_xticks(range(3))
    ax.set_xticklabels(t["qa_names"], fontsize=10)
    ax.set_ylim(0, 108)
    ax.set_ylabel(t["qa_y"])
    ax.set_title(t["t_qa"], fontsize=14, weight="bold", pad=18)
    ax.text(.5, 1.01, t["qa_note"], transform=ax.transAxes, ha="center", fontsize=9, color=MUTED)
    style(ax)
    src(fig, t["src_qa"])
    return fig


GROUP_OF = {
    "prod_area_stn_nm": 0, "prod_area_temp_avg_lag1": 0, "prod_area_rain_sum7": 0, "prod_area_rain_sum30": 0,
    "prod_area_gdd_sum30": 0, "prod_area_clim_temp_avg10": 0, "prod_area_clim_yr_cnt": 0,
    "whsl_prc_lag1": 1, "whsl_prc_lag3": 1, "whsl_prc_lag7": 1, "whsl_prc_avg7": 1, "whsl_prc_avg14": 1,
    "whsl_prc_std7": 1, "whsl_prc_prev_yr": 1,
    "holiday_remain_d": 2, "lead_biz_d": 2, "target_dow": 2, "kimchi_season_yn": 2, "market_closed_lag1_yn": 2,
    "arr_qty_lag1": 3, "arr_qty_avg7": 3, "arr_qty_prev_yr": 3,
    "auc_prc_lag1": 4, "auc_prc_lag3": 4, "auc_prc_avg7": 4, "auc_prc_spread_lag1": 4, "auc_vol_lag1": 4,
    "auc_whsl_ratio_lag1": 4,
    "rtl_prc_lag1": 5, "_anchor_mix": 6, "market_temp_avg_lag1": 7, "item_nm": 8,
}


def importance():
    import lightgbm as lgb
    out = {}
    for k in ("auc", "whsl", "rtl"):
        acc = [0.0] * 9
        files = sorted(glob.glob(str(KIT / f"ops_{k}" / "model_seed*.txt")))
        for f in files:
            b = lgb.Booster(model_file=f)
            g = b.feature_importance("gain")
            tot = float(sum(g)) or 1.0
            for n, v in zip(b.feature_name(), g):
                acc[GROUP_OF[n]] += v / tot / len(files) * 100
        out[k] = acc
    return out


def imp_chart(t, imp):
    palette = ["#3E7CB1", "#81A4CD", "#E07A5F", "#F2CC8F", "#6D597A", "#B56576", "#9E9E9E", "#76B39D", "#CCCCCC"]
    order = ["auc", "whsl", "rtl"]
    fig, ax = plt.subplots(figsize=(10, 3.9))
    y = [2, 1, 0]
    for yy, k in zip(y, order):
        left = 0.0
        for gi, v in enumerate(imp[k]):
            if v <= 0:
                continue
            ax.barh(yy, v, left=left, color=palette[gi], height=.6, zorder=3,
                    label=t["groups"][gi] if k == "auc" or (k == "rtl" and gi == 5) else None)
            if v >= 4:
                ax.text(left + v / 2, yy, f"{v:.0f}", ha="center", va="center", fontsize=8.5,
                        color="white" if gi in (0, 2, 4, 5) else INK)
            left += v
    ax.text(101, 0, t["rtl_noweather"], va="center", fontsize=8, color=MUTED)
    ax.set_yticks(y)
    ax.set_yticklabels([t["models"][k] for k in order], fontsize=11)
    ax.set_xlim(0, 100)
    ax.set_xlabel(t["imp_x"])
    handles, labels = ax.get_legend_handles_labels()
    seen = {}
    for h, l in zip(handles, labels):
        seen.setdefault(l, h)
    ax.legend([seen[g] for g in t["groups"] if g in seen], [g for g in t["groups"] if g in seen],
              loc="upper center", bbox_to_anchor=(.5, -.2), ncol=5, fontsize=8.5, frameon=False)
    ax.set_title(t["t_imp"], fontsize=14, weight="bold", pad=10)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    src(fig, t["src_imp"])
    return fig, imp


def main():
    imp = importance()
    for lang, t in T.items():
        out = BASE_OUT / f"최종_{lang.upper()}"
        out.mkdir(parents=True, exist_ok=True)
        figs = [
            ("1_error_retail_auction", err_chart(t, ["rtl", "auc"], "", t["t_err"])),
            ("2_algorithm_comparison", alg_chart(t)),
            ("3_packaging_fix", mix_chart(t)),
            ("4_qa_agent_accuracy", qa_chart(t)),
            ("B1_error_all_prices", err_chart(t, ["rtl", "auc", "whsl"], "", t["t_err3"])),
            ("B2_error_by_lead_time", lt_chart(t)),
            ("B3_feature_importance", imp_chart(t, imp)[0]),
        ]
        for name, fig in figs:
            fig.savefig(out / f"{name}.png")
            plt.close(fig)
            print(out / f"{name}.png")
    for k, v in imp.items():
        print(k, [round(x, 1) for x in v], round(sum(v), 1))


if __name__ == "__main__":
    main()
