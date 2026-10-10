"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from "recharts";
import {
  getEvents,
  getEscalations,
  getCosts,
  resolveEscalation,
  AgentEvent,
  Escalation,
  AgentCost,
} from "@/lib/api";

export default function DashboardPage() {
  const router = useRouter();
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [escalations, setEscalations] = useState<Escalation[]>([]);
  const [costs, setCosts] = useState<AgentCost[]>([]);
  const [loading, setLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState("");

  useEffect(() => {
    if (!window.localStorage.getItem("guardloop_api_key")) {
      router.push("/");
      return;
    }
    loadData();
  }, []);

  async function loadData() {
    try {
      const [e, esc, c] = await Promise.all([
        getEvents(50),
        getEscalations("pending"),
        getCosts(),
      ]);
      setEvents(e);
      setEscalations(esc);
      setCosts(c);
    } catch {
      setErrorMsg(
        "Could not reach the Guardloop API. Check that NEXT_PUBLIC_API_URL points to a running backend."
      );
    } finally {
      setLoading(false);
    }
  }

  async function handleResolve(id: number, status: string) {
    await resolveEscalation(id, { status, resolved_by: "demo@guardloop.ai" });
    setEscalations((prev) => prev.filter((esc) => esc.id !== id));
  }

  const costByAgent = costs.reduce<Record<string, number>>((acc, row) => {
    acc[row.agent_name] = (acc[row.agent_name] || 0) + row.total_cost_usd;
    return acc;
  }, {});
  const chartData = Object.entries(costByAgent).map(([agent, cost]) => ({
    agent,
    cost: Number(cost.toFixed(4)),
  }));

  if (loading) {
    return (
      <main className="min-h-screen bg-slate-950 text-slate-400 flex items-center justify-center text-sm">
        Loading agent activity...
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-slate-950 text-slate-100 px-8 py-8">
      <header className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-slate-50">Guardloop</h1>
          <p className="text-sm text-slate-400 mt-1">
            Live view of every agent decision, what got escalated, and what it's costing you.
          </p>
        </div>
        <button
          onClick={() => {
            window.localStorage.removeItem("guardloop_api_key");
            router.push("/");
          }}
          className="text-sm text-slate-400 hover:text-slate-200 border border-slate-800 rounded-md px-3 py-1.5"
        >
          Sign out
        </button>
      </header>

      {errorMsg && (
        <div className="mb-6 border border-amber-900 bg-amber-950/40 text-amber-300 text-sm rounded-md px-4 py-3">
          {errorMsg}
        </div>
      )}

      <section className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
        <div className="border border-slate-800 rounded-lg p-5 bg-slate-900/40">
          <p className="text-xs text-slate-400">Total events (recent)</p>
          <p className="text-3xl font-semibold text-slate-50 mt-1">{events.length}</p>
        </div>
        <div className="border border-slate-800 rounded-lg p-5 bg-slate-900/40">
          <p className="text-xs text-slate-400">Pending escalations</p>
          <p className="text-3xl font-semibold text-amber-400 mt-1">{escalations.length}</p>
        </div>
        <div className="border border-slate-800 rounded-lg p-5 bg-slate-900/40">
          <p className="text-xs text-slate-400">Cost tracked (all agents)</p>
          <p className="text-3xl font-semibold text-emerald-400 mt-1">
            ${costs.reduce((sum, c) => sum + c.total_cost_usd, 0).toFixed(3)}
          </p>
        </div>
      </section>

      <section className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="border border-slate-800 rounded-lg p-5 bg-slate-900/40">
          <h2 className="text-sm font-medium text-slate-200 mb-4">
            Cost by agent
          </h2>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis dataKey="agent" stroke="#64748b" fontSize={11} />
              <YAxis stroke="#64748b" fontSize={11} />
              <Tooltip
                contentStyle={{ background: "#0f172a", border: "1px solid #1e293b" }}
                labelStyle={{ color: "#e2e8f0" }}
              />
              <Bar dataKey="cost" fill="#f59e0b" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="border border-slate-800 rounded-lg p-5 bg-slate-900/40">
          <h2 className="text-sm font-medium text-slate-200 mb-4">
            Pending escalations
          </h2>
          {escalations.length === 0 ? (
            <p className="text-sm text-slate-500">Nothing waiting on human review right now.</p>
          ) : (
            <ul className="space-y-3">
              {escalations.map((esc) => (
                <li
                  key={esc.id}
                  className="border border-amber-900/50 bg-amber-950/20 rounded-md p-3"
                >
                  <p className="text-xs text-amber-400 mb-1">{esc.agent_events?.agent_name}</p>
                  <p className="text-sm text-slate-200">{esc.agent_events?.input_summary}</p>
                  <p className="text-xs text-slate-400 mt-1">{esc.reason}</p>
                  <div className="flex gap-2 mt-3">
                    <button
                      onClick={() => handleResolve(esc.id, "approved")}
                      className="text-xs bg-emerald-600 hover:bg-emerald-500 text-slate-950 rounded px-2.5 py-1"
                    >
                      Approve
                    </button>
                    <button
                      onClick={() => handleResolve(esc.id, "rejected")}
                      className="text-xs bg-slate-700 hover:bg-slate-600 text-slate-100 rounded px-2.5 py-1"
                    >
                      Reject
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      </section>

      <section className="mt-6 border border-slate-800 rounded-lg p-5 bg-slate-900/40">
        <h2 className="text-sm font-medium text-slate-200 mb-4">Recent events</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-slate-500 border-b border-slate-800">
                <th className="pb-2 pr-4 font-normal">Agent</th>
                <th className="pb-2 pr-4 font-normal">Summary</th>
                <th className="pb-2 pr-4 font-normal">Confidence</th>
                <th className="pb-2 pr-4 font-normal">Status</th>
              </tr>
            </thead>
            <tbody>
              {events.slice(0, 15).map((ev) => (
                <tr key={ev.id} className="border-b border-slate-900">
                  <td className="py-2 pr-4 text-slate-300">{ev.agent_name}</td>
                  <td className="py-2 pr-4 text-slate-400">{ev.input_summary}</td>
                  <td className="py-2 pr-4 text-slate-400">
                    {ev.confidence !== null ? ev.confidence.toFixed(2) : "—"}
                  </td>
                  <td className="py-2 pr-4">
                    <span
                      className={
                        ev.status === "escalated"
                          ? "text-amber-400"
                          : "text-emerald-400"
                      }
                    >
                      {ev.status}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </main>
  );
}