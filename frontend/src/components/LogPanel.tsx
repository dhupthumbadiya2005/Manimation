import { useEffect, useRef } from "react";

export default function LogPanel({ lines, connected }: { lines: string[]; connected: boolean }) {
  const ref = useRef<HTMLPreElement>(null);
  useEffect(() => {
    const el = ref.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [lines]);

  return (
    <details className="panel log" open>
      <summary>
        Agent log <span className={`conn ${connected ? "on" : "off"}`}>{connected ? "live" : "reconnecting…"}</span>
      </summary>
      <pre ref={ref}>{lines.length ? lines.join("\n") : "Waiting for activity…"}</pre>
    </details>
  );
}
