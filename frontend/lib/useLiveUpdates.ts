"use client";

import { useEffect, useRef, useState } from "react";
import type { RealtimeChannel } from "@supabase/supabase-js";

import { getRealtimeToken } from "@/lib/api";
import { getRealtimeClient, isRealtimeConfigured } from "@/lib/supabaseRealtime";

export type LiveStatus = "connecting" | "live" | "polling";

const POLL_INTERVAL_MS = 15_000;
const TOKEN_REFRESH_MS = 50 * 60 * 1000; // server tokens last 60 minutes
const DEBOUNCE_MS = 500;

/**
 * Calls `onChange` whenever agent_events or escalations change for this
 * organization. Uses Supabase Realtime when it is configured and connects;
 * otherwise falls back to refreshing every 15 seconds, so the dashboard
 * never silently goes stale. Returns which mode is active.
 */
export function useLiveUpdates(onChange: () => void): LiveStatus {
  const [status, setStatus] = useState<LiveStatus>("connecting");
  const onChangeRef = useRef(onChange);

  useEffect(() => {
    onChangeRef.current = onChange;
  });

  useEffect(() => {
    let cancelled = false;
    let channel: RealtimeChannel | null = null;
    let pollTimer: ReturnType<typeof setInterval> | null = null;
    let refreshTimer: ReturnType<typeof setInterval> | null = null;
    let debounceTimer: ReturnType<typeof setTimeout> | null = null;

    // One ingest touches several rows; collapse the burst into one refresh.
    const notify = () => {
      if (debounceTimer) clearTimeout(debounceTimer);
      debounceTimer = setTimeout(() => onChangeRef.current(), DEBOUNCE_MS);
    };

    const startPolling = () => {
      if (cancelled) return;
      setStatus("polling");
      if (!pollTimer) {
        pollTimer = setInterval(() => onChangeRef.current(), POLL_INTERVAL_MS);
      }
    };

    const stopPolling = () => {
      if (pollTimer) {
        clearInterval(pollTimer);
        pollTimer = null;
      }
    };

    async function connect() {
      if (!isRealtimeConfigured()) {
        startPolling();
        return;
      }

      try {
        const { token } = await getRealtimeToken();
        if (cancelled) return;

        const supabase = getRealtimeClient();
        supabase.realtime.setAuth(token);

        channel = supabase
          .channel("guardloop-live")
          .on(
            "postgres_changes",
            { event: "*", schema: "public", table: "agent_events" },
            notify
          )
          .on(
            "postgres_changes",
            { event: "*", schema: "public", table: "escalations" },
            notify
          )
          .subscribe((subscriptionStatus) => {
            if (cancelled) return;
            if (subscriptionStatus === "SUBSCRIBED") {
              stopPolling();
              setStatus("live");
            } else if (
              subscriptionStatus === "CHANNEL_ERROR" ||
              subscriptionStatus === "TIMED_OUT" ||
              subscriptionStatus === "CLOSED"
            ) {
              startPolling();
            }
          });

        // Renew the token before the current one expires.
        refreshTimer = setInterval(async () => {
          try {
            const fresh = await getRealtimeToken();
            supabase.realtime.setAuth(fresh.token);
          } catch {
            // If renewal fails, the channel will error and polling takes over.
          }
        }, TOKEN_REFRESH_MS);
      } catch {
        startPolling();
      }
    }

    connect();

    return () => {
      cancelled = true;
      stopPolling();
      if (refreshTimer) clearInterval(refreshTimer);
      if (debounceTimer) clearTimeout(debounceTimer);
      if (channel) {
        try {
          getRealtimeClient().removeChannel(channel);
        } catch {
          // Client was never created; nothing to clean up.
        }
      }
    };
  }, []);

  return status;
}
