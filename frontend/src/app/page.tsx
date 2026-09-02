"use client";

/**
 * 콘솔 — 보여줄 것은 둘이다.
 *
 *   ① 예측가 그래프    품목별로 앞으로 18영업일 값과 범위. 채점된 날은 실제값도.
 *   ② agent 결과      데이터 품질 · 배치 장애 조사
 *
 * ★ **오늘을 2025-12-31 로 놓고 돈다.** 매입 파트 시연이 그 날짜 기준이라
 *   같은 날을 봐야 서로 말이 통한다 (`AS_OF`).
 */

import { useCallback, useEffect, useState } from "react";

import { AgentHistory } from "@/components/AgentHistory";
import { AgentPanel } from "@/components/AgentPanel";
import { ExplainPanel } from "@/components/ExplainPanel";
import { ForecastChart } from "@/components/ForecastChart";
import * as api from "@/lib/api";
import { ApiError, AS_OF } from "@/lib/api";
import type { AgentReport, BaseDate, Forecast, TargetKind } from "@/lib/types";

const KINDS: { kind: TargetKind; label: string; role: string }[] = [
  { kind: "auc", label: "경락가", role: "매입 — 경매에서 사는 값" },
  { kind: "whsl", label: "중도매가", role: "중도매 — 도매상이 파는 값" },
  { kind: "rtl", label: "소매가", role: "매도 — 소비자가 사는 값" },
];

/** 리드타임 3 미만은 모델을 안 쓴다 (어제 가격이 이미 정답에 가깝다). */
const GATE_LEAD = 3;

type Tab = "forecast" | "agents" | "history";

function Err({ e }: { e: unknown }) {
  const msg = e instanceof ApiError ? e.message : String(e);
  return (
    <div className="rounded-lg border border-warn/30 bg-warn-wash px-4 py-3 text-[12.5px] text-warn">
      {msg}
    </div>
  );
}

export default function Console() {
  const [tab, setTab] = useState<Tab>("forecast");

  const [dates, setDates] = useState<BaseDate[]>([]);
  const [baseDt, setBaseDt] = useState(AS_OF);
  const [kind, setKind] = useState<TargetKind>("auc");
  const [fc, setFc] = useState<Forecast | null>(null);
  const [fcErr, setFcErr] = useState<unknown>(null);
  const [loading, setLoading] = useState(false);

  //  실제값을 보여줄지. 시연은 켜고, 운영 모습을 보려면 끈다.
  //  ★ 운영에서는 예측을 낼 때 정답이 없다. 켜 둔 채로 보면
  //    "이만큼 맞힌다" 로 읽히는데, 실제로 쓸 때의 모습이 아니다.
  const [showActual, setShowActual] = useState(true);

  //  어느 품목을 보고 있나. 셋을 세로로 쌓으면 화면이 계속 길어져서 하나만 본다.
  const [item, setItem] = useState("배추");

  //  팝업으로 열어 둔 리드타임. null 이면 안 열려 있다.
  const [pick, setPick] = useState<number | null>(null);

  const [quality, setQuality] = useState<AgentReport | null>(null);
  const [batch, setBatch] = useState<AgentReport | null>(null);
  const [agentErr, setAgentErr] = useState<unknown>(null);

  useEffect(() => {
    api
      .baseDates()
      .then((d) => {
        setDates(d);
        //  운영에서는 **가장 최근 예측 하나**만 봅니다. 지난 날짜를 골라
        //  볼 일이 없습니다. 그래서 기본값을 최신으로 둡니다.
        //  AS_OF(시연 기준일)가 목록에 있으면 그걸 씁니다 — 시연은
        //  "오늘이 2025-12-31" 로 놓고 돌기 때문입니다.
        if (d.length > 0) {
          const demo = d.find((x) => x.base_dt === AS_OF);
          setBaseDt(demo ? demo.base_dt : d[0].base_dt);
        }
      })
      .catch(() => setDates([]));
  }, []);

  const loadForecast = useCallback(() => {
    setLoading(true);
    setFcErr(null);
    api
      .forecast(baseDt, kind, showActual)
      .then((d) => setFc(d))
      .catch((e) => {
        setFc(null);
        setFcErr(e);
      })
      .finally(() => setLoading(false));
  }, [baseDt, kind, showActual]);

  //  자료를 받아오는 효과다. 시작할 때 "불러오는 중" 을 켜야 해서 setState 가
  //  앞에 온다 — 그래서 아래 규칙을 이 줄에만 끈다.
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(loadForecast, [loadForecast]);

  useEffect(() => {
    if (tab !== "agents" || quality || batch) return;
    //  둘을 따로 부른다. 하나가 실패해도 나머지는 뜬다 — agent 가 죽어서
    //  화면이 통째로 비면 "이상 없음" 으로 오해된다.
    //  ★ 여기서 오류를 미리 지우지 않는다. 이 효과는 처음 한 번만 도는데
    //    (quality·batch 가 차면 위에서 멈춘다) 지울 오류가 없다.
    api.qualityAgent(180).then(setQuality).catch(setAgentErr);
    api.batchAgent().then(setBatch).catch(setAgentErr);
  }, [tab, quality, batch]);

  return (
    <main className="mx-auto max-w-[1180px] px-6 py-8">
      <header className="mb-6 border-b border-line pb-5">
        <p className="m-0 text-[11px] font-semibold uppercase tracking-[0.14em] text-faint">
          원가 캣쳐 · ML 파트
        </p>
        <h1 className="m-0 mt-1 text-[22px] font-bold tracking-tight">가격 예측 콘솔</h1>
        <p className="m-0 mt-1.5 text-[12.5px] text-muted">
          서울가락 · 특등급 · 원/kg · 배추 10kg · 무 20kg · 양파 15kg 규격 고정
        </p>
      </header>

      <nav className="mb-6 flex gap-1">
        {(
          [
            ["forecast", "예측가 그래프"],
            ["agents", "지금 상태"],
            ["history", "날짜별 기록"],
          ] as [Tab, string][]
        ).map(([t, label]) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`rounded-md px-3.5 py-1.5 text-[13px] font-medium transition-colors ${
              tab === t
                ? "bg-accent text-white"
                : "bg-sunk text-muted hover:text-ink"
            }`}
          >
            {label}
          </button>
        ))}
      </nav>

      {tab === "forecast" && (
        <>
          <div className="mb-5 flex flex-wrap items-end gap-4 rounded-lg border border-line bg-surface px-4 py-3.5">
            <label className="flex flex-col gap-1">
              <span className="text-[11px] font-semibold text-faint"
                    title="예측을 만든 날. 이 날까지의 정보만 씁니다. 옆 숫자는 그중 몇 건이 실제 가격과 맞춰졌는지입니다.">
                기준일 (예측을 만든 날)
              </span>
              <select
                value={baseDt}
                onChange={(e) => {
                  setBaseDt(e.target.value);
                  setPick(null);          // 조건이 바뀌면 열린 설명을 닫는다
                }}
                className="tabular rounded border border-line bg-surface px-2.5 py-1.5 font-mono text-[13px]"
              >
                {!dates.some((d) => d.base_dt === AS_OF) && <option value={AS_OF}>{AS_OF}</option>}
                {dates.map((d) => (
                  <option key={d.base_dt} value={d.base_dt}>
                    {d.base_dt}
                    {/*  "채점" 은 예측 몇 개가 실제 가격과 맞춰졌나다.
                        기준일이 오래될수록 대상일이 지나 늘어난다. */}
                    {d.scored > 0
                      ? ` · 결과 확인 ${d.scored}/${d.n}건`
                      : " · 아직 결과 안 나옴"}
                    {d.pre_fix && "  ⚠ 옛 기준"}
                  </option>
                ))}
              </select>
              {/*  운영에서는 이 칸을 쓸 일이 없습니다. 매일 아침 배치가 낸
                  **가장 최근 예측 하나**만 보면 됩니다. 지난 날짜를 고르는
                  건 시연과 되짚어보기 용도라, 그렇다고 밝혀 둡니다. */}
              <span className="text-[10.5px] text-faint">
                지난 날짜는 시연·되짚기용입니다
                {dates[0] && baseDt !== dates[0].base_dt && (
                  <button
                    onClick={() => {
                      setBaseDt(dates[0].base_dt);
                      setPick(null);
                    }}
                    className="ml-1.5 rounded bg-sunk px-1.5 py-0.5 text-[10.5px] text-accent-ink hover:bg-accent-wash"
                  >
                    최신으로
                  </button>
                )}
              </span>
            </label>

            <div className="flex flex-col gap-1">
              <span className="text-[11px] font-semibold text-faint">무엇의 가격</span>
              <div className="flex gap-1">
                {KINDS.map((k) => (
                  <button
                    key={k.kind}
                    onClick={() => {
                      setKind(k.kind);
                      setPick(null);
                    }}
                    title={k.role}
                    className={`rounded px-3 py-1.5 text-[12.5px] font-medium ${
                      kind === k.kind ? "bg-accent-wash text-accent-ink" : "bg-sunk text-muted"
                    }`}
                  >
                    {k.label}
                  </button>
                ))}
              </div>
            </div>

            <label className="flex flex-col gap-1">
              <span className="text-[11px] font-semibold text-faint">품목</span>
              <select
                value={item}
                onChange={(e) => {
                  setItem(e.target.value);
                  setPick(null);
                }}
                className="rounded border border-line bg-surface px-2.5 py-1.5 text-[13px]"
              >
                {(fc?.items ?? []).map((x) => (
                  <option key={x.item} value={x.item}>
                    {x.item}
                  </option>
                ))}
                {!fc && <option value={item}>{item}</option>}
              </select>
            </label>

            <label className="flex cursor-pointer select-none flex-col gap-1">
              <span className="text-[11px] font-semibold text-faint">실제값</span>
              <button
                onClick={() => {
                  setShowActual((v) => !v);
                  setPick(null);
                }}
                title={
                  showActual
                    ? "끄면 운영에서 보이는 모습이 됩니다 — 예측 시점에는 정답이 없습니다"
                    : "켜면 지난 날짜의 실제 가격을 함께 그립니다 (시연용)"
                }
                className={`rounded px-3 py-1.5 text-[12.5px] font-medium ${
                  showActual ? "bg-warn-wash text-warn" : "bg-sunk text-muted"
                }`}
              >
                {showActual ? "보임 (시연)" : "숨김 (운영)"}
              </button>
            </label>

            {fc && (
              <p className="m-0 ml-auto max-w-[300px] text-[11.5px] leading-snug text-muted">
                {fc.role}
              </p>
            )}
          </div>

          {/*  옛 기준으로 만든 예측을 고르면 왜 다른지 알려준다. 안 알려주면
              다른 날과 나란히 놓고 "예측이 들쭉날쭉하다" 로 읽는다. */}
          {dates.find((d) => d.base_dt === baseDt)?.pre_fix && (
            <div className="mb-4 rounded-lg border border-gold/40 bg-gold-wash px-4 py-3 text-[12px] leading-relaxed text-gold">
              <strong>이 날은 옛 기준으로 만든 예측입니다.</strong> 2026-08-27 에
              경락가에서 서로 다른 포장 규격이 한 평균에 섞여 있던 것을 찾아
              고쳤는데, 이 예측은 그 전에 만들어졌습니다.
              <br />
              값이 다른 날과 이어지지 않습니다. <strong>다른 날과 나란히 놓고
              비교하지 마세요.</strong> 실제로 나간 기록이라 지우지 않고 남겨 둡니다.
            </div>
          )}

          {loading && <p className="text-[12.5px] text-muted">불러오는 중…</p>}
          {fcErr !== null && <Err e={fcErr} />}

          {fc &&
            (() => {
              //  고른 품목 하나만 그린다. 없으면 첫 번째로 떨어진다 —
              //  가격종류를 바꿨을 때 그 종류에 없는 품목이 골라져 있으면
              //  화면이 통째로 비어 "자료가 없다" 로 잘못 읽힌다.
              const it = fc.items.find((x) => x.item === item) ?? fc.items[0];
              if (!it) return null;
              const scored = it.rows.filter((r) => r.actual !== null);
              const mape =
                scored.length > 0
                  ? scored.reduce((s, r) => s + (r.err_pct ?? 0), 0) / scored.length
                  : null;
              return (
                <article className="rounded-lg border border-line bg-surface p-4">
                  <header className="mb-3 flex flex-wrap items-baseline gap-x-3 gap-y-1">
                    <h2 className="m-0 text-[15px] font-semibold">{it.item}</h2>
                    <span className="text-[11.5px] text-muted">
                      {fc.kind_name} · {it.unit}
                    </span>
                    {it.use_recommended === false && (
                      <span className="rounded bg-warn-wash px-2 py-0.5 text-[11px] font-semibold text-warn">
                        모델 미사용 — 출발점 그대로 나감
                      </span>
                    )}
                      <span className="tabular ml-auto font-mono text-[11.5px] text-faint">
                        {!showActual
                          ? `예측 ${it.rows.length}개`
                          : mape === null
                            ? `예측 ${it.rows.length}개 · 결과는 아직`
                            : `결과 확인 ${scored.length}/${it.rows.length}건 · 평균 오차 ${mape.toFixed(1)}%`}
                      </span>
                  </header>

                  <ForecastChart
                    rows={it.rows}
                    unit={it.unit}
                    gateLead={GATE_LEAD}
                    //  기준일 그 자체를 맨 앞에 놓는다. 값은 출발점(앵커)이고
                    //  예측이 아니다 — 기준일이 12-31 인데 선이 1-2 에서
                    //  시작하면 "12-31 은 어디 갔나" 가 된다.
                    origin={
                      it.rows[0]?.anchor != null
                        ? { date: fc.base_dt, value: it.rows[0].anchor }
                        : null
                    }
                    picked={pick}
                    onPick={(lead) => setPick(pick === lead ? null : lead)}
                  />

                  <p className="m-0 mt-2 text-[11.5px] text-faint">
                    점을 누르면 “왜 이렇게 봤나” 가 창으로 뜹니다.
                  </p>

                  {it.quality_note && (
                    <p className="m-0 mt-3 border-t border-line-soft pt-2.5 text-[11.5px] leading-relaxed text-muted">
                      <span className="font-semibold">판정 근거 </span>
                      {it.quality_note}
                    </p>
                  )}

                  {pick !== null && (
                    <ExplainPanel
                      baseDt={fc.base_dt}
                      item={it.item}
                      kind={fc.kind}
                      lead={pick}
                      showActual={showActual}
                      onClose={() => setPick(null)}
                    />
                  )}
                </article>
              );
            })()}
        </>
      )}

      {tab === "agents" && (
        <div className="grid gap-7">
          {agentErr !== null && <Err e={agentErr} />}
          {!quality && !batch && agentErr === null && (
            <p className="text-[12.5px] text-muted">
              agent 를 돌리는 중… 데이터 품질 점검은 DB 를 훑어서 10초쯤 걸립니다.
            </p>
          )}
          {batch && <AgentPanel report={batch} subtitle="배치가 실패했을 때만 할 말이 있습니다" />}
          {quality && (
            <AgentPanel
              report={quality}
              subtitle={`최근 ${quality.days}일 · 당연히 성립해야 하는 것만 봅니다`}
            />
          )}
        </div>
      )}

      {tab === "history" && (
        <>
          <p className="mb-4 text-[12px] leading-relaxed text-muted">
            매일 아침 09:23 에 무인으로 점검한 결과와, 그동안 직접 돌린 agent 보고서가
            날짜별로 쌓입니다. 줄을 눌러 펼치세요.
          </p>
          <AgentHistory />
        </>
      )}

      <footer className="mt-10 border-t border-line pt-4 text-[11px] leading-relaxed text-faint">
        값은 전부 DB 에서 그대로 옵니다. 화면은 계산하지 않습니다. 없는 값은 비워 두고 0 으로
        채우지 않습니다 — 0 과 모름은 다릅니다.
      </footer>
    </main>
  );
}
