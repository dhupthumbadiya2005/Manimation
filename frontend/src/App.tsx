import { useEffect, useState } from "react";
import { api } from "./api";
import HomePage from "./components/HomePage";
import ProjectPage from "./components/ProjectPage";
import type { Health } from "./types";

// Tiny hash router: "#/" -> home, "#/p/<id>" -> project.
function useRoute() {
  const [hash, setHash] = useState(location.hash);
  useEffect(() => {
    const onChange = () => setHash(location.hash);
    window.addEventListener("hashchange", onChange);
    return () => window.removeEventListener("hashchange", onChange);
  }, []);
  const match = hash.match(/^#\/p\/([\w.~-]+)$/);
  return match ? { page: "project" as const, id: match[1] } : { page: "home" as const };
}

export default function App() {
  const route = useRoute();
  const [health, setHealth] = useState<Health | null>(null);
  const [offline, setOffline] = useState(false);

  useEffect(() => {
    api.health().then(setHealth, () => setOffline(true));
  }, []);

  return (
    <div className="app">
      <header className="topbar">
        <a href="#/" className="brand">
          <span className="brand-mark" aria-hidden>
            <span className="dot blue" />
            <span className="dot yellow" />
          </span>
          MANImation <span className="brand-sub">Studio</span>
        </a>
        {health?.demo_mode && (
          <span className="pill demo" title="Agents answer from the tested cookbook; no Claude API calls are made.">
            Demo mode · no API calls
          </span>
        )}
        {health?.tts_voice && (
          <span className="pill voice" title="Narration voice (Deepgram Flux TTS)">
            Voice: {health.tts_voice.replace(/^flux-|-en$/g, "")}
          </span>
        )}
        {health && !health.demo_mode && !health.api_key_configured && (
          <span className="pill warn">No API key configured</span>
        )}
      </header>
      {offline && <div className="banner error">Cannot reach the backend. Start it with <code>uv run uvicorn app.main:app</code>.</div>}
      <main>{route.page === "project" ? <ProjectPage id={route.id} /> : <HomePage />}</main>
    </div>
  );
}
