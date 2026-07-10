import streamlit as st
from agente import responder, llm, prompt_template
from langchain_community.document_loaders import PyPDFLoader
import tempfile
import os
import base64

st.set_page_config(page_title="LogisCore RCA Agent", page_icon="🔧")

# --- Barra lateral: carga de PDFs propios ---
st.sidebar.header("📄 Cargar tus propios documentos")
st.sidebar.write("Si no cargás nada, se usa la base de conocimiento de LogisCore por defecto.")

archivo_incidentes = st.sidebar.file_uploader("Incidents (PDF)", type="pdf", key="incidents")
archivo_causa_raiz = st.sidebar.file_uploader("Root Cause (PDF)", type="pdf", key="root_cause")


def extraer_texto_pdf(archivo_subido):
    """Guarda el archivo subido temporalmente y extrae su texto."""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(archivo_subido.read())
        ruta_temp = tmp.name

    documentos = PyPDFLoader(ruta_temp).load()
    texto = "\n\n".join([doc.page_content for doc in documentos])

    os.remove(ruta_temp)
    return texto


# --- Título ---
st.markdown(
    """
    <h1 style="font-size: 42px; font-weight: 700; font-family: 'Courier New', monospace; color: #1a1a1a; letter-spacing: -1px; margin-bottom: 4px;">
        <span style="color: #5B7B9A;">⚙</span> LogisCore 
        <span style="color: #5B7B9A;">::</span> Root Cause Agent
    </h1>
    """,
    unsafe_allow_html=True
)

with open("assets/fishbone.jpg", "rb") as f:
    img_base64 = base64.b64encode(f.read()).decode()

st.markdown(
    f"""
    <div style="text-align: center;">
        <img src="data:image/jpeg;base64,{img_base64}" 
             style="width: 350px; filter: grayscale(100%) invert(90%); opacity: 0.5;">
    </div>
    """,
    unsafe_allow_html=True
)



st.markdown(
    """
    <p style="font-size: 18px; color: #1a1a1a; margin-bottom: 24px;">
        Preguntá sobre cualquier incidente y te ayudo a encontrar la <strong>causa raíz</strong> y la <strong>solución</strong>.
    </p>
    """,
    unsafe_allow_html=True
)

st.markdown(
    """
    <style>
    div[data-testid="stTextInput"] label p { font-size: 24px !important; font-weight: 600 !important; }
    div[data-testid="stTextInput"] input { font-size: 20px !important; padding: 12px !important; }
    </style>
    """,
    unsafe_allow_html=True
)

pregunta = st.text_input("¿Qué incidente querés investigar?", placeholder="Ej: ¿Por qué se cobra dos veces?")

if st.button("Buscar"):
    if pregunta.strip() == "":
        st.warning("Por favor escribí una pregunta.")
    else:
        with st.spinner("🔍 Analizando el incidente..."):

            # Si el usuario subió sus propios PDFs, usamos ESE contenido como contexto
            if archivo_incidentes and archivo_causa_raiz:
                contexto_incidentes = extraer_texto_pdf(archivo_incidentes)
                contexto_causa_raiz = extraer_texto_pdf(archivo_causa_raiz)
                contexto_manual = f"{contexto_incidentes}\n\n---\n\n{contexto_causa_raiz}"

                mensaje = prompt_template.format_messages(pregunta=pregunta, contexto=contexto_manual)
                respuesta = llm.invoke(mensaje).content
            else:
                # Si no subió nada, usamos el flujo normal (Pinecone con los documentos de LogisCore)
                respuesta = responder(pregunta)

        st.markdown("### 🤖 Respuesta:")
        st.markdown(respuesta)