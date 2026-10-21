import react from "@vitejs/plugin-react";
import { defineConfig, loadEnv, type Plugin } from "vite";

/** Writes /version.json with the git commit being built, so CI can tell when a new
 *  deploy is live. Vercel provides VERCEL_GIT_COMMIT_SHA at build time; locally it's "dev". */
function versionFile(commit: string): Plugin {
  return {
    name: "crashcart-version-file",
    generateBundle() {
      this.emitFile({ type: "asset", fileName: "version.json", source: JSON.stringify({ commit }) + "\n" });
    },
  };
}

export default defineConfig(({ mode }) => {
  // Third argument = which environment variable names to read ("" prefix would read all).
  const env = loadEnv(mode, ".", ["VERCEL_GIT_COMMIT_SHA"]);
  return {
    plugins: [react(), versionFile(env.VERCEL_GIT_COMMIT_SHA || "dev")],
    // Fixed port: the backend's CORS allow-list and the UI tests both expect 5173.
    server: { port: 5173, strictPort: true },
    preview: { port: 4173, strictPort: true },
  };
});
