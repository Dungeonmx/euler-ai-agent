import { StrictMode } from "react";
import App from "./App";
import { announceWidgetReady } from "./config";
import { mountShadow } from "./mount";

/*
  Entry point del bundle completo (React + three.js).

  Este archivo NO se carga al entrar a la pagina: lo inyecta
  `euler-launcher.js` cuando el usuario toca el boton flotante.

  Se monta en un Shadow DOM para quedar completamente aislado del CSS del
  sitio anfitrion. Ver `src/mount.jsx`.
*/
mountShadow(
  "data-euler-chat",
  <StrictMode>
    <App />
  </StrictMode>
);

window.__EULER_CHAT_MOUNTED__ = true;

// Le avisa al launcher que ya puede desenchufarse de la pagina.
announceWidgetReady();
