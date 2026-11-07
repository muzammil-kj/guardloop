"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { getCalibration, getVersions, type Calibration, type VersionRow } from "@/lib/reviewApi";

function pct(value: number | null) {
  return value === null ? "no data yet" : `${Math.round(value * 100)}%`;
}

function interval(low: number | null, high: number | null) {
  return low === null || high === null ? "" : ` (95% range ${Math.round(low * 100)}% to ${Math.round(high * 100)}%)`;
}

export default function QualityPage() {
  const router = useRouter();
  const [calibration, setCalibration] = useState<Calibration | null>(null);
  const [versions, setVersions] = useState<VersionRow[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!window.localStorage.getItem("guardloop_api_key")) {
      router.push("/reviewer-login");
      return;
    }
    Promise.all([getCalibration(), getVersions()])
      .then(([c, v]) => { setCalibration(c); setVersions(v); })
      .catch((err) => setError(err instanceof Error ? err.message : "Could not load quality data."));
  }, [router]);

  return (
    <main className="min-h-screen bg-slate-950 text-slate-100 px-8 py-8">
      <header className="mb-8">
        <Link href="/review" className="text-xs text-slate-500 hover:text-slate-300">← Review queue</Link>
        <h1 className="text-xl font-semibold text-slate-50 mt-2">Judge accuracy and agent versions</h1>
        <p className="text-sm text-slate-400 mt-1 max-w-2xl">
          When the judge flags a decision, a human reviews it. Rejecting the flag confirms the judge was right.
          Approving it means the judge was wrong.
        </p>
      </header>

      {error && <div className="mb-6 text-sm text-amber-300 border border-amber-900 bg-amber-950/40 rounded-md px-4 py-3">{error}</div>}

      {calibration && (
        <section className="border border-slate-800 rounded-lg p-5 bg-slate-900/40 mb-8 max-w-3xl">
          <h2 className="text-sm font-medium text-slate-200 mb-4">Judge precision</h2>
          <div className="grid grid-cols-3 gap-4 mb-4">
            <div>
              <p className="text-xs text-slate-400">Precision</p>
              <p className="text-2xl font-semibold text-slate-50 mt-1">{pct(calibration.precision)}</p>
              <p className="text-xs text-slate-500">{interval(calibration.precision_ci_low, calibration.precision_ci_high)}</p>
            </div>
            <div>
              <p className="text-xs text-slate-400">Confirmed by humans</p>
              <p className="text-2xl font-semibold text-emerald-400 mt-1">{calibration.flags_confirmed}</p>
            </div>
            <div>
              <p className="text-xs text-slate-400">Overruled by humans</p>
              <p className="text-2xl font-semibold text-amber-400 mt-1">{calibration.flags_overruled}</p>
            </div>
          </div>
          {!calibration.reliable && calibration.reviews > 0 && (
            <p className="text-xs text-amber-300 mb-4">
              Only {calibration.reviews} human reviews so far. Treat this as indicative until there are at least 30.
            </p>
          )}
          {calibration.by_agent.length > 0 && (
            <ul className="space-y-2 text-sm">
              {calibration.by_agent.map((agent) => (
                <li key={agent.agent_name} className="flex justify-between">
                  <span className="text-slate-200">{agent.agent_name}</span>
                  <span className="text-slate-400">
                    {pct(agent.precision)} of {agent.reviews} reviews
                  </span>
                </li>
              ))}
            </ul>
          )}
        </section>
      )}

      <section className="max-w-4xl">
        <h2 className="text-sm font-medium text-slate-200 mb-3">Decisions by agent version</h2>
        <p className="text-xs text-slate-500 mb-4">
          Oldest first. If a newer version shows a higher disagreement or escalation rate than the one before, that's a regression.
        </p>
        {versions.length === 0 && <p className="text-sm text-slate-500">No decisions yet.</p>}
        {versions.length > 0 && (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-slate-500 border-b border-slate-800">
                <th className="pb-2 pr-4 font-normal">Agent</th>
                <th className="pb-2 pr-4 font-normal">Version</th>
                <th className="pb-2 pr-4 font-normal">Decisions</th>
                <th className="pb-2 pr-4 font-normal">Escalated</th>
                <th className="pb-2 pr-4 font-normal">Judge disagreed</th>
              </tr>
            </thead>
            <tbody>
              {versions.map((row) => (
                <tr key={`${row.agent_name}-${row.agent_version}`} className="border-b border-slate-900">
                  <td className="py-2 pr-4 text-slate-300">{row.agent_name}</td>
                  <td className="py-2 pr-4 text-slate-200">{row.agent_version}</td>
                  <td className="py-2 pr-4 text-slate-400">{row.events}</td>
                  <td className="py-2 pr-4 text-slate-400">{pct(row.escalation_rate)}</td>
                  <td className="py-2 pr-4 text-slate-400">
                    {row.disagreement_rate === null ? "not reviewed" : `${pct(row.disagreement_rate)} of ${row.reviewed}`}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </main>
  );
}