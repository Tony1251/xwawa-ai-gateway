import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3001,
    proxy: {
      "/v1": "http://localhost:8800",
      "/health": "http://localhost:8800",
      "/metrics": "http://localhost:8800",
      "/admin": "http://localhost:8800",
    },
  },
});
