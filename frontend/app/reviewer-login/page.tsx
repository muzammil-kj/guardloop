"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { getAuthClient } from "@/lib/supabaseAuth";

export default function ReviewerLoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      const { data, error: authError } = await getAuthClient().auth.signInWithPassword({
        email: email.trim(),
        password,
      });
      if (authError || !data.session) {
        setError("That email or password isn't right, or the email isn't confirmed yet.");
        return;
      }
      // The backend verifies this token with Supabase on every request.
      window.localStorage.setItem("guardloop_api_key", data.session.access_token);
      router.push("/review");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Sign-in is not available right now.");
    } finally {
      setBusy(false);
    }
  }

  const input =
    "w-full rounded-md bg-slate-950 border border-slate-700 px-3 py-2 text-sm text-slate-100 mb-4 focus:outline-none focus:ring-2 focus:ring-amber-500";

  return (
    <main className="min-h-screen bg-slate-950 text-slate-100 flex items-center justify-center px-6">
      <div className="w-full max-w-sm">
        <h1 className="text-2xl font-semibold text-slate-50">Reviewer sign-in</h1>
        <p className="mt-2 mb-6 text-sm text-slate-400">
          For team members who review escalations. Use the email your organization owner invited.
        </p>
        <form onSubmit={handleSubmit} className="border border-slate-800 rounded-lg p-6 bg-slate-900/60">
          <label className="block text-sm text-slate-300 mb-1.5">Email</label>
          <input type="email" autoComplete="email" value={email}
                 onChange={(e) => setEmail(e.target.value)} className={input} />
          <label className="block text-sm text-slate-300 mb-1.5">Password</label>
          <input type="password" autoComplete="current-password" value={password}
                 onChange={(e) => setPassword(e.target.value)} className={input} />
          {error && <p className="text-sm text-amber-400 mb-4">{error}</p>}
          <button type="submit" disabled={busy}
                  className="w-full bg-amber-500 hover:bg-amber-400 text-slate-950 font-medium rounded-md py-2 text-sm disabled:opacity-50">
            {busy ? "Signing in..." : "Sign in"}
          </button>
        </form>
        <p className="mt-4 text-xs text-slate-500">
          Owners sign in with an organization API key on the <Link href="/" className="text-amber-400">main page</Link>.
        </p>
      </div>
    </main>
  );
}
