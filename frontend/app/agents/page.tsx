"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  getAgentsOverview,
  getMe,
  setAgentBudget,
  setKillSwitch,
  type AgentOverview,
  type Me,
} from "@/lib/reviewApi";

function money(value: number | null) {
  return value === null ? "no cap" : `$${value.toFixed(2)}`;
}

function status(agent: AgentOverview) {
  if (agent.killed) return { label: "Switched off", className: "text-red-400" };
  if (!agent.allowed) return { label: "Over budget", className: "text-amber-400" };
  return { label: "Active", className: "text-emerald-400" };
}

export default function AgentsPage() {
  const router = useRouter();
  const [me, setMe] = useState<Me | null>(null);
  const [agents, setAgents] = useState<AgentOverview[]>([]);
  const [budgetDrafts, setBudgetDrafts] = useState<Record<string, string>>({});
  const [reasonDrafts, setReasonDrafts] = useState<Record<string, string>>({});
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      setAgents(await getAgentsOverview());
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load agents.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!window.localStorage.getItem("guardloop_api_key")) {
      router.push("/reviewer-login");
      return;
    }
    getMe().then(setMe).catch(() => undefined);
    load();
  }, [router, load]);

  const isOwner = me?.role === "owner";

  async function saveBudget(agent: AgentOverview) {
    setError("");
    const raw = (budgetDrafts[agent.agent_name] ?? "").trim();
    const value = raw === "" ? null : Number(raw);
    if (value !== null && (!Number.isFinite(value) || value <= 0)) {
      setError("Enter a positive amount, or leave the box empty to remove the cap.");
      return;
    }
    try {
      await setAgentBudget(agent.agent_name, value);
      setBudgetDrafts((prev) => ({ ...prev, [agent.agent_name]: "" }));
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save the budget.");
    }
  }

  async function toggleKillSwitch(agent: AgentOverview) {
    setError("");
    const switchOff = !agent.killed;
    const reason = switchOff ? (reasonDrafts[agent.agent_name] ?? "").trim() || null : null;
    try {
      await setKillSwitch(agent.agent_name, switchOff, reason);
      setReasonDrafts((prev) => ({ ...prev, [agent.agent_name]: "" }));
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not change the switch.");
    }
  }

  const input =
    "rounded-md bg-slate-950 border border-slate-700 px-2 py-1 text-xs text-slate-100 focus:outline-none focus:ring-2 focus:ring-amber-500";
  const button =
    "text-xs rounded-md px-2.5 py-1 disabled:opacity-40";

  return (
    <main className="min-h-screen bg-slate-950 text-slate-100 px-8 py-8">
      <header className="mb-8 flex items-center justify-between gap-4">
        <div>
          <Link href="/review" className="text-xs text-slate-500 hover:text-slate-300">← Review queue</Link>
          <h1 className="text-xl font-semibold text-slate-50 mt-2">Agents, budgets and switches</h1>
          {me && (
            <p className="text-sm text-slate-400 mt-1">
              Signed in as {me.actor_name} ({me.role}).{" "}
              {isOwner ? "You can change budgets and switch agents off." : "You can view this page. Only owners can change it."}
            </p>
          )}
        </div>
      </header>

      {error && (
        <div className="mb-6 text-sm text-amber-300 border border-amber-900 bg-amber-950/40 rounded-md px-4 py-3">
          {error}
        </div>
      )}
      {loading && <p className="text-sm text-slate-500">Loading...</p>}
      {!loading && agents.length === 0 && (
        <p className="text-sm text-slate-500">No agents have reported yet.</p>
      )}

      {agents.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-slate-500 border-b border-slate-800">
                <th className="pb-2 pr-4 font-normal">Agent</th>
                <th className="pb-2 pr-4 font-normal">Status</th>
                <th className="pb-2 pr-4 font-normal">Daily cap</th>
                <th className="pb-2 pr-4 font-normal">Spent today</th>
                <th className="pb-2 pr-4 font-normal">Set budget</th>
                <th className="pb-2 pr-4 font-normal">Kill switch</th>
              </tr>
            </thead>
            <tbody>
              {agents.map((agent) => {
                const state = status(agent);
                return (
                  <tr key={agent.agent_name} className="border-b border-slate-900 align-top">
                    <td className="py-3 pr-4 text-slate-200">{agent.agent_name}</td>
                    <td className={`py-3 pr-4 ${state.className}`}>
                      {state.label}
                      {agent.killed && agent.kill_reason && (
                        <p className="text-xs text-slate-500 mt-1">{agent.kill_reason}</p>
                      )}
                    </td>
                    <td className="py-3 pr-4 text-slate-400">
                      {money(agent.daily_budget_usd)}
                      {agent.budget_source && (
                        <p className="text-xs text-slate-600">{agent.budget_source === "agent" ? "agent setting" : "organization default"}</p>
                      )}
                    </td>
                    <td className="py-3 pr-4 text-slate-400">
                      {money(agent.spent_today_usd)}
                      {agent.remaining_usd !== null && (
                        <p className="text-xs text-slate-600">{money(agent.remaining_usd)} left</p>
                      )}
                    </td>
                    <td className="py-3 pr-4">
                      {isOwner ? (
                        <div className="flex gap-2">
                          <input
                            type="number"
                            min={0.01}
                            step={0.5}
                            placeholder="USD, empty = no cap"
                            value={budgetDrafts[agent.agent_name] ?? ""}
                            onChange={(e) => setBudgetDrafts((prev) => ({ ...prev, [agent.agent_name]: e.target.value }))}
                            className={`${input} w-32`}
                          />
                          <button onClick={() => saveBudget(agent)}
                                  className={`${button} bg-slate-700 hover:bg-slate-600 text-slate-100`}>
                            Save
                          </button>
                        </div>
                      ) : (
                        <span className="text-xs text-slate-600">Owners only</span>
                      )}
                    </td>
                    <td className="py-3 pr-4">
                      {isOwner ? (
                        <div className="flex flex-col gap-2 items-start">
                          {!agent.killed && (
                            <input
                              type="text"
                              maxLength={300}
                              placeholder="Reason (optional)"
                              value={reasonDrafts[agent.agent_name] ?? ""}
                              onChange={(e) => setReasonDrafts((prev) => ({ ...prev, [agent.agent_name]: e.target.value }))}
                              className={`${input} w-56`}
                            />
                          )}
                          <button
                            onClick={() => toggleKillSwitch(agent)}
                            className={`${button} ${agent.killed
                              ? "bg-emerald-600 hover:bg-emerald-500 text-slate-950"
                              : "bg-red-600 hover:bg-red-500 text-slate-50"}`}
                          >
                            {agent.killed ? "Switch back on" : "Switch off"}
                          </button>
                        </div>
                      ) : (
                        <span className="text-xs text-slate-600">Owners only</span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </main>
  );
}