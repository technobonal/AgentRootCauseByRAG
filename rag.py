import os
from dotenv import load_dotenv
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_cohere import CohereEmbeddings
from langchain_pinecone import PineconeVectorStore
from pinecone import Pinecone, ServerlessSpec

load_dotenv()

COHERE_API_KEY = os.getenv("COHERE_API_KEY")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")

# Conexión a Pinecone (esto se ejecuta siempre que se importe el archivo)
pc = Pinecone(api_key=PINECONE_API_KEY)
index_name = "logiscore-rag"

embeddings = CohereEmbeddings(
    model="embed-multilingual-v3.0",
    cohere_api_key=COHERE_API_KEY
)

def obtener_vectorstore():
    index = pc.Index(index_name)
    return PineconeVectorStore(index=index, embedding=embeddings)

def obtener_retriever():
    vectorstore = obtener_vectorstore()
    return vectorstore.as_retriever(search_kwargs={"k": 3})

# Esto SOLO se ejecuta si corrés "python rag.py" directamente,
# NO cuando tools.py importa este archivo
if __name__ == "__main__":
    loader_issues = PyPDFLoader("data/operations issues logiscore.pdf")
    loader_root_cause = PyPDFLoader("data/root cause logiccore.pdf")

    documentos_issues = loader_issues.load()
    documentos_root_cause = loader_root_cause.load()

    for doc in documentos_issues:
        doc.metadata["tipo"] = "incidente"
    for doc in documentos_root_cause:
        doc.metadata["tipo"] = "causa_raiz"

    todos_los_documentos = documentos_issues + documentos_root_cause

    splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=100)
    chunks = splitter.split_documents(todos_los_documentos)

    if index_name not in pc.list_indexes().names():
        pc.create_index(
            name=index_name,
            dimension=1024,
            metric="cosine",
            spec=ServerlessSpec(cloud="aws", region="us-east-1")
        )
        print(f"✅ Índice '{index_name}' creado")

    PineconeVectorStore.from_documents(
        documents=chunks,
        embedding=embeddings,
        index_name=index_name
    )
    print(f"✅ {len(chunks)} fragmentos guardados en Pinecone correctamente")