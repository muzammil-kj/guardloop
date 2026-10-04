const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface AgentEvent {
  id: number;
  agent_name: string;
  event_type: string;
  input_summary: string | null;
  output_summary: string | null;
  confidence: number | null;
  status: "approved" | "escalated";
  cost_usd: number;
  created_at: string;
}

export interface Escalation {
  id: number;
  event_id: number;
  reason: string;
  status: string;
  resolved_by: string | null;
  resolution_note: string | null;
  created_at: string;
  agent_events: AgentEvent;
}

export interface AgentCost {
  id: number;
  agent_name: string;
  date: string;
  total_cost_usd: number;
  event_count: number;
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    throw new Error(`Request to ${path} failed with status ${res.status}`);
  }
  return res.json();
}

export const getEvents = (limit = 50) =>
  request<AgentEvent[]>(`/events?limit=${limit}`);

export const getEscalations = (status = "pending") =>
  request<Escalation[]>(`/escalations?status=${status}`);

export const getCosts = () => request<AgentCost[]>(`/costs`);

export const resolveEscalation = (
  id: number,
  payload: { status: string; resolved_by: string; resolution_note?: string }
) =>
  request(`/escalations/${id}/resolve`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });