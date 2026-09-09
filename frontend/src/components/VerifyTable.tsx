"use client";

/**
 * 재학습 검증 표 — **바꿀지 말지를 여기서 정한다.**
 *
 * ★ 왜 표인가. 지금까지 화면은 「배추 — 후보가 낫습니다」 한 줄만 보였다.
 *   그러면 사람이 할 수 있는 게 **글을 믿고 누르는 것뿐**이다.
 *   바꿀지 말지는 숫자를 나란히 놓고 정하는 일이다.
 *
 * ★ 판정 규칙을 그대로 보인다.
 *
 *       차이(현행−후보)  >  시드 편차×2     ->  후보가 낫다
 *       차이가 그 안      ->  판정 불가 (**«같다» 가 아니라 «모른다»**)
 *
 *   그래서 「차이」와 「필요」를 **나란히** 놓는다. 둘을 떨어뜨려 놓으면
 *   판정이 어디서 나왔는지 눈으로 못 따라간다.
 *
 * ★ 앵커를 같이 보인다. 후보가 현행보다 나아도 **어제값을 못 이기면**
 *   모델을 쓸 이유가 없다. 그 사실이 표에서 바로 보여야 한다.
 *
 * ★ `null` 은 0 이 아니라 공란이다. 표본이 모자라 판정을 안 한 품목이다.
 */

import type { VerifyItem } from "@/lib/types";

const TONE: Record<string, { fg: string; bg: string }> = {
  "후보가 낫다": { fg: "text-accent-ink", bg: "bg-accent-wash" },
  "후보가 나쁘다": { fg: "text-warn", bg: "bg-warn-wash" },
  "판정 불가": { fg: "text-muted", bg: "bg-sunk" },
  "표본 부족": { fg: "text-muted", bg: "bg-sunk" },
};

/** 오차율을 백분율로. `null` 이면 공란. */
function pct(v: number | null): string {
  return v === null || v === undefined ? "—" : `${(v * 100).toFixed(2)}%`;
}

/** 부호를 붙여 보인다 — 양수면 후보가 낫다는 뜻이라 방향이 중요하다. */
function signed(v: number | null): string {
  if (v === null || v === undefined) return "—";
  return `${v >= 0 ? "+" : "−"}${(Math.abs(v) * 100).toFixed(2)}%p`;
}

export function VerifyTable({ items }: { items: VerifyItem[] }) {
  if (!items || items.length === 0) return null;

  const decided = items.filter((r) => r.verdict !== "표본 부족");
  const better = decided.filter((r) => r.verdict === "후보가 낫다").length;
  const worse = decided.filter((r) => r.verdict === "후보가 나쁘다").length;

  return (
    <section className="space-y-2.5">
      <div className="overflow-x-auto rounded-lg border border-line">
        <table className="w-full border-collapse text-[12px]">
          <thead>
            <tr className="bg-sunk text-left text-[11px] text-muted">
              <th scope="col" className="px-3 py-2 font-medium">품목</th>
              <th scope="col" className="px-3 py-2 text-right font-medium">행수</th>
              <th scope="col" className="px-3 py-2 text-right font-medium">
                앵커
                <span className="ml-1 font-normal text-faint">어제값</span>
              </th>
              <th scope="col" className="px-3 py-2 text-right font-medium">현행</th>
              <th scope="col" className="px-3 py-2 text-right font-medium">후보</th>
              <th scope="col" className="px-3 py-2 text-right font-medium">
                차이
                <span className="ml-1 font-normal text-faint">현행−후보</span>
              </th>
              <th scope="col" className="px-3 py-2 text-right font-medium">
                필요
                <span className="ml-1 font-normal text-faint">편차×2</span>
              </th>
              <th scope="col" className="px-3 py-2 font-medium">판정</th>
            </tr>
          </thead>
          <tbody>
            {items.map((r) => {
              const tone = TONE[r.verdict] ?? TONE["판정 불가"];
              //  후보가 앵커를 못 이기면 그 칸을 눈에 띄게 둔다 —
              //  현행보다 나아도 어제값보다 나쁘면 쓸 이유가 없다.
              const losesToAnchor =
                r.cand !== null && r.anchor !== null && r.cand >= r.anchor;
              return (
                <tr key={r.item} className="border-t border-line-soft">
                  <td className="px-3 py-2 font-medium">{r.item}</td>
                  <td className="tabular px-3 py-2 text-right font-mono text-faint">
                    {r.n.toLocaleString("ko-KR")}
                  </td>
                  <td
                    className={`tabular px-3 py-2 text-right font-mono ${
                      losesToAnchor ? "bg-warn-wash text-warn" : "text-muted"
                    }`}
                    title={losesToAnchor ? "후보가 어제값을 못 이깁니다" : undefined}
                  >
                    {pct(r.anchor)}
                  </td>
                  <td className="tabular px-3 py-2 text-right font-mono">{pct(r.cur)}</td>
                  <td className="tabular px-3 py-2 text-right font-mono font-semibold">
                    {pct(r.cand)}
                  </td>
                  <td
                    className={`tabular px-3 py-2 text-right font-mono ${
                      r.diff !== null && r.diff > 0 ? "text-accent-ink" : "text-warn"
                    }`}
                  >
                    {signed(r.diff)}
                  </td>
                  <td className="tabular px-3 py-2 text-right font-mono text-faint">
                    {r.need === null ? "—" : `±${(r.need * 100).toFixed(2)}%p`}
                  </td>
                  <td className="px-3 py-2">
                    <span
                      className={`rounded px-2 py-0.5 text-[11px] font-semibold ${tone.bg} ${tone.fg}`}
                    >
                      {r.verdict}
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <p className="m-0 text-[11.5px] leading-relaxed text-muted">
        <b className="text-ink">읽는 법</b> — 「차이」가 「필요」보다 커야 판정합니다.
        그 안이면 <b className="text-ink">«같다» 가 아니라 «모른다»</b> 입니다.
        {" "}시드를 바꿔 다시 학습하면 그만큼은 그냥 흔들립니다.
        <br />
        <b className="text-ink">앵커</b>는 어제 가격을 그대로 썼을 때의 오차입니다.
        {" "}<b className="text-ink">후보가 이것보다 나쁘면 모델을 쓸 이유가 없습니다</b> —
        그 칸을 노랗게 칠해 둡니다.
      </p>

      {worse > 0 && (
        <p className="m-0 rounded-lg border border-warn/30 bg-warn-wash px-3.5 py-2.5 text-[12px] leading-relaxed text-warn">
          ★ <b>나빠진 품목이 {worse}개 있습니다.</b> 좋아진 품목이 {better}개라도
          바꾸지 않습니다. 경락 양파를 따로 뗀 안이 3폴드를 통과하고도 운영에서
          배추가 5.70% 나빠진 적이 있습니다.
        </p>
      )}
      {worse === 0 && better === 0 && decided.length > 0 && (
        <p className="m-0 rounded-lg border border-line bg-sunk px-3.5 py-2.5 text-[12px] leading-relaxed text-muted">
          나빠진 품목은 없지만 <b className="text-ink">좋아진 것도 증명 못 했습니다.</b>
          {" "}바꿀 이유가 없으니 안 바꿉니다.
        </p>
      )}
    </section>
  );
}
