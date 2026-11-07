const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export type Role = "owner" | "reviewer" | "viewer";

export interface Me {
  organization: { id: string; name?: string };
  actor_name: string;
  actor_type: "user" | "api_key";
  role: Role;
}

export interface Escalation {
  id: number;
  reason: string;
  created_at: string;
  due_at: string | null;
  assigned_to: string | null;
  agent_events?: {
    agent_name: string;
    input_summary: string | null;
    confidence: number | null;
  } | null;
}

export interface AuditRow {
  id: number;
  created_at: string;
  actor_name: string;
  actor_type: string;
  action: string;
  target_type: string | null;
  target_id: string | null;
  detail: unknown;
}

function storedToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem("guardloop_api_key");
}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const token = storedToken();
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(init?.headers ?? {}),
    },
  });

  if (res.status === 401) {
    // Expired or revoked sign-in: send the person back to sign in again.
    window.localStorage.removeItem("guardloop_api_key");
    window.location.href = "/reviewer-login";
    throw new Error("Your sign-in has expired. Please sign in again.");
  }
  if (!res.ok) {
    let message = `Request failed (${res.status}).`;
    try {
      const body = await res.json();
      if (typeof body?.detail === "string") message = body.detail;
    } catch {
      // not JSON; keep the generic message
    }
    throw new Error(message);
  }
  return res.json();
}

export const getMe = () => call<Me>("/me");

export const getPendingEscalations = () =>
  call<Escalation[]>("/escalations?status=pending");

export const resolveEscalation = (id: number, status: "approved" | "rejected") =>
  call(`/escalations/${id}/resolve`, {
    method: "PATCH",
    body: JSON.stringify({ status, resolved_by: "reviewer" }),
  });

export const assignEscalation = (id: number, assigneeEmail: string | null) =>
  call(`/escalations/${id}/assign`, {
    method: "PATCH",
    body: JSON.stringify({ assignee_email: assigneeEmail }),
  });

export const getAuditLog = () => call<AuditRow[]>("/audit?limit=200");

/** Downloads a CSV export. A plain link can't send the Authorization header, so fetch it. */
export async function downloadCsv(path: string, filename: string): Promise<void> {
  const token = storedToken();
  const res = await fetch(`${API_URL}${path}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) throw new Error(`Export failed (${res.status}).`);
  const url = URL.createObjectURL(await res.blob());
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}


export interface CalibrationAgent {
  agent_name: string;
  reviews: number;
  flags_confirmed: number;
  flags_overruled: number;
  precision: number | null;
  precision_ci_low: number | null;
  precision_ci_high: number | null;
  reliable: boolean;
}

export interface Calibration extends CalibrationAgent {
  by_agent: CalibrationAgent[];
}

export interface VersionRow {
  agent_name: string;
  agent_version: string;
  first_seen: string | null;
  events: number;
  escalation_rate: number;
  block_rate: number;
  reviewed: number;
  disagreement_rate: number | null;
}

export const getCalibration = () => call<Calibration>("/quality/calibration");
export const getVersions = () => call<VersionRow[]>("/quality/versions");