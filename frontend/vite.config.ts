import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// base '/codementor-ai/' + HashRouter: built assets resolve under the
// GitHub Pages project URL https://astroelaa.github.io/codementor-ai/.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  base: "/codementor-ai/",
  server: { port: 5173, host: "127.0.0.1" },
  preview: { port: 4173, host: "127.0.0.1" },
  build: {
    outDir: "dist",
    sourcemap: false,
    chunkSizeWarningLimit: 900,
  },
});
