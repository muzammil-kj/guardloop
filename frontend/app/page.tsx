"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

const DEMO_EMAIL = "demo@guardloop.ai";
const DEMO_PASSWORD = "guardloop2026";

export default function LoginPage() {
  const [email, setEmail] = useState(DEMO_EMAIL);
  const [password, setPassword] = useState(DEMO_PASSWORD);
  const [error, setError] = useState("");
  const router = useRouter();

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (email === DEMO_EMAIL && password === DEMO_PASSWORD) {
      window.localStorage.setItem("guardloop_demo_session", "true");
      router.push("/dashboard");
    } else {
      setError("Use the pre-filled demo credentials shown below the form.");
    }
  }

  return (
    <main className="min-h-screen bg-slate-950 text-slate-100 flex items-center justify-center px-6">
      <div className="w-full max-w-sm">
        <div className="mb-8">
          <h1 className="text-2xl font-semibold tracking-tight text-slate-50">
            Guardloop
          </h1>
          <p className="mt-2 text-sm text-slate-400 leading-relaxed">
            A guardrail and observability layer for AI agents. Sign in to view
            live agent activity, flagged decisions, and cost tracking.
          </p>
        </div>

        <form
          onSubmit={handleSubmit}
          className="border border-slate-800 rounded-lg p-6 bg-slate-900/60"
        >
          <label className="block text-sm text-slate-300 mb-1.5">
            Email
          </label>
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="w-full rounded-md bg-slate-950 border border-slate-700 px-3 py-2 text-sm text-slate-100 mb-4 focus:outline-none focus:ring-2 focus:ring-amber-500"
          />

          <label className="block text-sm text-slate-300 mb-1.5">
            Password
          </label>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="w-full rounded-md bg-slate-950 border border-slate-700 px-3 py-2 text-sm text-slate-100 mb-4 focus:outline-none focus:ring-2 focus:ring-amber-500"
          />

          {error && (
            <p className="text-sm text-amber-400 mb-4">{error}</p>
          )}

          <button
            type="submit"
            className="w-full bg-amber-500 hover:bg-amber-400 text-slate-950 font-medium rounded-md py-2 text-sm transition-colors"
          >
            Sign in
          </button>
        </form>

        <p className="mt-4 text-xs text-slate-500">
          Demo credentials are pre-filled. This is a review build; no real
          account system is behind it.
        </p>
      </div>
    </main>
  );
}