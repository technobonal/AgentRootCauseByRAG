import base64
import html
import os
import re
import tempfile

import streamlit as st
from langchain_community.document_loaders import PyPDFLoader

from agente import responder_estructurado, responder_desde_texto

# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------
# Configuración general de la página (título, ícono, ancho y estado del sidebar)
st.set_page_config(
    page_title="LogisCore Root Cause Agent",
    page_icon="🔧",
    layout="centered",
    initial_sidebar_state="expanded",
)

RUTA_IMAGEN = "assets/fishbone.jpg"
MAX_CHARS_PDF = 60000  # límite de texto por PDF para no saturar el prompt
MAX_CHARS_EVIDENCIA = 600  # largo máximo del fragmento mostrado en cada evidencia

# Consultas de ejemplo que se muestran como chips clickeables
EJEMPLOS = [
    "¿Por qué se cobra dos veces?",
    "¿Por qué se demora una entrega?",
    "¿Por qué falla el inventario?",
]

# Nombres legibles para los tipos de evidencia
ETIQUETAS_TIPO = {"incidente": "Incidente", "causa_raiz": "Causa raíz"}

# ---------------------------------------------------------------------------
# Estilos (mejorados)
# ---------------------------------------------------------------------------
# Bloque único de CSS que se inyecta en la página con st.markdown
CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,600;9..144,700&family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');
:root {
    /* ---------- Fondo "sala de incidentes": azul noche con acento ámbar ---------- */
    --bg-top: #101B3D;        /* azul noche en la parte superior */
    --bg-upper: #0C1530;      /* transición suave hacia lo oscuro */
    --bg-lower: #0A1020;      /* zona de lectura, la más estable */
    --bg-bottom: #060A14;     /* profundidad, sin llegar a negro puro */
    --bg-warm: rgba(245, 184, 75, 0.10);    /* calidez ámbar sutil en la esquina superior izquierda */
    --bg-glow: rgba(22, 39, 90, 0.55);      /* resplandor azul arriba al centro */
    --btn-text: #06102A;            /* texto del botón principal: azul noche muy oscuro sobre azul claro */
    --btn-from: #A8C3FF;            /* inicio del degradado del botón (texto encima: 10.7:1) */
    --btn-to: #6B9BFF;              /* final del degradado del botón (texto encima: 7.0:1, AAA) */
    --btn-glow: 127, 166, 255;      /* rgb del brillo azul claro alrededor del botón */
    --halo-azul: 91, 140, 255;      /* rgb del halo brillante de las tarjetas principales */
    --text: #EAF0FF;
    --text-soft: #C5D0EA;
    --text-mute: #BAC6E3;          /* contraste > 7:1 sobre el fondo (WCAG AAA) */
    --glass: rgba(170, 190, 255, 0.07);
    --glass-strong: rgba(170, 190, 255, 0.12);
    --glass-border: rgba(150, 175, 255, 0.18);
    --chip-border: rgba(150, 175, 255, 0.32);
    --coral: #F5B84B;               /* acento único: ámbar */
    --coral-soft: #FFD58A;
    --pink: #FFCF70;                 /* ámbar claro: final de los degradados del acento */
    --violet: #7FA6FF;               /* azul claro: acento secundario frío */
    --ok: #6EE7B7;
    --warn: #FDE047;
    --bad: #FDA4AF;
    --pattern: rgba(170, 190, 255, 0.07);    /* rombos apenas visibles */
    --sidebar: rgba(8, 13, 26, 0.96);
    --bar-bg: rgba(10, 16, 32, 0.90);
}
html, body, [class*="css"], .stApp {
    font-family: 'Inter', sans-serif;
    color: var(--text);
}
/* Fondo fijo: calidez ámbar arriba a la izquierda + resplandor azul arriba + degradado vertical a azul casi negro */
.stApp {
    background-color: var(--bg-bottom);
    background-image:
        radial-gradient(640px 420px at 0% 0%, var(--bg-warm), transparent 70%),
        radial-gradient(900px 440px at 50% -8%, var(--bg-glow), transparent 65%),
        linear-gradient(180deg, var(--bg-top) 0%, var(--bg-upper) 22%, var(--bg-lower) 48%, var(--bg-bottom) 72%, var(--bg-bottom) 100%);
    background-attachment: fixed;
    isolation: isolate;   /* contexto propio: la capa de rombos queda detrás del contenido */
}
/* Rombos de líneas finas: solo en la franja superior, se desvanecen hacia abajo hasta desaparecer */
.stApp::before {
    content: "";
    position: fixed;
    inset: 0;
    z-index: -1;
    pointer-events: none;
    background-image:
        repeating-linear-gradient(45deg, var(--pattern) 0 1px, transparent 1px 88px),
        repeating-linear-gradient(-45deg, var(--pattern) 0 1px, transparent 1px 88px);
    -webkit-mask-image: linear-gradient(180deg, #000 0%, rgba(0, 0, 0, 0.55) 18%, transparent 42%);
    mask-image: linear-gradient(180deg, #000 0%, rgba(0, 0, 0, 0.55) 18%, transparent 42%);
}
header[data-testid="stHeader"] { background: transparent; }
div[data-testid="stAppDeployButton"], .stAppDeployButton { display: none; }
.block-container { padding-top: 1.4rem; max-width: 840px; }   /* menos espacio arriba */

/* ---------- Foco visible para teclado (accesibilidad) ---------- */
button:focus-visible,
summary:focus-visible,
a:focus-visible {
    outline: 2px solid var(--coral-soft) !important;
    outline-offset: 2px !important;
}

/* ---------- Hero ---------- */
.hero { text-align: center; margin: 0.15rem 0 0.5rem 0; }
.hero-eyebrow {
    display: inline-block;
    font-family: 'JetBrains Mono', monospace;
    font-size: 12px;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    color: var(--text-soft);
    background: var(--glass);
    border: 1px solid var(--glass-border);
    border-radius: 999px;
    padding: 5px 14px;
    margin-bottom: 14px;
    backdrop-filter: blur(8px);
}
.hero-eyebrow b { color: var(--coral); font-weight: 500; }
.hero-title {
    font-family: 'Fraunces', serif;
    font-weight: 600;
    font-size: 54px;
    line-height: 1.08;
    letter-spacing: -0.02em;
    color: var(--text);
    margin: 0 0 10px 0;
    text-wrap: balance;
}
.hero-title em {
    font-style: normal;
    background: linear-gradient(90deg, #FFE2A8, var(--coral));
    -webkit-background-clip: text;
    background-clip: text;
    color: transparent;
}
.hero-sub { font-size: 17px; color: var(--text-soft); margin: 0 auto; max-width: 520px; text-wrap: balance; }
.hero-img { text-align: center; margin: 0 0 4px 0; }
.hero-img img {
    width: 170px;
    mix-blend-mode: screen;
    opacity: 0.9;
    filter: grayscale(100%) brightness(1.3) contrast(1.1);
    -webkit-mask-image: radial-gradient(closest-side, #000 55%, transparent 100%);
    mask-image: radial-gradient(closest-side, #000 55%, transparent 100%);
}
.hero-compact {
    display: flex;
    align-items: center;
    justify-content: center;
    flex-wrap: wrap;
    gap: 6px 16px;
    margin: 0 0 12px 0;
}
.hero-compact .hero-eyebrow { margin: 0; font-size: 11px; padding: 4px 11px; }
.hero-compact .hero-title { font-size: 28px; margin: 0; }

/* ---------- Buscador ---------- */
div[data-testid="stForm"] {
    border: 1.5px solid transparent !important;
    border-radius: 18px;
    padding: 8px 10px;
    background:
        linear-gradient(var(--bar-bg), var(--bar-bg)) padding-box,
        linear-gradient(90deg, var(--coral), var(--violet)) border-box;
    box-shadow: 0 12px 40px rgba(0, 0, 0, 0.28), 0 0 0 5px rgba(127, 166, 255, 0.08);
    transition: box-shadow 0.15s ease;
}
div[data-testid="stForm"]:focus-within {
    box-shadow:
        0 12px 40px rgba(0, 0, 0, 0.28),
        0 0 0 3px rgba(255, 213, 138, 0.70),
        0 0 0 8px rgba(127, 166, 255, 0.22);
}
div[data-testid="stTextInput"] div[data-baseweb="input"],
div[data-testid="stTextInput"] div[data-baseweb="base-input"],
div[data-testid="stTextInputRootElement"],
div[data-testid="stTextInputRootElement"] > div {
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
}
div[data-testid="stTextInputRootElement"]:focus-within,
div[data-testid="stTextInput"] div[data-baseweb="input"]:focus-within {
    border: none !important;
    box-shadow: none !important;
    outline: none !important;
}
div[data-testid="stTextInput"] input {
    font-size: 18px !important;
    padding: 14px 10px !important;
    color: var(--text) !important;
    background: transparent !important;
}
/* Placeholder con mejor contraste */
div[data-testid="stTextInput"] input::placeholder {
    color: var(--text-mute) !important;
    opacity: 0.92 !important;
}
div[data-testid="InputInstructions"] { display: none; }

/* Botón Investigar — más destacado */
div[data-testid="stFormSubmitButton"] button {
    border: none;
    border-radius: 12px;
    padding: 0.75rem 1.1rem;                 /* más padding */
    font-weight: 700;
    font-size: 15.5px;
    color: var(--btn-text) !important;
    background: linear-gradient(90deg, var(--btn-from), var(--btn-to));   /* azul claro luminoso, de claro a más intenso */
    box-shadow:
        inset 0 1px 0 rgba(255, 255, 255, 0.55),     /* filo de luz arriba: el botón se ve "encendido" */
        0 8px 24px rgba(var(--btn-glow), 0.50),      /* brillo azul bajo el botón */
        0 0 28px rgba(var(--btn-glow), 0.22);        /* halo suave alrededor */
    transition: transform 0.12s ease, box-shadow 0.12s ease;
}
div[data-testid="stFormSubmitButton"] button p,
div[data-testid="stFormSubmitButton"] button div {
    color: var(--btn-text) !important;
    font-weight: 700;
}
div[data-testid="stFormSubmitButton"] button:hover {
    transform: translateY(-2px);
    box-shadow:
        inset 0 1px 0 rgba(255, 255, 255, 0.65),
        0 12px 32px rgba(var(--btn-glow), 0.70),     /* el brillo sube al pasar el mouse */
        0 0 36px rgba(var(--btn-glow), 0.38);
    color: var(--btn-text) !important;
    border: none;
}
div[data-testid="stFormSubmitButton"] button:active { transform: translateY(0); }

/* ---------- Chips de ejemplo — más clickeables ---------- */
div[data-testid="stButton"] button,
div[data-testid="stDownloadButton"] button {
    border-radius: 999px;
    border: 1px solid var(--chip-border);
    background: var(--glass-strong);
    color: var(--text);
    font-size: 13.5px;
    font-weight: 500;
    padding: 0.5rem 1.15rem;                 /* más padding */
    backdrop-filter: blur(8px);
    transition: border-color 0.12s ease, color 0.12s ease, background 0.12s ease, transform 0.12s ease, box-shadow 0.12s ease;
}
div[data-testid="stButton"] button:hover,
div[data-testid="stDownloadButton"] button:hover {
    border-color: var(--coral);
    color: #FFFFFF;
    background: rgba(245, 184, 75, 0.22);
    transform: translateY(-1px);
    box-shadow: 0 4px 14px rgba(245, 184, 75, 0.28);
}
.chips-label { font-size: 13px; color: var(--text-mute); text-align: center; margin: 14px 0 8px 0; }
.hint { font-size: 13px; color: var(--text-mute); text-align: center; margin: 12px 0 0 0; }
.hint b { color: var(--text-soft); font-weight: 600; }

/* ---------- Tarjetas de resultado ---------- */
div[data-testid="stVerticalBlockBorderWrapper"] {
    background: var(--glass);
    border: 1px solid var(--glass-border);
    border-radius: 18px;
    backdrop-filter: blur(14px);
    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.22);
}
div[data-testid="stVerticalBlockBorderWrapper"]:has(.card-accent),
.st-key-card_causa {
    border: 1.5px solid rgba(245, 184, 75, 0.60) !important;
    background: linear-gradient(135deg, rgba(245, 184, 75, 0.16), rgba(245, 184, 75, 0.09)) !important;
}
.st-key-card_solucion p, .st-key-card_solucion li {
    font-size: 16px;
    line-height: 1.65;
    max-width: 78ch;
}
.st-key-card_solucion strong { color: #FFFFFF; }

/* ---------- Tarjetas flotantes ----------
   1) Sombra en capas + filo de luz arriba: parecen suspendidas sobre el fondo.
   2) Al pasar el mouse se elevan unos px y la sombra se agranda.
   3) Al aparecer el análisis suben con un fundido, una tras otra.
   Los selectores cubren las distintas versiones de Streamlit (la clase de la tarjeta
   puede estar en la caja misma o en el bloque interior de un contenedor con borde). */
:root {
    --float-ease: cubic-bezier(0.2, 0.8, 0.2, 1);
    --shadow-float:
        inset 0 1px 0 rgba(255, 255, 255, 0.24),
        0 2px 4px rgba(2, 5, 14, 0.30),
        0 18px 34px -8px rgba(2, 5, 14, 0.60),
        0 30px 56px -22px rgba(60, 110, 230, 0.26);   /* halo azul sutil: da aire sin competir con el texto */
    --shadow-float-hover:
        inset 0 1px 0 rgba(255, 255, 255, 0.32),
        0 4px 8px rgba(2, 5, 14, 0.34),
        0 28px 48px -10px rgba(2, 5, 14, 0.62),
        0 44px 80px -22px rgba(70, 120, 240, 0.42);   /* al interactuar el halo sube: señal de que es "levantable" */
    /* Halo azul brillante (solo Causa raíz y Solución): dos capas de resplandor, una cercana
       y una amplia y muy suave, para que brille sin recargar la pantalla. Va por fuera de la
       tarjeta, así que no afecta el contraste del texto. */
    --shadow-halo:
        inset 0 1px 0 rgba(255, 255, 255, 0.24),
        0 2px 4px rgba(2, 5, 14, 0.30),
        0 0 22px -2px rgba(var(--halo-azul), 0.34),      /* resplandor cercano */
        0 0 64px 4px rgba(var(--halo-azul), 0.17),       /* resplandor amplio y suave */
        0 22px 44px -16px rgba(2, 5, 14, 0.60);          /* sombra de profundidad abajo */
    --shadow-halo-hover:
        inset 0 1px 0 rgba(255, 255, 255, 0.32),
        0 4px 8px rgba(2, 5, 14, 0.34),
        0 0 28px -2px rgba(var(--halo-azul), 0.50),      /* al interactuar, el halo sube */
        0 0 84px 8px rgba(var(--halo-azul), 0.26),
        0 28px 52px -16px rgba(2, 5, 14, 0.62);
    /* Cristal azulado: translúcido pero lo bastante cubriente para que los rombos del fondo
       no se vean detrás del texto (contraste del texto sobre la tarjeta > 10:1, WCAG AAA). */
    --card-violet: rgba(16, 27, 61, 0.90);
    --card-violet-soft: rgba(13, 22, 50, 0.88);
    --card-border: rgba(130, 165, 255, 0.24);
}
/* Evidencias: conserva la sombra flotante suave, sin halo, para no recargar la pantalla */
div[data-testid="stExpander"] {
    box-shadow: var(--shadow-float) !important;
}
/* Causa raíz y Solución (tarjetas principales): halo azul brillante */
:is(
    div[data-testid="stVerticalBlockBorderWrapper"]:has(> .st-key-card_solucion),
    div:not([data-testid="stVerticalBlockBorderWrapper"]) > .st-key-card_solucion,
    div[data-testid="stVerticalBlockBorderWrapper"]:has(> .st-key-card_causa),
    div:not([data-testid="stVerticalBlockBorderWrapper"]) > .st-key-card_causa
) {
    box-shadow: var(--shadow-halo) !important;
}
div[data-testid="stExpander"] { border-radius: 14px; }

/* Fondo azul translúcido en las tres tarjetas (misma familia de color = consistencia).
   Causa raíz conserva su acento ámbar como punto focal. */
:is(
    div[data-testid="stVerticalBlockBorderWrapper"]:has(> .st-key-card_solucion),
    div:not([data-testid="stVerticalBlockBorderWrapper"]) > .st-key-card_solucion
) {
    background: var(--card-violet-soft) !important;
    border: 1px solid var(--card-border) !important;
    border-radius: 18px;
    -webkit-backdrop-filter: blur(18px) saturate(1.15);
    backdrop-filter: blur(18px) saturate(1.15);
}
:is(
    div[data-testid="stVerticalBlockBorderWrapper"]:has(> .st-key-card_causa),
    div:not([data-testid="stVerticalBlockBorderWrapper"]) > .st-key-card_causa
) {
    background:
        linear-gradient(135deg, rgba(245, 184, 75, 0.09), rgba(245, 184, 75, 0.03)),
        var(--card-violet) !important;
    -webkit-backdrop-filter: blur(18px) saturate(1.15);
    backdrop-filter: blur(18px) saturate(1.15);
}

/* Ritmo vertical sobre una escala de 8 px: Causa → Solución 48 px (se lee como paso
   siguiente, sin separarlas tanto que pierdan la relación), Solución → Evidencias 32 px. */
:is(
    div[data-testid="stVerticalBlockBorderWrapper"]:has(> .st-key-card_solucion),
    div:not([data-testid="stVerticalBlockBorderWrapper"]) > .st-key-card_solucion
) {
    margin-top: 2rem;
}
div[data-testid="stExpander"] { margin-top: 1rem; }

@keyframes flotar-entrada {
    from { opacity: 0; transform: translateY(22px) scale(0.985); }
    to   { opacity: 1; transform: none; }
}
/* Vaivén suave y continuo. Usa la propiedad "translate" (no "transform") para sumarse
   a la entrada y a la elevación del hover sin pisarlas. */
@keyframes flotar-vaiven {
    0%, 100% { translate: 0 0; }
    50%      { translate: 0 -6px; }
}
@media (prefers-reduced-motion: no-preference) {
    :is(
        div[data-testid="stVerticalBlockBorderWrapper"]:has(> .st-key-card_causa),
        div:not([data-testid="stVerticalBlockBorderWrapper"]) > .st-key-card_causa,
        div[data-testid="stVerticalBlockBorderWrapper"]:has(> .st-key-card_solucion),
        div:not([data-testid="stVerticalBlockBorderWrapper"]) > .st-key-card_solucion,
        div[data-testid="stExpander"]
    ) {
        transition: transform 0.3s var(--float-ease), box-shadow 0.3s ease;
        /* "backwards": al terminar la entrada no bloquea el hover */
        animation:
            flotar-entrada 0.65s var(--float-ease) backwards,
            flotar-vaiven 7s ease-in-out 0.7s infinite;
    }
    :is(
        div[data-testid="stVerticalBlockBorderWrapper"]:has(> .st-key-card_solucion),
        div:not([data-testid="stVerticalBlockBorderWrapper"]) > .st-key-card_solucion
    ) { animation-delay: 0.12s, 1.8s; }
    .stApp div[data-testid="stExpander"] { animation-delay: 0.24s, 2.9s; }
}
@media (prefers-reduced-motion: no-preference) and (hover: hover) {
    /* Evidencias: se eleva con la sombra flotante, sin halo */
    div[data-testid="stExpander"]:hover {
        transform: translateY(-8px);
        box-shadow: var(--shadow-float-hover) !important;
        animation-play-state: running, paused;   /* al interactuar, el vaivén se congela: el contenido queda estable */
    }
    /* Causa raíz y Solución: se elevan y el halo azul sube de intensidad */
    :is(
        div[data-testid="stVerticalBlockBorderWrapper"]:has(> .st-key-card_solucion),
        div:not([data-testid="stVerticalBlockBorderWrapper"]) > .st-key-card_solucion,
        div[data-testid="stVerticalBlockBorderWrapper"]:has(> .st-key-card_causa),
        div:not([data-testid="stVerticalBlockBorderWrapper"]) > .st-key-card_causa
    ):hover {
        transform: translateY(-8px);
        box-shadow: var(--shadow-halo-hover) !important;
        animation-play-state: running, paused;
    }
}

.field-label {
    font-family: 'JetBrains Mono', monospace;
    font-size: 11px;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: var(--coral);
    margin: 12px 0 2px 0;
}
.txt-sintoma {
    font-size: 14.5px;
    line-height: 1.6;
    color: var(--text-soft);
    max-width: 78ch;
}
.txt-causa {
    font-size: 18.5px;
    font-weight: 500;
    line-height: 1.55;
    color: #FFFFFF;
    max-width: 70ch;
}
.txt-sintoma strong, .txt-causa strong { color: #FFFFFF; font-weight: 700; }
.txt-causa strong { color: var(--coral-soft); }
.result-head { display: flex; align-items: center; gap: 10px; margin: 26px 0 12px 0; }
.result-title {
    font-family: 'Fraunces', serif;
    font-weight: 600;
    font-size: 28px;
    color: var(--text);
}
.card-head { display: flex; align-items: center; justify-content: space-between; gap: 10px; margin-bottom: 6px; }
.card-title { font-family: 'Fraunces', serif; font-weight: 600; font-size: 22px; color: var(--text); }
.card-title::before {
    content: "";
    display: inline-block;
    width: 9px;
    height: 9px;
    border-radius: 50%;
    margin-right: 10px;
    vertical-align: middle;
}
.t-causa::before { background: var(--coral); box-shadow: 0 0 10px rgba(245, 184, 75, 0.7); }
.t-solucion::before { background: var(--violet); box-shadow: 0 0 10px rgba(127, 166, 255, 0.7); }
.badge {
    font-family: 'JetBrains Mono', monospace;
    font-size: 11px;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    border-radius: 999px;
    padding: 3px 10px;
    border: 1px solid currentColor;
}
.badge-alta { color: var(--ok); background: rgba(110, 231, 183, 0.10); }
.badge-media { color: var(--warn); background: rgba(252, 211, 77, 0.10); }
.badge-baja { color: var(--bad); background: rgba(253, 164, 175, 0.10); }

/* ---------- Fuentes ---------- */
.src-row {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 8px;
    margin-top: 14px;
    padding-top: 12px;
    border-top: 1px solid rgba(255, 255, 255, 0.12);
}
.src-label {
    font-family: 'JetBrains Mono', monospace;
    font-size: 11px;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: var(--text-mute);
}
.src-chip {
    font-family: 'JetBrains Mono', monospace;
    font-size: 12px;
    color: var(--text-soft);
    background: var(--glass);
    border: 1px solid var(--glass-border);
    border-radius: 999px;
    padding: 3px 11px;
}
.empty-state {
    background: var(--glass);
    border: 1px dashed rgba(255, 255, 255, 0.28);
    border-radius: 18px;
    padding: 22px 24px;
    backdrop-filter: blur(12px);
}
.empty-title { font-family: 'Fraunces', serif; font-weight: 600; font-size: 21px; color: var(--text); margin-bottom: 6px; }
.empty-text { font-size: 14.5px; color: var(--text-soft); }
.timing { font-family: 'JetBrains Mono', monospace; font-size: 12px; color: var(--text-mute); margin: 10px 0 14px 2px; }

/* ---------- Evidencias ---------- */
div[data-testid="stExpander"] details {
    background: var(--card-violet-soft);
    border: 1px solid var(--card-border);
    border-radius: 14px;
    -webkit-backdrop-filter: blur(18px) saturate(1.15);
    backdrop-filter: blur(18px) saturate(1.15);
}
div[data-testid="stExpander"] summary { color: var(--text-soft); }
/* Abierto, Streamlit le pone a la barra del título un fondo gris claro y el texto claro
   queda ilegible: se deja transparente sobre la tarjeta azul y se da feedback al hover. */
div[data-testid="stExpander"] summary,
div[data-testid="stExpander"] details[open] > summary {
    background: transparent !important;
    border-radius: 14px;
}
div[data-testid="stExpander"] summary:hover,
div[data-testid="stExpander"] details[open] > summary:hover {
    background: rgba(255, 255, 255, 0.07) !important;
    color: #FFFFFF;
}
.ev-item { padding: 12px 0; border-bottom: 1px solid rgba(255, 255, 255, 0.10); }
.ev-item:last-child { border-bottom: none; }
.ev-meta { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; margin-bottom: 8px; }
.ev-tipo {
    font-family: 'JetBrains Mono', monospace;
    font-size: 10.5px;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--violet);
    background: rgba(127, 166, 255, 0.12);
    border: 1px solid rgba(127, 166, 255, 0.30);
    border-radius: 999px;
    padding: 2px 9px;
}
.ev-src { font-family: 'JetBrains Mono', monospace; font-size: 12px; color: var(--text-soft); }
.ev-used {
    font-size: 11px;
    color: var(--ok);
    background: rgba(110, 231, 183, 0.10);
    border: 1px solid rgba(110, 231, 183, 0.30);
    border-radius: 999px;
    padding: 2px 9px;
}
.ev-bar { height: 4px; border-radius: 999px; background: rgba(255, 255, 255, 0.10); overflow: hidden; }
.ev-fill { height: 100%; border-radius: 999px; background: linear-gradient(90deg, var(--coral), var(--pink)); }
.ev-rel { font-size: 11.5px; color: var(--text-mute); margin: 4px 0 8px 0; }
.ev-best {
    font-size: 11px;
    color: var(--coral-soft);
    background: rgba(245, 184, 75, 0.12);
    border: 1px solid rgba(245, 184, 75, 0.34);
    border-radius: 999px;
    padding: 2px 9px;
}
.ev-note {
    font-size: 12.5px;
    line-height: 1.55;
    color: var(--text-mute);
    padding: 2px 0 12px 0;
    border-bottom: 1px solid rgba(255, 255, 255, 0.10);
}
.ev-note b { color: var(--text-soft); font-weight: 600; }
.badge[title] { cursor: help; }
.ev-text {
    font-size: 13.5px;
    line-height: 1.5;
    color: var(--text-soft);
    border-left: 2px solid rgba(245, 184, 75, 0.55);
    padding-left: 12px;
}

/* ---------- Sidebar ---------- */
section[data-testid="stSidebar"] {
    background: var(--sidebar);
    border-right: 1px solid var(--glass-border);
}
section[data-testid="stSidebar"] h3 { font-family: 'Fraunces', serif; color: var(--text); }
section[data-testid="stFileUploaderDropzone"] {
    background: var(--glass);
    border: 1.5px dashed rgba(255, 255, 255, 0.28);
    border-radius: 14px;
}
section[data-testid="stFileUploaderDropzone"] button {
    border-radius: 10px;
    border: 1px solid var(--glass-border);
    background: var(--glass-strong);
    color: var(--text);
}
.sb-note { font-size: 13px; color: var(--text-soft); line-height: 1.45; margin-bottom: 14px; }

/* ---------- Mobile ---------- */
@media (max-width: 640px) {
    .hero-title { font-size: 36px; }
    .hero-compact .hero-title { font-size: 24px; }
    .txt-causa { font-size: 17px; }
    div[data-testid="stButton"] button,
    div[data-testid="stDownloadButton"] button {
        min-height: 44px;
        padding: 0.55rem 1rem;
    }
    div[data-testid="stFormSubmitButton"] button {
        padding: 0.8rem 1rem;
    }
}
</style>
"""
# Inyecta el CSS en la página (unsafe_allow_html permite renderizar la etiqueta <style>)
st.markdown(CSS, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def extraer_texto_pdf(contenido: bytes) -> str:
    """Extrae el texto de un PDF (cacheado por contenido, no se repite en cada clic)."""
    # PyPDFLoader necesita una ruta en disco, así que se guarda el PDF en un archivo temporal
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(contenido)
        ruta_temp = tmp.name
    try:
        documentos = PyPDFLoader(ruta_temp).load()
        # Une el texto de todas las páginas, separadas por una línea en blanco
        return "\n\n".join(doc.page_content for doc in documentos)
    finally:
        # Siempre borra el temporal, aunque la lectura falle
        os.remove(ruta_temp)


@st.cache_data(show_spinner=False)
def cargar_imagen_base64(ruta: str):
    """Devuelve la imagen en base64 o None si el archivo no existe."""
    try:
        with open(ruta, "rb") as f:
            return base64.b64encode(f.read()).decode()
    except OSError:
        # Si el archivo falta o no se puede leer, la app sigue sin ilustración
        return None


def usar_ejemplo(texto: str):
    """Callback de los chips: rellena el buscador y dispara la búsqueda."""
    st.session_state["pregunta_input"] = texto
    st.session_state["lanzar"] = True


def nueva_consulta():
    """Callback de 'Nueva consulta': limpia el buscador y el resultado anterior."""
    st.session_state["pregunta_input"] = ""
    st.session_state.pop("ultimo", None)


def html_hero(compacto: bool) -> str:
    """Hero completo (con ilustración) o compacto (una línea) para subir el resultado."""
    # Versión compacta: una sola línea, se usa cuando ya hay una consulta en curso o resultado
    if compacto:
        return (
            '<div class="hero hero-compact">'
            '<div class="hero-eyebrow"><b>⚙</b> LogisCore :: Root Cause Agent</div>'
            '<div class="hero-title">Del síntoma a la <em>causa raíz</em></div>'
            "</div>"
        )

    # Versión completa: título, subtítulo y (si existe) la ilustración
    hero = (
        '<div class="hero">'
        '<div class="hero-eyebrow"><b>⚙</b> LogisCore :: Root Cause Agent</div>'
        '<div class="hero-title">Del síntoma a la <em>causa raíz</em></div>'
        '<div class="hero-sub">Preguntá sobre cualquier incidente y te ayudo a encontrar la causa raíz y la solución.</div>'
        "</div>"
    )
    img_base64 = cargar_imagen_base64(RUTA_IMAGEN)
    # Solo agrega la imagen si se pudo cargar
    if img_base64:
        hero += (
            f'<div class="hero-img"><img src="data:image/jpeg;base64,{img_base64}" '
            'alt="Diagrama de causa raíz"></div>'
        )
    return hero


def texto_a_html(texto: str) -> str:
    """Escapa el texto del modelo y respeta la **negrita** markdown (único formato que se le pide)."""
    # Primero se escapa todo el HTML para evitar inyección desde la salida del modelo
    seguro = html.escape(texto.strip())
    # Convierte **texto** en <strong>texto</strong>
    seguro = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", seguro, flags=re.DOTALL)
    return seguro.replace("\n", "<br>")


def fuentes_usadas(evidencias: list) -> list:
    """Lista única de (archivo, página) de las evidencias que el modelo usó."""
    vistas, resultado = set(), []
    # Recorre cada evidencia recuperada
    for ev in evidencias:
        # Se ignoran las evidencias que el modelo no usó en el análisis
        if not ev.get("usada"):
            continue
        clave = (ev["fuente"], ev["pagina"])
        # Evita repetir la misma fuente/página
        if clave not in vistas:
            vistas.add(clave)
            resultado.append(clave)
    return resultado


def html_fuentes(evidencias: list) -> str:
    """Fila de chips con las fuentes que sustentan la respuesta."""
    fuentes = fuentes_usadas(evidencias)
    # Sin fuentes usadas no se muestra la fila
    if not fuentes:
        return ""
    # Un chip por fuente; agrega el número de página solo si existe
    chips = "".join(
        f'<span class="src-chip">{html.escape(f)}{f" · p. {p}" if p else ""}</span>'
        for f, p in fuentes
    )
    return f'<div class="src-row"><span class="src-label">Fuentes</span>{chips}</div>'


# Nota explicativa que se muestra arriba de la lista de evidencias
NOTA_EVIDENCIAS = (
    '<div class="ev-note"><b>Similitud</b>: qué tan parecido es cada fragmento a tu consulta '
    "(lo mide el buscador); la barra compara los fragmentos entre sí. "
    "<b>Confianza</b>: cuánto respalda el contexto la respuesta; la estima el modelo y se baja "
    "si la similitud es débil.</div>"
)


def texto_ayuda_confianza(resultado: dict, confianza: str) -> str:
    """Texto del tooltip del indicador de Confianza: explica de dónde sale."""
    # Sin evidencias, la confianza es solo la estimación del modelo
    if not resultado.get("evidencias"):
        return "Estimada por el modelo según cuánto respalda el contexto la respuesta."
    texto = (
        "Combina el juicio del modelo con qué tan parecidas son las evidencias "
        "recuperadas a tu consulta."
    )
    # Si la confianza se bajó por similitud débil, se explica el ajuste
    if resultado.get("ajustada") and resultado.get("similitud_base") is not None:
        pct = int(round(resultado["similitud_base"] * 100))
        texto += (
            f" El modelo estimó «{resultado.get('confianza_modelo')}», pero la mejor evidencia "
            f"usada tiene una similitud de {pct}%, así que se muestra «{confianza}»."
        )
    return texto


def html_evidencias(evidencias: list) -> str:
    """Arma el HTML de la lista de evidencias (una sola línea por fragmento, escapado)."""
    items = []
    # Una entrada visual por cada evidencia recuperada
    for ev in evidencias:
        # Similitud real del buscador (ev["relevancia"] queda como respaldo para datos viejos).
        sim = max(0.0, min(1.0, ev.get("puntaje", ev.get("relevancia", 0.0))))
        pct = int(round(sim * 100))
        # La barra compara con el fragmento más similar; si no hay dato, usa la similitud directa.
        ancho = int(round(max(0.0, min(1.0, ev.get("similitud_relativa", sim))) * 100))
        tipo = ETIQUETAS_TIPO.get(ev["tipo"], str(ev["tipo"]).capitalize())
        # La página se muestra solo si el fragmento la tiene
        pagina = f" · p. {ev['pagina']}" if ev["pagina"] else ""
        # Etiquetas opcionales según el estado de la evidencia
        mejor = '<span class="ev-best">mejor coincidencia</span>' if ev.get("mejor") else ""
        usada = '<span class="ev-used">usada en el análisis</span>' if ev.get("usada") else ""

        # Compacta saltos de línea y recorta el fragmento si es muy largo
        texto = re.sub(r"\s*\n\s*", " ", ev["texto"]).strip()
        if len(texto) > MAX_CHARS_EVIDENCIA:
            texto = texto[:MAX_CHARS_EVIDENCIA].rstrip() + "…"

        items.append(
            '<div class="ev-item">'
            f'<div class="ev-meta"><span class="ev-tipo">{html.escape(tipo)}</span>'
            f'<span class="ev-src">{html.escape(ev["fuente"])}{pagina}</span>{mejor}{usada}</div>'
            f'<div class="ev-bar" title="La barra compara este fragmento con el más similar">'
            f'<div class="ev-fill" style="width:{ancho}%"></div></div>'
            f'<div class="ev-rel">Similitud {pct}%</div>'
            f'<div class="ev-text">{html.escape(texto)}</div>'
            "</div>"
        )
    return NOTA_EVIDENCIAS + "".join(items)


def construir_markdown(pregunta: str, analisis, evidencias: list) -> str:
    """Texto del análisis para descargar como .md."""
    lineas = [
        "# Análisis de causa raíz",
        "",
        f"**Consulta:** {pregunta}",
        f"**Confianza:** {analisis.confianza}",
        "",
    ]
    # El síntoma es opcional: solo se agrega si el modelo lo devolvió
    if analisis.incidente:
        lineas += ["## Síntoma", analisis.incidente, ""]
    lineas += ["## Causa raíz", analisis.causa_raiz, ""]
    # La solución también es opcional
    if analisis.solucion:
        lineas += ["## Solución", analisis.solucion, ""]
    fuentes = fuentes_usadas(evidencias)
    # Sección de fuentes solo si hay evidencias usadas
    if fuentes:
        lineas += ["## Fuentes"]
        lineas += [f"- {f}" + (f", p. {p}" if p else "") for f, p in fuentes]
        lineas += [""]
    return "\n".join(lineas)


def mostrar_resultado(resultado: dict, origen: str, pregunta: str):
    """Pinta el análisis estructurado: causa raíz, solución, evidencias, tiempos y acciones."""
    analisis = resultado["analisis"]
    evidencias = resultado["evidencias"]

    st.markdown(
        '<div class="result-head"><span class="result-title">Análisis</span></div>',
        unsafe_allow_html=True,
    )

    # Si el agente no encontró información, se muestra un estado vacío con sugerencias
    if not analisis.encontrado:
        st.markdown(
            '<div class="empty-state">'
            '<div class="empty-title">No encuentro esa información en la documentación disponible</div>'
            '<div class="empty-text">Probá reformulando con el síntoma que observás '
            "(por ejemplo, qué ve el cliente o qué sistema falla) o elegí uno de los ejemplos.</div>"
            "</div>",
            unsafe_allow_html=True,
        )
    else:
        # Tarjeta de causa raíz (con acento ámbar)
        with st.container(border=True, key="card_causa"):
            st.markdown('<div class="card-accent"></div>', unsafe_allow_html=True)
            st.markdown(
                '<div class="card-head"><span class="card-title t-causa">Causa raíz</span>'
                f'<span class="badge badge-{analisis.confianza}" '
                f'title="{html.escape(texto_ayuda_confianza(resultado, analisis.confianza), quote=True)}">'
                f'Confianza {analisis.confianza}</span></div>',
                unsafe_allow_html=True,
            )
            # El síntoma solo se muestra si el modelo lo devolvió
            if analisis.incidente:
                st.markdown('<div class="field-label">Síntoma</div>', unsafe_allow_html=True)
                st.markdown(
                    f'<div class="txt-sintoma">{texto_a_html(analisis.incidente)}</div>',
                    unsafe_allow_html=True,
                )
            st.markdown('<div class="field-label">Causa</div>', unsafe_allow_html=True)
            st.markdown(
                f'<div class="txt-causa">{texto_a_html(analisis.causa_raiz)}</div>',
                unsafe_allow_html=True,
            )
            fuentes_html = html_fuentes(evidencias)
            # Los chips de fuentes se agregan solo si hay alguna
            if fuentes_html:
                st.markdown(fuentes_html, unsafe_allow_html=True)

        # Tarjeta de solución
        with st.container(border=True, key="card_solucion"):
            st.markdown('<div class="card-head"><span class="card-title t-solucion">Solución</span></div>', unsafe_allow_html=True)
            # Si no hay solución, se avisa en vez de dejar la tarjeta vacía
            if analisis.solucion:
                st.markdown(analisis.solucion)
            else:
                st.caption("La documentación no propone una solución para este caso.")

    # Lista desplegable con las evidencias recuperadas
    if evidencias:
        with st.expander(f"Evidencias recuperadas ({len(evidencias)})"):
            st.markdown(html_evidencias(evidencias), unsafe_allow_html=True)

    # Línea de tiempos: solo incluye los tiempos que realmente se midieron
    partes = []
    if resultado["t_busqueda"]:
        partes.append(f"Búsqueda {resultado['t_busqueda']:.1f} s")
    if resultado["t_modelo"]:
        partes.append(f"Modelo {resultado['t_modelo']:.1f} s")
    partes.append(origen)
    st.markdown(f'<div class="timing">{" · ".join(partes)}</div>', unsafe_allow_html=True)

    # Acciones sobre el resultado
    col_descarga, col_nueva, _ = st.columns([1.5, 1.1, 2.4])
    with col_descarga:
        # Solo se ofrece la descarga si hubo un análisis encontrado
        if analisis.encontrado:
            contenido_md = construir_markdown(pregunta, analisis, evidencias)
            try:
                # Versiones nuevas de Streamlit: on_click="ignore" evita recargar la app al descargar
                st.download_button(
                    "⬇ Descargar análisis",
                    data=contenido_md,
                    file_name="analisis_causa_raiz.md",
                    mime="text/markdown",
                    key="descargar",
                    on_click="ignore",
                    use_container_width=True,
                )
            except Exception:
                # Versiones anteriores no aceptan on_click="ignore": se usa la llamada clásica
                st.download_button(
                    "⬇ Descargar análisis",
                    data=contenido_md,
                    file_name="analisis_causa_raiz.md",
                    mime="text/markdown",
                    key="descargar",
                    use_container_width=True,
                )
    with col_nueva:
        st.button("Nueva consulta", key="nueva", on_click=nueva_consulta, use_container_width=True)


# ---------------------------------------------------------------------------
# Sidebar: documentos propios
# ---------------------------------------------------------------------------
st.sidebar.markdown("### 📄 Tus documentos")
st.sidebar.markdown(
    '<div class="sb-note">Si no cargás nada, se usa la base de conocimiento '
    "de LogisCore por defecto.</div>",
    unsafe_allow_html=True,
)

# Dos cargadores de PDF: uno de incidentes y otro de causas raíz
archivo_incidentes = st.sidebar.file_uploader("Incidents (PDF)", type="pdf", key="incidents")
archivo_causa_raiz = st.sidebar.file_uploader("Root Cause (PDF)", type="pdf", key="root_cause")

# Solo se usan PDFs propios si están cargados los dos
usa_pdfs_propios = bool(archivo_incidentes and archivo_causa_raiz)

# Mensajes de estado en el sidebar según lo cargado
if (archivo_incidentes or archivo_causa_raiz) and not usa_pdfs_propios:
    # Falta uno de los dos: se avisa y se mantiene la base por defecto
    st.sidebar.warning(
        "Falta uno de los dos PDFs. Hasta que cargues ambos, "
        "se usa la base de LogisCore por defecto."
    )
elif usa_pdfs_propios:
    # Ambos cargados: se confirma el uso de los PDFs propios
    st.sidebar.success("Usando tus PDFs como contexto.")

# ---------------------------------------------------------------------------
# Hero
# ---------------------------------------------------------------------------
# Espacio reservado: el hero se dibuja más abajo, cuando ya se sabe si hay consulta o resultado
hero_slot = st.empty()

# ---------------------------------------------------------------------------
# Buscador
# ---------------------------------------------------------------------------
# Formulario de búsqueda: el texto y el botón viajan juntos al presionar Enter o "Investigar"
with st.form("form_busqueda", clear_on_submit=False, border=False):
    col_input, col_boton = st.columns([4.8, 1.7], vertical_alignment="center")  # botón un poco más ancho
    with col_input:
        st.text_input(
            "¿Qué incidente querés investigar?",
            placeholder="Describí el incidente: ¿Por qué se cobra dos veces?",
            key="pregunta_input",
            label_visibility="collapsed",
        )
    with col_boton:
        enviado = st.form_submit_button("✦ Investigar", use_container_width=True)

st.markdown('<div class="chips-label">Probá con un ejemplo</div>', unsafe_allow_html=True)
columnas = st.columns(len(EJEMPLOS))
# Un chip por ejemplo; al hacer clic rellena el buscador y lanza la búsqueda
for col, ejemplo in zip(columnas, EJEMPLOS):
    col.button(ejemplo, key=f"chip_{ejemplo}", on_click=usar_ejemplo, args=(ejemplo,), use_container_width=True)

# Texto que indica de dónde saldrá la respuesta
fuente_activa = "tus PDFs cargados" if usa_pdfs_propios else "base de conocimiento de LogisCore"
st.markdown(
    f'<div class="hint">Fuente activa: <b>{fuente_activa}</b> · '
    "¿Tenés tus propios documentos? Abrí el panel lateral (<b>»</b>) y cargá tus PDFs.</div>",
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Ejecución
# ---------------------------------------------------------------------------
# Se lanza la búsqueda al enviar el formulario o al elegir un chip de ejemplo
lanzar = enviado or st.session_state.pop("lanzar", False)
pregunta = st.session_state.get("pregunta_input", "").strip()

# El hero se compacta cuando ya hay un resultado o una consulta en curso
hero_compacto = bool(st.session_state.get("ultimo")) or (lanzar and bool(pregunta))
hero_slot.markdown(html_hero(hero_compacto), unsafe_allow_html=True)

if lanzar:
    # Sin texto en el buscador no hay nada que analizar
    if not pregunta:
        st.warning("Por favor escribí una pregunta.")
    else:
        # Descarta el resultado anterior antes de calcular el nuevo
        st.session_state.pop("ultimo", None)
        resultado = None
        origen = ""
        try:
            with st.spinner("🔍 Analizando el incidente..."):
                # Camino 1: el usuario cargó sus propios PDFs
                if usa_pdfs_propios:
                    contexto_incidentes = extraer_texto_pdf(archivo_incidentes.getvalue())
                    contexto_causa_raiz = extraer_texto_pdf(archivo_causa_raiz.getvalue())

                    # Si algún PDF supera el límite, se avisa que se recorta
                    if len(contexto_incidentes) > MAX_CHARS_PDF or len(contexto_causa_raiz) > MAX_CHARS_PDF:
                        st.info(
                            f"Algún PDF es muy largo: se usan los primeros {MAX_CHARS_PDF:,} caracteres de cada uno."
                        )
                    contexto_manual = (
                        f"{contexto_incidentes[:MAX_CHARS_PDF]}\n\n---\n\n"
                        f"{contexto_causa_raiz[:MAX_CHARS_PDF]}"
                    )

                    resultado = responder_desde_texto(pregunta, contexto_manual)
                    origen = "Fuente: tus PDFs cargados"
                # Camino 2: se usa la base de conocimiento por defecto (RAG con Pinecone)
                else:
                    resultado = responder_estructurado(pregunta)
                    origen = "Fuente: base de conocimiento de LogisCore"
        except Exception as e:
            # Cualquier fallo (modelo, Pinecone, PDF) se muestra con un mensaje claro y el detalle técnico
            st.error("No pude completar el análisis. Revisá la conexión con el modelo o con Pinecone e intentá de nuevo.")
            with st.expander("Ver detalle técnico"):
                st.code(f"{type(e).__name__}: {e}")

        # Guarda el resultado para que sobreviva a los reruns de Streamlit
        if resultado:
            st.session_state["ultimo"] = {"resultado": resultado, "origen": origen, "pregunta": pregunta}

# Pinta el último resultado guardado (si lo hay)
ultimo = st.session_state.get("ultimo")
if ultimo:
    mostrar_resultado(ultimo["resultado"], ultimo["origen"], ultimo["pregunta"])