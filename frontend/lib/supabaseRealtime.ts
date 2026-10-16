import { createClient, SupabaseClient } from "@supabase/supabase-js";

// These two values are PUBLIC by design (they ship to the browser). Use the
// project's anon / publishable key here, never the secret or service key.
// Access to data is enforced by row-level security plus the short-lived,
// organization-scoped token minted by the Guardloop API.
const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL;
const SUPABASE_PUBLIC_KEY = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

let client: SupabaseClient | null = null;

export function isRealtimeConfigured(): boolean {
  return Boolean(SUPABASE_URL && SUPABASE_PUBLIC_KEY);
}

export function getRealtimeClient(): SupabaseClient {
  if (!SUPABASE_URL || !SUPABASE_PUBLIC_KEY) {
    throw new Error("Supabase public URL/key are not configured.");
  }
  if (!client) {
    client = createClient(SUPABASE_URL, SUPABASE_PUBLIC_KEY, {
      // We only use Realtime; there is no Supabase Auth session to persist.
      auth: { persistSession: false, autoRefreshToken: false },
    });
  }
  return client;
}
