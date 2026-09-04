import path from "node:path";
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
// The dev server proxies /api to the backend so the browser sees a single origin.
// That is what lets the session cookie be HttpOnly + SameSite=Lax with no CORS
// preflight and no token juggling in the client.
export default defineConfig({
    // vitest 2 ships its own (older) copy of vite, so the plugin type is
    // structurally identical but nominally different from the root vite 6 one.
    plugins: [react()],
    resolve: {
        alias: { "@": path.resolve(__dirname, "./src") },
    },
    server: {
        port: 5173,
        host: true,
        proxy: {
            "/api": {
                target: process.env.VITE_API_PROXY_TARGET ?? "http://localhost:8000",
                changeOrigin: true,
            },
        },
    },
    preview: { port: 5173, host: true },
    test: {
        globals: true,
        environment: "jsdom",
        setupFiles: ["./src/test/setup.ts"],
        css: false,
    },
});
