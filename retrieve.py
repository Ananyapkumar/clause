"""Assemble a document's context from retrieved chunks instead of the whole text.

Day 13. No API calls - embeddings run locally. Costs nothing to run.

WHAT THIS SIMULATES
-------------------
Right now the whole datasheet goes into the prompt. That works because these
documents are 500-2000 characters. Real technical documents are 20-80 pages.
At that size the whole document does not fit, and even where it does, you are
paying to send text irrelevant to the question.

So: retrieve only the parts likely to contain each field, and send those.

WHY ONE QUERY PER FIELD
-----------------------
A single query like "extract the specifications" retrieves chunks that look
generically spec-like. But the nine fields live in different places - the model
number is usually in the header, the IP rating in a protection section, the
lifespan in a lifetime table.

Querying per field and taking the union targets each one. It also makes the
failure legible: if lifespan is wrong, you can look at which chunk the lifespan
query retrieved.

Embeddings are free and local, so nine queries per document costs nothing.
"""

from pathlib import Path

import chromadb
from sentence_transformers import SentenceTransformer

DB_DIR = "chroma_db"
COLLECTION = "datasheets"
EMBED_MODEL = "all-MiniLM-L6-v2"

# One natural-language query per schema field. These are deliberately phrased
# the way the label appears on a datasheet, not the way the field is named in
# code - the embedder is matching against document text, not against Python.
FIELD_QUERIES = {
    "model_number": "order code model number product reference",
    "wattage_w": "system wattage power consumption watts",
    "luminous_flux_lm": "luminous flux lumen output lm",
    "cct_k": "colour temperature correlated CCT kelvin",
    "cri": "colour rendering index CRI Ra",
    "beam_angle_deg": "beam angle distribution degrees",
    "ip_rating": "ingress protection IP rating",
    "lifespan_hours": "rated life L80 B10 lifetime hours",
    "dimmable": "dimming dimmable DALI control gear",
}

# Loaded once and reused. Re-instantiating the model per call would dominate
# the runtime.
_embedder = None
_collection = None


def _setup():
    global _embedder, _collection
    if _embedder is None:
        _embedder = SentenceTransformer(EMBED_MODEL)
    if _collection is None:
        client = chromadb.PersistentClient(path=DB_DIR)
        _collection = client.get_collection(COLLECTION)
    return _embedder, _collection


def build_context(doc_id: str, k_per_field: int = 2) -> dict:
    """Retrieve chunks for one document and assemble them into a context block.

    Filters to a single document with metadata - we already know which
    datasheet we are extracting from. The retrieval problem here is
    WHICH PART of the document, not which document.

    Returns the assembled text plus statistics for reporting.
    """
    embedder, collection = _setup()

    queries = list(FIELD_QUERIES.values())
    query_vectors = embedder.encode(queries).tolist()

    # One search per field, restricted to this document.
    raw = collection.query(
        query_embeddings=query_vectors,
        n_results=k_per_field,
        where={"doc_id": doc_id},
    )

    # Union the results. A chunk retrieved by three different field queries
    # should appear once, not three times.
    selected = {}                       # chunk_id -> (chunk_index, text)
    per_field = {}                      # which chunks each field pulled

    for i, field in enumerate(FIELD_QUERIES):
        ids = raw["ids"][i]
        docs = raw["documents"][i]
        metas = raw["metadatas"][i]
        per_field[field] = ids

        for chunk_id, text, meta in zip(ids, docs, metas):
            selected[chunk_id] = (meta["chunk_index"], text)

    # Reassemble in DOCUMENT ORDER, not relevance order. A datasheet read out
    # of sequence is harder to interpret, and ordering by relevance would put
    # the header in the middle.
    ordered = sorted(selected.values(), key=lambda pair: pair[0])
    context = "\n...\n".join(text for _, text in ordered)

    return {
        "context": context,
        "chunks_used": len(selected),
        "context_chars": len(context),
        "per_field_chunks": per_field,
    }


def full_document(doc_id: str, docs_dir: str = "evals/documents") -> str:
    """The whole document, for comparison against the retrieved version."""
    return Path(docs_dir, f"{doc_id}.txt").read_text(encoding="utf-8")


if __name__ == "__main__":
    import sys

    doc_id = sys.argv[1] if len(sys.argv) > 1 else "e10"
    result = build_context(doc_id)
    full = full_document(doc_id)

    print(f"Document: {doc_id}")
    print(f"  full document   {len(full)} chars")
    print(f"  retrieved       {result['context_chars']} chars "
          f"({result['chunks_used']} chunks)")
    reduction = 1 - result["context_chars"] / len(full)
    print(f"  reduction       {reduction:.1%}")
    print("\nWhich chunks each field pulled:")
    for field, ids in result["per_field_chunks"].items():
        print(f"  {field:<20} {ids}")
    print("\n--- assembled context ---")
    print(result["context"])
