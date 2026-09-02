# -*- coding: utf-8 -*-
"""실험 결과 그래프 (2026-08-28).

실험결과/ 의 로그에서 뽑은 수치만 쓴다. 손으로 적은 값은 없다.
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pathlib import Path

plt.rcParams["font.family"] = "Malgun Gothic"
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams["mathtext.default"] = "regular"
plt.rcParams["figure.dpi"] = 140
plt.rcParams["savefig.bbox"] = "tight"
plt.rcParams["savefig.facecolor"] = "white"

OUT = Path(r"C:\IDE\workplace\mainproject_jh_workplace\발표\그래프")
OUT.mkdir(parents=True, exist_ok=True)

C_A, C_B = "#2E6FBA", "#D9534F"      # 폴드 A / B
C_OLD, C_NEW = "#9E9E9E", "#2E8B57"  # 현행 / 채택

SRC = "출처: 실험결과/2026-08-28_153454_exp_anchor.txt"
SRC2 = "출처: 실험결과/2026-08-28_1528~1530 train_*_a10 · a06 (12개)"


def fig1():
    """α 별 개선율 — 두 폴드가 반대로 간다"""
    al = [1.0, 0.8, 0.6, 0.4]
    a = [-3.2, -0.1, 3.4, 5.4]
    b = [7.1, 7.8, 7.4, 6.6]
    fig, ax = plt.subplots(figsize=(7.6, 4.8))
    ax.axvspan(0.55, 0.65, color=C_NEW, alpha=.10, zorder=0)
    ax.plot(al, a, "o-", color=C_A, lw=2.2, ms=8, zorder=3,
            label="폴드 A (검증 2023 · 조용한 해)")
    ax.plot(al, b, "s-", color=C_B, lw=2.2, ms=8, zorder=3,
            label="폴드 B (검증 2022 · 태풍 든 해)")
    ax.axhline(0, color="#333", lw=1, ls="--", alpha=.6, zorder=1)
    for xx, yy in zip(al, a):
        ax.annotate(f"{yy:+.1f}", (xx, yy), textcoords="offset points",
                    xytext=(0, -15), ha="center", fontsize=8.5, color=C_A)
    for xx, yy in zip(al, b):
        ax.annotate(f"{yy:+.1f}", (xx, yy), textcoords="offset points",
                    xytext=(0, 9), ha="center", fontsize=8.5, color=C_B)
    ax.set_ylim(-6.5, 11.5)
    ax.text(0.60, 10.2, "채택 α=0.6" + chr(10) + "두 폴드 모두 현행보다 나음",
            fontsize=9.5, color=C_NEW, weight="bold", ha="center", va="top")
    ax.text(1.0, -5.6, "현행", fontsize=9.5, ha="center", color="#555")
    ax.annotate("폴드 B 에서 후퇴 → 탈락", xy=(0.415, 6.9), xytext=(0.44, 9.4),
                fontsize=9, color="#8a6d3b", ha="center",
                arrowprops=dict(arrowstyle="->", color="#8a6d3b", lw=1.2))
    ax.set_xlabel("α   (앵커 = α x 어제 가격 + (1-α) x 7일 평균)")
    ax.set_ylabel("baseline 대비 개선율 (%)")
    ax.set_title("경락가 · 출발점을 바꾸면 어떻게 되나",
                 fontsize=13, weight="bold", pad=10)
    ax.invert_xaxis()
    ax.set_xticks(al)
    ax.grid(alpha=.25, zorder=0)
    ax.legend(loc="upper left", fontsize=9, framealpha=.95)
    fig.text(0.99, -0.02, SRC, ha="right", fontsize=7.5, color="#888")
    fig.savefig(OUT / "1_알파별_개선율.png")
    plt.close(fig)


def fig2():
    """3타겟 × 2폴드 · 현행 vs 채택"""
    labels = ["경락가\n폴드A", "경락가\n폴드B", "중도매가\n폴드A", "중도매가\n폴드B",
              "소매가\n폴드A", "소매가\n폴드B"]
    old = [-3.0, 6.0, 14.8, 9.3, 16.1, 9.1]
    new = [3.7, 6.4, 14.8, 11.0, 17.5, 10.3]
    x = range(len(labels))
    fig, ax = plt.subplots(figsize=(8.6, 4.6))
    ax.bar([i - .2 for i in x], old, .4, label="현행 α=1.0", color=C_OLD)
    ax.bar([i + .2 for i in x], new, .4, label="채택 α=0.6", color=C_NEW)
    ax.axhline(0, color="#333", lw=1)
    for i, (o, n) in enumerate(zip(old, new)):
        ax.text(i - .2, o + (.45 if o >= 0 else -1.9), f"{o:+.1f}", ha="center", fontsize=8.5)
        ax.text(i + .2, n + (.45 if n >= 0 else -1.3), f"{n:+.1f}",
                ha="center", fontsize=8.5, weight="bold")
    ax.set_ylim(-7, 21)
    ax.annotate("현행에서 유일하게 음수였던 칸 — 양수로 뒤집힘",
                xy=(-0.2, -3.2), xytext=(2.6, -5.2),
                fontsize=10, color=C_NEW, weight="bold", ha="center",
                arrowprops=dict(arrowstyle="->", color=C_NEW, lw=1.6,
                                connectionstyle="arc3,rad=-0.2"))
    ax.set_xticks(list(x)); ax.set_xticklabels(labels, fontsize=9.5)
    ax.set_ylabel("baseline 대비 개선율 (%)")
    ax.set_title("세 가격 모두 두 폴드에서 양수 — 처음", fontsize=13, weight="bold", pad=12)
    ax.grid(axis="y", alpha=.25)
    ax.legend(fontsize=9.5)
    fig.text(0.99, -0.04, SRC2, ha="right", fontsize=7.5, color="#888")
    fig.savefig(OUT / "2_세가격_개선율.png")
    plt.close(fig)


def fig3():
    """원 단위 오차 — 경락가 폴드 A"""
    items = ["배추", "무", "양파"]
    actual = [679, 544, 1173]
    e_old = [164, 124, 132]
    e_new = [150, 111, 130]
    p_old = [24.2, 22.7, 11.3]
    p_new = [22.1, 20.4, 11.1]
    x = range(3)
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10.4, 4.3))

    ax1.bar([i - .2 for i in x], e_old, .4, label="현행 α=1.0", color=C_OLD)
    ax1.bar([i + .2 for i in x], e_new, .4, label="채택 α=0.6", color=C_NEW)
    for i, (o, n, a) in enumerate(zip(e_old, e_new, actual)):
        ax1.text(i - .2, o + 3, f"{o}원", ha="center", fontsize=8.5)
        ax1.text(i + .2, n + 3, f"{n}원", ha="center", fontsize=8.5, weight="bold")
    ax1.set_xticks(list(x))
    ax1.set_xticklabels([it + chr(10) + f"({a:,}원)"
                         for it, a in zip(items, actual)], fontsize=10.5)
    ax1.set_ylabel("평균 오차 (원/kg)")
    ax1.set_title("1kg 당 얼마나 틀리나", fontsize=12, weight="bold")
    ax1.set_ylim(0, 205); ax1.grid(axis="y", alpha=.25); ax1.legend(fontsize=9)

    ax2.bar([i - .2 for i in x], p_old, .4, color=C_OLD)
    ax2.bar([i + .2 for i in x], p_new, .4, color=C_NEW)
    for i, (o, n) in enumerate(zip(p_old, p_new)):
        ax2.text(i - .2, o + .4, f"{o}%", ha="center", fontsize=8.5)
        ax2.text(i + .2, n + .4, f"{n}%", ha="center", fontsize=8.5, weight="bold")
    ax2.set_xticks(list(x))
    ax2.set_xticklabels([it + chr(10) + f"({a:,}원)"
                         for it, a in zip(items, actual)], fontsize=10.5)
    ax2.set_ylabel("오차율 (%)")
    ax2.set_title("실제 가격 대비 오차율", fontsize=12, weight="bold")
    ax2.set_ylim(0, 28); ax2.grid(axis="y", alpha=.25)

    fig.suptitle("경락가 · 검증 2023 — 실제 가격과 얼마나 차이나나",
                 fontsize=13, weight="bold", y=1.04)
    fig.text(0.5, -0.02, "괄호 안은 그 품목의 실제 평균 가격 (원/kg)",
             ha="center", fontsize=9, color="#666")
    fig.text(0.99, -0.03, SRC2, ha="right", fontsize=7.5, color="#888")
    fig.savefig(OUT / "3_원단위_오차.png")
    plt.close(fig)


def fig4():
    """앵커가 하루 낡은 비용"""
    items = ["배추", "무", "양파"]
    d1 = [11.7, 9.9, 3.7]
    d2 = [14.0, 14.2, 5.4]
    x = range(3)
    fig, ax = plt.subplots(figsize=(7.2, 4.3))
    ax.bar([i - .2 for i in x], d1, .4, label="하루 전 값에서 출발 (가능한데 안 씀)",
           color=C_NEW)
    ax.bar([i + .2 for i in x], d2, .4, label="이틀 전 값에서 출발 (지금)", color="#C0504D")
    for i, (a, b) in enumerate(zip(d1, d2)):
        ax.text(i - .2, a + .25, f"{a}%", ha="center", fontsize=9)
        ax.text(i + .2, b + .25, f"{b}%", ha="center", fontsize=9)
        ax.text(i, max(a, b) + 1.5, f"+{b - a:.1f}%p 손해", ha="center",
                fontsize=9.5, color="#C0504D", weight="bold")
    ax.set_xticks(list(x)); ax.set_xticklabels(items, fontsize=11)
    ax.set_ylabel("오차율 (%)")
    ax.set_title("아직 안 고친 것 — 출발점이 하루 낡았다\n(경락가 · 2024년 이후 794 거래일 실측)",
                 fontsize=12.5, weight="bold", pad=12)
    ax.set_ylim(0, 21); ax.grid(axis="y", alpha=.25)
    ax.legend(fontsize=9, loc="upper right", framealpha=.95)
    fig.text(0.99, -0.03, "출처: auction_prices_daily 직접 집계 (2026-08-28)",
             ha="right", fontsize=7.5, color="#888")
    fig.savefig(OUT / "4_앵커_날짜_손해.png")
    plt.close(fig)


for fn in (fig1, fig2, fig3, fig4):
    fn()
    print("생성:", fn.__doc__.split("\n")[0])
print("저장 위치:", OUT)
