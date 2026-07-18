import { defineConfig } from "vite";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const rootDir = dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  root: rootDir,
  build: {
    outDir: resolve(rootDir, "../static"),
    emptyOutDir: true,
    rollupOptions: {
      input: {
        app: resolve(rootDir, "src/app.ts"),
      },
      output: {
        entryFileNames: "js/[name].js",
        chunkFileNames: "js/[name]-[hash].js",
        assetFileNames: "assets/[name]-[hash][extname]",
      },
    },
  },
  server: {
    port: 5173,
    proxy: {
      "/api": "http://127.0.0.1:5000",
      "/page": "http://127.0.0.1:5000",
      "/download": "http://127.0.0.1:5000",
      "/login": "http://127.0.0.1:5000",
      "/logout": "http://127.0.0.1:5000",
    },
  },
});
