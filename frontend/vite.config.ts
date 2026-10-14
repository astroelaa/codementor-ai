import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { VitePWA } from "vite-plugin-pwa";
import { defineConfig } from "vite";

// base '/codementor-ai/' + HashRouter: built assets resolve under the
// GitHub Pages project URL https://astroelaa.github.io/codementor-ai/.
export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
    VitePWA({
      // Do not auto-register: main.tsx registers explicitly so update and
      // offline states can show honest UI instead of silent swaps.
      injectRegister: null,
      strategies: "generateSW",
      registerType: "prompt",
      manifest: {
        name: "CodeMentor AI",
        short_name: "CodeMentor",
        description:
          "A Socratic programming mentor that teaches you to understand code.",
        theme_color: "#0A0A0F",
        background_color: "#0A0A0F",
        display: "standalone",
        scope: "/codementor-ai/",
        start_url: "/codementor-ai/#/",
        icons: [
          {
            src: "icons/icon-192.png",
            sizes: "192x192",
            type: "image/png",
          },
          {
            src: "icons/icon-512.png",
            sizes: "512x512",
            type: "image/png",
          },
          {
            src: "icons/maskable-512.png",
            sizes: "512x512",
            type: "image/png",
            purpose: "maskable",
          },
        ],
      },
      workbox: {
        // App shell is precached. API traffic is NEVER cached: no tokens,
        // no private conversations, no cross-user leaks through the cache.
        navigateFallback: "/codementor-ai/index.html",
        runtimeCaching: [
          {
            urlPattern: ({ url }) => url.pathname.startsWith("/api/"),
            handler: "NetworkOnly",
          },
          {
            urlPattern: /^https:\/\/fonts\.(googleapis|gstatic)\.com\/.*/i,
            handler: "CacheFirst",
            options: {
              cacheName: "fonts",
              expiration: { maxEntries: 10, maxAgeSeconds: 60 * 60 * 24 * 30 },
            },
          },
        ],
      },
      devOptions: { enabled: false },
    }),
  ],
  base: "/codementor-ai/",
  server: { port: 5173, host: "127.0.0.1" },
  preview: { port: 4173, host: "127.0.0.1" },
  build: {
    outDir: "dist",
    sourcemap: false,
    chunkSizeWarningLimit: 900,
  },
});
