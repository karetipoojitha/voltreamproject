import os
from dotenv import load_dotenv

import chromadb
from google import genai

from config import VERTEX_AI_MODEL
from pdf_loader import load_pdf


# ----------------------------
# CONFIG
# ----------------------------

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))

PDF_PATH = os.path.join(BASE_DIR, "data", "energy.pdf")

# Lazy-loaded — only initialised when first needed, not on import
_embedder = None
_vertex_client = None

def get_embedder():
    global _embedder
    if _embedder is None:
        from sentence_transformers import SentenceTransformer
        _embedder = SentenceTransformer("all-MiniLM-L6-v2")
    return _embedder

def get_vertex_client():
    global _vertex_client
    if _vertex_client is None:
        _vertex_client = genai.Client()
    return _vertex_client

# Keep module-level name for backward compat (used in main.py imports)
@property
def embedder():
    return get_embedder()

client = chromadb.PersistentClient(
    path=os.path.join(BASE_DIR, "vector_db")
)

collection = client.get_or_create_collection("energy_docs")


# ----------------------------
# UTIL: detect history question
# ----------------------------

def is_history_question(q: str) -> bool:
    q = q.lower()
    keywords = [
        "history", "timeline", "evolution",
        "development", "how did", "journey"
    ]
    return any(k in q for k in keywords)


# ----------------------------
# BUILD DATABASE (optimized chunking)
# ----------------------------

def build_db():
    text = load_pdf(PDF_PATH)

    if not text:
        print("PDF missing or empty")
        return

    words = text.split()

    chunk_size = 300
    overlap = 50

    chunks = []
    for i in range(0, len(words), chunk_size - overlap):
        chunk = " ".join(words[i:i + chunk_size])
        chunks.append(chunk)

    # clear old DB safely
    try:
        old = collection.get()
        if old.get("ids"):
            collection.delete(ids=old["ids"])
    except:
        pass

    # batch embedding (FASTER)
    embeddings = get_embedder().encode(
        chunks,
        normalize_embeddings=True
    ).tolist()

    collection.add(
        ids=[str(i) for i in range(len(chunks))],
        documents=chunks,
        embeddings=embeddings
    )

    print(f"Vector DB ready ({len(chunks)} chunks)")


# ----------------------------
# RETRIEVAL 
# ----------------------------

def retrieve_chunks(question: str, n_results: int = 5):

    q_emb = get_embedder().encode(
        question,
        normalize_embeddings=True
    ).tolist()

    results = collection.query(
        query_embeddings=[q_emb],
        n_results=min(n_results, collection.count()),
        include=["documents"]
    )

    return results["documents"][0]


def retrieve_full_context(n_results=50):
    """
    Used only for history/timeline questions
    """
    data = collection.get(include=["documents"])
    return data.get("documents", [])[:n_results]


# ----------------------------
# ASK QUESTION (FIXED + FASTER)
# ----------------------------

def ask_question(question: str):

    if collection.count() == 0:
        build_db()

    # choose retrieval strategy
    if is_history_question(question):
        docs = retrieve_full_context(80)   # expanded context for history
    else:
        docs = retrieve_chunks(question, n_results=5)

    if not docs:
        return "I don't have that information."

    context = "\n\n".join(docs)

    if is_history_question(question):
        prompt = f"""
You are a strict RAG assistant.

TASK:
- Explain full history using ONLY the context
- Provide a clear chronological timeline
- Do NOT skip events if present in context
- Do NOT hallucinate missing events

FORMAT:
1. Short overview
2. Chronological timeline (bullet points)
3. Summary of evolution

CONTEXT:
{context}

QUESTION:
{question}
"""
    else:
        prompt = f"""
You are a strict assistant.

RULES:
- Answer ONLY from context
- Be concise (2–5 sentences)
- If not in context say: "I don't have that information."

CONTEXT:
{context}

QUESTION:
{question}
"""

    try:
        response = get_vertex_client().models.generate_content(
            model=VERTEX_AI_MODEL,
            contents=prompt
        )
        return response.text

    except Exception as e:
        return f"""
Vertex AI unavailable.

Error: {str(e)}

--- Context Used ---
{context}
"""


# ----------------------------
# MAIN LOOP (optimized)
# ----------------------------

if __name__ == "__main__":

    if collection.count() == 0:
        build_db()

    print("\nRAG System Ready 🚀")

    while True:

        question = input("\nAsk a question (or type exit): ")

        if question.lower() == "exit":
            break

        answer = ask_question(question)

        print("\nAnswer:\n")
        print(answer)