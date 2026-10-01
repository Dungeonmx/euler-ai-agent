import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// https://vitejs.dev/config/
export default defineConfig(({ command }) => ({
  base: "./",
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      "/chat": "http://localhost:8000",
      "/audio": "http://localhost:8000",
    },
  },
  preview: {
    cors: true,
  },
  /*
    En el bundle de libreria, Vite deja las referencias a `process.env.*` sin
    resolver, y en el navegador eso es un ReferenceError que mata el widget
    entero. En `vite dev` no se define, para no romper React DevTools.
  */
  define:
    command === "build" ? { "process.env.NODE_ENV": JSON.stringify("production") } : {},
  /*
    Modo librería: en vez de una SPA con su index.html, se emite UN único
    archivo JavaScript autocontenido, listo para inyectar con un `<script src>`.

    El CSS no se emite aparte porque `src/main.jsx` lo importa con `?inline`
    (llega como string y se mete en el shadow root en `src/mount.jsx`).

    Este bundle pesa ~1,8 MB porque incluye three.js y el avatar 3D, y por eso
    NO se carga al entrar a la pagina: lo inyecta `public/iniciar.js` cuando el
    visitante toca el boton flotante.
  */
  build: {
    lib: {
      entry: "src/main.jsx",
      name: "EulerChat",
      formats: ["iife"],
      fileName: () => "euler-chat.js",
    },
    outDir: "dist",
    emptyOutDir: true,
    cssCodeSplit: false,
    target: "es2020",
  },
}));

