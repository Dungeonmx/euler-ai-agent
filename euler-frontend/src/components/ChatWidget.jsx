import { useEffect, useRef, useState } from "react";
import { lipsyncManager } from "../App";
import { API_BASE, assetUrl, consumeOpenRequest, onOpenRequest } from "../config";

/*
  El panel de chat. El boton flotante NO se dibuja aca: lo dibuja
  `public/iniciar.js`, que es el archivo que se incrusta en la pagina
  anfitriona. Si se dibujara en los dos lados, un cambio visual al boton
  habria que aplicarlo en dos lugares y se desincronizarian.

  ATENCION con los degradados: van como `bg-[linear-gradient(...)]` con los
  colores escritos a mano, y no como `bg-linear-to-r from-indigo-500 to-pink-500`.

  La razon: las utilidades de gradiente de Tailwind v4 se apoyan en
  `@property` para componer los color stops. Dentro de un Shadow DOM esas
  declaraciones no se aplican, `--tw-gradient-stops` queda invalido y el
  `background-image` termina computando en `none`: el degradado desaparece
  sin ningun error en consola. Verificado en Chromium.

  Como el Shadow DOM es justamente lo que hace que el widget se pueda
  incrustar en cualquier sitio, no se pueden usar las utilidades de gradiente
  de Tailwind. Si alguna vez se actualiza Tailwind, hay que volver a probar esto.
*/
const AVATAR_SRC = assetUrl("images/robot.svg");

/*
  Avisos para cuando algo falla.

  Van escritos para una persona que abrio un chat de la facultad, no para un
  log: a nadie le sirve ver "HTTP 500" o "Failed to fetch". Se distinguen tres
  casos porque son tres situaciones distintas desde el lado del visitante:

    AVISO_TIMEOUT   el sistema esta lento, es transitorio y el usuario no hizo
                    nada mal.
    AVISO_SERVIDOR  fallo de nuestro lado; no vamos a mostrarle el detalle.
    AVISO_CONEXION  probablemente su internet, algo que si puede revisar.

  El detalle tecnico igual se consola con `console.error`, para depurar sin
  ensuciar la conversacion.
*/
const AVISO_TIMEOUT =
  "Perdón, estoy tardando demasiado en pensar esto. Ya estoy trabajando para solucionarlo, probá de nuevo en un momento.";
const AVISO_SERVIDOR =
  "Uy, algo falló de mi lado. Ya lo estoy revisando. Probá de nuevo en un ratito.";
const AVISO_CONEXION =
  "No pude conectarme. Revisá tu conexión a internet y probá de nuevo.";

/*
  Si el backend no contesta en este tiempo, el front corta la peticion el mismo
  modo en que lo haria el usuario. Sin esto, si el LLM se cuelga, los tres
  puntitos quedan girando para siempre y el input se queda bloqueado: no hay
  forma de recuperarse sin recargar la pagina.
*/
const TIMEOUT_MS = 50000;

export const ChatWidget = () => {
  const [isOpen, setIsOpen] = useState(consumeOpenRequest);
  const [messages, setMessages] = useState([]);
  const [inputValue, setInputValue] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const scrollRef = useRef(null);
  const audioRef = useRef(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, isLoading]);

  // Si el widget ya esta en memoria y el snippet (o el sitio) pide abrirlo, se
  // abre al instante sin volver a descargarlo.
  useEffect(() => onOpenRequest(() => setIsOpen(true)), []);

  const playAudio = (audioUrl) => {
    if (!audioRef.current) return;
    lipsyncManager.connectAudio(audioRef.current);
    audioRef.current.src = audioUrl;
    audioRef.current.play().catch(() => {});
  };

  const sendMessage = async () => {
    if (lipsyncManager.audioContext?.state === "suspended") {
      lipsyncManager.audioContext.resume();
    }
    const text = inputValue.trim();
    if (!text || isLoading) return;

    const userMessage = { role: "user", content: text };
    const newMessages = [...messages, userMessage];
    setMessages(newMessages);
    setInputValue("");
    setIsLoading(true);
    const assistantMsgIndex = newMessages.length;
    setMessages((prev) => [...prev, { role: "assistant", content: "" }]);

    let accumulatedText = "";

    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);
    // Para poder elegir el aviso despues: si llego la respuesta pero venia mal,
    // el problema no fue la conexion.
    let llegoRespuesta = false;

    try {
      const response = await fetch(`${API_BASE}/chat/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ messages: newMessages }),
        signal: controller.signal,
      });
      llegoRespuesta = true;

      // /chat/stream responde text/event-stream, no JSON. Parsear el cuerpo con
      // response.json() consume el stream entero y falla con "Unexpected
      // character at line 1", porque el cuerpo empieza con "event:".
      if (!response.ok) {
        setMessages((prev) => {
          const updated = [...prev];
          updated[assistantMsgIndex] = {
            role: "assistant",
            content: AVISO_SERVIDOR,
          };
          return updated;
        });
        return;
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder("utf-8");
      let buffer = "";

      // El estado del SSE (evento y datos) tiene que sobrevivir entre chunks:
      // un evento puede quedar partido entre dos lecturas del reader.
      let currentEvent = null;
      let currentData = [];

      const processEvent = () => {
        const data = currentData.join("\n");

        if (currentEvent === "text" && data) {
          accumulatedText += data;
          setMessages((prev) => {
            const updated = [...prev];
            updated[assistantMsgIndex] = {
              role: "assistant",
              content: accumulatedText,
            };
            return updated;
          });
        } else if (currentEvent === "final_text" && data) {
          // El backend manda el mensaje final del LLM, que tiene los espacios
          // correctos. Reemplaza lo acumulado por tokens sin agregar otro globo.
          accumulatedText = data;
          setMessages((prev) => {
            const updated = [...prev];
            updated[assistantMsgIndex] = {
              role: "assistant",
              content: accumulatedText,
            };
            return updated;
          });
          // El texto ya esta completo: el tiempo restante es solo el TTS.
          // No abortar la conexion mientras se genera el audio.
          clearTimeout(timer);
        } else if (currentEvent === "audio" && data) {
          // El backend emite `audio` recien despues de escribir el archivo,
          // asi que no hace falta hacer polling.
          playAudio(`${API_BASE}${data.trim()}`);
        } else if (currentEvent === "error") {
          console.error("El backend reporto un error en el stream");
          // Si ya hay texto, no borrarlo por un fallo de audio.
          if (!accumulatedText) {
            setMessages((prev) => {
              const updated = [...prev];
              updated[assistantMsgIndex] = {
                role: "assistant",
                content: AVISO_SERVIDOR,
              };
              return updated;
            });
          }
        } else if (currentEvent === "done") {
          setIsLoading(false);
        }

        currentEvent = null;
        currentData = [];
      };

      const handleLine = (rawLine) => {
        if (rawLine.endsWith("\r")) rawLine = rawLine.slice(0, -1);

        if (rawLine === "") {
          processEvent();
          return;
        }
        if (rawLine.startsWith(":")) return;

        const colon = rawLine.indexOf(":");
        const field = colon === -1 ? rawLine : rawLine.slice(0, colon);
        let fieldValue = colon === -1 ? "" : rawLine.slice(colon + 1);
        if (fieldValue.startsWith(" ")) fieldValue = fieldValue.slice(1);

        if (field === "event") currentEvent = fieldValue;
        else if (field === "data") currentData.push(fieldValue);
      };

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop();

        for (const line of lines) handleLine(line);
      }

      // Si el backend cierra sin la linea en blanco final, no perder el evento.
      if (buffer) handleLine(buffer);
      if (currentData.length > 0) processEvent();

    } catch (error) {
      console.error("Chat error:", error);

      // `AbortError` con esta forma solo lo dispara nuestro `setTimeout`, o sea
      // que es un timeout. Si llego la respuesta pero algo fallo despues, el
      // problema fue del servidor; si no llego nada, de la conexion.
      const porTiempo = error?.name === "AbortError";
      const aviso = porTiempo
        ? AVISO_TIMEOUT
        : llegoRespuesta
          ? AVISO_SERVIDOR
          : AVISO_CONEXION;

      // Si ya llego texto (por ejemplo, fallo solo el audio), no borrarlo.
      if (!accumulatedText) {
        // Reemplaza el placeholder; no agrega una segunda burbuja de asistente.
        setMessages((prev) => {
          const updated = [...prev];
          updated[assistantMsgIndex] = { role: "assistant", content: aviso };
          return updated;
        });
      }
    } finally {
      clearTimeout(timer);
      setIsLoading(false);
    }
  };

  const clearChat = () => {
    setMessages([]);
  };

  const closeIcon = (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      className="h-4 w-4"
    >
      <path d="M18 6 6 18M6 6l12 12" />
    </svg>
  );

  const sendIcon = (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className="h-4 w-4"
    >
      <path d="M22 2 11 13M22 2l-7 20-4-9-9-4Z" />
    </svg>
  );

  const trashIcon = (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      className="h-4 w-4"
    >
      <path d="M3 6h18M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2m3 0v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6" />
    </svg>
  );

  return (
    <>
      <audio ref={audioRef} className="hidden" crossOrigin="anonymous" />

       {isOpen && (
         <div className="animate-pop-in fixed z-50 flex flex-col overflow-hidden border border-gray-200/70 bg-white shadow-2xl bottom-0 right-0 h-[100dvh] w-full rounded-none sm:bottom-24 sm:right-6 sm:h-[min(36rem,calc(100dvh-8rem))] sm:w-[min(22rem,calc(100vw-3rem))] sm:rounded-2xl">
          <header className="flex items-center gap-3 bg-[linear-gradient(to_right,#6366f1,#ec4899)] px-4 py-3">
            <img
              src={AVATAR_SRC}
              alt="Avatar de Euler"
              className="h-9 w-9 rounded-full border-2 border-white/80 object-cover shadow"
            />
            <div className="flex-1">
              <h2 className="text-sm font-semibold leading-tight text-white">
                Euler
              </h2>
              <p className="flex items-center gap-1.5 text-xs text-white/80">
                <span className="inline-block h-1.5 w-1.5 rounded-full bg-green-300" />
                En línea
              </p>
            </div>
            <button
              className="flex h-8 w-8 items-center justify-center rounded-full text-white/80 transition-colors hover:bg-white/20 cursor-pointer"
              aria-label="Cerrar chat"
              onClick={() => setIsOpen(false)}
            >
              {closeIcon}
            </button>
          </header>

          <div className="relative h-40 bg-[radial-gradient(circle_at_top,#a78bfa,#6366f1_55%,#4f46e5)] flex items-center justify-center">
            <img
              src={AVATAR_SRC}
              alt="Avatar de Euler"
              className="h-36 w-36 drop-shadow-[0_6px_16px_rgba(15,23,42,0.25)]"
            />
          </div>

          <div
            ref={scrollRef}
            className="flex-1 space-y-2.5 overflow-y-auto bg-gray-50 px-3 py-3"
          >
            {messages.length === 0 && (
              <div className="flex flex-col items-center gap-1.5 pt-6 text-center">
                <p className="text-sm text-gray-500">
                  ¡Hola! Soy Euler, tu asistente virtual.
                </p>
                <p className="text-xs text-gray-400">
                  Escribe un mensaje para comenzar.
                </p>
              </div>
            )}
            {messages.map((msg, index) => (
              <div
                key={index}
                className={`flex ${
                  msg.role === "user" ? "justify-end" : "justify-start"
                }`}
              >
                <div
                  className={`max-w-[80%] rounded-2xl px-3 py-2 text-[13px] leading-snug whitespace-pre-wrap ${
                    msg.role === "user"
                      ? "rounded-br-md bg-[linear-gradient(to_right,#6366f1,#8b5cf6)] text-white shadow-sm"
                      : "rounded-bl-md border border-gray-200 bg-white text-gray-800 shadow-sm"
                  }`}
                >
                  {msg.content}
                </div>
              </div>
            ))}
            {isLoading && (
              <div className="flex items-center justify-start gap-1 py-1">
                <span className="flex items-center gap-1 rounded-full bg-white px-3 py-2.5 shadow-sm">
                  <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-gray-400 [animation-delay:0ms]" />
                  <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-gray-400 [animation-delay:150ms]" />
                  <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-gray-400 [animation-delay:300ms]" />
                </span>
              </div>
            )}
          </div>

          <div className="border-t border-gray-200 bg-white px-3 py-3">
            <form
              className="flex items-center gap-2"
              onSubmit={(e) => {
                e.preventDefault();
                sendMessage();
              }}
            >
              <button
                type="button"
                className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-gray-400 transition-colors hover:bg-gray-100 hover:text-gray-600 cursor-pointer"
                aria-label="Borrar conversación"
                onClick={clearChat}
              >
                {trashIcon}
              </button>
              <input
                type="text"
                className="h-9 min-w-0 flex-1 rounded-full border border-gray-200 bg-gray-100 px-4 text-sm text-gray-900 placeholder-gray-400"
                placeholder="Escribe tu mensaje..."
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                disabled={isLoading}
              />
              <button
                type="submit"
                className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-[linear-gradient(to_right,#6366f1,#8b5cf6)] text-white shadow transition-transform hover:scale-105 disabled:opacity-50 cursor-pointer"
                aria-label="Enviar mensaje"
                disabled={isLoading || !inputValue.trim()}
              >
                {sendIcon}
              </button>
            </form>
          </div>
        </div>
      )}
    </>
  );
};
