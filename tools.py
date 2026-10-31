import os
import time

from rag import obtener_retriever, obtener_vectorstore

retriever = obtener_retriever()
vectorstore = obtener_vectorstore()


def buscar_incidente(pregunta: str) -> str:
    """
    Busca información relevante sobre incidentes del sistema LogisCore
    y sus causas raíz correspondientes.
    (Se mantiene por compatibilidad: devuelve solo el texto concatenado.)
    """
    inicio = time.time()
    resultados = retriever.invoke(pregunta)
    duracion = time.time() - inicio
    print(f"⏱️  Búsqueda (Cohere + Pinecone): {duracion:.2f} segundos")

    if not resultados:
        return "No se encontró información relevante sobre ese incidente."

    contexto = "\n\n---\n\n".join([doc.page_content for doc in resultados])
    return contexto


def buscar_con_fuentes(pregunta: str, k: int = 4) -> list[dict]:
    """
    Igual que buscar_incidente, pero devuelve cada fragmento con sus metadatos
    (fuente, página, tipo) y su puntaje de similitud, para mostrar evidencias.

    Cada evidencia incluye, además del texto y la fuente:
      - puntaje: puntaje crudo del índice. Con métrica cosine es la similitud (0 a 1,
        más alto = más parecido a la consulta).
      - relevancia: el mismo puntaje acotado a [0, 1] (se mantiene por compatibilidad).
      - similitud_relativa: puntaje dividido por el del mejor fragmento (0 a 1);
        sirve para dibujar la barra comparando los fragmentos entre sí.
      - mejor: True en el fragmento más similar a la consulta.
    """
    inicio = time.time()
    resultados = vectorstore.similarity_search_with_score(pregunta, k=k)
    duracion = time.time() - inicio
    print(f"⏱️  Búsqueda con fuentes (Cohere + Pinecone): {duracion:.2f} segundos")

    puntajes = [float(score) for _, score in resultados]
    mejor_puntaje = max(puntajes) if puntajes else 0.0
    indice_mejor = puntajes.index(mejor_puntaje) if puntajes else -1

    evidencias = []
    for i, (doc, score) in enumerate(resultados):
        pagina = doc.metadata.get("page")
        puntaje = float(score)
        evidencias.append(
            {
                "fuente": os.path.basename(str(doc.metadata.get("source", "desconocida"))),
                # PyPDFLoader numera las páginas desde 0
                "pagina": int(pagina) + 1 if isinstance(pagina, (int, float)) else None,
                "tipo": doc.metadata.get("tipo", "desconocido"),
                "puntaje": puntaje,
                "relevancia": max(0.0, min(1.0, puntaje)),
                "similitud_relativa": (
                    max(0.0, min(1.0, puntaje / mejor_puntaje)) if mejor_puntaje > 0 else 0.0
                ),
                "mejor": i == indice_mejor,
                "texto": doc.page_content,
            }
        )
    return evidencias