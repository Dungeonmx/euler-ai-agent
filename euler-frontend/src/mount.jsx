import React from "react";
import ReactDOM from "react-dom/client";
import widgetCss from "./index.css?inline";

/*
  Monta una app de React dentro de un Shadow DOM.

  El Shadow DOM es lo que permite incrustar el widget en cualquier sitio: las
  reglas de CSS de la pagina anfitriona no alcanzan a lo que hay adentro, y las
  reglas del widget no salen. Sin esto, un `* { box-sizing }` o un
  `button { font-family }` del sitio anfitrion deformaria el chat.

  Devuelve el elemento host, para poder quitarlo de la pagina si hace falta.
*/
export function mountShadow(marker, element) {
  const host = document.createElement("div");
  host.setAttribute(marker, "");

  // Estilos INLINE a proposito: ganan contra cualquier selector de la pagina
  // anfitriona, que no tendria por que conocer la existencia de este div.
  //
  // La geometria va acá (fixed, sin tamaño, z-index al tope) porque tiene que
  // sobrevivir al CSS de la pagina. La tipografia y el reset de herencia van
  // en index.css, para que el reset de la pagina no gane contra ellos.
  host.style.cssText = [
    "position:fixed",
    "left:0",
    "top:0",
    "width:0",
    "height:0",
    "z-index:2147483000",
  ].join(";");

  const shadow = host.attachShadow({ mode: "open" });

  // index.css se importa con `?inline`, asi que llega como string y se inyecta
  // aca. Por eso el build no emite ningun archivo .css suelto.
  const style = document.createElement("style");
  style.textContent = widgetCss;
  shadow.appendChild(style);

  const root = document.createElement("div");
  shadow.appendChild(root);

  (document.body || document.documentElement).appendChild(host);

  ReactDOM.createRoot(root).render(element);

  return host;
}

export const removeHost = (host) => {
  if (host && host.isConnected) host.remove();
};
