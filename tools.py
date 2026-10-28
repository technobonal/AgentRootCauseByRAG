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
    """
    inicio = time.time()
    resultados = vectorstore.similarity_search_with_score(pregunta, k=k)
    duracion = time.time() - inicio
    print(f"⏱️  Búsqueda con fuentes (Cohere + Pinecone): {duracion:.2f} segundos")

    evidencias = []
    for doc, score in resultados:
        pagina = doc.metadata.get("page")
        evidencias.append(
            {
                "fuente": os.path.basename(str(doc.metadata.get("source", "desconocida"))),
                # PyPDFLoader numera las páginas desde 0
                "pagina": int(pagina) + 1 if isinstance(pagina, (int, float)) else None,
                "tipo": doc.metadata.get("tipo", "desconocido"),
                "relevancia": max(0.0, min(1.0, float(score))),
                "texto": doc.page_content,
            }
        )
    return evidencias