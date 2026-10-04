import { useEffect, useRef, useState } from "react";
import type { PipelineEvent } from "./types";

/**
 * Live pipeline log for one project over a WebSocket. Calls `onChange` (throttled)
 * whenever the backend reports progress, so the caller can refetch project state.
 * Reconnects automatically; the server replays recent history on connect.
 */
export function useProjectEvents(projectId: string, onChange: () => void) {
  const [lines, setLines] = useState<string[]>([]);
  const [connected, setConnected] = useState(false);
  const onChangeRef = useRef(onChange);
  onChangeRef.current = onChange;

  useEffect(() => {
    let socket: WebSocket | null = null;
    let retry: number | undefined;
    let throttle: number | undefined;
    let closed = false;

    const notify = () => {
      if (throttle !== undefined) return;
      throttle = window.setTimeout(() => {
        throttle = undefined;
        onChangeRef.current();
      }, 400);
    };

    const connect = () => {
      const proto = location.protocol === "https:" ? "wss" : "ws";
      socket = new WebSocket(`${proto}://${location.host}/api/projects/${projectId}/events`);
      socket.onopen = () => setConnected(true);
      socket.onclose = () => {
        setConnected(false);
        if (!closed) retry = window.setTimeout(connect, 2000);
      };
      socket.onmessage = (msg) => {
        const data = JSON.parse(msg.data) as PipelineEvent | { type: "history"; events: PipelineEvent[] };
        if (data.type === "history") {
          setLines(data.events.flatMap((e) => (e.type === "log" ? [e.line] : [])));
        } else if (data.type === "log") {
          setLines((prev) => [...prev.slice(-500), data.line]);
          notify();
        } else if (data.type === "state") {
          onChangeRef.current();
        }
      };
    };

    connect();
    return () => {
      closed = true;
      window.clearTimeout(retry);
      window.clearTimeout(throttle);
      socket?.close();
    };
  }, [projectId]);

  return { lines, connected };
}
