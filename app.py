import streamlit as st
from agente import responder
import base64

st.set_page_config(page_title="LogisCore RCA Agent", page_icon="🔧")

st.title("🔧 LogisCore - Root Cause Agent")

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

st.write("Preguntá sobre cualquier incidente del sistema LogisCore y te ayudo a encontrar la causa raíz y solución.")

pregunta = st.text_input("¿Qué incidente querés investigar?", placeholder="Ej: ¿Por qué se cobra dos veces?")

if st.button("Buscar"):
    if pregunta.strip() == "":
        st.warning("Por favor escribí una pregunta.")
    else:
        with st.spinner("🔍 Analizando el incidente..."):
            respuesta = responder(pregunta)

        st.markdown("### 🤖 Respuesta:")
        st.markdown(respuesta)