import { createClient, SupabaseClient } from "@supabase/supabase-js";

// Public values only: the publishable/anon key is designed to be shipped to browsers.
const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL;
const SUPABASE_PUBLIC_KEY = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

let client: SupabaseClient | null = null;

/** Client for reviewer sign-in. Keeps the session so the access token can be read. */
export function getAuthClient(): SupabaseClient {
  if (!SUPABASE_URL || !SUPABASE_PUBLIC_KEY) {
    throw new Error("Reviewer sign-in is not configured for this dashboard.");
  }
  if (!client) {
    client = createClient(SUPABASE_URL, SUPABASE_PUBLIC_KEY, {
      auth: { persistSession: true, autoRefreshToken: true, storageKey: "guardloop-auth" },
    });
  }
  return client;
}