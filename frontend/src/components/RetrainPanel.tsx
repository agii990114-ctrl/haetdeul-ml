"use client";

/**
 * 재학습 패널 — **사람이 화면에서 누른다.**
 *
 * ★ 왜 버튼이 둘인가
 *
 *   ① 후보 만들기 → (자동 검증) → ② 적용하기
 *
 *   검증을 통과해도 자동으로 안 바꿉니다. "성능이 나아졌나" 와 "지금 바꿔도
 *   되나" 는 다른 질문이고, 뒤엣것은 화면이 모릅니다 (발표 직전이거나 매입
 *   파트가 재고 있을 수 있습니다).
 *
 * ★ 실제로 검증이 한 번 막았습니다 (2026-09-07)
 *
 *   "학습이 981일 낡았으니 다시 배우자" 는 당연해 보였는데, 2년치를 더 배운
 *   후보가 2026 실전에서 배추 −10% 였습니다. 그래서 ②를 사람이 누릅니다.
 *
 * ★ 판정을 화면이 다시 계산하지 않습니다. agent 가 정한 글자를 그대로 씁니다.
 */

import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError, retrainApply, retrainBuild, retrainJob, retrainRollback, retrainStatus } from "@/lib/api";
import type { RetrainCheck, RetrainJob, RetrainStatus } from "@/lib/types";

import { Verdict } from "./AgentPanel";

const KIND_LABEL: Record<string, string> = {
  auc: "경락가",
  whsl: "중도매가",
  rtl: "소매가",
};

function Button({
  onClick,
  disabled,
  tone = "plain",
  children,
}: {
  onClick: () => void;
  disabled?: boolean;
  tone?: "plain" | "primary" | "warn";
  children: React.ReactNode;
}) {
  const skin =
    tone === "primary"
      ? "bg-accent text-white hover:brightness-110"
      : tone === "warn"
        ? "border border-warn text-warn hover:bg-warn-wash"
        : "border border-line text-ink hover:bg-sunk";
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={`rounded-md px-3 py-1.5 text-[12.5px] font-semibold transition
        disabled:cursor-not-allowed disabled:opacity-40 ${skin}`}
    >
      {children}
    </button>
  );
}

/** 검증 결과 표 — 품목별로 보여준다. 통합값은 안 보여준다 (비싼 품목이 지배한다). */
function CheckResult({ check }: { check: RetrainCheck }) {
  return (
    <div className="mt-3 rounded-lg border border-line bg-surface p-3.5">
      <div className="flex items-center gap-2">
        <Verdict level={check.verdict} />
        <span className="text-[12.5px] font-semibold">
          {check.passed ? "검증 통과" : "검증 통과 못 함"}
        </span>
        <span className="ml-auto text-[11px] text-muted">{check.at}</span>
      </div>

      <dl className="mt-2 grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5 text-[11.5px] text-muted">
        <dt>후보</dt>
        <dd className="m-0 font-mono">{check.candidate}</dd>
        <dt>견준 창</dt>
        <dd className="m-0">{check.eval_from} 이후 — 현행·후보 **둘 다 학습에 안 쓴 구간**</dd>
      </dl>

      <ul className="m-0 mt-2.5 list-none space-y-2 p-0">
        {check.findings.map((f, i) => (
          <li key={i} className="rounded-md border border-line-soft p-2.5">
            <div className="flex items-start gap-2">
              <Verdict level={f.level} />
              <p className="m-0 flex-1 text-[12.5px] font-semibold leading-snug">{f.title}</p>
            </div>
            {f.detail && (
              <p className="m-0 mt-1.5 whitespace-pre-line text-[11.5px] leading-relaxed text-muted">
                {f.detail}
              </p>
            )}
            {f.numbers.length > 0 && (
              <dl className="mt-1.5 grid grid-cols-[minmax(0,1fr)_auto] gap-x-3 border-t border-line-soft pt-1.5 text-[11.5px]">
                {f.numbers.map(([k, v], j) => (
                  <div key={j} className="contents">
                    <dt className="m-0 text-muted">{k}</dt>
                    <dd className="m-0 text-right font-mono tabular-nums">{v}</dd>
                  </div>
                ))}
              </dl>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}

export function RetrainPanel({ kind = "auc" }: { kind?: "auc" | "whsl" | "rtl" }) {
  const [status, setStatus] = useState<RetrainStatus | null>(null);
  const [job, setJob] = useState<RetrainJob | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<string | null>(null);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);

  const load = useCallback(async () => {
    try {
      setStatus(await retrainStatus(kind));
      setError(null);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    }
  }, [kind]);

  useEffect(() => {
    void load();
  }, [load]);

  //  돌고 있는 동안만 3초마다 물어본다. 끝나면 멈춘다 — 계속 물으면 서버가 논다.
  useEffect(() => {
    const running = job?.state === "running" || status?.job.state === "running";
    if (!running) {
      if (timer.current) clearInterval(timer.current);
      timer.current = null;
      return;
    }
    timer.current = setInterval(() => {
      void (async () => {
        const j = await retrainJob(40);
        setJob(j);
        if (j.state !== "running") void load();
      })();
    }, 3000);
    return () => {
      if (timer.current) clearInterval(timer.current);
    };
  }, [job?.state, status?.job.state, load]);

  const onBuild = async () => {
    setBusy(true);
    setNote(null);
    try {
      await retrainBuild(kind);
      setJob({ state: "running", started: null, kind, log: [], result: null });
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const onApply = async () => {
    const label = KIND_LABEL[kind] ?? kind;
    if (
      !window.confirm(
        `${label} 운영 모델을 후보로 바꿉니다.\n\n` +
          "· 지금 것은 통째로 백업됩니다 (되돌리기 가능)\n" +
          "· 모델 이름은 안 바뀝니다 — 매입 파트가 이름으로 찾습니다\n\n" +
          "바꿀까요?",
      )
    )
      return;
    setBusy(true);
    try {
      const r = await retrainApply(kind);
      setNote(`적용했습니다 — ${r.applied}`);
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const onRollback = async () => {
    if (!window.confirm("가장 최근 백업으로 되돌립니다. 계속할까요?")) return;
    setBusy(true);
    try {
      const r = await retrainRollback(kind);
      setNote(`되돌렸습니다 — ${r.restored}`);
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  if (error && !status)
    return (
      <p className="m-0 rounded-lg border border-warn bg-warn-wash p-3 text-[12.5px] text-warn">
        {error}
      </p>
    );
  if (!status) return <p className="m-0 text-[12.5px] text-muted">재학습 판정을 읽는 중…</p>;

  const running = job?.state === "running" || status.job.state === "running";
  const check = job?.result ?? status.last_check;

  return (
    <section className="space-y-3">
      <header className="flex flex-wrap items-center gap-2">
        <Verdict level={status.verdict} />
        <h3 className="m-0 text-[14px] font-semibold">
          {KIND_LABEL[status.kind] ?? status.kind} — 다시 배워야 하나
        </h3>
        <span className="text-[11px] text-muted">{status.at}</span>
        <div className="ml-auto flex gap-2">
          <Button onClick={onBuild} disabled={busy || running} tone="primary">
            {running ? "만드는 중…" : "후보 만들기"}
          </Button>
          <Button onClick={onApply} disabled={busy || running || !check?.passed}>
            적용하기
          </Button>
          {status.backups.length > 0 && (
            <Button onClick={onRollback} disabled={busy || running} tone="warn">
              되돌리기
            </Button>
          )}
        </div>
      </header>

      <p className="m-0 text-[11.5px] leading-relaxed text-muted">
        후보를 만들면 <b>현행과 똑같은 조리법</b>으로 학습해, 둘 다 안 본 구간(
        {check?.eval_from ?? "2026-01-01"} 이후)으로 견줍니다. 몇 분 걸립니다.
        <br />
        검증을 통과해도 <b>자동으로 안 바꿉니다</b> — 사람이 「적용하기」를 눌러야 바뀝니다.
      </p>

      {note && (
        <p className="m-0 rounded-md border border-accent bg-accent-wash p-2.5 text-[12px] text-accent-ink">
          {note}
        </p>
      )}
      {error && (
        <p className="m-0 rounded-md border border-warn bg-warn-wash p-2.5 text-[12px] text-warn">
          {error}
        </p>
      )}

      {/* 판정 근거 */}
      <ul className="m-0 list-none space-y-2 p-0">
        {status.findings.map((f, i) => (
          <li key={i} className="rounded-lg border border-line bg-surface p-3">
            <div className="flex items-start gap-2">
              <Verdict level={f.level} />
              <p className="m-0 flex-1 text-[12.5px] font-semibold leading-snug">{f.title}</p>
            </div>
            {f.detail && (
              <p className="m-0 mt-1.5 whitespace-pre-line text-[11.5px] leading-relaxed text-muted">
                {f.detail}
              </p>
            )}
            {f.numbers.length > 0 && (
              <dl className="mt-1.5 grid grid-cols-[minmax(0,1fr)_auto] gap-x-3 border-t border-line-soft pt-1.5 text-[11.5px]">
                {f.numbers.map(([k, v], j) => (
                  <div key={j} className="contents">
                    <dt className="m-0 text-muted">{k}</dt>
                    <dd className="m-0 text-right font-mono tabular-nums">{v}</dd>
                  </div>
                ))}
              </dl>
            )}
          </li>
        ))}
      </ul>

      {/* 돌고 있는 동안의 기록 */}
      {running && job && (
        <pre className="m-0 max-h-56 overflow-auto rounded-lg border border-line bg-sunk p-3 text-[11px] leading-relaxed">
          {job.log.length ? job.log.join("\n") : "시작하는 중…"}
        </pre>
      )}

      {/* 검증 결과 */}
      {check && !running && <CheckResult check={check} />}
    </section>
  );
}
