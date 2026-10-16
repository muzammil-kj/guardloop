"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  getPolicies,
  setDefaultPolicy,
  setAgentPolicy,
  deleteAgentPolicy,
  listAlertChannels,
  createAlertChannel,
  testAlertChannel,
  deleteAlertChannel,
  Policy,
  AlertChannel,
} from "@/lib/api";

function PolicyEditor({
  title,
  description,
  initial,
  onSave,
  onDelete,
  saveLabel,
}: {
  title: string;
  description: string;
  initial: Policy | undefined;
  onSave: (threshold: number, hardEscalate: string[]) => Promise<void>;
  onDelete?: () => Promise<void>;
  saveLabel: string;
}) {
  const [threshold, setThreshold] = useState(
    initial?.confidence_threshold ?? 0.75
  );
  const [hardEscalateText, setHardEscalateText] = useState(
    (initial?.hard_escalate_event_types ?? []).join(", ")
  );
  const [saving, setSaving] = useState(false);
  const [savedMsg, setSavedMsg] = useState("");

  async function handleSave() {
    setSaving(true);
    setSavedMsg("");
    const types = hardEscalateText
      .split(",")
      .map((t) => t.trim())
      .filter(Boolean);
    try {
      await onSave(threshold, types);
      setSavedMsg("Saved.");
    } catch {
      setSavedMsg("Failed to save.");
    } finally {
      setSaving(false);
      setTimeout(() => setSavedMsg(""), 2500);
    }
  }

  return (
    <div className="border border-slate-800 rounded-lg p-5 bg-slate-900/40">
      <h3 className="text-sm font-medium text-slate-200">{title}</h3>
      <p className="text-xs text-slate-500 mt-1 mb-4">{description}</p>

      <label className="block text-xs text-slate-400 mb-1.5">
        Confidence threshold ({threshold.toFixed(2)})
      </label>
      <input
        type="range"
        min={0}
        max={1}
        step={0.01}
        value={threshold}
        onChange={(e) => setThreshold(Number(e.target.value))}
        className="w-full mb-4 accent-amber-500"
      />

      <label className="block text-xs text-slate-400 mb-1.5">
        Always escalate these event types (comma-separated)
      </label>
      <input
        type="text"
        placeholder="job_application, complaint"
        value={hardEscalateText}
        onChange={(e) => setHardEscalateText(e.target.value)}
        className="w-full rounded-md bg-slate-950 border border-slate-700 px-3 py-2 text-sm text-slate-100 mb-4 focus:outline-none focus:ring-2 focus:ring-amber-500"
      />

      <div className="flex items-center gap-3">
        <button
          onClick={handleSave}
          disabled={saving}
          className="text-xs bg-amber-500 hover:bg-amber-400 text-slate-950 font-medium rounded-md px-3 py-1.5 disabled:opacity-50"
        >
          {saving ? "Saving..." : saveLabel}
        </button>
        {onDelete && (
          <button
            onClick={onDelete}
            className="text-xs text-slate-400 hover:text-amber-400"
          >
            Remove override (fall back to default)
          </button>
        )}
        {savedMsg && <span className="text-xs text-slate-500">{savedMsg}</span>}
      </div>
    </div>
  );
}

function AlertChannelsSection() {
  const [channels, setChannels] = useState<AlertChannel[]>([]);
  const [loading, setLoading] = useState(true);
  const [channelType, setChannelType] = useState<"discord" | "slack">("discord");
  const [webhookUrl, setWebhookUrl] = useState("");
  const [queueThreshold, setQueueThreshold] = useState(10);
  const [dailyBudget, setDailyBudget] = useState(5);
  const [formError, setFormError] = useState("");
  const [saving, setSaving] = useState(false);
  const [testResult, setTestResult] = useState<Record<number, string>>({});

  async function reload() {
    setChannels(await listAlertChannels());
  }

  useEffect(() => {
    reload()
      .catch(() => setFormError("Could not load alert channels."))
      .finally(() => setLoading(false));
  }, []);

  async function handleAdd(e: React.FormEvent) {
    e.preventDefault();
    setFormError("");
    setSaving(true);
    try {
      await createAlertChannel({
        channel_type: channelType,
        webhook_url: webhookUrl.trim(),
        queue_depth_threshold: queueThreshold,
        daily_budget_usd: dailyBudget,
      });
      setWebhookUrl("");
      await reload();
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "Could not add channel.");
    } finally {
      setSaving(false);
    }
  }

  async function handleTest(id: number) {
    setTestResult((prev) => ({ ...prev, [id]: "Sending..." }));
    try {
      await testAlertChannel(id);
      setTestResult((prev) => ({ ...prev, [id]: "Test message sent." }));
    } catch (err) {
      setTestResult((prev) => ({
        ...prev,
        [id]: err instanceof Error ? err.message : "Test failed.",
      }));
    }
  }

  async function handleDelete(id: number) {
    await deleteAlertChannel(id);
    await reload();
  }

  return (
    <section className="max-w-2xl mt-12">
      <h2 className="text-lg font-semibold text-slate-50">Alerts</h2>
      <p className="text-sm text-slate-400 mt-1 mb-6">
        Get a Discord or Slack message when escalations pile up or your daily
        agent spend reaches its budget. Checks run every few minutes. Webhook
        URLs are stored on the server and are never shown again after saving.
      </p>

      {loading ? (
        <p className="text-sm text-slate-500">Loading alert channels...</p>
      ) : (
        <ul className="space-y-3 mb-6">
          {channels.length === 0 && (
            <li className="text-sm text-slate-500">No alert channels yet.</li>
          )}
          {channels.map((channel) => (
            <li
              key={channel.id}
              className="border border-slate-800 rounded-lg p-4 bg-slate-900/40"
            >
              <div className="flex items-start justify-between gap-4">
                <div>
                  <p className="text-sm text-slate-200 capitalize">
                    {channel.channel_type}{" "}
                    <span className="text-slate-500 normal-case">
                      {channel.webhook_hint}
                    </span>
                  </p>
                  <p className="text-xs text-slate-400 mt-1">
                    Alert at {channel.queue_depth_threshold} pending escalations,
                    or ${channel.daily_budget_usd.toFixed(2)} spent per day.
                  </p>
                </div>
                <div className="flex gap-3 shrink-0">
                  <button
                    onClick={() => handleTest(channel.id)}
                    className="text-xs text-amber-400 hover:text-amber-300"
                  >
                    Send test alert
                  </button>
                  <button
                    onClick={() => handleDelete(channel.id)}
                    className="text-xs text-slate-400 hover:text-slate-200"
                  >
                    Remove
                  </button>
                </div>
              </div>
              {testResult[channel.id] && (
                <p className="text-xs text-slate-400 mt-2">{testResult[channel.id]}</p>
              )}
            </li>
          ))}
        </ul>
      )}

      <form
        onSubmit={handleAdd}
        className="border border-dashed border-slate-700 rounded-lg p-5"
      >
        <h3 className="text-sm font-medium text-slate-200 mb-4">Add a channel</h3>

        <label className="block text-xs text-slate-400 mb-1.5">Service</label>
        <select
          value={channelType}
          onChange={(e) => setChannelType(e.target.value as "discord" | "slack")}
          className="w-full rounded-md bg-slate-950 border border-slate-700 px-3 py-2 text-sm text-slate-100 mb-4 focus:outline-none focus:ring-2 focus:ring-amber-500"
        >
          <option value="discord">Discord</option>
          <option value="slack">Slack</option>
        </select>

        <label className="block text-xs text-slate-400 mb-1.5">Webhook URL</label>
        <input
          type="password"
          autoComplete="off"
          placeholder={
            channelType === "discord"
              ? "https://discord.com/api/webhooks/..."
              : "https://hooks.slack.com/services/..."
          }
          value={webhookUrl}
          onChange={(e) => setWebhookUrl(e.target.value)}
          className="w-full rounded-md bg-slate-950 border border-slate-700 px-3 py-2 text-sm text-slate-100 mb-4 focus:outline-none focus:ring-2 focus:ring-amber-500"
        />

        <div className="grid grid-cols-2 gap-4 mb-4">
          <div>
            <label className="block text-xs text-slate-400 mb-1.5">
              Alert when pending escalations reach
            </label>
            <input
              type="number"
              min={1}
              value={queueThreshold}
              onChange={(e) => setQueueThreshold(Number(e.target.value))}
              className="w-full rounded-md bg-slate-950 border border-slate-700 px-3 py-2 text-sm text-slate-100 focus:outline-none focus:ring-2 focus:ring-amber-500"
            />
          </div>
          <div>
            <label className="block text-xs text-slate-400 mb-1.5">
              Daily budget (USD)
            </label>
            <input
              type="number"
              min={0.01}
              step={0.5}
              value={dailyBudget}
              onChange={(e) => setDailyBudget(Number(e.target.value))}
              className="w-full rounded-md bg-slate-950 border border-slate-700 px-3 py-2 text-sm text-slate-100 focus:outline-none focus:ring-2 focus:ring-amber-500"
            />
          </div>
        </div>

        {formError && <p className="text-sm text-amber-400 mb-4">{formError}</p>}

        <button
          type="submit"
          disabled={saving || !webhookUrl.trim()}
          className="text-xs bg-amber-500 hover:bg-amber-400 text-slate-950 font-medium rounded-md px-3 py-1.5 disabled:opacity-50"
        >
          {saving ? "Adding..." : "Add channel"}
        </button>
      </form>
    </section>
  );
}

export default function SettingsPage() {
  const router = useRouter();
  const [policies, setPolicies] = useState<Policy[]>([]);
  const [loading, setLoading] = useState(true);
  const [newAgentName, setNewAgentName] = useState("");
  const [showNewAgentForm, setShowNewAgentForm] = useState(false);

  useEffect(() => {
    if (!window.localStorage.getItem("guardloop_api_key")) {
      router.push("/");
      return;
    }
    load();
  }, []);

  async function load() {
    setLoading(true);
    const data = await getPolicies();
    setPolicies(data);
    setLoading(false);
  }

  const defaultPolicy = policies.find((p) => p.agent_name === null);
  const agentPolicies = policies.filter((p) => p.agent_name !== null);

  if (loading) {
    return (
      <main className="min-h-screen bg-slate-950 text-slate-400 flex items-center justify-center text-sm">
        Loading policies...
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-slate-950 text-slate-100 px-8 py-8">
      <header className="mb-8">
        <Link href="/dashboard" className="text-xs text-slate-500 hover:text-slate-300">
          ← Back to dashboard
        </Link>
        <h1 className="text-xl font-semibold text-slate-50 mt-2">
          Policy settings
        </h1>
        <p className="text-sm text-slate-400 mt-1">
          Control how confident an agent needs to be before Guardloop auto-approves
          it, and which event types always require a human, no matter how
          confident the model is.
        </p>
      </header>

      <section className="grid grid-cols-1 gap-6 max-w-2xl">
        <PolicyEditor
          title="Organization default"
          description="Applies to every agent that doesn't have its own override below."
          initial={defaultPolicy}
          saveLabel="Save default"
          onSave={async (threshold, types) => {
            await setDefaultPolicy({
              confidence_threshold: threshold,
              hard_escalate_event_types: types,
            });
            await load();
          }}
        />

        {agentPolicies.map((policy) => (
          <PolicyEditor
            key={policy.agent_name}
            title={policy.agent_name ?? ""}
            description="Per-agent override. Takes priority over the org default for this agent only."
            initial={policy}
            saveLabel="Save override"
            onSave={async (threshold, types) => {
              await setAgentPolicy(policy.agent_name as string, {
                confidence_threshold: threshold,
                hard_escalate_event_types: types,
              });
              await load();
            }}
            onDelete={async () => {
              await deleteAgentPolicy(policy.agent_name as string);
              await load();
            }}
          />
        ))}

        {showNewAgentForm ? (
          <div className="border border-dashed border-slate-700 rounded-lg p-5">
            <label className="block text-xs text-slate-400 mb-1.5">
              Agent name (must match the agent_name sent in /ingest calls)
            </label>
            <div className="flex gap-2">
              <input
                type="text"
                placeholder="email-triage-agent"
                value={newAgentName}
                onChange={(e) => setNewAgentName(e.target.value)}
                className="flex-1 rounded-md bg-slate-950 border border-slate-700 px-3 py-2 text-sm text-slate-100 focus:outline-none focus:ring-2 focus:ring-amber-500"
              />
              <button
                onClick={async () => {
                  if (!newAgentName.trim()) return;
                  await setAgentPolicy(newAgentName.trim(), {
                    confidence_threshold: 0.75,
                    hard_escalate_event_types: [],
                  });
                  setNewAgentName("");
                  setShowNewAgentForm(false);
                  await load();
                }}
                className="text-xs bg-amber-500 hover:bg-amber-400 text-slate-950 font-medium rounded-md px-3 py-1.5"
              >
                Add
              </button>
            </div>
          </div>
        ) : (
          <button
            onClick={() => setShowNewAgentForm(true)}
            className="text-sm text-slate-400 hover:text-amber-400 border border-dashed border-slate-700 rounded-lg py-3"
          >
            + Add a per-agent override
          </button>
        )}
      </section>

      <AlertChannelsSection />
    </main>
  );
}