import time
from rag import obtener_retriever

retriever = obtener_retriever()

def buscar_incidente(pregunta: str) -> str:
    """
    Busca información relevante sobre incidentes del sistema LogisCore
    y sus causas raíz correspondientes.
    """
    inicio = time.time()
    resultados = retriever.invoke(pregunta)
    duracion = time.time() - inicio
    print(f"⏱️  Búsqueda (Cohere + Pinecone): {duracion:.2f} segundos")

    if not resultados:
        return "No se encontró información relevante sobre ese incidente."

    contexto = "\n\n---\n\n".join([doc.page_content for doc in resultados])
    return contexto