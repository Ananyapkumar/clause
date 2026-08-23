"""Search the indexed chunks. No LLM involved.

Day 12. This is deliberately separate from extraction, and that separation
is the point.

Your original plan puts it this way:

    "hit@5 is 72% - meaning 28% of the time, the answer isn't even in what
     I hand to the model."

If the retriever does not return the chunk containing the answer, no
amount of prompt tuning will fix it. Measuring retrieval on its own tells
you whether you have a retrieval problem or a generation problem. Almost
everyone skips this and then spends weeks tuning prompts to fix a
retrieval failure.

Costs nothing. Runs locally.

Run:
    py search.py "system wattage of the track spot"
    py search.py "rated life" --k 5
"""

import argparse

import chromadb
from sentence_transformers import SentenceTransformer

DB_DIR = "chroma_db"
COLLECTION = "datasheets"
EMBED_MODEL = "all-MiniLM-L6-v2"


def search(query: str, k: int = 3) -> list[dict]:
    """Return the k chunks whose meaning is closest to the query."""
    embedder = SentenceTransformer(EMBED_MODEL)
    client = chromadb.PersistentClient(path=DB_DIR)
    collection = client.get_collection(COLLECTION)

    # The query goes through the SAME embedding model as the chunks did.
    # It has to - two texts can only be compared if they were mapped into
    # the same space by the same model.
    query_vector = embedder.encode([query]).tolist()

    raw = collection.query(query_embeddings=query_vector, n_results=k)

    results = []
    for i in range(len(raw["ids"][0])):
        results.append({
            "chunk_id": raw["ids"][0][i],
            "doc_id": raw["metadatas"][0][i]["doc_id"],
            # DISTANCE, not similarity: lower is closer. It is easy to
            # read this backwards and conclude your retriever is broken.
            "distance": raw["distances"][0][i],
            "text": raw["documents"][0][i],
        })
    return results


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("query", help="what to search for")
    parser.add_argument("--k", type=int, default=3, help="how many chunks")
    parser.add_argument("--full", action="store_true",
                        help="print whole chunks instead of a preview")
    args = parser.parse_args()

    results = search(args.query, args.k)

    print(f'\nQuery: "{args.query}"')
    print(f"Top {len(results)} of {args.k} requested\n")

    for rank, r in enumerate(results, start=1):
        print(f"[{rank}] {r['chunk_id']}   distance {r['distance']:.4f}")
        if args.full:
            print(r["text"])
        else:
            preview = " ".join(r["text"].split())[:160]
            print(f"    {preview}...")
        print()


if __name__ == "__main__":
    main()
