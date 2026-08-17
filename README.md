# Euler AI Agent

Agente de IA con avatar 3D, voz natural y chat en tiempo real.

## Características

- **Chat con LLM local** — Modelo LFM2.5-1.2B ejecutado con llama.cpp
- **Text-to-Speech natural** — MOSS-TTS-Nano con clonación de voz
- **Avatar 3D con lip-sync** — Three.js + wawa-lipsync en tiempo real
- **Visualizador de audio** — Animación de ondas del audio generado

## Estructura del proyecto

```
euler-ai-agent/
├── euler-backend/
│   ├── src/
│   │   ├── main.py          # Punto de entrada (FastAPI + uvicorn)
│   │   ├── api.py           # Endpoints: /chat, /audio/{filename}
│   │   ├── tts.py           # Motor TTS con MOSS-TTS-Nano
│   │   └── v2g.py           # Voice to Gesture (Audio2Face)
│   ├── MOSS-TTS-Nano/       # Motor TTS y modelos ONNX
│   │   ├── models/          # Modelos descargados (ignorados en git)
│   │   ├── onnx_tts_runtime.py
│   │   └── ...
│   ├── .models/             # Modelo LLM (ignorados en git)
│   │   └── LFM2.5-1.2B-Instruct-Q4_K_M.gguf
│   ├── audios/
│   │   ├── referencia_neutra.wav   # Voz de referencia para TTS
│   │   └── generated/              # Audios generados (ignorados en git)
│   ├── animaicones/         # Animaciones USD generadas
│   ├── docker-compose-cpu.yml  # llama.cpp container
│   └── requerimentes.txt    # Dependencias Python
└── euler-frontend/
    ├── src/
    │   ├── components/
    │   │   ├── Avatar.jsx       # Avatar 3D con wawa-lipsync
    │   │   ├── Chat.jsx         # Interfaz de chat
    │   │   ├── UI.jsx           # Componentes de interfaz
    │   │   ├── Visualizer.jsx   # Visualizador de audio
    │   │   └── Experience.jsx   # Escena Three.js
    │   ├── App.jsx
    │   └── main.jsx
    ├── package.json
    └── vite.config.js
```

## Requisitos

- Python 3.10+
- Node.js 18+ (o Bun)
- Docker (para llama.cpp)
- CPU (el backend corre en CPU, GPU es opcional)

---

## Instalación paso a paso

### Paso 1 — Clonar el repositorio

```bash
git clone https://github.com/Dungeonmx/euler-ai-agent.git
cd euler-ai-agent
```

### Paso 2 — Configurar el backend

```bash
cd euler-backend

# Crear entorno virtual
python3 -m venv .venv

# Activar entorno virtual
source .venv/bin/activate

# Instalar dependencias
pip install -r requerimentes.txt
```

### Paso 3 — Descargar el modelo LLM

Descarga tu modelo de preferencia gguf, en este caso utilizamos `LFM2.5-1.2B-Instruct-Q4_K_M.gguf` y colócalo en:

```
euler-backend/.models/LFM2.5-1.2B-Instruct-Q4_K_M.gguf
```

### Paso 4 — Clonar MOSS-TTS-Nano y descargar modelos

El motor TTS usa [MOSS-TTS-Nano](https://github.com/OpenMOSS/MOSS-TTS-Nano). Primero clona el repositorio:

```bash
cd euler-backend
git clone https://github.com/OpenMOSS/MOSS-TTS-Nano.git
cd MOSS-TTS-Nano
```

Luego descarga los modelos ONNX. Tienes dos opciones:

**Opción 1 — Descarga automática (recomendada):**

Ejecuta el script de inferencia ONNX y los modelos se descargan automáticamente la primera vez:

```bash
python infer_onnx.py \
  --prompt-audio-path assets/audio/zh_1.wav \
  --text "Welcome to the ONNX Runtime CPU demo."
```

Los modelos se descargan automáticamente a:
- `models/MOSS-TTS-Nano-100M-ONNX/`
- `models/MOSS-Audio-Tokenizer-Nano-ONNX/`

**Opción 2 — Descarga manual con huggingface-cli:**

```bash
pip install huggingface_hub

huggingface-cli download OpenMOSS-Team/MOSS-TTS-Nano-100M-ONNX \
  --local-dir models/MOSS-TTS-Nano-100M-ONNX

huggingface-cli download OpenMOSS-Team/MOSS-Audio-Tokenizer-Nano-ONNX \
  --local-dir models/MOSS-Audio-Tokenizer-Nano-ONNX
```

**Repositorios de Hugging Face:**
- [MOSS-TTS-Nano-100M-ONNX](https://huggingface.co/OpenMOSS-Team/MOSS-TTS-Nano-100M-ONNX)
- [MOSS-Audio-Tokenizer-Nano-ONNX](https://huggingface.co/OpenMOSS-Team/MOSS-Audio-Tokenizer-Nano-ONNX)

### Paso 5 — Iniciar llama.cpp (servidor LLM)

```bash
# Desde euler-backend/
./start.sh

# O manualmente:
docker compose -f docker-compose-cpu.yml up -d
```

Esto inicia el servidor llama.cpp en `http://localhost:8010`.

Verifica que está corriendo:

```bash
curl http://localhost:8010/health
```

### Paso 6 — Iniciar el backend (API + TTS)

```bash
# Desde euler-backend/ (con el venv activado)
python src/main.py
```

Verás:
```
INFO:     Started server process
INFO:     Uvicorn running on http://0.0.0.0:8000
```

La API estará disponible en `http://localhost:8000`.

### Paso 7 — Configurar el frontend

```bash
cd euler-frontend

# Con Bun (recomendado):
bun install

# O con npm:
npm install
```

### Paso 8 — Iniciar el frontend

```bash
# Con Bun:
bun dev

# O con npm:
npm run dev
```

El frontend estará disponible en `http://localhost:5173`.

---

## Endpoints de la API

### POST /chat

Envía un mensaje y recibe la respuesta del LLM + audio sintetizado.

**Cuerpo de la solicitud:**

```json
{
  "messages": [
    { "role": "user", "content": "Hola, ¿cómo estás?" }
  ]
}
```

**Respuesta:**

```json
{
  "messages": [
    { "role": "user", "content": "Hola, ¿cómo estás?" },
    { "role": "assistant", "content": "¡Hola! Estoy bien, ¿y tú?" }
  ],
  "audio_url": "/audio/assistant_20260817_142010_abc12345.wav"
}
```

**Ejemplo con curl:**

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"Hola, ¿cómo estás?"}]}'
```

**Con respuesta formateada:**

```bash
curl -s -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"Cuéntame un chiste"}]}' | python3 -m json.tool
```

**Con historial de conversación (múltiples mensajes):**

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role": "user", "content": "Mi nombre es Benjamín"},
      {"role": "assistant", "content": "¡Hola Benjamín!"},
      {"role": "user", "content": "¿Cómo me llamo?"}
    ]
  }'
```

### GET /audio/{filename}

Descarga el audio generado.

**Ejemplo con curl (usando el filename de la respuesta anterior):**

```bash
curl -o audio.wav http://localhost:8000/audio/assistant_20260817_142010_abc12345.wav
```

---

## Ejemplos de consultas

Estas son algunas consultas de prueba para verificar que todo funciona:

```bash
# Saludo simple
curl -s -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"Hola"}]}' | python3 -m json.tool
```

```bash
# Pregunta de conocimiento
curl -s -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"¿Cuál es la capital de Francia?"}]}' | python3 -m json.tool
```

```bash
# Pregunta matemática
curl -s -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"Cuánto es 25 por 4?"}]}' | python3 -m json.tool
```

```bash
# Generar audio y descargarlo en un solo comando
curl -s -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"Di hola al mundo"}]}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['audio_url'])" \
  | xargs -I {} curl -o respuesta.wav "http://localhost:8000/{}"
```


