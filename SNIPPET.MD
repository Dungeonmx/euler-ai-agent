# SNIPPET — cómo se incrusta el chatbot en una web externa

Este documento explica cómo funciona el widget de Euler, por qué se puede meter en
cualquier sitio con una sola línea, y cómo se trabaja con los cambios.

---

## 1. La idea

El chatbot **no es una página web**. Es un componente que se le inyecta a una página
que ya existe, ajena, y que no nos pertenece.

Por eso todo el diseño está pensado alrededor de una regla: **la página anfitriona no
tiene que instalar nada, ni compilar nada, ni tocar su HTML o su CSS.**

En el HTML de cualquier sitio, una sola línea antes de `</body>`:

```html
<script src="https://www.ing.unlpam.edu.ar/euler/js/iniciar.js"
        data-api="https://api.ing.unlpam.edu.ar"></script>
```

Eso es todo. El script va con `async`, así que no frena el renderizado de la página.

---

## 2. Los archivos que componen el widget

Son **dos**, y pesan muy distinto porque se descargan en momentos distintos:

| Archivo | Qué es | Cuándo se descarga | Tamaño |
|---|---|---|---|
| `iniciar.js` | El snippet. Dibuja el botón flotante con DOM plano, sin dependencias. | Al cargar la página | **6 KB (3 KB gzip)** |
| `euler-chat.js` | El chatbot: React + three.js + Tailwind + el avatar 3D. | Recién cuando el visitante toca el botón | **1,2 MB (332 KB gzip)** |
| `models/*.glb` | El avatar 3D. | Recién cuando se abre el panel | **11 MB** |

Que haya dos archivos no es capricho: es lo que hace que el widget sea aceptable en una
página pública. Un visitante que nunca abre el chatbot se descarga **3 KB**, no 1,2 MB.

Si el botón flotante estuviera hecho en React (que es lo más natural si pensás en el
widget como una app), costaría 181 KB gzip solo el botón, porque React y ReactDOM pesan
más que todo el resto del widget junto. Por eso el botón se dibuja a mano.

### La regla que sigue todo el diseño

> **El botón se dibuja en el snippet. El panel se dibuja en React.**

Nunca en los dos lados. Si el botón estuviera en `iniciar.js` *y* en `ChatWidget.jsx`,
cada cambio visual habría que aplicarlo en dos lugares y tarde o temprano se
desincronizan. Ahora el botón tiene un único dueño y el panel tiene otro.

---

## 3. Qué pasa por detrás, paso a paso

1. La página termina de cargar y el navegador pide `iniciar.js` (6 KB).
2. `iniciar.js` lee **su propia URL** para deducir dónde está alojado el resto del
   widget, y guarda la configuración en dos variables de `window`:
   ```js
   window.EULER_CHAT_API  = "https://api.ing.unlpam.edu.ar";
   window.EULER_CHAT_BASE = "https://www.ing.unlpam.edu.ar/euler/js/";
   ```
3. `iniciar.js` crea un `<div>` vacío y le engancha un **Shadow DOM**. Adentro mete el
   botón. Nada más. No descarga el chatbot.
4. El visitante hace clic en el botón.
5. `iniciar.js` marca `window.__EULER_CHAT_OPEN_REQUESTED__ = true` y se inyecta a sí
   mismo el bundle pesado, `euler-chat.js`.
6. `euler-chat.js` arranca, lee la marca del paso 5 y monta el panel **directamente
   abierto** (sin parpadeo: no aparece el botón un segundo y después el panel).
7. Recién en ese momento se piden los 11 MB del avatar 3D.

---

## 4. Por qué no rompe la página anfitrión

Cuatro mecanismos, todos necesarios:

### 4.1 Shadow DOM

El widget se monta en su propio árbol de estilos. El CSS de la página **no alcanza** a
lo que está adentro del shadow root, y el CSS del widget **no sale** de ahí.

Da igual si el sitio anfitrión tiene un `* { box-sizing: border-box }` agresivo o un
`button { font-family: Arial }` con `!important`. No se mezclan.

Es la razón principal por la que el widget puede vivir en una página que no controlás.

> **Consecuencia importante:** el CSS que Vite emite con `@property` no funciona dentro
> de un shadow root. Ver la sección 8.

### 4.2 Estilos inline en el host

El `<div>` contenedor lleva su geometría y su `z-index` como **estilos inline**, no como
reglas de CSS:

```js
host.style.cssText = "position:fixed;left:0;top:0;width:0;height:0;z-index:2147483000";
```

Los estilos inline ganan contra cualquier selector de la página anfitriona. Sin esto,
un `body > div:last-child { display: none }` en la página de la facultad mataría el
widget en silencio.

Lo único que no se puede defender es un `!important` en la página anfitrión apuntando al
div. Es un caso patológico que tienen todos los widgets del mercado.

### 4.3 Rutas absolutas de los assets

Acá está el bug más importante, y el más fácil de no ver.

Si el avatar estuviera escrito así:

```js
<img src="images/robot.svg" />                            // MAL
const modelo = useGLTF("models/64f1a714fe61576b46f27ca2.glb");  // MAL
```

esas rutas son **relativas**, así que el navegador las resuelve contra la URL de la
**página anfitriona**, no contra el servidor del widget. En la página de la veterinaria
iría a pedir `/images/robot.svg` a su propio servidor, daría 404, y el avatar
3D no aparecería nunca.

Por eso todos los assets pasan por `assetUrl()` (`src/config.js`), que los convierte en
URLs absolutas usando `window.EULER_CHAT_BASE`.

### 4.4 CORS en el backend

El widget se sirve desde un dominio y le habla a una API en otro. El navegador, por
seguridad, bloquea esa petición antes de que llegue al servidor.

Sin `CORSMiddleware` en el backend el chat no responde **nada** en un dominio real. Y es
un fallo silencioso: en desarrollo no aparece, porque el proxy de Vite hace que el
frontend y el backend parezcan el mismo origen.

Por eso el backend tiene:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,     # viene de la variable CORS_ORIGINS
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)
```

---

## 5. Los atributos del snippet

| Atributo | Para qué sirve | Si se omite |
|---|---|---|
| `data-api` | URL del backend de la API. | Usa rutas relativas (solo útil al probar en local con el proxy de Vite). |
| `data-base` | Carpeta donde vive el resto de los archivos del widget. | Usa la misma carpeta que el propio `iniciar.js`. |

El snippet también es **idempotente**: si por error aparece dos veces en la misma página,
solo se dibuja un botón.

Y expone una API mínima por si el sitio quiere controlar el chat:

```js
EulerChat.open();   // abre el panel (cargando el widget si hace falta)
```

---

## 6. Cómo se trabaja con los cambios

Hay **dos escenarios distintos**, y cada uno necesita levantar un número distinto de
servidores. Esto es lo que más confunde, así que conviene tenerlo claro de una vez.

### Escenario A — cambiar cosas (lo que se usa el 99% del tiempo)

**Dos terminales:**

```bash
# Terminal 1 — Backend
cd ~/Dev/euler-ai-agent/euler-backend
python src/main.py                                          # http://localhost:8000

# Terminal 2 — Frontend
cd ~/Dev/euler-ai-agent/euler-frontend
npm run dev                                                 # http://localhost:5173
```

Abrís **`http://localhost:5173`**.

Aparece el botón flotante abajo a la derecha, igual que en producción, porque el
`index.html` de desarrollo carga el **mismo** `iniciar.js` que usa cualquier sitio
externo. Podés abrir el chat, cerrarlo y volver a abrirlo.

Acá tenés **HMR**: editás un archivo, guardás, y el navegador se actualiza solo. No hay
que recompilar nada. El proxy de Vite le manda los mensajes al backend en el 8000, así
que **el chat responde**.

Es lo que hay que usar para cambiar colores, tamaños, textos, animaciones o el botón.

### Escenario B — verlo embebido en una página ajena

**Tres terminales**, porque estás simulando tres servidores reales:

```bash
# Terminal 1 — Backend
cd ~/Dev/euler-ai-agent/euler-backend
python src/main.py                                          # http://localhost:8000

# Terminal 2 — Los archivos del widget
cd ~/Dev/euler-ai-agent/euler-frontend
npm run build && npm run preview                            # http://localhost:4173

# Terminal 3 — La página que lo incrusta
cd ~/Dev/pagina-gatitos
python3 -m http.server 5174                                # http://localhost:5174
```

Abrís **`http://localhost:5174`**.

> **Importante:** `pagina-gatitos` **no contiene el chatbot**. Es un HTML con una sola
> línea relevante:
>
> ```html
> <script src="http://localhost:4173/iniciar.js" data-api="http://localhost:8000"></script>
> ```
>
> Pide `iniciar.js` al **4173**. Si el terminal 2 no está levantado, ese script da 404,
> no se dibuja el botón y no aparece **nada** — el sitio se ve normal, sin ningún error
> que te avise. Es el síntoma más común y el más confuso: **falta el `npm run preview`**.

Si vas a iterar sobre el build, el ciclo es: editás → `npm run build` → recargás. Son ~3
segundos, y es exactamente el mismo ciclo que va a tener la página de la facultad.

### La tabla de puertos

| Puerto | Quién lo levanta | Qué sirve | Qué se ve |
|---|---|---|---|
| **8000** | `python src/main.py` | La API del chat. | Nada navegable; es solo la API. |
| **4173** | `npm run preview` | `dist/`: `iniciar.js`, `euler-chat.js`, `models/`, `images/`. | **Nada. Da 404.** Ver abajo. |
| **5173** | `npm run dev` | El widget solo, con HMR. | El chatbot suelto, con su botón. |
| **5174** | `http.server` en `pagina-gatitos` | La página de la veterinaria. | La veterinaria **con el chatbot abajo a la derecha**. |

**¿Por qué `localhost:4173` da 404?**

Porque `dist/` **no tiene ningún `index.html`**. No es un olvido: en modo librería Vite
no emite ninguno, justamente porque el widget no es una página.

`dist/` contiene `euler-chat.js`, `iniciar.js`, `models/` e `images/`. Son **archivos**,
no páginas. Pedir `/` es pedir un `index.html` que no existe. Ese servidor es el
equivalente local de la carpeta a la que se van a subir los archivos: no se navega, se lo
referencia desde el `<script>`.

**¿Por qué `localhost:5173` a veces dice que no se puede acceder?**

Porque el `npm run dev` no está corriendo. Es todo.

### Nota sobre los puertos

`npm run dev` (5173) y `npm run preview` (4173) **sí pueden correr al mismo tiempo**: van
a puertos distintos.

Lo que no pueden es **competir por el mismo puerto**. Por eso ambos tienen
`strictPort: true` en `vite.config.js`: si el puerto pedido está ocupado, Vite **falla
ruidosamente** en vez de correrse silenciosamente a otro. Sin eso, Vite se quedaba con
puertos prestados (por ejemplo, agarraba el 5174 de `pagina-gatitos`) y de golpe
`localhost:5174` te servía la app de desarrollo en vez de la veterinaria — y parecía que
el widget estaba roto, cuando era una colisión de puertos.


---

## 7. Dónde se hacen los cambios

Todo dentro de `~/Dev/euler-ai-agent/euler-frontend/`. **Ningún sitio externo se toca
nunca**: cuando actualizás el `dist/` en el servidor, todas las páginas que ya tengan el
`<script>` ven los cambios en el próximo refresh.

| Qué querés cambiar | Dónde |
|---|---|
| Colores, tamaños, posición, textos del **panel** | `src/components/ChatWidget.jsx` |
| El **botón flotante** | `public/iniciar.js` — está en CSS plano, en la variable `CSS`, arriba del archivo |
| Animaciones, tipografía | `src/index.css` |
| El avatar de Euler (robotito) | `public/images/robot.svg` |

El avatar es **un solo archivo SVG** compartido por el botón flotante y por el header del
panel. Lleva sus propias animaciones declaradas adentro —parpadeo, balanceo y latido de
las antenas—, así que andan igual dentro del Shadow DOM del botón que dentro del panel en
React. Al ir cargado con `<img>`, un SVG no puede tocar el CSS ni el DOM de la página de
afuera, que es justo el aislamiento que se quiere.

---

## 8. Trampas conocidas

Estas cosas rompieron el widget durante el desarrollo y están documentadas en el código
para que no se deshagan por accidente.

### 8.1 Los degradados de Tailwind NO funcionan dentro de un Shadow DOM

**Síntoma:** el degradado del header del chat desaparece, y **no hay ningún error en la
consola**.

**Causa:** las utilidades de gradiente de Tailwind v4 (`bg-linear-to-r` +
`from-indigo-500 to-pink-500`) se apoyan en `@property` para componer los color stops.
Dentro de un shadow root esas declaraciones no se aplican, `--tw-gradient-stops` queda
inválido, y el `background-image` computa en `none`.

Verificado en Chromium con un repro mínimo: la misma CSS funciona en un documento normal
y falla dentro de un shadow root.

**Solución:** escribir los degradados como valores arbitrarios, con los colores a mano.

```jsx
// MAL — desaparece silenciosamente
className="bg-linear-to-r from-indigo-500 to-pink-500"

// BIEN
className="bg-[linear-gradient(to_right,#6366f1,#ec4899)]"
```

Como el Shadow DOM es justamente lo que hace que el widget se pueda incrustar en
cualquier sitio, no se pueden usar las utilidades de gradiente. Si alguna vez se actualiza
Tailwind, hay que volver a probar esto.

### 8.2 `process is not defined`

**Síntoma:** el widget no monta nada y la consola dice `process is not defined`.

**Causa:** en modo librería, Vite deja las referencias a `process.env.*` sin resolver, y
en el navegador eso es un ReferenceError.

**Solución:** en `vite.config.js`, dentro de `define`:

```js
define: command === "build" ? { "process.env.NODE_ENV": '"production"' } : {}
```

Además de arreglar el error, esto **reduced el bundle de 1,86 MB a 1,23 MB**, porque
hasta entonces se estaba empaquetando la build de desarrollo de React.

### 8.3 No usar `useGLTF.preload()`

`Avatar.jsx` tenía `useGLTF.preload()` sobre los `.glb`, que precalienta **11 MB en cada
carga de página**, aunque el visitante nunca abra el chat.

Como el `<Canvas>` solo se monta cuando el panel está abierto, **sacando el preload los
11 MB se piden recién cuando el usuario decide usar el chatbot.** Es la diferencia entre
pagar 11 MB siempre y pagarlos solo si se usa.

---

## 9. Publicar en producción

1. Subir el contenido de `euler-frontend/dist/` al servidor, en la ruta que apunte el
   `src` del snippet.
   ```
   dist/iniciar.js          ->  https://www.ing.unlpam.edu.ar/euler/js/iniciar.js
   dist/euler-chat.js       ->  https://www.ing.unlpam.edu.ar/euler/js/euler-chat.js
   dist/models/             ->  https://www.ing.unlpam.edu.ar/euler/js/models/
   dist/images/             ->  https://www.ing.unlpam.edu.ar/euler/js/images/
   ```

2. Poner `CORS_ORIGINS` en el `.env` del backend con los dominios reales, en vez del `*`
   por defecto:
   ```
   CORS_ORIGINS=https://www.ing.unlpam.edu.ar,https://ing.unlpam.edu.ar
   ```
   Sin esto, en un dominio real el chat no responde nada (y en local parece funcionar,
   porque el proxy de Vite oculta el problema).

3. Listo. No hay que tocar el HTML de ningún sitio que ya tenga el snippet.

---

## 10. Diagnóstico rápido

| Síntoma | Causa probable |
|---|---|
| El botón no aparece | El `src` del script está mal, o faltó el archivo en el servidor. Mirá la pestaña Network buscando un 404 en `iniciar.js`. |
| El botón aparece pero el panel no abre | `euler-chat.js` no se descargó. Buscalo en Network; si da 404, está en otra carpeta y falta `data-base`. |
| El panel abre pero el avatar 3D no se ve | Rutas de assets relativas. Verificá que `Avatar.jsx` use `assetUrl()` y no rutas peladas. |
| El panel abre pero no responde el chat | CORS. Mirá la consola: si dice *blocked by CORS policy*, falta `CORS_ORIGINS` en el backend. |
| Los colores del panel se ven raros | CSS de la página invadiendo al widget, o al revés. Debería ser imposible por el Shadow DOM: revisá que `mount.jsx` siga montando en shadow y no en el DOM normal. |
| Faltan los degradados | Ver 8.1. |
| `localhost:4173` da 404 | Es normal: ese servidor no tiene páginas, solo archivos. Ver sección 6. |
| En `localhost:5174` no aparece el botón y la página se ve normal | Falta el terminal 2 (`npm run build && npm run preview`). El `<script>` del snippet le pide `iniciar.js` al 4173, y sin ese servidor da 404 silencioso. |
| `localhost:5173` dice que no se puede acceder | Falta el terminal 2 (`npm run dev`). |

---

## 11. Resumen en una línea

El widget se monta en un Shadow DOM para no molestar al sitio anfitrión, se descarga
por partes para no pesar 1,2 MB de entrada, y se actualiza subiendo un `dist/` sin tocar
el HTML de nadie.