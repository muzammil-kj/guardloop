"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { downloadCsv, getAuditLog, getMe, type AuditRow, type Me } from "@/lib/reviewApi";

export default function AuditPage() {
  const router = useRouter();
  const [me, setMe] = useState<Me | null>(null);
  const [rows, setRows] = useState<AuditRow[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!window.localStorage.getItem("guardloop_api_key")) {
      router.push("/reviewer-login");
      return;
    }
    getMe()
      .then(async (who) => {
        setMe(who);
        if (who.role !== "owner") {
          setError("Only owners can view the audit log.");
          return;
        }
        setRows(await getAuditLog());
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Could not load the audit log."))
      .finally(() => setLoading(false));
  }, [router]);

  async function exportCsv(path: string, filename: string) {
    setError("");
    try {
      await downloadCsv(path, filename);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Export failed.");
    }
  }

  return (
    <main className="min-h-screen bg-slate-950 text-slate-100 px-8 py-8">
      <header className="mb-8 flex items-center justify-between gap-4">
        <div>
          <Link href="/review" className="text-xs text-slate-500 hover:text-slate-300">← Review queue</Link>
          <h1 className="text-xl font-semibold text-slate-50 mt-2">Audit log</h1>
          <p className="text-sm text-slate-400 mt-1">
            Every review, assignment, policy, budget, key and membership change.
          </p>
        </div>
        {me?.role === "owner" && (
          <div className="flex gap-3 shrink-0">
            <button onClick={() => exportCsv("/exports/decisions.csv", "guardloop-decisions.csv")}
                    className="text-sm text-slate-400 hover:text-slate-200 border border-slate-800 rounded-md px-3 py-1.5">
              Export decisions (CSV)
            </button>
            <button onClick={() => exportCsv("/exports/audit.csv", "guardloop-audit.csv")}
                    className="text-sm text-slate-400 hover:text-slate-200 border border-slate-800 rounded-md px-3 py-1.5">
              Export audit (CSV)
            </button>
          </div>
        )}
      </header>

      {error && <div className="mb-6 text-sm text-amber-300 border border-amber-900 bg-amber-950/40 rounded-md px-4 py-3">{error}</div>}
      {loading && <p className="text-sm text-slate-500">Loading...</p>}

      {rows.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-slate-500 border-b border-slate-800">
                <th className="pb-2 pr-4 font-normal">When</th>
                <th className="pb-2 pr-4 font-normal">Who</th>
                <th className="pb-2 pr-4 font-normal">Action</th>
                <th className="pb-2 pr-4 font-normal">Target</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.id} className="border-b border-slate-900">
                  <td className="py-2 pr-4 text-slate-400">{new Date(row.created_at).toLocaleString()}</td>
                  <td className="py-2 pr-4 text-slate-300">{row.actor_name}</td>
                  <td className="py-2 pr-4 text-slate-200">{row.action}</td>
                  <td className="py-2 pr-4 text-slate-400">
                    {row.target_type ? `${row.target_type} ${row.target_id ?? ""}` : "-"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </main>
  );
}