/*
  ============================================================================
  Euler Chat - snippet de incrustacion
  ============================================================================

  Este es el UNICO archivo que se agrega a una pagina externa. No requiere
  instalar nada, ni compilar nada, ni tocar el HTML o el CSS del sitio.

      <script src="https://www.ing.unlpam.edu.ar/euler/js/iniciar.js"
              data-api="https://api.ing.unlpam.edu.ar"></script>

  Que hace:
    1. Lee su propia URL para deducir donde esta hosted el resto del widget.
    2. Publica la configuracion en `window`.
    3. Dibuja el boton flotante con DOM plano (~3 KB, sin dependencias).

  Que NO hace, a proposito:
    No descarga el chatbot. Ese bundle (`euler-chat.js`, ~1,8 MB con three.js
    y el avatar 3D) se pide recien cuando el visitante toca el boton. Asi la
    pagina que lo incrusta no paga 1,8 MB de JavaScript que casi nadie va a
    usar. Por eso el boton esta en vanilla y no en React: React por si solo
    pesa mas que todo el resto del widget junto.

  El boton vive en este archivo y el panel de chat en `ChatWidget.jsx`. No se
  dibujan en los dos lados, porque entonces un cambio visual al boton habria
  que aplicarlo en dos lugares y tarde o temprano se desincronizan.

  Atributos opcionales:
    data-api   URL del backend de la API. Si se omite, el chat usa rutas
               relativas (solo util al probar en local con el proxy de Vite).
    data-base  Carpeta donde vive el resto de los archivos del widget. Si se
               omite se usa la misma carpeta que este archivo.

  Por que se puede cargar sin romper el sitio anfitrion:
    - Va con `async`, no bloquea el renderizado de la pagina.
    - Es idempotente: si el snippet aparece dos veces, solo se dibuja una vez.
    - El boton y el widget se montan en Shadow DOM, asi que ni el CSS del
      sitio ni el CSS del widget se pisan entre si.
*/
(function () {
  var LOADER_ID = "euler-chat-loader";
  var HOST_ID = "euler-chat-launcher";
  var WIDGET_ID = "euler-chat-widget";

  if (document.getElementById(LOADER_ID)) return;

  var current = document.currentScript;
  if (!current) return;

  current.id = LOADER_ID;

  // La carpeta del propio snippet, con barra final. Ej:
  // https://www.ing.unlpam.edu.ar/euler/js/iniciar.js
  //   -> https://www.ing.unlpam.edu.ar/euler/js/
  var ownFolder = current.src.replace(/[^/]*$/, "");

  var base = current.getAttribute("data-base") || ownFolder;
  if (base.charAt(base.length - 1) !== "/") base += "/";

  // Se publica antes que nada: el widget lo lee en el momento de evaluarse.
  window.EULER_CHAT_API = current.getAttribute("data-api") || "";
  window.EULER_CHAT_BASE = base;

  var OPEN_EVENT = "euler:chat:open";
  var READY_EVENT = "euler:chat:ready";

  function loadWidget() {
    if (document.getElementById(WIDGET_ID)) return;
    var script = document.createElement("script");
    script.id = WIDGET_ID;
    script.src = base + "euler-chat.js";
    script.async = true;
    (document.head || document.documentElement).appendChild(script);
  }

  /*
    CSS del boton, a mano. Va dentro del shadow root, asi que no le afecta el
    CSS de la pagina ni al reves. Equivale a las clases de Tailwind que usaba
    antes en ChatWidget.jsx; si se cambia el diseno, se cambia aca y en el
    atributo `src` de la imagen de mas abajo.
  */
  var CSS = [
    ":host{all:initial;display:block}",
    "button{all:unset;box-sizing:border-box;position:fixed;right:1.5rem;bottom:1.5rem;",
    "width:3rem;height:3rem;border-radius:9999px;cursor:pointer;",
    "background:linear-gradient(to bottom right,#6366f1,#ec4899);",
    "box-shadow:0 0 0 4px rgba(255,255,255,.8),0 10px 15px -3px rgba(0,0,0,.1),",
    "0 4px 6px -4px rgba(0,0,0,.1);",
    "transition:transform .15s ease}",
    "button:hover{transform:scale(1.05)}",
    "button:focus-visible{outline:2px solid #6366f1;outline-offset:2px}",
    "button[data-loading=true]{transform:none;cursor:progress}",
    "img{display:block;width:100%;height:100%;border-radius:9999px;object-fit:cover}",
    "i{position:absolute;right:-2px;top:-2px;width:12px;height:12px;",
    "border-radius:9999px;border:2px solid #fff;background:#4ade80}",
    "button[data-loading=true]>i{background:#fcd34d}",
  ].join("");

  function build() {
    var host = document.createElement("div");
    host.id = HOST_ID;

    // Estilos inline: ganan contra cualquier selector de la pagina anfitriona.
    host.style.cssText =
      "all:initial;position:fixed;left:0;top:0;width:0;height:0;z-index:2147483000";

    var shadow = host.attachShadow({ mode: "open" });

    var style = document.createElement("style");
    style.textContent = CSS;
    shadow.appendChild(style);

    var button = document.createElement("button");
    button.type = "button";
    button.setAttribute("aria-label", "Abrir el chat de Euler");

    var img = document.createElement("img");
    img.src = base + "images/wawasensei.png";
    img.alt = "";
    button.appendChild(img);

    // El puntito de "en linea", arriba a la derecha.
    var dot = document.createElement("i");
    button.appendChild(dot);

    function setLoading(state) {
      button.setAttribute("data-loading", state ? "true" : "false");
      button.setAttribute("aria-busy", state ? "true" : "false");
    }

    function open() {
      // Se marca antes de inyectar, para que el widget arranque con el panel
      // ya abierto en vez de aparecer el boton y un instante despues el panel.
      window.__EULER_CHAT_OPEN_REQUESTED__ = true;
      window.dispatchEvent(new Event(OPEN_EVENT));

      if (window.__EULER_CHAT_MOUNTED__) return;

      setLoading(true);
      loadWidget();
    }

    // Si el widget termino de montar, el boton vuelve a su estado normal.
    window.addEventListener(READY_EVENT, function () {
      setLoading(false);
    });

    button.addEventListener("click", open);

    shadow.appendChild(button);
    (document.body || document.documentElement).appendChild(host);
  }

  if (document.body) build();
  else document.addEventListener("DOMContentLoaded", build);

  // API para que el sitio pueda controlarlo (p. ej. abrirlo desde un boton
  // propio sin mostrar el flotante).
  window.EulerChat = window.EulerChat || {};
  window.EulerChat.open = function () {
    window.__EULER_CHAT_OPEN_REQUESTED__ = true;
    window.dispatchEvent(new Event(OPEN_EVENT));
    loadWidget();
  };
})();
