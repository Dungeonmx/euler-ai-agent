import { useEffect, useRef, useState } from "react";
import { copyText } from "../clipboard";

/*
  Boton de copiar, en la esquina del globo del asistente.

  El texto del chat es seleccionable, pero seleccionar a mano un par de
  parrafos con el mouse es una molestia. Este boton copia la respuesta entera
  de un clic.

  Cuando copia, el icono se cambia por un tilde durante un par de segundos:
  si no, no hay forma de saber si salio bien (o si fallo).
*/
export const CopyButton = ({ text }) => {
  const [copiado, setCopiado] = useState(false);
  const timerRef = useRef(null);

  useEffect(() => () => clearTimeout(timerRef.current), []);

  const handleClick = async (event) => {
    // El boton esta sobre el texto: sin esto, el click selecciona el mensaje.
    event.stopPropagation();

    const ok = await copyText(text);
    if (!ok) return;

    setCopiado(true);
    clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => setCopiado(false), 2000);
  };

  return (
    <button
      type="button"
      onClick={handleClick}
      aria-label={copiado ? "Texto copiado" : "Copiar la respuesta"}
      title={copiado ? "Copiado" : "Copiar"}
      className="absolute -top-2 -right-2 flex h-6 w-6 items-center justify-center rounded-full border border-gray-300 bg-white text-gray-500 opacity-70 transition hover:bg-gray-100 hover:text-gray-800 hover:opacity-100 focus:opacity-100 cursor-pointer select-none"
    >
      {copiado ? (
        <svg
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2.5"
          strokeLinecap="round"
          strokeLinejoin="round"
          className="h-3.5 w-3.5"
        >
          <path d="M20 6 9 17l-5-5" />
        </svg>
      ) : (
        <svg
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          className="h-3.5 w-3.5"
        >
          <rect x="9" y="9" width="12" height="12" rx="2" />
          <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
        </svg>
      )}
    </button>
  );
};
