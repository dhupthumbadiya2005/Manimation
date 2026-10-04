import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev: the FastAPI backend runs on :8000; the UI proxies API, media and WebSocket calls to it.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": { target: "http://127.0.0.1:8000", ws: true },
      "/media": "http://127.0.0.1:8000",
    },
  },
});
