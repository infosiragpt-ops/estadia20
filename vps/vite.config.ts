import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  root: new URL(".", import.meta.url).pathname,
  publicDir: new URL("../public", import.meta.url).pathname,
  plugins: [react()],
  build: {
    outDir: "public",
    emptyOutDir: true,
  },
});
