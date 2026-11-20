/// <reference types="vitest/config" />
import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import path from "node:path";

// SearchHax frontend. The FastAPI exploration service stays authoritative.
// In development the browser talks to /api on this origin and Vite proxies it to
// SEARCHHAX_API_PROXY_TARGET, so the backend's CORS allow-list is untouched.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const target = env.SEARCHHAX_API_PROXY_TARGET || "http://127.0.0.1:8000";
  return {
    plugins: [react(), tailwindcss()],
    resolve: { alias: { "@": path.resolve(__dirname, "./src") } },
    server: {
      host: "127.0.0.1",
      port: Number(env.PORT || 5173),
      strictPort: true,
      proxy: { "/api": { target, changeOrigin: false } },
    },
    preview: { host: "127.0.0.1", port: Number(env.PORT || 4173), proxy: { "/api": { target } } },
    test: {
      environment: "jsdom",
      globals: true,
      include: ["src/**/*.test.{ts,tsx}"],
      setupFiles: ["src/test/setup.ts"],
    },
  };
});
