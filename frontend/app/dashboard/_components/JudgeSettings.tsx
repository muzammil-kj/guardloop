"use client";

import { useEffect, useState } from "react";

import { getJudgeSettings, updateJudgeSettings } from "@/lib/judgeApi";

export default function JudgeSettings() {
  const [enabled, setEnabled] = useState(false);
  const [samplePercent, setSamplePercent] = useState(20);
  const [configured, setConfigured] = useState(true);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");

  useEffect(() => {
    getJudgeSettings()
      .then((s) => {
        setEnabled(s.enabled);
        setSamplePercent(Math.round(s.sample_rate * 100));
        setConfigured(s.judge_configured);
      })
      .catch(() =>
        setMessage("Could not load judge settings. Has PHASE5_MIGRATION.sql been run?")
      )
      .finally(() => setLoading(false));
  }, []);

  async function handleSave() {
    setSaving(true);
    setMessage("");
    try {
      const saved = await updateJudgeSettings({
        enabled,
        sample_rate: samplePercent / 100,
      });
      setConfigured(saved.judge_configured);
      setMessage("Saved.");
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Could not save.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="max-w-2xl mt-12">
      <h2 className="text-lg font-semibold text-slate-50">Judge review</h2>
      <p className="text-sm text-slate-400 mt-1 mb-6">
        A second model re-checks a sample of decisions your agents were confident
        enough to auto-approve, to catch confident mistakes. When it disagrees,
        the decision is added to your review queue. It is a second opinion, not
        ground truth: it can be wrong too.
      </p>

      {loading ? (
        <p className="text-sm text-slate-500">Loading...</p>
      ) : (
        <div className="border border-slate-800 rounded-lg p-5 bg-slate-900/40">
          {!configured && (
            <p className="text-sm text-amber-400 mb-4">
              This server has no <code>GEMINI_API_KEY</code>, so the judge can&apos;t
              run yet. You can still save your settings.
            </p>
          )}

          <label className="flex items-center gap-3 mb-5 cursor-pointer">
            <input
              type="checkbox"
              checked={enabled}
              onChange={(e) => setEnabled(e.target.checked)}
              className="h-4 w-4 accent-amber-500"
            />
            <span className="text-sm text-slate-200">
              Review a sample of auto-approved decisions
            </span>
          </label>

          <label className="block text-xs text-slate-400 mb-1.5">
            Share of auto-approved events to review ({samplePercent}%)
          </label>
          <input
            type="range"
            min={5}
            max={100}
            step={5}
            value={samplePercent}
            disabled={!enabled}
            onChange={(e) => setSamplePercent(Number(e.target.value))}
            className="w-full mb-2 accent-amber-500 disabled:opacity-40"
          />
          <p className="text-xs text-slate-500 mb-5">
            Higher catches more mistakes but sends more data to the review model
            and uses more of its quota.
          </p>

          <p className="text-xs text-slate-500 mb-5 border-l-2 border-slate-700 pl-3">
            Data notice: for each reviewed event, the agent name, event type, and
            its input and output summaries are sent to Google&apos;s Gemini API.
            Don&apos;t enable this if those summaries contain data you aren&apos;t
            allowed to share with Google.
          </p>

          <div className="flex items-center gap-3">
            <button
              onClick={handleSave}
              disabled={saving}
              className="text-xs bg-amber-500 hover:bg-amber-400 text-slate-950 font-medium rounded-md px-3 py-1.5 disabled:opacity-50"
            >
              {saving ? "Saving..." : "Save"}
            </button>
            {message && <span className="text-xs text-slate-400">{message}</span>}
          </div>
        </div>
      )}
    </section>
  );
}
