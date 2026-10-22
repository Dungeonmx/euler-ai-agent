/*
  Saneado del texto que llega del LLM (o del visitante).

  El widget arma la respuesta del asistente con nodos de React, asi que React
  escapa el HTML y un `<script>` no se puede ejecutar. Este modulo es la red de
  seguridad: si manana alguien cambia el render a `dangerouslySetInnerHTML`, o
  mete un `innerHTML` por ahi, el texto ya llega limpio.

  Que saca:
    - los bloques que pueden ejecutar codigo (`<script>`, `<style>`, `<iframe>`,
      `<object>`, `<embed>`, `<svg>`, `<template>`, ...) con todo su contenido;
    - los tags HTML conocidos (`<img onerror=...>`, `<b>`, `<div>`, ...);
    - cualquier tag con manejador de evento (`onclick=`, `onerror=`, ...), aunque
      el nombre no sea un tag conocido;
    - los bloques de PHP (`<?php ... ?>`, `<?= ... ?>`) y los comentarios HTML.

  Lo que NO hace, a proposito: escapar los `<` sueltos ni los `&`. React ya
  escapa al pintar, y escapar dos veces terminaria mostrando `&lt;b&gt;` al
  visitante. Por eso un texto legitimo como "<Ctrl+C>" se deja como estaba.
*/

/*
  Los links solo pueden ser http o https. Cualquier otro esquema
  (`javascript:`, `data:`, `vbscript:`, `file:`) puede ejecutar codigo en el
  navegador del visitante con un solo click.
*/
const ESQUEMAS_PERMITIDOS = new Set(["http:", "https:"]);

/*
  Tags HTML conocidos. No hace falta la lista completa: con los que mas se
  usan en una respuesta (y con los que se puede colgar un script) alcanza.
*/
const TAGS_HTML = new Set([
  "a", "abbr", "address", "area", "article", "aside", "audio", "b", "base",
  "bdi", "bdo", "blockquote", "body", "br", "button", "canvas", "caption",
  "cite", "code", "col", "colgroup", "data", "datalist", "dd", "del", "details",
  "dfn", "dialog", "div", "dl", "dt", "em", "embed", "fieldset",
  "figcaption", "figure", "footer", "form", "h1", "h2", "h3", "h4", "h5", "h6",
  "head", "header", "hgroup", "hr", "html", "i", "iframe", "img", "input",
  "ins", "kbd", "label", "legend", "li", "link", "main", "map", "mark", "menu",
  "meta", "meter", "nav", "noscript", "object", "ol", "optgroup", "option",
  "output", "p", "param", "picture", "pre", "progress", "q", "rp", "rt", "ruby",
  "s", "samp", "script", "section", "select", "slot", "small", "source",
  "span", "strong", "style", "sub", "summary", "sup", "table", "tbody", "td",
  "template", "textarea", "tfoot", "th", "thead", "time", "title", "tr",
  "track", "u", "ul", "var", "video", "wbr",
]);

/* Bloques que se borran con todo su contenido: su texto es codigo, no respuesta. */
const BLOQUES = /<(script|style|iframe|object|embed|svg|math|template|noscript)\b[^>]*>[\s\S]*?<\/\s*\1\s*>/gi;

/* El mismo bloque pero sin cerrar: se borra hasta el final del texto. */
const BLOQUES_SIN_CIERRE = /<(script|style|iframe|object|embed|svg|math|template|noscript)\b[^>]*>[\s\S]*$/gi;

const COMENTARIOS = /<!--[\s\S]*?(?:-->|$)/g;
const PHP = /<\?[\s\S]*?(?:\?>|$)/g;

/* Cualquier cosa con forma de tag: `</?nombre ...>` */
const TAG = /<\/?([a-zA-Z][a-zA-Z0-9-]*)((?:"[^"]*"|'[^']*'|[^<>])*)>/g;

/* Un manejador de evento dentro de los atributos del tag. */
const MANEJADOR = /\bon[a-z]+\s*=/i;

/*
  Un href es seguro si el esquema es http o https.

  Se usa `new URL` a proposito: el parser del navegador normaliza el esquema
  (lo pasa a minusculas, saca tabs y saltos de linea), asi que "JaVaScRiPt:" o
  "java\tscript:" siguen cayendo en el mismo caso y quedan afuera.
*/
export const isSafeUrl = (url) => {
  const valor = String(url ?? "").trim();
  if (!valor) return false;

  try {
    const parsed = new URL(valor, "https://euler.invalid/");
    return ESQUEMAS_PERMITIDOS.has(parsed.protocol);
  } catch (error) {
    return false;
  }
};

/*
  Quita el markup del texto y deja solo lo que se puede mostrar.

  Devuelve el texto tal cual si no hay nada que sacar, para no tocar las
  respuestas normales.
*/
export const sanitizeText = (text) => {
  const original = String(text ?? "");
  if (!original) return "";

  let limpio = original;
  limpio = limpio.replace(COMENTARIOS, "");
  limpio = limpio.replace(PHP, "");
  limpio = limpio.replace(BLOQUES, "");
  limpio = limpio.replace(BLOQUES_SIN_CIERRE, "");
  limpio = limpio.replace(TAG, (tag, nombre, atributos = "") => {
    const etiqueta = String(nombre).toLowerCase();
    if (TAGS_HTML.has(etiqueta)) return "";
    if (MANEJADOR.test(atributos)) return "";
    // Elemento a medida (`<mi-widget>`): puede traer manejadores de evento, y
    // si se saca el de apertura hay que sacar el de cierre tambien.
    if (etiqueta.includes("-")) return "";
    return tag;
  });

  return limpio;
};
