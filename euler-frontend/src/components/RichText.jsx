/*
  Texto con formato para los mensajes del asistente.

  El LLM responde en Markdown: **negrita** para las palabras importantes y links
  cuando hace falta. Si eso se pinta como texto plano, el visitante ve los
  asteriscos crudos y las URLs sueltas que no se pueden tocar.

  Aca va un parser chico que convierte el Markdown de uso frecuente en nodos de
  React. Nada de `dangerouslySetInnerHTML`: el texto viene del LLM y se arma
  elemento por elemento, asi que no hay forma de que se inyecte HTML.

  Markdown que se entiende:
    **negrita**   -> <strong>
    *cursiva*     -> <em>
    [texto](url)  -> <a>
    https://...   -> <a>

  Lo que no se toca: los saltos de linea (los aporta `whitespace-pre-wrap` del
  globo) y las listas con guiones, que se muestran tal cual.

  Antes de parsear, el texto pasa por `sanitizeText` (ver `src/sanitize.js`):
  React ya escapa el HTML al pintar, pero el texto se limpia igual para que no
  quede markup en pantalla ni en el portapapeles. Los links, ademas, solo se
  convierten en `<a>` si el esquema es http o https: un `javascript:` en un href
  se ejecuta con un click.
*/

import { isSafeUrl, sanitizeText } from "../sanitize";

const LINK_STYLES = {
  assistant:
    "font-medium text-indigo-700 underline decoration-indigo-300 underline-offset-2 hover:text-indigo-800 hover:decoration-indigo-500 break-words",
  user: "font-medium text-white underline decoration-white/70 underline-offset-2 hover:decoration-white break-words",
};

const BOLD_STYLES = {
  assistant: "font-semibold text-gray-900",
  user: "font-semibold text-white",
};

// El regex se arma por llamada: con la flag `g` el `lastIndex` es compartido y
// dos renders seguidos se pisan.
//
// La URL de un link markdown puede tener un par de parentesis adentro
// ("alert(1)"), asi que se toma el grupo que los balancea en vez de cortar en
// el primer ")".
const URL_MARKDOWN = "[^()\\s]*(?:\\([^()]*\\)[^()\\s]*)*";

// La URL, con su par de parentesis de captura. Ojo: tiene que ser un grupo que
// capture, si no el `exec` no devuelve la URL y el link se arma con `undefined`.
const URL_CAPTURADA = `(${URL_MARKDOWN})`;

const tokenPattern = () =>
  new RegExp(
    `(\\*\\*[^*\\n]+\\*\\*|\\*[^*\\n]+\\*|\\[[^\\]\\n]+\\]\\(${URL_MARKDOWN}\\)|https?:\\/\\/[^\\s<>"']+)`,
    "g"
  );

// Grupo 1: el texto del link. Grupo 2: la URL.
const MARKDOWN_LINK = new RegExp(`^\\[([^\\]]+)\\]\\(${URL_CAPTURADA}\\)$`);

const renderToken = (token, variant, key) => {
  const enlace = MARKDOWN_LINK.exec(token);
  if (enlace) {
    // Un link con esquema raro (`javascript:`, `data:`) no se convierte en
    // `<a>`: se muestra solo el texto, sin link y sin la URL peligrosa.
    if (!isSafeUrl(enlace[2])) {
      return <span key={key}>{enlace[1]}</span>;
    }

    return (
      <a
        key={key}
        href={enlace[2]}
        target="_blank"
        rel="noopener noreferrer"
        className={LINK_STYLES[variant]}
      >
        {enlace[1]}
      </a>
    );
  }


  if (token.startsWith("**") && token.endsWith("**")) {
    return (
      <strong key={key} className={BOLD_STYLES[variant]}>
        {token.slice(2, -2)}
      </strong>
    );
  }

  if (token.startsWith("*") && token.endsWith("*")) {
    return (
      <em key={key} className="italic">
        {token.slice(1, -1)}
      </em>
    );
  }

  // URL suelta. Los signos de puntuacion del final ("...com." o "mas,") no
  // forman parte del link.
  const url = token.replace(/[.,;:!?]+$/, "");
  const cola = token.slice(url.length);

  if (!isSafeUrl(url)) {
    return <span key={key}>{token}</span>;
  }

  return (
    <span key={key}>
      <a
        href={url}
        target="_blank"
        rel="noopener noreferrer"
        className={LINK_STYLES[variant]}
      >
        {url}
      </a>
      {cola}
    </span>
  );
};

export const RichText = ({ text, variant = "assistant" }) => {
  if (!text) return null;

  const limpio = sanitizeText(text);
  if (!limpio) return null;

  const pattern = tokenPattern();
  const nodes = [];
  let lastIndex = 0;
  let match;

  while ((match = pattern.exec(limpio)) !== null) {
    if (match.index > lastIndex) {
      nodes.push(limpio.slice(lastIndex, match.index));
    }
    nodes.push(renderToken(match[0], variant, nodes.length));
    lastIndex = match.index + match[0].length;
  }

  if (lastIndex < limpio.length) nodes.push(limpio.slice(lastIndex));

  return nodes;
};

/*
  El texto tal como lo ve el visitante, para copiar.

  Se sacan los asteriscos de la negrita y los corchetes de los links, pero la
  URL se deja a la vista: al pegar en otro lado, el link tiene que seguir
  siendo utilizable.

  Tambien pasa por el saneado, para que al portapapeles no viaje markup.
*/
export const plainText = (text) =>
  sanitizeText(text)
    .replace(
      new RegExp(`\\[([^\\]]+)\\]\\(${URL_CAPTURADA}\\)`, "g"),
      (_, etiqueta, url) => (isSafeUrl(url) ? `${etiqueta} (${url})` : etiqueta)
    )
    .replace(/\*\*([^*\n]+)\*\*/g, "$1")
    .replace(/\*([^*\n]+)\*/g, "$1");
