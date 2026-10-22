import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In dev, /api calls go to the FastAPI server, so there are no CORS headaches.
export default defineConfig({
  plugins: [react()],
  server: { port: 5173, proxy: { "/api": "http://localhost:8000" } },
});
