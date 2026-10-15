import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Build direto para a pasta servida pelo FastAPI (backend/static).
export default defineConfig({
  plugins: [react()],
  base: "./",
  build: { outDir: "../backend/static", emptyOutDir: true },
  server: { proxy: { "/api": "http://127.0.0.1:8000" } },
});
