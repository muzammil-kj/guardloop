import { request } from "@/lib/api";

export type JudgeVerdict = "agree" | "disagree" | "unsure";

export interface JudgeSettings {
  enabled: boolean;
  sample_rate: number; // 0 to 1
  judge_configured: boolean; // does the server have a model key?
}

export interface JudgeAgentStats {
  agent_name: string;
  reviewed: number;
  agree: number;
  disagree: number;
  unsure: number;
  disagreement_rate: number; // 0 to 1
  avg_agent_confidence: number | null;
  needs_attention: boolean;
}

export interface JudgeSummary extends JudgeSettings {
  pending: number;
  totals: { reviewed: number; agree: number; disagree: number; unsure: number };
  agents: JudgeAgentStats[];
}

export interface JudgeReview {
  id: number;
  agent_name: string;
  event_type: string;
  input_summary: string | null;
  output_summary: string | null;
  confidence: number | null;
  judge_verdict: JudgeVerdict | null;
  judge_score: number | null;
  judge_reason: string | null;
  judge_reviewed_at: string | null;
}

export interface JudgeRunResult {
  reviewed: number;
  flagged: number;
  skipped: number;
  failed: number;
  retry_later: number;
  deferred: number;
  rate_limited: boolean;
  last_error: string | null;
}

export const getJudgeSettings = () => request<JudgeSettings>(`/judge/settings`);

export const updateJudgeSettings = (payload: {
  enabled: boolean;
  sample_rate: number;
}) =>
  request<JudgeSettings>(`/judge/settings`, {
    method: "PUT",
    body: JSON.stringify(payload),
  });

export const getJudgeSummary = () => request<JudgeSummary>(`/judge/summary`);

export const getJudgeReviews = (limit = 10) =>
  request<JudgeReview[]>(`/judge/reviews?limit=${limit}`);

export const runJudgeNow = () =>
  request<JudgeRunResult>(`/judge/run`, { method: "POST" });
