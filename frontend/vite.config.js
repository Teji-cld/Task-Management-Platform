import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

// The app code only ever calls the relative path /api. During development the
// Vite server forwards /api to the backend, so the browser sees ONE origin
// (no CORS needed). In production, a reverse proxy does this job instead.
//
// DEV_PROXY_TARGET is read here, in the dev tooling only. It never enters the
// built JavaScript. Set it (in your shell or frontend/.env) if your backend is
// not on the default address below.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const backend = env.DEV_PROXY_TARGET || "http://127.0.0.1:8000";
  const proxy = { "/api": { target: backend, changeOrigin: true } };

  return {
    plugins: [react()],
    server: { port: 5173, proxy },
    preview: { port: 4173, proxy },
  };
});
