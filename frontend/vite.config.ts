import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// base './' + HashRouter: the static build works under any subpath,
// including a GitHub Pages project URL, with no rebuild per host.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  base: "./",
  server: { port: 5173, host: "127.0.0.1" },
  preview: { port: 4173, host: "127.0.0.1" },
  build: {
    outDir: "dist",
    sourcemap: false,
    chunkSizeWarningLimit: 900,
  },
});
