/*
  Puente entre el snippet y el widget.

  `public/iniciar.js` (que no se compila, viaja tal cual) escribe estas
  variables en `window` ANTES de inyectar los bundles. Como el launcher y el
  widget son bundles separados, cada uno tiene su propia copia de este modulo:
  por eso el estado de "el usuario ya toco el boton" vive en `window` y no en
  una variable de modulo.
*/
const scope = typeof window !== "undefined" ? window : {};

const trimTrailingSlashes = (value) => String(value).replace(/\/+$/, "");

export const API_BASE = trimTrailingSlashes(scope.EULER_CHAT_API || "");

const ASSET_ROOT = scope.EULER_CHAT_BASE || "/";

/*
  Convierte una ruta relativa de public/ en una URL absoluta.

  Esto es lo que permite incrustar el widget en un sitio externo: sin esto,
  `images/wawasensei.png` se resolveria contra la URL de la pagina anfitriona
  (y daria 404), en vez de contra el servidor donde vive el widget.
*/
export const assetUrl = (path) =>
  `${trimTrailingSlashes(ASSET_ROOT)}/${String(path).replace(/^\/+/, "")}`;

const OPEN_EVENT = "euler:chat:open";
const CLOSE_EVENT = "euler:chat:close";
const READY_EVENT = "euler:chat:ready";
const STATE_EVENT = "euler:chat:state";
const OPEN_FLAG = "__EULER_CHAT_OPEN_REQUESTED__";
const OPEN_STATE_FLAG = "__EULER_CHAT_OPEN__";

export const requestOpen = () => {
  scope[OPEN_FLAG] = true;
  scope[OPEN_STATE_FLAG] = true;
  scope.dispatchEvent(new Event(OPEN_EVENT));
};

// El widget escucha este evento para cerrar el panel. Es el camino inverso del
// `OPEN_EVENT`: el snippet no puede tocar el estado de React, asi que el pedido
// viaja como un evento.
export const requestClose = () => {
  scope[OPEN_STATE_FLAG] = false;
  scope.dispatchEvent(new Event(CLOSE_EVENT));
};

// El widget lo consulta al montarse: si el usuario ya habia tocado el boton
// antes de que terminara de descargarse, el panel arranca abierto.
//
// OJO: esta funcion solo LEE la marca. Consumirla (ponerla en false) lo hace
// `clearOpenRequest`, en un efecto: como el inicializador de `useState` corre
// dos veces en modo estricto, un inicializador con efecto de onda lateral
// devolveria `true` en la primera pasada y `false` en la segunda, y el panel
// arrancaria cerrado durante el desarrollo.
export const consumeOpenRequest = () => scope[OPEN_FLAG] === true;

export const clearOpenRequest = () => {
  scope[OPEN_FLAG] = false;
};

// Si el widget ya esta en memoria, se abre al instante en vez de esperar
// a que termine de cargar.
export const onOpenRequest = (handler) => {
  scope.addEventListener(OPEN_EVENT, handler);
  return () => scope.removeEventListener(OPEN_EVENT, handler);
};

export const onCloseRequest = (handler) => {
  scope.addEventListener(CLOSE_EVENT, handler);
  return () => scope.removeEventListener(CLOSE_EVENT, handler);
};

/*
  El widget le avisa al snippet si el panel esta abierto o cerrado.

  Sin esto, el boton flotante no puede saber que tocarlo tiene que cerrar el
  chat en vez de abrirlo: son dos bundles distintos y no comparten memoria.
  El estado tambien queda en `window`, para que el snippet lo pueda consultar
  al instante del click (el evento llega despues).
*/
export const announceOpenState = (isOpen) => {
  scope[OPEN_STATE_FLAG] = isOpen;
  scope.dispatchEvent(new CustomEvent(STATE_EVENT, { detail: { isOpen } }));
};

// El widget avisa que monto, para que el boton del snippet deje de mostrar el
// estado de "cargando". El nombre del evento esta escrito a mano en
// `public/iniciar.js` tambien, porque ese archivo no se compila y no importa
// este modulo.
export const announceWidgetReady = () => {
  scope.dispatchEvent(new Event(READY_EVENT));
};
