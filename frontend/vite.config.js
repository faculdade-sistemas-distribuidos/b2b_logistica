import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      "/api/logistica": {
        target: "http://localhost:5008",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api\/logistica/, ""),
      },
    },
  },
});
