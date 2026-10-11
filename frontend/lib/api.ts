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

export interface OrganizationCreated {
  organization_id: string;
  name: string;
  api_key: string;
}

export interface Policy {
  agent_name: string | null; // null = this org's default policy
  confidence_threshold: number;
  hard_escalate_event_types: string[];
  updated_at: string;
}

export interface PolicyUpdatePayload {
  confidence_threshold: number;
  hard_escalate_event_types: string[];
}

function getStoredApiKey(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem("guardloop_api_key");
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const apiKey = getStoredApiKey();
  const res = await fetch(`${API_URL}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(apiKey ? { Authorization: `Bearer ${apiKey}` } : {}),
    },
    ...options,
  });

  if (res.status === 401) {
    // Key is missing, invalid, or revoked - clear it and send the user back
    // to sign in again rather than showing a confusing broken dashboard.
    window.localStorage.removeItem("guardloop_api_key");
    window.location.href = "/";
    throw new Error("Unauthorized");
  }

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

export const getPolicies = () => request<Policy[]>(`/policies`);

export const setDefaultPolicy = (payload: PolicyUpdatePayload) =>
  request<Policy>(`/policies/default`, {
    method: "PUT",
    body: JSON.stringify(payload),
  });

export const setAgentPolicy = (agentName: string, payload: PolicyUpdatePayload) =>
  request<Policy>(`/policies/${encodeURIComponent(agentName)}`, {
    method: "PUT",
    body: JSON.stringify(payload),
  });

export const deleteAgentPolicy = (agentName: string) =>
  request(`/policies/${encodeURIComponent(agentName)}`, {
    method: "DELETE",
  });

export async function createOrganization(name: string): Promise<OrganizationCreated> {
  const res = await fetch(`${API_URL}/organizations`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
  if (!res.ok) {
    throw new Error("Failed to create organization");
  }
  return res.json();
}