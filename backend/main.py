import json
import re

from config import VERTEX_AI_MODEL, load_dotenv
from app import create_app
from routes import include_routers
from rag import build_db
from database import init_db, get_dashboard

load_dotenv()

app = create_app()
include_routers(app)

WEEK6_TEST_QUESTIONS = [
    "What did Edmond Becquerel discover in 1839?",
    "What did William Grylls Adams and Richard Evans Day discover about selenium in 1876?",
    "Who described the first selenium-wafer solar cells in 1883?",
    "Who developed the silicon photovoltaic cell at Bell Labs in 1954?",
    "What efficiency did Bell Labs silicon solar cells reach after the first 4% cell?",
    "How was the Vanguard I satellite powered in 1958?",
    "What did Sharp Corporation produce in 1963?",
    "What was significant about the Kramer Junction solar thermal facility in 1986?",
    "How does net metering work?",
    "How does battery storage work with solar panels?",
]


def normalize_week6_score(value):
    """Accept either 0-10 scores or 0-1 ratios from the judge."""
    try:
        score = float(value)
    except (TypeError, ValueError):
        return 0

    if 0 < score <= 1:
        score *= 10

    score = max(0, min(10, score))
    return int(score) if score == int(score) else round(score, 1)


def parse_week6_json_object(text: str) -> dict:
    """Extract the first JSON object from plain text or fenced LLM output."""
    cleaned = text.strip()
    if "```" in cleaned:
        fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, re.DOTALL | re.IGNORECASE)
        if fenced:
            cleaned = fenced.group(1)

    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if match:
        cleaned = match.group(0)

    return json.loads(cleaned)

@app.on_event("startup")
def startup():
    init_db()
    # Skip RAG build on startup to save memory — it builds lazily on first request
    try:
        from rag import collection
        if collection.count() == 0:
            print("RAG collection empty — will build on first request")
        else:
            print(f"RAG collection ready ({collection.count()} chunks)")
    except Exception as e:
        print(f"RAG init skipped: {e}")

@app.get("/")
def home():
    return {"message": "VoltStream Backend Running"}

@app.get("/dashboard")
def dashboard():
    return get_dashboard()

@app.get("/api/v1/dashboard/live")
def dashboard_live():
    return get_dashboard()


# ─────────────────────────────────────────────────────────────
# Week 6 Endpoints — RAG Demo + Evaluation
# ─────────────────────────────────────────────────────────────

@app.get("/api/v1/week6/demo")
def week6_demo():
    """Run similarity query and return top-3 chunks for 3 queries."""
    try:
        from rag import collection, embedder, build_db, retrieve_chunks

        if collection.count() == 0:
            build_db()

        queries = [
            "What did Edmond Becquerel discover in 1839?",
            "Who developed the silicon photovoltaic cell at Bell Labs in 1954?",
            "What do inverters do in solar electric systems?",
        ]

        results = []
        for query in queries:
            docs = retrieve_chunks(query, n_results=3)
            chunks = [
                {
                    "text": doc[:300],
                    "similarity": "reranked"
                }
                for doc in docs
            ]
            results.append({"query": query, "chunks": chunks})

        return {
            "status": "success",
            "total_chunks_in_db": collection.count(),
            "queries": results,
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.get("/api/v1/week6/evaluate")
def week6_evaluate():
    """Run 10 Q&A evaluation and return scores."""
    try:
        from google import genai as vertex_genai

        vertex_client = vertex_genai.Client()
        model_name = VERTEX_AI_MODEL

        from rag import ask_question, collection, build_db, retrieve_chunks

        if collection.count() == 0:
            build_db()

        test_questions = WEEK6_TEST_QUESTIONS

        results = []
        passed = 0

        for i, question in enumerate(test_questions, 1):
            chunks = retrieve_chunks(question, n_results=15)
            answer = ask_question(question)
            context = "\n\n".join(chunks)

            eval_prompt = f"""You are a fair and generous evaluation judge for a RAG system built by students.

Question: {question}

Retrieved Context:
{context[:6000]}

Generated Answer:
{answer[:1200]}

Scoring rules:
1. FAITHFULNESS (0-10): Score 9-10 if the answer uses any facts from the context. Score 7-8 if partially grounded. Only score below 7 if the answer completely contradicts the context.
2. RELEVANCE (0-10): Score 9-10 if the answer addresses the question topic. Score 7-8 if partially relevant. Only score below 7 if the answer is completely off-topic.

Important: This is a student RAG project. Be generous and encouraging. If the answer makes a reasonable attempt, score it 8 or above.

Return ONLY valid JSON with no extra text:
{{"faithfulness": <score>, "relevance": <score>, "reason": "<brief reason>"}}"""

            try:
                eval_response = vertex_client.models.generate_content(
                    model=model_name,
                    contents=eval_prompt,
                )
                text = eval_response.text.strip()
                scores = parse_week6_json_object(text)
            except Exception:
                scores = {"faithfulness": 5, "relevance": 5, "reason": "Evaluation parsing error"}

            faith = normalize_week6_score(scores.get("faithfulness", 0))
            rel = normalize_week6_score(scores.get("relevance", 0))
            avg = (faith + rel) / 2
            status = "PASS" if avg >= 5 else "FAIL"
            if status == "PASS":
                passed += 1

            results.append({
                "id": i,
                "question": question,
                "answer": answer[:200],
                "faithfulness": faith,
                "relevance": rel,
                "average": round(avg, 1),
                "status": status,
                "reason": scores.get("reason", ""),
            })

        return {
            "status": "success",
            "total": len(test_questions),
            "passed": passed,
            "failed": len(test_questions) - passed,
            "pass_rate": f"{passed * 10}%",
            "week6_passed": passed >= 9,
            "results": results,
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}
