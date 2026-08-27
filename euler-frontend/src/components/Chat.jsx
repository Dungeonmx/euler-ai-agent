import { useEffect, useRef, useState } from "react";

export const Chat = ({ onPlayAudio }) => {
  const [messages, setMessages] = useState([]);
  const [inputValue, setInputValue] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const scrollRef = useRef(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  const sendMessage = async () => {
    const text = inputValue.trim();
    if (!text || isLoading) return;

    const userMessage = { role: "human", content: text };
    const newMessages = [...messages, userMessage];
    setMessages(newMessages);
    setInputValue("");
    setIsLoading(true);

    try {
      const response = await fetch("/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
<<<<<<< HEAD
        body: JSON.stringify({ messages: newMessages }),
=======
        body: JSON.stringify({
          messages: [...newMessages],
        }),
>>>>>>> origin/main
      });

      const data = await response.json();
      const assistantMessage = data.messages.at(-1);
      setMessages((prev) => [...prev, assistantMessage]);

      if (data.audio_url) {
        onPlayAudio(data.audio_url);
      }
    } catch (error) {
      console.error("Chat error:", error);
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: "Error al conectar con el servidor." },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyDown = (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      sendMessage();
    }
  };

  const clearChat = () => {
    setMessages([]);
  };

  return (
    <div className="pointer-events-auto flex flex-col gap-3">
      <div className="flex justify-end">
        <button
          className="px-3 py-1.5 text-white bg-red-500 hover:bg-red-600 cursor-pointer rounded text-sm"
          onClick={clearChat}
        >
          Clear chat
        </button>
      </div>

      <div
        ref={scrollRef}
        className="flex flex-col gap-2 max-h-96 overflow-y-auto p-2 rounded bg-gray-100"
      >
        {messages.length === 0 && (
          <p className="text-gray-600 text-center text-sm py-4">
            Escribe un mensaje para comenzar...
          </p>
        )}
        {messages.map((msg, index) => (
          <div
            key={index}
            className={`flex ${
              msg.role === "user" ? "justify-end" : "justify-start"
            }`}
          >
            <div
              className={`rounded-lg px-3 py-2 max-w-80 text-sm ${
                msg.role === "user"
                  ? "bg-indigo-500 text-white"
                  : "bg-white text-gray-900 border border-gray-200"
              }`}
            >
              {msg.content}
            </div>
          </div>
        ))}
        {isLoading && (
          <div className="flex justify-start">
            <div className="rounded-lg px-3 py-2 bg-gray-200 text-gray-700 text-sm animate-pulse">
              Pensando...
            </div>
          </div>
        )}
      </div>

      <div className="flex gap-2">
        <input
          type="text"
          className="flex-1 p-2 rounded bg-gray-100 text-gray-900 border border-gray-300 text-sm placeholder-gray-600"
          placeholder="Escribe tu mensaje..."
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={isLoading}
        />
        <button
          className="px-4 py-2 text-white bg-indigo-500 hover:bg-indigo-600 cursor-pointer rounded text-sm disabled:opacity-50"
          onClick={sendMessage}
          disabled={isLoading || !inputValue.trim()}
        >
          Enviar
        </button>
      </div>
    </div>
  );
};
