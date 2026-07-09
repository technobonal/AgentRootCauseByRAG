import os
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from tools import buscar_incidente

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

llm = ChatGroq(
    model="openai/gpt-oss-120b",
    api_key=GROQ_API_KEY,
    temperature=0.2,
    max_tokens=800
)

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

# 🔗 Cadena LCEL: toma la pregunta, busca contexto, arma el prompt, genera y parsea
rag_chain = (
    {"contexto": lambda x: buscar_incidente(x["pregunta"]), "pregunta": lambda x: x["pregunta"]}
    | prompt_template
    | llm
    | StrOutputParser()
)

import time

def responder(pregunta: str) -> str:
    inicio = time.time()
    resultado = rag_chain.invoke({"pregunta": pregunta})
    duracion = time.time() - inicio
    print(f"⏱️  Tiempo total de la cadena (búsqueda + LLM): {duracion:.2f} segundos")
    return resultado


if __name__ == "__main__":
    preguntas = [
        "¿Por qué a los clientes se les cobra dos veces?"
        
    ]

    for pregunta in preguntas:
        respuesta = responder(pregunta)
        print(f"\n{'='*60}")
        print(f"❓ Pregunta: {pregunta}")
        print(f"{'='*60}")
        print(respuesta)