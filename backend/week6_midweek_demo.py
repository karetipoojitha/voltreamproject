
"""
Week 6 Midweek Demo — ChromaDB Similarity Query
Shows top-3 retrieved chunks for a given query.
Run: python week6_midweek_demo.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()


def run_similarity_demo():
    from rag import collection, retrieve_chunks, build_db

    # Build DB if empty
    if collection.count() == 0:
        print("Building vector DB from energy.pdf...")
        build_db()
        print(f"Vector DB built: {collection.count()} chunks\n")
    else:
        print(f"Vector DB ready: {collection.count()} chunks\n")

    queries = [
        "What did Edmond Becquerel discover in 1839?",
        "Who developed the silicon photovoltaic cell at Bell Labs in 1954?",
        "What do inverters do in solar electric systems?",
    ]

    for i, query in enumerate(queries, 1):
        print(f"{'='*60}")
        print(f"Query {i}: {query}")
        print(f"{'='*60}")

        docs = retrieve_chunks(query, n_results=3)

        for j, doc in enumerate(docs, 1):
            print(f"\nChunk {j} (reranked):")
            print(f"  {doc[:300]}...")
        print()


if __name__ == "__main__":
    run_similarity_demo()
