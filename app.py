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
st.set_page_config(
    page_title="LogisCore RCA Agent",
    page_icon="🔧",
    layout="centered",
    initial_sidebar_state="expanded",
)

RUTA_IMAGEN = "assets/fishbone.jpg"
MAX_CHARS_PDF = 60000  # límite de texto por PDF para no saturar el prompt
MAX_CHARS_EVIDENCIA = 600  # largo máximo del fragmento mostrado en cada evidencia

EJEMPLOS = [
    "¿Por qué se cobra dos veces?",
    "¿Por qué se demora una entrega?",
    "¿Por qué falla el inventario?",
]

ETIQUETAS_TIPO = {"incidente": "Incidente", "causa_raiz": "Causa raíz"}

# ---------------------------------------------------------------------------
# Estilos: ciruela medio + vidrio translúcido (opción A).
# Todos los colores viven en variables CSS (:root).
# ---------------------------------------------------------------------------
CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,600;9..144,700&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap');
:root {
    --bg-top: #2B1B36;
    --bg-mid: #3D2450;
    --bg-bottom: #4A2D5C;
    --text: #F6EEF9;
    --text-soft: #CDBBD6;
    --text-mute: #A992B5;
    --glass: rgba(255, 255, 255, 0.08);
    --glass-strong: rgba(255, 255, 255, 0.12);
    --glass-border: rgba(255, 255, 255, 0.17);
    --coral: #FF8A65;
    --pink: #F472B6;
    --violet: #C04BD6;
    --ok: #6EE7B7;
    --warn: #FCD34D;
    --bad: #FDA4AF;
    --pattern: rgba(255, 255, 255, 0.055);
    --sidebar: rgba(28, 16, 38, 0.94);
}
html, body, [class*="css"], .stApp {
    font-family: 'Inter', sans-serif;
    color: var(--text);
}
.stApp {
    background-color: var(--bg-top);
    background-image:
        radial-gradient(900px 420px at 50% -6%, rgba(244, 114, 182, 0.24), transparent 62%),
        repeating-linear-gradient(45deg, var(--pattern) 0 1px, transparent 1px 64px),
        repeating-linear-gradient(-45deg, var(--pattern) 0 1px, transparent 1px 64px),
        linear-gradient(180deg, var(--bg-top) 0%, var(--bg-mid) 55%, var(--bg-bottom) 100%);
    background-attachment: fixed;
}
header[data-testid="stHeader"] { background: transparent; }
div[data-testid="stAppDeployButton"], .stAppDeployButton { display: none; }
.block-container { padding-top: 2.5rem; max-width: 840px; }
/* ---------- Hero ---------- */
.hero { text-align: center; margin: 0.5rem 0 1.2rem 0; }
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
    margin-bottom: 18px;
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
    margin: 0 0 12px 0;
}
.hero-title em {
    font-style: normal;
    background: linear-gradient(90deg, #FFB199, var(--pink));
    -webkit-background-clip: text;
    background-clip: text;
    color: transparent;
}
.hero-sub { font-size: 17px; color: var(--text-soft); margin: 0 auto; max-width: 520px; text-wrap: balance; }
.hero-img { text-align: center; margin: 4px 0 8px 0; }
.hero-img img {
    width: 260px;
    mix-blend-mode: screen;
    opacity: 0.9;
    filter: grayscale(100%) brightness(1.3) contrast(1.1);
    -webkit-mask-image: radial-gradient(closest-side, #000 55%, transparent 100%);
    mask-image: radial-gradient(closest-side, #000 55%, transparent 100%);
}
/* ---------- Buscador (el st.form es la barra completa) ---------- */
div[data-testid="stForm"] {
    border: 1.5px solid transparent !important;
    border-radius: 18px;
    padding: 8px 10px;
    background:
        linear-gradient(rgba(34, 20, 45, 0.88), rgba(34, 20, 45, 0.88)) padding-box,
        linear-gradient(90deg, var(--coral), var(--violet)) border-box;
    box-shadow: 0 12px 40px rgba(0, 0, 0, 0.28), 0 0 0 5px rgba(192, 75, 214, 0.08);
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
div[data-testid="stTextInput"] input::placeholder { color: var(--text-mute) !important; opacity: 1; }
div[data-testid="InputInstructions"] { display: none; }
div[data-testid="stFormSubmitButton"] button {
    border: none;
    border-radius: 12px;
    padding: 0.65rem 0.8rem;
    font-weight: 600;
    font-size: 15px;
    color: #FFFFFF;
    background: linear-gradient(90deg, var(--coral), var(--pink));
    box-shadow: 0 6px 18px rgba(244, 114, 182, 0.30);
    transition: transform 0.12s ease, box-shadow 0.12s ease;
}
div[data-testid="stFormSubmitButton"] button:hover {
    transform: translateY(-1px);
    box-shadow: 0 10px 26px rgba(244, 114, 182, 0.42);
    color: #FFFFFF;
    border: none;
}
div[data-testid="stFormSubmitButton"] button:active { transform: translateY(0); }
/* ---------- Chips de ejemplo ---------- */
div[data-testid="stButton"] button {
    border-radius: 999px;
    border: 1px solid var(--glass-border);
    background: var(--glass);
    color: var(--text-soft);
    font-size: 13.5px;
    padding: 0.4rem 0.9rem;
    backdrop-filter: blur(8px);
    transition: border-color 0.12s ease, color 0.12s ease, background 0.12s ease;
}
div[data-testid="stButton"] button:hover {
    border-color: var(--coral);
    color: #FFFFFF;
    background: var(--glass-strong);
}
.chips-label { font-size: 12.5px; color: var(--text-mute); text-align: center; margin: 16px 0 6px 0; }
/* ---------- Tarjetas de resultado (vidrio) ---------- */
div[data-testid="stVerticalBlockBorderWrapper"] {
    background: var(--glass);
    border: 1px solid var(--glass-border);
    border-radius: 18px;
    backdrop-filter: blur(14px);
    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.22);
}
div[data-testid="stVerticalBlockBorderWrapper"]:has(.card-accent),
.st-key-card_causa {
    border: 1.5px solid rgba(255, 138, 101, 0.60) !important;
    background: linear-gradient(135deg, rgba(255, 138, 101, 0.16), rgba(244, 114, 182, 0.09)) !important;
    box-shadow: 0 10px 34px rgba(244, 114, 182, 0.22) !important;
}
.result-head { display: flex; align-items: center; gap: 10px; margin: 30px 0 12px 0; }
.result-title {
    font-family: 'Fraunces', serif;
    font-weight: 600;
    font-size: 28px;
    color: var(--text);
}
.pill {
    font-family: 'JetBrains Mono', monospace;
    font-size: 11px;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--coral);
    background: rgba(255, 138, 101, 0.12);
    border: 1px solid rgba(255, 138, 101, 0.35);
    border-radius: 999px;
    padding: 3px 10px;
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
.t-causa::before { background: var(--coral); box-shadow: 0 0 10px rgba(255, 138, 101, 0.7); }
.t-solucion::before { background: var(--violet); box-shadow: 0 0 10px rgba(192, 75, 214, 0.7); }
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
.empty-state {
    background: var(--glass);
    border: 1px dashed rgba(255, 255, 255, 0.28);
    border-radius: 18px;
    padding: 22px 24px;
    backdrop-filter: blur(12px);
}
.empty-title { font-family: 'Fraunces', serif; font-weight: 600; font-size: 21px; color: var(--text); margin-bottom: 6px; }
.empty-text { font-size: 14.5px; color: var(--text-soft); }
.timing { font-family: 'JetBrains Mono', monospace; font-size: 12px; color: var(--text-mute); margin: 10px 0 0 2px; }
/* ---------- Evidencias ---------- */
div[data-testid="stExpander"] details {
    background: var(--glass);
    border: 1px solid var(--glass-border);
    border-radius: 14px;
    backdrop-filter: blur(12px);
}
div[data-testid="stExpander"] summary { color: var(--text-soft); }
.ev-item { padding: 12px 0; border-bottom: 1px solid rgba(255, 255, 255, 0.10); }
.ev-item:last-child { border-bottom: none; }
.ev-meta { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; margin-bottom: 8px; }
.ev-tipo {
    font-family: 'JetBrains Mono', monospace;
    font-size: 10.5px;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--pink);
    background: rgba(244, 114, 182, 0.12);
    border: 1px solid rgba(244, 114, 182, 0.30);
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
.ev-text {
    font-size: 13.5px;
    line-height: 1.5;
    color: var(--text-soft);
    border-left: 2px solid rgba(255, 138, 101, 0.55);
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
}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def extraer_texto_pdf(contenido: bytes) -> str:
    """Extrae el texto de un PDF (cacheado por contenido, no se repite en cada clic)."""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(contenido)
        ruta_temp = tmp.name
    try:
        documentos = PyPDFLoader(ruta_temp).load()
        return "\n\n".join(doc.page_content for doc in documentos)
    finally:
        os.remove(ruta_temp)


@st.cache_data(show_spinner=False)
def cargar_imagen_base64(ruta: str):
    """Devuelve la imagen en base64 o None si el archivo no existe."""
    try:
        with open(ruta, "rb") as f:
            return base64.b64encode(f.read()).decode()
    except OSError:
        return None


def usar_ejemplo(texto: str):
    """Callback de los chips: rellena el buscador y dispara la búsqueda."""
    st.session_state["pregunta_input"] = texto
    st.session_state["lanzar"] = True


def html_evidencias(evidencias: list) -> str:
    """Arma el HTML de la lista de evidencias (una sola línea por fragmento, escapado)."""
    items = []
    for ev in evidencias:
        pct = int(round(ev["relevancia"] * 100))
        tipo = ETIQUETAS_TIPO.get(ev["tipo"], str(ev["tipo"]).capitalize())
        pagina = f" · p. {ev['pagina']}" if ev["pagina"] else ""
        usada = '<span class="ev-used">usada en el análisis</span>' if ev.get("usada") else ""

        texto = re.sub(r"\s*\n\s*", " ", ev["texto"]).strip()
        if len(texto) > MAX_CHARS_EVIDENCIA:
            texto = texto[:MAX_CHARS_EVIDENCIA].rstrip() + "…"

        items.append(
            '<div class="ev-item">'
            f'<div class="ev-meta"><span class="ev-tipo">{html.escape(tipo)}</span>'
            f'<span class="ev-src">{html.escape(ev["fuente"])}{pagina}</span>{usada}</div>'
            f'<div class="ev-bar"><div class="ev-fill" style="width:{pct}%"></div></div>'
            f'<div class="ev-rel">Relevancia {pct}%</div>'
            f'<div class="ev-text">{html.escape(texto)}</div>'
            "</div>"
        )
    return "".join(items)


def mostrar_resultado(resultado: dict, origen: str):
    """Pinta el análisis estructurado: causa raíz, solución, evidencias y tiempos."""
    analisis = resultado["analisis"]
    evidencias = resultado["evidencias"]

    st.markdown(
        '<div class="result-head"><span class="result-title">Análisis</span>'
        '<span class="pill">Causa raíz · Solución</span></div>',
        unsafe_allow_html=True,
    )

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
        with st.container(border=True, key="card_causa"):
            st.markdown('<div class="card-accent"></div>', unsafe_allow_html=True)
            st.markdown(
                '<div class="card-head"><span class="card-title t-causa">Causa raíz</span>'
                f'<span class="badge badge-{analisis.confianza}">Confianza {analisis.confianza}</span></div>',
                unsafe_allow_html=True,
            )
            if analisis.incidente:
                st.markdown(f"**Incidente:** {analisis.incidente}")
            st.markdown(analisis.causa_raiz)

        with st.container(border=True, key="card_solucion"):
            st.markdown('<div class="card-head"><span class="card-title t-solucion">Solución</span></div>', unsafe_allow_html=True)
            if analisis.solucion:
                st.markdown(analisis.solucion)
            else:
                st.caption("La documentación no propone una solución para este caso.")

    if evidencias:
        with st.expander(f"Evidencias recuperadas ({len(evidencias)})"):
            st.markdown(html_evidencias(evidencias), unsafe_allow_html=True)

    partes = []
    if resultado["t_busqueda"]:
        partes.append(f"Búsqueda {resultado['t_busqueda']:.1f} s")
    if resultado["t_modelo"]:
        partes.append(f"Modelo {resultado['t_modelo']:.1f} s")
    partes.append(origen)
    st.markdown(f'<div class="timing">{" · ".join(partes)}</div>', unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Sidebar: documentos propios
# ---------------------------------------------------------------------------
st.sidebar.markdown("### 📄 Tus documentos")
st.sidebar.markdown(
    '<div class="sb-note">Si no cargás nada, se usa la base de conocimiento '
    "de LogisCore por defecto.</div>",
    unsafe_allow_html=True,
)

archivo_incidentes = st.sidebar.file_uploader("Incidents (PDF)", type="pdf", key="incidents")
archivo_causa_raiz = st.sidebar.file_uploader("Root Cause (PDF)", type="pdf", key="root_cause")

usa_pdfs_propios = bool(archivo_incidentes and archivo_causa_raiz)

if (archivo_incidentes or archivo_causa_raiz) and not usa_pdfs_propios:
    st.sidebar.warning(
        "Falta uno de los dos PDFs. Hasta que cargues ambos, "
        "se usa la base de LogisCore por defecto."
    )
elif usa_pdfs_propios:
    st.sidebar.success("Usando tus PDFs como contexto.")

# ---------------------------------------------------------------------------
# Hero
# ---------------------------------------------------------------------------
st.markdown(
    """<div class="hero">
<div class="hero-eyebrow"><b>⚙</b> LogisCore :: RCA Agent</div>
<div class="hero-title">Del síntoma a la <em>causa raíz</em></div>
<div class="hero-sub">Preguntá sobre cualquier incidente y te ayudo a encontrar la causa raíz y la solución.</div>
</div>""",
    unsafe_allow_html=True,
)

img_base64 = cargar_imagen_base64(RUTA_IMAGEN)
if img_base64:
    st.markdown(
        f'<div class="hero-img"><img src="data:image/jpeg;base64,{img_base64}" alt="Diagrama de causa raíz"></div>',
        unsafe_allow_html=True,
    )

# ---------------------------------------------------------------------------
# Buscador (st.form: Enter también envía la consulta)
# ---------------------------------------------------------------------------
with st.form("form_busqueda", clear_on_submit=False, border=False):
    col_input, col_boton = st.columns([5, 1.5], vertical_alignment="center")
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
for col, ejemplo in zip(columnas, EJEMPLOS):
    col.button(ejemplo, key=f"chip_{ejemplo}", on_click=usar_ejemplo, args=(ejemplo,), use_container_width=True)

# ---------------------------------------------------------------------------
# Ejecución
# ---------------------------------------------------------------------------
lanzar = enviado or st.session_state.pop("lanzar", False)
pregunta = st.session_state.get("pregunta_input", "").strip()

if lanzar:
    if not pregunta:
        st.warning("Por favor escribí una pregunta.")
    else:
        resultado = None
        origen = ""
        try:
            with st.spinner("🔍 Analizando el incidente..."):
                if usa_pdfs_propios:
                    contexto_incidentes = extraer_texto_pdf(archivo_incidentes.getvalue())
                    contexto_causa_raiz = extraer_texto_pdf(archivo_causa_raiz.getvalue())

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
                else:
                    resultado = responder_estructurado(pregunta)
                    origen = "Fuente: base de conocimiento de LogisCore"
        except Exception as e:
            st.error("No pude completar el análisis. Revisá la conexión con el modelo o con Pinecone e intentá de nuevo.")
            with st.expander("Ver detalle técnico"):
                st.code(f"{type(e).__name__}: {e}")

        if resultado:
            mostrar_resultado(resultado, origen)