#!/usr/bin/env python3
"""
Week 6 Evaluation Script — LLM-as-Judge
Scores 10 Q&A pairs for faithfulness and relevance.
Run: python week6_evaluation.py
"""
import sys
import os
import json
import re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from google import genai as vertex_genai
from config import VERTEX_AI_MODEL

vertex_client = vertex_genai.Client()
model_name = VERTEX_AI_MODEL

from rag import ask_question, collection, retrieve_chunks, build_db

# ─── Build DB if needed ───
if collection.count() == 0:
    print("Building vector DB...")
    build_db()

# ─── 10 Test Questions ───
TEST_QUESTIONS = [
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


def normalize_score(value):
    """Accept either 0-10 scores or 0-1 ratios from the judge."""
    try:
        score = float(value)
    except (TypeError, ValueError):
        return 0

    if 0 < score <= 1:
        score *= 10

    score = max(0, min(10, score))
    return int(score) if score.is_integer() else round(score, 1)

# ─── LLM Judge Evaluation ───
def parse_json_object(text: str) -> dict:
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


def evaluate_answer(question: str, answer: str, context_chunks: list) -> dict:
    context = "\n\n".join(context_chunks)
    eval_prompt = f"""You are an evaluation judge for a RAG (Retrieval-Augmented Generation) system.

Question: {question}

Retrieved Context (from documents):
{context}

Generated Answer: {answer}

Evaluate the answer on two criteria:

1. FAITHFULNESS (0-10): Is the answer grounded in the provided context? 
   - 8-10: Answer is fully supported by context
   - 5-7: Answer is mostly supported, minor additions
   - 0-4: Answer contains significant unsupported claims

2. RELEVANCE (0-10): Does the answer actually address the question?
   - 8-10: Directly and completely answers the question
   - 5-7: Partially answers the question
   - 0-4: Does not answer the question

Respond with ONLY valid JSON:
{{"faithfulness": <score>, "relevance": <score>, "reason": "<brief reason>"}}
"""
    try:
        response = vertex_client.models.generate_content(
            model=model_name,
            contents=eval_prompt,
        )
        text = response.text.strip()
        scores = parse_json_object(text)
        return scores
    except Exception as e:
        return {"faithfulness": 0, "relevance": 0, "reason": f"Evaluation error: {e}"}


def run_evaluation():
    print("=" * 70)
    print("WEEK 6 — RAG EVALUATION REPORT")
    print("=" * 70)
    print(f"Evaluating {len(TEST_QUESTIONS)} questions...\n")

    results = []
    passed = 0

    for i, question in enumerate(TEST_QUESTIONS, 1):
        print(f"[{i:2d}/10] {question[:60]}...")

        # Get RAG answer and chunks
        chunks = retrieve_chunks(question, n_results=5)

        answer = ask_question(question)

        # Evaluate
        scores = evaluate_answer(question, answer, chunks)
        faith = normalize_score(scores.get("faithfulness", 0))
        rel   = normalize_score(scores.get("relevance", 0))
        avg   = (faith + rel) / 2

        status = "PASS" if avg >= 7 else "FAIL"
        if status == "PASS":
            passed += 1

        result = {
            "id": i,
            "question": question,
            "answer": answer[:150] + "..." if len(answer) > 150 else answer,
            "faithfulness": faith,
            "relevance": rel,
            "average": round(avg, 1),
            "status": status,
            "reason": scores.get("reason", ""),
        }
        results.append(result)
        print(f"        Faithfulness: {faith}/10 | Relevance: {rel}/10 | {status}")

    # ─── Summary ───
    print("\n" + "=" * 70)
    print("EVALUATION SUMMARY")
    print("=" * 70)
    print(f"Total questions : {len(TEST_QUESTIONS)}")
    print(f"Passed (avg>=7) : {passed}/10")
    print(f"Failed          : {len(TEST_QUESTIONS) - passed}/10")
    print(f"Pass rate       : {passed * 10}%")
    print(f"Week 6 target   : 7/10 (70%)")
    print(f"Result          : {'WEEK 6 PASSED' if passed >= 7 else 'NEEDS IMPROVEMENT'}")

    # ─── Detailed table ───
    print("\n" + "-" * 70)
    print(f"{'#':>2} {'Faithfulness':>13} {'Relevance':>10} {'Avg':>5} {'Status':>8}")
    print("-" * 70)
    for r in results:
        print(f"{r['id']:>2} {r['faithfulness']:>13} {r['relevance']:>10} {r['average']:>5} {r['status']:>8}")
    print("-" * 70)

    # ─── Save report ───
    report_path = os.path.join(os.path.dirname(__file__), "week6_eval_report.json")
    with open(report_path, "w") as f:
        json.dump({
            "total": len(TEST_QUESTIONS),
            "passed": passed,
            "pass_rate": f"{passed * 10}%",
            "week6_passed": passed >= 7,
            "results": results
        }, f, indent=2)
    print(f"\nReport saved to: {report_path}")


if __name__ == "__main__":
    run_evaluation()
