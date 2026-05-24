import os
from dotenv import load_dotenv

import chromadb
from sentence_transformers import SentenceTransformer
from pdf_loader import load_pdf

import google.generativeai as genai


# ENV

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))

API_KEY = os.getenv("GEMINI_API_KEY")

# INIT MODELS

embedder = SentenceTransformer("all-MiniLM-L6-v2")

genai.configure(api_key=API_KEY)
model = genai.GenerativeModel("gemini-2.5-flash")

# CHROMA DB

client = chromadb.PersistentClient(path=os.path.join(BASE_DIR, "vector_db"))
collection = client.get_or_create_collection("energy_docs")

PDF_PATH = os.path.join(BASE_DIR, "data", "energy.pdf")

# BUILD VECTOR DB

def build_db():
    text = load_pdf(PDF_PATH)

    if not text:
        print("Error: PDF not found or empty")
        return

    words = text.split()
    chunks = [" ".join(words[i:i+300]) for i in range(0, len(words), 300)]

    # clear old DB
    try:
        old = collection.get()
        if old and old.get("ids"):
            collection.delete(ids=old["ids"])
    except:
        pass

    for i, chunk in enumerate(chunks):
        emb = embedder.encode(chunk).tolist()

        collection.add(
            ids=[str(i)],
            documents=[chunk],
            embeddings=[emb]
        )

    print("Success: Vector DB Ready!")

# ASK QUESTION (RAG)
def ask_question(question: str):

    if collection.count() == 0:
        return "DB not built"

    q_emb = embedder.encode(question).tolist()

    results = collection.query(
        query_embeddings=[q_emb],
        n_results=3
    )

    docs = results.get("documents", [[]])[0]

    if not docs:
        return "I don't have that information"

    context = "\n\n".join(docs)

    prompt = f"""
You are a strict RAG assistant.

Use ONLY this context:

{context}

Question: {question}

If answer is not in context, say:
"I don't have that information"
"""

    response = model.generate_content(prompt)
    return response.text


def _is_rag_miss(answer: str) -> bool:
    text = (answer or "").strip().lower()
    misses = [
        "i don't have that information",
        "db not built",
        "error:",
    ]
    return not text or any(miss in text for miss in misses)


def ask_normal_agent(question: str, mode: str = "advisor") -> str:
    mode_instructions = {
        "advisor": "Give practical, action-focused home energy advice.",
        "solar": "Explain solar and energy concepts clearly, and say when details are general knowledge.",
        "billing": "Focus on bills, usage cost, budgeting, and savings advice.",
    }
    instruction = mode_instructions.get(mode, mode_instructions["advisor"])

    prompt = f"""
You are VoltStream's normal AI energy assistant.

{instruction}

Answer the user in a helpful, concise way. If you are not using the PDF knowledge base,
do not pretend the answer came from a document. Prefer short bullets when useful.

User question: {question}
"""

    response = model.generate_content(prompt)
    return response.text


def ask_project_assistant(question: str, mode: str = "advisor", project_context: str = "") -> str:
    mode_instructions = {
        "advisor": "Give practical, action-focused guidance for the VoltStream energy dashboard project.",
        "solar": "Explain solar and energy concepts in the context of this VoltStream project.",
        "billing": "Focus on billing, cost, usage, budget alerts, and savings inside the VoltStream project.",
    }
    instruction = mode_instructions.get(mode, mode_instructions["advisor"])

    prompt = f"""
You are the VoltStream Project AI Assistant.

You help users understand and operate this specific project: dashboard metrics,
smart devices, analytics, billing, and energy-saving actions.

{instruction}

Current project data:
{project_context}

Answer clearly and practically. If the project data does not include a detail,
say what is missing and give the best next action inside the app.

User question: {question}
"""

    response = model.generate_content(prompt)
    return response.text


def ask_hybrid_assistant(question: str, mode: str = "advisor") -> dict:
    rag_answer = ask_question(question)

    if not _is_rag_miss(rag_answer):
        return {
            "answer": rag_answer,
            "source": "rag",
            "label": "RAG knowledge base",
        }

    normal_answer = ask_normal_agent(question, mode)
    return {
        "answer": normal_answer,
        "source": "agent",
        "label": "Normal agent",
    }
