import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  // Fixed port: the backend's CORS allow-list and the UI tests both expect 5173.
  server: { port: 5173, strictPort: true },
  preview: { port: 4173, strictPort: true },
});
