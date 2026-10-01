# Euler AI Agent

Agente de IA con avatar 3D, voz natural y chat en tiempo real, **incrustable en cualquier web con una sola línea de HTML**.

## Características

- **Chat con LLM local** — Modelo LFM2.5-1.2B ejecutado con llama.cpp
- **Text-to-Speech natural** — Qwen3-TTS con API de inferencia
- **Avatar 3D con lip-sync** — Three.js + wawa-lipsync en tiempo real
- **Visualizador de audio** — Animación de ondas del audio generado
- **Widget embebible** — Shadow DOM + carga diferida, se agrega con un `<script>` y no toca el sitio anfitrión

## Estructura del proyecto

```
euler-ai-agent/
├── euler-backend/
│   ├── src/
│   │   ├── main.py          # Punto de entrada (FastAPI + uvicorn)
│   │   ├── api.py           # Endpoints: /chat, /audio/{filename} + CORS
│   │   ├── tts.py           # Motor TTS (API Qwen3-TTS)
│   │   └── v2g.py           # Voice to Gesture (Audio2Face)
│   ├── .models/             # Modelo LLM (ignorados en git)
│   │   └── LFM2.5-1.2B-Instruct-Q4_K_M.gguf
│   ├── audios/
│   │   └── generated/              # Audios generados (ignorados en git)
│   ├── animaicones/         # Animaciones USD generadas
│   ├── docker-compose.yml  # llama.cpp container
│   └── requerimentes.txt    # Dependencias Python
└── euler-frontend/
    ├── public/
    │   ├── iniciar.js       # EL SNIPPET: el archivo que se incrusta
    │   ├── models/          # Avatar 3D (.glb)
    │   └── images/          # Avatar del botón
    ├── src/
    │   ├── main.jsx         # Entry del bundle del widget
    │   ├── mount.jsx        # Montaje en Shadow DOM
    │   ├── config.js        # Rutas absolutas y comunicación entre bundles
    │   ├── components/
    │   │   ├── ChatWidget.jsx   # Panel de chat ( acá van los cambios visuales )
    │   │   ├── Avatar.jsx       # Avatar 3D con wawa-lipsync
    │   │   └── Experience.jsx   # Escena Three.js
    │   ├── index.css        # Estilos del widget
    │   └── App.jsx
    ├── index.html           # Solo para `npm run dev`
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

### Paso 3 — Crear la carpeta donde se almacenaran los audios generados

```bash
mkdir -p audios/generated
```

### Paso 4 — Iniciar llama.cpp (servidor LLM) e iniciar qwen3tts.cpp (servidor TTS)

Primero descarga los modelos en la carpeta `.models/`
- https://huggingface.co/Serveurperso/Qwen3-TTS-GGUF/resolve/main/qwen-talker-1.7b-customvoice-Q4_K_M.gguf?download=true
- https://huggingface.co/Serveurperso/Qwen3-TTS-GGUF/resolve/main/qwen-tokenizer-12hz-Q4_K_M.gguf?download=true
- https://huggingface.co/viniciusianni/LFM2.5-1.2B-Instruct-Q4_K_M-GGUF/resolve/main/lfm2.5-1.2b-instruct-q4_k_m.gguf?download=true

```bash
mkdir .models && \
curl -L -o .models/qwen-talker-1.7b-customvoice-Q4_K_M.gguf https://huggingface.co/Serveurperso/Qwen3-TTS-GGUF/resolve/main/qwen-talker-1.7b-customvoice-Q4_K_M.gguf?download=true && \
curl -L -o .models/qwen-tokenizer-12hz-Q4_K_M.gguf https://huggingface.co/Serveurperso/Qwen3-TTS-GGUF/resolve/main/qwen-tokenizer-12hz-Q4_K_M.gguf?download=true && \
curl -L -o .models/LFM2.5-1.2B-Instruct-Q4_K_M.gguf https://huggingface.co/viniciusianni/LFM2.5-1.2B-Instruct-Q4_K_M-GGUF/resolve/main/lfm2.5-1.2b-instruct-q4_k_m.gguf?download=true
```

Luego lanza los contenedores

```bash
docker compose -f docker-compose.yml up -d
```

Esto inicia el servidor llama.cpp en `http://localhost:8010` y el servidor qwen3tts.cpp en `http://localhost:8019`.

Verifica que está corriendo:

```bash
curl http://localhost:8010/health
```

### Paso 5 — Iniciar el backend (API + TTS)

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

### Paso 6 — Configurar el frontend

```bash
cd euler-frontend

# Con Bun (recomendado):
bun install

# O con npm:
npm install
```

### Paso 7 — Iniciar el frontend

```bash
# Con Bun:
bun dev

# O con npm:
npm run dev
```

El frontend estará disponible en `http://localhost:5173`.

---

## El widget: cómo se mete en una web externa

### La línea que se agrega al sitio

En el HTML de cualquier página, antes de `</body>`:

```html
<script src="https://www.ing.unlpam.edu.ar/euler/js/iniciar.js"
        data-api="https://api.ing.unlpam.edu.ar"></script>
```

Eso es todo. El sitio anfitrión **no instala nada, no compila nada y no toca su CSS**. El script va con `async`, así que no frena el renderizado de la página.

### Qué pasa por detrás

Son dos archivos, con dos costos bien distintos:

| Archivo | Qué es | Cuándo se descarga |
|---|---|---|
| `iniciar.js` | El snippet. Dibuja el botón flotante con DOM plano. **6 KB (3 KB con gzip).** | Al cargar la página |
| `euler-chat.js` | El chatbot: React + three.js + Tailwind. **1,2 MB (332 KB con gzip).** | Recién cuando el visitante toca el botón |
| `models/*.glb` | El avatar 3D. **11 MB.** | Recién cuando se abre el panel |

La carga diferida es lo que hace que esto sea aceptable en una página pública: un visitante que nunca abre el chatbot se descarga **3 KB**, no 1,2 MB.

Por qué no se rompe el sitio anfitrión:

- **Shadow DOM** — el widget se monta en su propio árbol de estilos. El CSS de la página no lo alcanza y el del widget no sale. Da igual si el sitio tiene un `* { box-sizing }` o un `button { font-family }` agresivo.
- **Estilos inline en el host** — la geometría y el `z-index` van como estilos inline, que ganan contra cualquier selector de la página.
- **Rutas absolutas** — los assets se resuelven contra la URL del widget, no contra la de la página. Sin esto, el avatar daría 404 en cualquier sitio que no tenga un `/images/wawasensei.png`.
- **CORS en el backend** — sin `CORSMiddleware` el navegador bloquea el `fetch` antes de que llegue al servidor.

### Atributos del snippet

| Atributo | Para qué sirve | Si se omite |
|---|---|---|
| `data-api` | URL del backend de la API | Usa rutas relativas (solo sirve al probar en local) |
| `data-base` | Carpeta donde vive el resto de los archivos | Usa la misma carpeta que el `iniciar.js` |

### Cómo trabajar con los cambios

`dist/` es lo único que hay que subir al servidor. **Todos los sitios que ya tengan el `<script>` actualizado ven los cambios al instante**, sin tocar el HTML de nadie.

**Levantar todo para probar** (3 terminales):

```bash
# 1 — Backend (solo si tocás algo del LLM o del TTS)
cd ~/Dev/euler-ai-agent/euler-backend
source .venv/bin/activate && python src/main.py          # http://localhost:8000

# 2 — Widget compilado y servido en dist/
cd ~/Dev/euler-ai-agent/euler-frontend
npm run build && npm run preview                          # http://localhost:4173

# 3 — La "página de la facultad" de mentira
cd ~/Dev/pagina-gatitos
python3 -m http.server 5174                              # http://localhost:5174
```

Abrís `http://localhost:5174` y te aparece el botón abajo a la derecha.

> **Ojo con los puertos:** `npm run dev` (5173) y `npm run preview` (4173) no se pueden usar al mismo tiempo. Si los levantás juntos, Vite puede correrse de puerto y `localhost:5174` termina apuntando al servidor equivocado. Para probar, usá `preview`; el `dev` es solo para escribir código.

**Cada vez que hacés un cambio visual:**

1. Editás `euler-frontend/src/components/ChatWidget.jsx` (o `src/index.css` para animaciones)
2. `npm run build`
3. Recargás el navegador

No hay HMR: `npm run preview` sirve `dist/` estático, así que hay que recompilar y recargar. No es una molestia, el build tarda ~3 segundos y es exactamente el mismo ciclo que va a tener la página de la facultad.

> Para iterar más rápido existe `npm run dev` (localhost:5173, con HMR y proxy a `/chat`). Pero ahí el widget se sirve desde la raíz de Vite, así que no reproduce exactamente la realidad. Usalo para escribir código y el `build` para verificar.

### Dónde se hacen los cambios visuales

Todo en `euler-frontend/`:

| Qué querés cambiar | Dónde |
|---|---|
| Colores, tamaños, posición, textos del **panel** | `src/components/ChatWidget.jsx` |
| El **botón flotante** | `public/iniciar.js` (está en CSS plano, arriba del archivo) |
| Animaciones, tipografía | `src/index.css` |
| La imagen del avatar | `public/images/wawasensei.png` |

El botón NO se dibuja en React, a propósito: si se dibujara en los dos lados (en el snippet y en el widget), cada cambio visual habría que aplicarlo en dos lugares y tarde o temprano se desincronizan. Por eso el snippet dibuja el botón y React solo el panel.

> **Ojo con los degradados.** Van escritos como `bg-[linear-gradient(to_right,#6366f1,#ec4899)]` y no como `bg-linear-to-r from-indigo-500 to-pink-500`. Las utilidades de gradiente de Tailwind v4 dependen de `@property`, que **no funciona dentro de un Shadow DOM**: el `--tw-gradient-stops` queda inválido y el degradado desaparece sin dar ningún error en la consola. Está documentado en `ChatWidget.jsx`.

### Antes de subir a producción

1. Subir el contenido de `euler-frontend/dist/` al servidor, en la ruta que apunte el `src` del snippet.
2. Poner `CORS_ORIGINS` en el `.env` del backend con los dominios reales, en vez del `*` por defecto:
   ```
   CORS_ORIGINS=https://www.ing.unlpam.edu.ar,https://ing.unlpam.edu.ar
   ```
   Sin esto, en un dominio real el chat no responde nada (aunque en local funcione, porque el proxy de Vite oculta el problema).

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
