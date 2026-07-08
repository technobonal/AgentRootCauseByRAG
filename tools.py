from rag import obtener_retriever

retriever = obtener_retriever()

def buscar_incidente(pregunta: str) -> str:
    """
    Busca información relevante sobre incidentes del sistema LogisCore
    y sus causas raíz correspondientes.
    """
    resultados = retriever.invoke(pregunta)

    if not resultados:
        return "No se encontró información relevante sobre ese incidente."

    contexto = "\n\n---\n\n".join([doc.page_content for doc in resultados])
    return contexto


if __name__ == "__main__":
    pregunta_prueba = "¿Por qué se congela el rastreo los viernes?"
    resultado = buscar_incidente(pregunta_prueba)
    print("🔍 Resultado de la búsqueda:\n")
    print(resultado)