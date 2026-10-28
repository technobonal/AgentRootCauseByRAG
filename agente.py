import json
import os
import re
import time
from typing import List, Literal, Optional

from dotenv import load_dotenv
from pydantic import BaseModel, Field, field_validator
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from tools import buscar_incidente, buscar_con_fuentes

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# max_tokens sube de 800 a 2000: gpt-oss razona y esos tokens cuentan contra el límite,
# con salida estructurada el JSON podía quedar cortado.
llm = ChatGroq(
    model="openai/gpt-oss-120b",
    api_key=GROQ_API_KEY,
    temperature=0.2,
    max_tokens=2000
)

# ---------------------------------------------------------------------------
# Flujo original (texto libre). Se mantiene sin cambios.
# ---------------------------------------------------------------------------
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


def responder(pregunta: str) -> str:
    inicio = time.time()
    resultado = rag_chain.invoke({"pregunta": pregunta})
    duracion = time.time() - inicio
    print(f"⏱️  Tiempo total de la cadena (búsqueda + LLM): {duracion:.2f} segundos")
    return resultado


# ---------------------------------------------------------------------------
# Fase 2: salida estructurada + evidencias
# ---------------------------------------------------------------------------
class AnalisisRCA(BaseModel):
    """Resultado estructurado del análisis de causa raíz."""

    encontrado: bool = Field(
        description="True solo si el contexto contiene información suficiente para responder."
    )
    incidente: str = Field(
        description="El síntoma o incidente, en una oración. Vacío si no se encontró."
    )
    causa_raiz: str = Field(
        description="La causa raíz técnica, en una a tres oraciones. Vacío si no se encontró."
    )
    solucion: Optional[str] = Field(
        description="Solución técnica propuesta en el contexto, o null si el contexto no propone ninguna."
    )
    confianza: Literal["alta", "media", "baja"] = Field(
        description="Qué tan bien respalda el contexto la respuesta."
    )
    fragmentos_usados: List[int] = Field(
        description="Números de los fragmentos del contexto que sustentan la respuesta. Lista vacía si no hay numeración."
    )

    @field_validator("confianza", mode="before")
    @classmethod
    def _normalizar_confianza(cls, v):
        return str(v).strip().lower() if v else "baja"


_DEFAULTS_ANALISIS = {
    "encontrado": False,
    "incidente": "",
    "causa_raiz": "",
    "solucion": None,
    "confianza": "baja",
    "fragmentos_usados": [],
}

prompt_estructurado = ChatPromptTemplate.from_messages([
    ("system", """Sos un Analista de Causa Raíz (Root Cause Analyst) especializado en sistemas de software.

Tu tarea es identificar el INCIDENTE (síntoma) y su CAUSA RAÍZ técnica,
basándote únicamente en el contexto proporcionado sobre el sistema LogisCore.

Reglas que debés seguir siempre:
1. Usá SOLO información presente en el contexto. Si no alcanza para responder, poné
   encontrado=false y dejá incidente y causa_raiz vacíos.
2. incidente: el síntoma, en una oración. causa_raiz: la causa técnica, en una a tres oraciones.
3. solucion: solo si el contexto propone una solución técnica; si no, null. Podés usar viñetas markdown.
4. No inventes nombres de incidentes, códigos de error ni soluciones que no estén en el contexto.
5. confianza: "alta" si el contexto responde directamente la pregunta; "media" si hay que inferir
   una parte; "baja" si el respaldo es débil o indirecto.
6. fragmentos_usados: números de los fragmentos que sustentan tu respuesta. Si el contexto no
   está numerado, dejá la lista vacía.
7. Respondé en el mismo idioma de la pregunta.

Contexto disponible:
{contexto}
"""),
    ("human", "{pregunta}")
])


def _formatear_contexto(evidencias: list[dict]) -> str:
    """Numera los fragmentos para que el modelo pueda indicar cuáles usó."""
    bloques = []
    for i, ev in enumerate(evidencias, start=1):
        pagina = f", p.{ev['pagina']}" if ev["pagina"] else ""
        bloques.append(f"[{i}] ({ev['tipo']} · {ev['fuente']}{pagina})\n{ev['texto']}")
    return "\n\n---\n\n".join(bloques)


def _analizar_con_json_manual(mensajes) -> AnalisisRCA:
    """Plan B: pide JSON en texto plano y lo valida con Pydantic."""
    instruccion = HumanMessage(content=(
        "Respondé ÚNICAMENTE con un objeto JSON válido, sin texto extra ni bloques de código, "
        "con estas claves: encontrado (bool), incidente (str), causa_raiz (str), "
        "solucion (str o null), confianza ('alta', 'media' o 'baja'), "
        "fragmentos_usados (lista de enteros)."
    ))
    contenido = llm.invoke(list(mensajes) + [instruccion]).content
    coincidencia = re.search(r"\{.*\}", contenido, re.DOTALL)
    if not coincidencia:
        raise ValueError("El modelo no devolvió un JSON válido.")
    datos = {**_DEFAULTS_ANALISIS, **json.loads(coincidencia.group(0))}
    return AnalisisRCA(**datos)


def _analizar(pregunta: str, contexto: str) -> tuple[AnalisisRCA, float]:
    """Llama al modelo con salida estructurada. Devuelve (análisis, segundos)."""
    mensajes = prompt_estructurado.format_messages(contexto=contexto, pregunta=pregunta)
    inicio = time.time()
    analisis = None
    try:
        analisis = llm.with_structured_output(AnalisisRCA).invoke(mensajes)
    except Exception as e:
        print(f"⚠️  Salida estructurada falló ({type(e).__name__}: {e}). Usando JSON manual.")
    if analisis is None:
        analisis = _analizar_con_json_manual(mensajes)
    return analisis, time.time() - inicio


def responder_estructurado(pregunta: str) -> dict:
    """Flujo RAG con fuentes: busca, analiza y devuelve análisis + evidencias + tiempos."""
    inicio = time.time()
    evidencias = buscar_con_fuentes(pregunta)
    t_busqueda = time.time() - inicio

    if not evidencias:
        return {
            "analisis": AnalisisRCA(**_DEFAULTS_ANALISIS),
            "evidencias": [],
            "t_busqueda": t_busqueda,
            "t_modelo": 0.0,
        }

    analisis, t_modelo = _analizar(pregunta, _formatear_contexto(evidencias))

    # Las evidencias salen del retriever (el modelo no puede inventar fuentes);
    # solo se marca cuáles dice haber usado, ignorando números fuera de rango.
    usados = {n for n in analisis.fragmentos_usados if 1 <= n <= len(evidencias)}
    for i, ev in enumerate(evidencias, start=1):
        ev["usada"] = i in usados

    print(f"⏱️  Búsqueda {t_busqueda:.2f}s + modelo {t_modelo:.2f}s")
    return {
        "analisis": analisis,
        "evidencias": evidencias,
        "t_busqueda": t_busqueda,
        "t_modelo": t_modelo,
    }


def responder_desde_texto(pregunta: str, contexto: str) -> dict:
    """Mismo esquema, pero con un contexto propio (PDFs subidos). No hay fragmentos de evidencia."""
    analisis, t_modelo = _analizar(pregunta, contexto)
    return {
        "analisis": analisis,
        "evidencias": [],
        "t_busqueda": 0.0,
        "t_modelo": t_modelo,
    }


if __name__ == "__main__":
    preguntas = [
        "¿Por qué a los clientes se les cobra dos veces?"
    ]

    for pregunta in preguntas:
        print(f"\n{'='*60}")
        print(f"❓ Pregunta: {pregunta}")
        print(f"{'='*60}")
        resultado = responder_estructurado(pregunta)
        print(resultado["analisis"].model_dump_json(indent=2))
        for i, ev in enumerate(resultado["evidencias"], start=1):
            print(f"\n[{i}] {ev['tipo']} · {ev['fuente']} p.{ev['pagina']} · relevancia {ev['relevancia']:.2f} · usada={ev['usada']}")
            print(ev["texto"][:200].replace("\n", " ") + "…")