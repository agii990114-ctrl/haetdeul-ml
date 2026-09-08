/**
 * 우리 백엔드(`backend/main.py`) 클라이언트.
 *
 * ★ **`/api` 는 `next.config.ts` 의 개발 프록시가 백엔드로 넘긴다.** 같은 출처라
 *   CORS 가 없다. 배포(정적 export)에는 프록시가 없으므로 `NEXT_PUBLIC_API_BASE`
 *   로 절대 주소를 준다.
 *
 * ★ **서버가 낸 오류 문장을 그대로 올린다.** 화면이 "오류가 발생했습니다" 로 덮으면
 *   `2025-12-31 의 경락가 예측이 없습니다` 처럼 **무엇을 해야 하는지 알려주는 문장**
 *   이 사라진다. mainproject 화면과 같은 규칙이다.
 */

import type {
  Accuracy,
  AgentReport,
  BaseDate,
  Forecast,
  HistoryDay,
  Meta,
  GraphStatus,
  RetrainJob,
  RetrainStatus,
  TargetKind,
} from "./types";

const BASE = process.env.NEXT_PUBLIC_API_BASE ?? "/api";

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
  }
}

async function call<T>(path: string): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${BASE}${path}`);
  } catch {
    throw new ApiError(
      0,
      "백엔드에 닿지 못했습니다 — `python -m uvicorn backend.main:app --port 8100` 이 떠 있는지 확인해 주세요.",
    );
  }

  const body = await response.text();
  if (!response.ok) {
    let detail = body;
    try {
      const parsed = JSON.parse(body) as { detail?: unknown };
      if (typeof parsed.detail === "string") detail = parsed.detail;
      else if (parsed.detail) detail = JSON.stringify(parsed.detail);
    } catch {
      /* JSON 이 아니면 본문을 그대로 쓴다 */
    }
    throw new ApiError(response.status, detail);
  }
  return JSON.parse(body) as T;
}

/**
 * 쓰기 요청. **읽기(`call`)와 나눠 둔다** — 실수로 GET 자리에 POST 가
 * 들어가면 화면을 새로 그릴 때마다 재학습이 돈다.
 */
async function post<T>(path: string): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${BASE}${path}`, { method: "POST" });
  } catch {
    throw new ApiError(0, "백엔드에 닿지 못했습니다.");
  }
  const body = await response.text();
  if (!response.ok) {
    let detail = body;
    try {
      const parsed = JSON.parse(body) as { detail?: unknown };
      if (typeof parsed.detail === "string") detail = parsed.detail;
    } catch {
      /* JSON 이 아니면 본문 그대로 */
    }
    throw new ApiError(response.status, detail);
  }
  return JSON.parse(body) as T;
}

/** 시연 기준일. 매입 파트가 이 날짜로 돈다 — mainproject 화면의 `AS_OF` 와 같다. */
export const AS_OF = process.env.NEXT_PUBLIC_AS_OF ?? "2025-12-31";

export const meta = () => call<Meta>("/meta");
//  ★ 90 -> 400 (2026-09-04). 2026 기준일 137개를 백필하자 목록이 잘려
//    1월이 화면에서 사라졌다. "지워졌나" 로 보이지만 잘린 것이었다.
//    서버 상한이 400 이다.
export const baseDates = () => call<BaseDate[]>("/forecast/base-dates?limit=400");
/**
 * `showActual` — 실제값을 함께 받을지.
 *
 * 지금은 지난 날짜로 시연하니 정답이 이미 있지만, **실제 운영에서는 예측을
 * 낼 때 정답이 없다.** 끄면 서버가 `actual`·`err_pct` 를 null 로 비워 보낸다.
 */
export const forecast = (baseDt: string, kind: TargetKind, showActual = true) =>
  call<Forecast>(
    `/forecast?base_dt=${encodeURIComponent(baseDt)}&kind=${kind}` +
      `&show_actual=${showActual}`,
  );
export const accuracy = (minLead = 3) => call<Accuracy>(`/accuracy?min_lead=${minLead}`);

/** 데이터 품질 agent — DB 를 훑어 10초쯤 걸린다. 백엔드가 10분 캐시한다. */
export const qualityAgent = (days = 180) => call<AgentReport>(`/quality?days=${days}`);

/**
 * 뉴스 agent — 오늘 기사에서 우리 품목 이야기를 골라 온다.
 *
 * ★ ollama 를 15번쯤 부르므로 30초쯤 걸린다. 백엔드가 30분 캐시한다.
 *   AI 가 죽어도 빈칸이 안 온다 — 규칙으로 떨어지고 그 사실을 보고에 적는다.
 */
export const newsAgent = (date?: string) =>
  call<AgentReport & { date: string }>(
    "/agent/news" + (date ? `?date=${encodeURIComponent(date)}` : ""),
  );

/** 배치 장애 조사 agent — 규칙 부분만. AI 조사는 부르지 않는다. */
export const batchAgent = () => call<AgentReport>("/agent/batch");

/** 지난 agent 보고서 목록 — 날짜별로 묶여 온다. */
export const agentHistory = () => call<{ dates: HistoryDay[] }>("/agent/history");

/** 보고서 한 개의 내용. 파일 이름만 넘긴다 (경로는 서버가 막는다). */
export const agentReport = (file: string) =>
  call<{ file: string; text: string; is_claude: boolean }>(
    `/agent/report?file=${encodeURIComponent(file)}`,
  );

/** 예측 하나를 왜 그렇게 냈는지. 규칙만 돌아서 빠르다 (AI 안 부름). */
export const explain = (
  baseDt: string,
  item: string,
  kind: TargetKind,
  lead: number,
  showActual = true,
) =>
  call<AgentReport>(
    `/agent/explain?base_dt=${encodeURIComponent(baseDt)}` +
      `&item=${encodeURIComponent(item)}&kind=${kind}&lead=${lead}` +
      `&show_actual=${showActual}`,
  );

// ───────────────────────────────────────────────────────────── 재학습
//
//  ★ 두 번 누릅니다 — ① 후보 만들기 ② 적용하기. 사이에 검증이 들어갑니다.
//    검증을 통과 못 하면 서버가 ②를 거절합니다 (화면이 막는 게 아니라).

/** 다시 배워야 하나. 몇 초 걸린다. */
export const retrainStatus = (kind: TargetKind = "auc") =>
  call<RetrainStatus>(`/retrain/status?kind=${kind}`);

/** 후보를 만들고 검증한다. **적용은 안 한다.** 몇 분 걸려 배경에서 돈다. */
export const retrainBuild = (kind: TargetKind = "auc") =>
  post<{ state: string; kind: string }>(`/retrain/build?kind=${kind}`);

/** 돌고 있는 작업 상태와 최근 줄. */
export const retrainJob = (tail = 60) => call<RetrainJob>(`/retrain/job?tail=${tail}`);

/** 검증을 통과한 후보를 적용한다. 통과 못 했으면 서버가 거절한다. */
export const retrainApply = (kind: TargetKind = "auc") =>
  post<{ applied: string; backup: string[] }>(`/retrain/apply?kind=${kind}`);

/** 되돌린다. 이름을 안 주면 가장 최근 백업. */
export const retrainRollback = (kind: TargetKind = "auc", backup?: string) =>
  post<{ restored: string }>(
    `/retrain/rollback?kind=${kind}` + (backup ? `&backup=${encodeURIComponent(backup)}` : ""),
  );

// ───────────────────────────────────────── 재학습 (LangGraph)
//
//  ★ 위의 retrain* 다섯과 **나란히** 있다. 지금 것을 안 지웠다.
//    다른 점: 상태가 서버 메모리가 아니라 체크포인트에 있어
//    **서버가 재시작돼도 작업이 남는다.**

/** 지금 어디 서 있나. 체크포인트를 읽는다. */
export const graphStatus = (kind: TargetKind = "auc") =>
  call<GraphStatus>(`/retrain/graph/status?kind=${kind}`);

/**
 * 그래프를 굴린다.
 *   answer 없음 = 처음부터 (판정)
 *   "build"     = 후보를 만든다 (몇 분)
 *   "apply"     = 운영 모델을 바꾼다
 *   "stop"      = 그만둔다
 */
export const graphAct = (kind: TargetKind = "auc", answer?: "build" | "apply" | "stop") =>
  post<{ started: boolean }>(
    `/retrain/graph/act?kind=${kind}` + (answer ? `&answer=${answer}` : ""),
  );

/** 흐름만 처음으로 되돌린다. **모델은 안 건드린다.** */
export const graphReset = (kind: TargetKind = "auc") =>
  post<{ reset: string }>(`/retrain/graph/reset?kind=${kind}`);
