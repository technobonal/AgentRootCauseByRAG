import os
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from tools import buscar_incidente

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

llm = ChatGroq(
    model="openai/gpt-oss-120b",
    api_key=GROQ_API_KEY,
    temperature=0.2,
    max_tokens=1024
)

# Prompt template con rol y restricciones
prompt_template = ChatPromptTemplate.from_messages([
    ("system", """Sos un Analista de Causa Raíz (Root Cause Analyst) especializado en sistemas de software.

Tu tarea es ayudar a identificar el INCIDENTE (síntoma) y su CAUSA RAÍZ técnica correspondiente,
basándote únicamente en el contexto proporcionado sobre el sistema LogisCore.

Reglas que debés seguir siempre:
1. Respondé SOLO con información presente en el contexto. Si no está la respuesta ahí, decí
   claramente: "No encuentro esa información en la documentación disponible."
2. Estructurá tu respuesta en dos partes claras: "Incidente:" y "Causa Raíz:"
3. Sé conciso y técnico, máximo 4-5 oraciones en total.
4. No inventes nombres de incidentes, códigos de error, ni soluciones que no estén en el contexto.
5. Si el contexto incluye una solución técnica propuesta, mencionala brevemente al final.

Contexto disponible:
{contexto}
"""),
    ("human", "{pregunta}")
])

def responder(pregunta: str, contexto: str) -> str:
    mensaje = prompt_template.format_messages(pregunta=pregunta, contexto=contexto)
    respuesta = llm.invoke(mensaje)
    return respuesta.content


if __name__ == "__main__":
    from tools import buscar_incidente

    pregunta = "¿Por qué se congela el rastreo los viernes?"
    contexto = buscar_incidente(pregunta)
    respuesta = responder(pregunta, contexto)

    print("🤖 Respuesta del agente:\n")
    print(respuesta)