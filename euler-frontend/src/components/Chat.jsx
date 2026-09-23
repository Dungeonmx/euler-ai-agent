import { useEffect, useRef, useState } from "react";

export const Chat = ({ onPlayAudio }) => {
    const [messages, setMessages] = useState([]);
    const [inputValue, setInputValue] = useState("");
    const [isLoading, setIsLoading] = useState(false);
    const scrollRef = useRef(null);
    const abortRef = useRef(null);

    useEffect(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
        }
    }, [messages]);

    const sendMessage = async () => {
        const text = inputValue.trim();
        if (!text || isLoading) return;

        const userMessage = { role: "user", content: text };
        const newMessages = [...messages, userMessage];
        setMessages(newMessages);
        setInputValue("");
        setIsLoading(true);

        if (abortRef.current) {
            abortRef.current.abort();
        }
        abortRef.current = new AbortController();

        const assistantMsgIndex = newMessages.length;
        setMessages((prev) => [...prev, { role: "assistant", content: "" }]);

        let accumulatedText = "";

        try {
            const response = await fetch("/chat/stream", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ messages: [...newMessages] }),
                signal: abortRef.current.signal,
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const reader = response.body.getReader();
            const decoder = new TextDecoder("utf-8");
            let buffer = "";

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });

                const lines = buffer.split("\n");
                buffer = lines.pop();

                let currentEvent = null;
                let currentData = null;

                for (const line of lines) {
                    if (line.startsWith("event:")) {
                        currentEvent = line.slice(7).trim();
                    } else if (line.startsWith("data:")) {
                      currentData = line.slice(6).trimEnd();
                    } else if (line === "") {
                        if (currentEvent === "text" && currentData) {
                            accumulatedText += currentData;
                            setMessages((prev) => {
                                const updated = [...prev];
                                updated[assistantMsgIndex] = {
                                    role: "assistant",
                                    content: accumulatedText,
                                };
                                return updated;
                            });
                        } else if (currentEvent === "audio" && currentData) {
                            onPlayAudio(currentData);
                        } else if (currentEvent === "done") {
                            setIsLoading(false);
                        }

                        currentEvent = null;
                        currentData = null;
                    }
                }
            }

            if (buffer.trim()) {
                const remainingLines = buffer.split("\n");
                let currentEvent = null;
                let currentData = null;

                for (const line of remainingLines) {
                    if (line.startsWith("event:")) {
                        currentEvent = line.slice(7).trim();
                    } else if (line.startsWith("data:")) {
                      currentData = line.slice(6).trimEnd();
                    } else if (line === "") {
                        if (currentEvent === "text" && currentData) {
                            accumulatedText += currentData;
                            setMessages((prev) => {
                                const updated = [...prev];
                                updated[assistantMsgIndex] = {
                                    role: "assistant",
                                    content: accumulatedText,
                                };
                                return updated;
                            });
                        } else if (currentEvent === "audio" && currentData) {
                            onPlayAudio(currentData);
                        } else if (currentEvent === "done") {
                            setIsLoading(false);
                        }
                        currentEvent = null;
                        currentData = null;
                    }
                }
            }

        } catch (error) {
            if (error.name === "AbortError") {
                return;
            }
            console.error("Chat error:", error);
            setMessages((prev) => {
                const updated = [...prev];
                updated[assistantMsgIndex] = {
                    role: "assistant",
                    content: "Error al conectar con el servidor.",
                };
                return updated;
            });
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
        if (abortRef.current) {
            abortRef.current.abort();
        }
        setMessages([]);
        setIsLoading(false);
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
                            className={`rounded-lg px-3 py-2 max-w-80 text-sm break-words whitespace-pre-wrap ${
                                msg.role === "user"
                                    ? "bg-indigo-500 text-white"
                                    : "bg-white text-gray-900 border border-gray-200"
                            }`}
                        >
                            {msg.content}{msg.role === "assistant" && isLoading && <span className="inline-block w-2 h-4 bg-gray-400 animate-pulse ml-0.5 align-middle"></span>}
                        </div>
                    </div>
                ))}
                {isLoading && messages.length > 0 && messages[messages.length - 1].role === "assistant" && !messages[messages.length - 1].content && (
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
