"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { createOrganization } from "@/lib/api";

export default function LoginPage() {
  const [mode, setMode] = useState<"existing" | "new">("existing");
  const [apiKey, setApiKey] = useState("");
  const [orgName, setOrgName] = useState("");
  const [issuedKey, setIssuedKey] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const router = useRouter();

  function enterDashboard(key: string) {
    window.localStorage.setItem("guardloop_api_key", key);
    router.push("/dashboard");
  }

  async function handleCreateOrg(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const result = await createOrganization(orgName);
      setIssuedKey(result.api_key);
    } catch {
      setError("Could not create organization. Check that the backend is reachable.");
    } finally {
      setLoading(false);
    }
  }

  function handleUseExisting(e: React.FormEvent) {
    e.preventDefault();
    if (!apiKey.trim()) {
      setError("Enter your API key.");
      return;
    }
    enterDashboard(apiKey.trim());
  }

  if (issuedKey) {
    return (
      <main className="min-h-screen bg-slate-950 text-slate-100 flex items-center justify-center px-6">
        <div className="w-full max-w-md border border-amber-900/50 bg-amber-950/20 rounded-lg p-6">
          <h2 className="text-lg font-semibold text-amber-400 mb-2">
            Save your API key now
          </h2>
          <p className="text-sm text-slate-300 mb-4">
            This is shown only once. Your agents will use this key to report
            events to Guardloop.
          </p>
          <code className="block bg-slate-950 border border-slate-700 rounded-md p-3 text-sm text-emerald-400 break-all mb-4">
            {issuedKey}
          </code>
          <button
            onClick={() => enterDashboard(issuedKey)}
            className="w-full bg-amber-500 hover:bg-amber-400 text-slate-950 font-medium rounded-md py-2 text-sm transition-colors"
          >
            I've saved it, continue to dashboard
          </button>
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-slate-950 text-slate-100 flex items-center justify-center px-6">
      <div className="w-full max-w-sm">
        <div className="mb-8">
          <h1 className="text-2xl font-semibold tracking-tight text-slate-50">
            Guardloop
          </h1>
          <p className="mt-2 text-sm text-slate-400 leading-relaxed">
            A guardrail and observability layer for AI agents.
          </p>
        </div>

        <div className="flex gap-2 mb-5">
          <button
            onClick={() => setMode("existing")}
            className={`flex-1 text-sm rounded-md py-2 border ${
              mode === "existing"
                ? "border-amber-500 text-amber-400"
                : "border-slate-800 text-slate-500"
            }`}
          >
            Use API key
          </button>
          <button
            onClick={() => setMode("new")}
            className={`flex-1 text-sm rounded-md py-2 border ${
              mode === "new"
                ? "border-amber-500 text-amber-400"
                : "border-slate-800 text-slate-500"
            }`}
          >
            New organization
          </button>
        </div>

        {mode === "existing" ? (
          <form
            onSubmit={handleUseExisting}
            className="border border-slate-800 rounded-lg p-6 bg-slate-900/60"
          >
            <label className="block text-sm text-slate-300 mb-1.5">
              API key
            </label>
            <input
              type="password"
              placeholder="gl_live_..."
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              className="w-full rounded-md bg-slate-950 border border-slate-700 px-3 py-2 text-sm text-slate-100 mb-4 focus:outline-none focus:ring-2 focus:ring-amber-500"
            />
            {error && <p className="text-sm text-amber-400 mb-4">{error}</p>}
            <button
              type="submit"
              className="w-full bg-amber-500 hover:bg-amber-400 text-slate-950 font-medium rounded-md py-2 text-sm transition-colors"
            >
              Continue
            </button>
          </form>
        ) : (
          <form
            onSubmit={handleCreateOrg}
            className="border border-slate-800 rounded-lg p-6 bg-slate-900/60"
          >
            <label className="block text-sm text-slate-300 mb-1.5">
              Organization name
            </label>
            <input
              type="text"
              placeholder="Acme Inc."
              value={orgName}
              onChange={(e) => setOrgName(e.target.value)}
              className="w-full rounded-md bg-slate-950 border border-slate-700 px-3 py-2 text-sm text-slate-100 mb-4 focus:outline-none focus:ring-2 focus:ring-amber-500"
            />
            {error && <p className="text-sm text-amber-400 mb-4">{error}</p>}
            <button
              type="submit"
              disabled={loading}
              className="w-full bg-amber-500 hover:bg-amber-400 text-slate-950 font-medium rounded-md py-2 text-sm transition-colors disabled:opacity-50"
            >
              {loading ? "Creating..." : "Create organization"}
            </button>
          </form>
        )}
      </div>
    </main>
  );
}