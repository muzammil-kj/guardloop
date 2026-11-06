"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  assignEscalation,
  getMe,
  getPendingEscalations,
  resolveEscalation,
  type Escalation,
  type Me,
} from "@/lib/reviewApi";

function isOverdue(item: Escalation) {
  return item.due_at !== null && new Date(item.due_at).getTime() < Date.now();
}

export default function ReviewQueuePage() {
  const router = useRouter();
  const [me, setMe] = useState<Me | null>(null);
  const [items, setItems] = useState<Escalation[]>([]);
  const [assignDrafts, setAssignDrafts] = useState<Record<number, string>>({});
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      setItems(await getPendingEscalations());
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load the queue.");
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

  const canReview = me !== null && me.role !== "viewer";

  async function decide(id: number, status: "approved" | "rejected") {
    setError("");
    try {
      await resolveEscalation(id, status);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save that decision.");
    }
  }

  async function assign(id: number) {
    setError("");
    const email = (assignDrafts[id] ?? "").trim();
    try {
      await assignEscalation(id, email || null);
      setAssignDrafts((prev) => ({ ...prev, [id]: "" }));
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not assign that review.");
    }
  }

  return (
    <main className="min-h-screen bg-slate-950 text-slate-100 px-8 py-8">
      <header className="mb-8 flex items-center justify-between gap-4">
        <div>
          <Link href="/dashboard" className="text-xs text-slate-500 hover:text-slate-300">← Dashboard</Link>
          <h1 className="text-xl font-semibold text-slate-50 mt-2">Review queue</h1>
          {me && (
            <p className="text-sm text-slate-400 mt-1">
              Signed in as {me.actor_name} ({me.role})
            </p>
          )}
        </div>
        <div className="flex gap-3">
          {me?.role === "owner" && (
            <Link href="/audit" className="text-sm text-slate-400 hover:text-slate-200 border border-slate-800 rounded-md px-3 py-1.5">
              Audit log
            </Link>
          )}
        </div>
      </header>

      {error && <div className="mb-6 text-sm text-amber-300 border border-amber-900 bg-amber-950/40 rounded-md px-4 py-3">{error}</div>}
      {loading && <p className="text-sm text-slate-500">Loading...</p>}
      {!loading && items.length === 0 && <p className="text-sm text-slate-500">Nothing is waiting for review.</p>}

      <ul className="space-y-4 max-w-3xl">
        {items.map((item) => (
          <li key={item.id} className="border border-slate-800 rounded-lg p-5 bg-slate-900/40">
            <div className="flex items-center justify-between gap-3 mb-2">
              <span className="text-xs text-amber-400">{item.agent_events?.agent_name ?? "agent"}</span>
              <span className={`text-xs ${isOverdue(item) ? "text-red-400 font-medium" : "text-slate-400"}`}>
                {item.due_at
                  ? `${isOverdue(item) ? "Overdue since" : "Due"} ${new Date(item.due_at).toLocaleString()}`
                  : "No deadline"}
              </span>
            </div>
            {item.agent_events?.input_summary && (
              <p className="text-sm text-slate-200 mb-2">{item.agent_events.input_summary}</p>
            )}
            <p className="text-xs text-slate-400 mb-3">{item.reason}</p>
            <p className="text-xs text-slate-500 mb-3">
              Assigned to: {item.assigned_to ?? "nobody yet"}
            </p>

            {canReview && (
              <>
                <div className="flex gap-2 mb-3">
                  <input
                    type="email"
                    placeholder="colleague@company.com"
                    value={assignDrafts[item.id] ?? ""}
                    onChange={(e) => setAssignDrafts((prev) => ({ ...prev, [item.id]: e.target.value }))}
                    className="flex-1 rounded-md bg-slate-950 border border-slate-700 px-3 py-1.5 text-xs text-slate-100 focus:outline-none focus:ring-2 focus:ring-amber-500"
                  />
                  <button onClick={() => assign(item.id)}
                          className="text-xs border border-slate-700 hover:border-slate-500 rounded-md px-3">
                    Assign
                  </button>
                </div>
                <div className="flex gap-2">
                  <button onClick={() => decide(item.id, "approved")}
                          className="text-xs bg-emerald-600 hover:bg-emerald-500 text-slate-950 rounded px-2.5 py-1">
                    Approve
                  </button>
                  <button onClick={() => decide(item.id, "rejected")}
                          className="text-xs bg-slate-700 hover:bg-slate-600 text-slate-100 rounded px-2.5 py-1">
                    Reject
                  </button>
                </div>
              </>
            )}
          </li>
        ))}
      </ul>
    </main>
  );
}
