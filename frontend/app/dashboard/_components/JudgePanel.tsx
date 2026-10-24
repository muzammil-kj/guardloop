"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";

import {
  getJudgeReviews,
  getJudgeSummary,
  runJudgeNow,
  type JudgeReview,
  type JudgeSummary,
  type JudgeVerdict,
} from "@/lib/judgeApi";

const VERDICT_STYLE: Record<JudgeVerdict, { dot: string; text: string; label: string }> = {
  agree: { dot: "bg-emerald-400", text: "text-emerald-400", label: "Agreed" },
  disagree: { dot: "bg-amber-400", text: "text-amber-400", label: "Disagreed" },
  unsure: { dot: "bg-slate-500", text: "text-slate-400", label: "Unsure" },
};

function percent(value: number) {
  return `${Math.round(value * 100)}%`;
}

/**
 * `refreshKey` is any value that changes when the dashboard's data refreshes
 * (the page passes its events array), so judge results stay as live as the
 * rest of the dashboard without this panel needing its own subscription.
 */
export default function JudgePanel({ refreshKey }: { refreshKey?: unknown }) {
  const [summary, setSummary] = useState<JudgeSummary | null>(null);
  const [reviews, setReviews] = useState<JudgeReview[]>([]);
  const [unavailable, setUnavailable] = useState(false);
  const [running, setRunning] = useState(false);
  const [message, setMessage] = useState("");

  const load = useCallback(async () => {
    try {
      const [s, r] = await Promise.all([getJudgeSummary(), getJudgeReviews(6)]);
      setSummary(s);
      setReviews(r);
      setUnavailable(false);
    } catch {
      setUnavailable(true);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load, refreshKey]);

  async function handleRun() {
    setRunning(true);
    setMessage("");
    try {
      const result = await runJudgeNow();
      const problems = result.retry_later + result.failed;
      if (result.rate_limited) {
        setMessage(
          `Reviewed ${result.reviewed}. The review model asked us to slow down; the rest will run on the next pass.`
        );
      } else if (result.reviewed + result.skipped + problems === 0) {
        setMessage("Nothing is waiting for review.");
      } else {
        const base = `Reviewed ${result.reviewed}, sent ${result.flagged} to your review queue.`;
        setMessage(
          problems > 0
            ? `${base} ${problems} could not be reviewed and will be retried. Last error: ${result.last_error ?? "unknown"}`
            : base
        );
      }
      await load();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Could not run the review.");
    } finally {
      setRunning(false);
    }
  }

  let body: React.ReactNode;

  if (unavailable) {
    body = (
      <p className="text-sm text-slate-500">
        Judge data isn&apos;t available yet. Run <code>PHASE5_MIGRATION.sql</code>{" "}
        in Supabase, then refresh.
      </p>
    );
  } else if (!summary) {
    body = <p className="text-sm text-slate-500">Loading...</p>;
  } else if (!summary.judge_configured) {
    body = (
      <p className="text-sm text-slate-400">
        The judge needs a <code>GEMINI_API_KEY</code> set on the server before it
        can review anything.
      </p>
    );
  } else if (!summary.enabled && summary.totals.reviewed === 0) {
    body = (
      <p className="text-sm text-slate-400">
        The judge is off. Turn it on in{" "}
        <Link href="/dashboard/settings" className="text-amber-400 hover:text-amber-300">
          Policy settings
        </Link>{" "}
        to have a second model check a sample of your auto-approved decisions.
      </p>
    );
  } else {
    body = (
      <>
        <div className="grid grid-cols-3 gap-4 mb-6">
          <div>
            <p className="text-xs text-slate-400">Reviewed</p>
            <p className="text-2xl font-semibold text-slate-50 mt-1">
              {summary.totals.reviewed}
            </p>
          </div>
          <div>
            <p className="text-xs text-slate-400">Disagreed</p>
            <p className="text-2xl font-semibold text-amber-400 mt-1">
              {summary.totals.disagree}
            </p>
          </div>
          <div>
            <p className="text-xs text-slate-400">Waiting for review</p>
            <p className="text-2xl font-semibold text-slate-50 mt-1">{summary.pending}</p>
          </div>
        </div>

        {summary.agents.length > 0 && (
          <div className="mb-6">
            <h3 className="text-xs text-slate-400 mb-2">
              How often the judge disagreed, per agent
            </h3>
            <ul className="space-y-2">
              {summary.agents.map((agent) => (
                <li key={agent.agent_name} className="text-sm">
                  <div className="flex items-center justify-between gap-3">
                    <span className="text-slate-200">
                      {agent.agent_name}
                      {agent.needs_attention && (
                        <span className="ml-2 text-xs text-amber-400">
                          looks overconfident
                        </span>
                      )}
                    </span>
                    <span className="text-xs text-slate-400">
                      {agent.disagree} of {agent.reviewed} ({percent(agent.disagreement_rate)})
                      {agent.avg_agent_confidence !== null &&
                        `, avg confidence ${agent.avg_agent_confidence.toFixed(2)}`}
                    </span>
                  </div>
                  <div className="h-1 mt-1.5 rounded bg-slate-800">
                    <div
                      className={`h-1 rounded ${
                        agent.needs_attention ? "bg-amber-400" : "bg-emerald-500"
                      }`}
                      style={{ width: percent(Math.min(agent.disagreement_rate, 1)) }}
                    />
                  </div>
                </li>
              ))}
            </ul>
          </div>
        )}

        {reviews.length > 0 && (
          <div>
            <h3 className="text-xs text-slate-400 mb-2">Recent reviews</h3>
            <ul className="space-y-2">
              {reviews.map((review) => {
                const style = review.judge_verdict
                  ? VERDICT_STYLE[review.judge_verdict]
                  : VERDICT_STYLE.unsure;
                return (
                  <li
                    key={review.id}
                    className="border border-slate-800 rounded-md p-3 text-sm"
                  >
                    <div className="flex items-center gap-2">
                      <span className={`h-1.5 w-1.5 rounded-full ${style.dot}`} />
                      <span className={`text-xs ${style.text}`}>{style.label}</span>
                      <span className="text-xs text-slate-500">{review.agent_name}</span>
                    </div>
                    {review.input_summary && (
                      <p className="text-slate-300 mt-1 truncate">{review.input_summary}</p>
                    )}
                    {review.judge_reason && (
                      <p className="text-xs text-slate-400 mt-1">{review.judge_reason}</p>
                    )}
                  </li>
                );
              })}
            </ul>
          </div>
        )}

        {summary.totals.reviewed === 0 && summary.pending === 0 && (
          <p className="text-sm text-slate-500">
            Nothing reviewed yet. Events the judge samples will show up here.
          </p>
        )}
      </>
    );
  }

  return (
    <section className="mt-6 border border-slate-800 rounded-lg p-5 bg-slate-900/40">
      <div className="flex items-start justify-between gap-4 mb-4">
        <div>
          <h2 className="text-sm font-medium text-slate-200">Judge review</h2>
          <p className="text-xs text-slate-500 mt-1 max-w-xl">
            A second model double-checks a sample of auto-approved decisions. When
            it disagrees, the decision lands in your review queue.
          </p>
        </div>
        <button
          onClick={handleRun}
          disabled={running || !summary?.judge_configured}
          className="text-xs bg-amber-500 hover:bg-amber-400 text-slate-950 font-medium rounded-md px-3 py-1.5 disabled:opacity-40 shrink-0"
        >
          {running ? "Reviewing..." : "Review sample now"}
        </button>
      </div>

      {message && <p className="text-xs text-slate-400 mb-4">{message}</p>}
      {body}
    </section>
  );
}
