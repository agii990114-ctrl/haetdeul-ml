/**
 * 백엔드 `backend/main.py` 가 내보내는 모양의 거울.
 *
 * ★ **여기서 값을 만들지 않는다.** 화면은 받은 것을 그리기만 한다.
 *   없는 값은 `null` 로 오고, 화면은 그 칸을 비운다. 0 으로 채우지 않는다 —
 *   **0 과 모름은 다르다.** 가격이 0원인 것과 가격을 모르는 것은 다르다.
 */

export type TargetKind = "auc" | "whsl" | "rtl";

/** 예측 한 줄. `actual` 은 대상일이 지나 채점된 것만 값이 있다. */
export interface ForecastRow {
  lead: number;
  target_dt: string;
  anchor: number | null;
  pred: number | null;
  lo: number | null;
  hi: number | null;
  actual: number | null;
  err_pct: number | null;
  gated: boolean;
  gate_reason: string | null;
}

export interface ForecastItem {
  item: string;
  unit: string;
  model_ver: string;
  /** 이 조합에 모델을 쓰라고 판정됐나. false 면 앵커가 그대로 나간다. */
  use_recommended: boolean | null;
  quality_note: string | null;
  rows: ForecastRow[];
}

export interface Forecast {
  base_dt: string;
  kind: TargetKind;
  kind_name: string;
  role: string;
  items: ForecastItem[];
}

export interface BaseDate {
  base_dt: string;
  n: number;
  scored: number;
  n_item: number;
  /**
   * 경락가 규격 혼합을 고치기(2026-08-27) 전에 만든 예측인가.
   *
   * true 면 서로 다른 포장 규격이 섞인 값으로 만든 것이라 다른 날과
   * 나란히 비교하면 안 된다. **지우지 않고 표시만 한다** — 그중에는
   * 매입 파트에 실제로 나간 기록도 있다.
   */
  pre_fix: boolean;
}

/** agent 점검 하나의 결과. `numbers` 는 [이름, 값] 짝이다. */
export interface Finding {
  level: "정상" | "주의" | "이상";
  title: string;
  detail: string;
  numbers: [string, string][];
  advice: string;
}

export interface AgentReport {
  name: string;
  verdict: "정상" | "주의" | "이상";
  at: string;
  days?: number;
  run_id?: number | null;
  findings: Finding[];
}

export interface AccuracyRow {
  kind: TargetKind;
  kind_name: string;
  item: string;
  n: number;
  model_wmape: number | null;
  anchor_wmape: number | null;
  mape: number | null;
  improve_pct: number | null;
  band_hit: number | null;
}

export interface Accuracy {
  min_lead: number;
  base_dt: string | null;
  rows: AccuracyRow[];
  caveat: string;
}

export interface Meta {
  kinds: { kind: TargetKind; name: string; role: string }[];
  items: string[];
  spec: Record<string, string>;
  market: string;
  note: string;
}

/** 저장된 agent 보고서 한 개. 파일이 원본이다. */
export interface HistoryItem {
  file: string;
  kind: string;
  /** "12:22:25" · Claude 일별 점검은 시각이 없어 null */
  time: string | null;
  /** 규칙 agent 만 판정을 갖는다. Claude 보고서는 null */
  verdict: "정상" | "주의" | "이상" | null;
  is_claude: boolean;
  bytes: number;
}

export interface HistoryDay {
  date: string;
  reports: HistoryItem[];
}
