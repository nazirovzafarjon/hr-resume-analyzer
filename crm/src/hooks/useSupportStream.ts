import { useEffect, useRef, useState } from "react";
import { API_BASE_URL, type SessionKind } from "../services/apiClient";
import { getCandidateToken, getToken } from "../auth/tokenStorage";
import type { SupportEvent } from "../types/support";

const MIN_RETRY_MS = 2_000;
const MAX_RETRY_MS = 30_000;

type Options = {
  /** Stream path under the API base, e.g. "/support/stream". */
  path: string;
  session: SessionKind;
  enabled: boolean;
  onEvent: (event: SupportEvent) => void;
  /** Called every time the stream (re)connects: reload anything missed meanwhile. */
  onOpen?: () => void;
  /**
   * Called after the stream was refused with 401. Should make one ordinary
   * authenticated request, which refreshes the access token (or signs out).
   */
  onUnauthorized?: () => Promise<unknown>;
};

/**
 * Subscribe to the backend's support Server-Sent Events stream.
 *
 * EventSource cannot send an Authorization header, so the stream is read with
 * fetch + a stream reader and the bearer token stays out of the URL. The
 * connection is re-opened with exponential backoff whenever it ends (server
 * restart, the server's periodic recycle, network loss). `connected` is false
 * while it is down, so callers can fall back to polling.
 */
export function useSupportStream({ path, session, enabled, onEvent, onOpen, onUnauthorized }: Options) {
  const [connected, setConnected] = useState(false);
  const handlers = useRef({ onEvent, onOpen, onUnauthorized });
  handlers.current = { onEvent, onOpen, onUnauthorized };

  useEffect(() => {
    if (!enabled || typeof fetch === "undefined" || typeof TextDecoder === "undefined") return;
    const controller = new AbortController();
    const readToken = session === "candidate" ? getCandidateToken : getToken;
    let retryMs = MIN_RETRY_MS;
    let timer: ReturnType<typeof setTimeout> | undefined;

    function handleFrame(frame: string) {
      let event = "message";
      let data = "";
      for (const line of frame.split("\n")) {
        if (line.startsWith("event:")) event = line.slice(6).trim();
        else if (line.startsWith("data:")) data += line.slice(5).trim();
      }
      if (event === "ready") {
        retryMs = MIN_RETRY_MS;
        setConnected(true);
        handlers.current.onOpen?.();
      } else if (event === "support") {
        try {
          handlers.current.onEvent(JSON.parse(data) as SupportEvent);
        } catch {
          /* A malformed frame is ignored; the next refresh catches up. */
        }
      } else if (event === "unavailable") {
        // The server cannot reach Redis: back off and rely on polling.
        retryMs = MAX_RETRY_MS;
      }
    }

    async function connect() {
      if (controller.signal.aborted) return;
      try {
        const token = readToken();
        const response = await fetch(`${API_BASE_URL}${path}`, {
          headers: {
            Accept: "text/event-stream",
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
          },
          cache: "no-store",
          signal: controller.signal,
        });
        if (response.status === 401) {
          await handlers.current.onUnauthorized?.().catch(() => undefined);
        } else if (response.ok && response.body) {
          const reader = response.body.getReader();
          const decoder = new TextDecoder();
          let buffer = "";
          for (;;) {
            const { value, done } = await reader.read();
            if (done) break;
            buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, "\n");
            let boundary = buffer.indexOf("\n\n");
            while (boundary >= 0) {
              handleFrame(buffer.slice(0, boundary));
              buffer = buffer.slice(boundary + 2);
              boundary = buffer.indexOf("\n\n");
            }
          }
        }
      } catch {
        /* Network failure or abort: handled below. */
      }
      if (controller.signal.aborted) return;
      setConnected(false);
      timer = setTimeout(connect, retryMs);
      retryMs = Math.min(retryMs * 2, MAX_RETRY_MS);
    }

    void connect();
    return () => {
      controller.abort();
      if (timer) clearTimeout(timer);
      setConnected(false);
    };
  }, [enabled, path, session]);

  return { connected };
}
