"""Chop documents into chunks, turn them into vectors, store them.

Day 12. Nothing here calls an API. It all runs on your machine and costs
nothing.

WHY CHUNK AT ALL
----------------
Right now the whole datasheet goes into the prompt. That works, and it
scores 100%. It also means you pay for every word of every document on
every request.

If the corpus were 500 datasheets, or if one document were 80 pages, that
stops being possible - the model has a limit on how much it can read at
once, and you would be paying to send text that is irrelevant to the
question.

So: cut each document into pieces, and at query time send only the pieces
that look relevant.

WHY EMBEDDINGS
--------------
To pick the relevant pieces you need to compare meaning, not words. An
embedding turns a piece of text into a list of numbers - a point in space
- positioned so that text with similar meaning sits nearby.

"System wattage 18 W" and "power consumption" share no words, but their
embeddings are close together. That is what keyword search cannot do.

Run:
    py ingest.py
    py ingest.py --chunk-size 200 --overlap 20
"""

import argparse
from pathlib import Path

import chromadb
from sentence_transformers import SentenceTransformer

DOCS_DIR = Path("evals/documents")
DB_DIR = "chroma_db"
COLLECTION = "datasheets"

# all-MiniLM-L6-v2: small, fast, runs on a CPU, downloads once (~90 MB)
# and then works offline. Good enough for short technical text and it
# costs nothing.
EMBED_MODEL = "all-MiniLM-L6-v2"


def chunk_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    """Split text into overlapping pieces of roughly chunk_size characters.

    OVERLAP matters. Cut a datasheet at exactly 400 characters and you may
    land in the middle of:

        Rated life L80/B10        60000 h

    leaving "Rated life L80" in one chunk and "60000 h" in the next. Both
    are then useless. Overlapping means each boundary appears in two
    chunks, so at least one copy stays intact.

    This splits on line breaks rather than blindly at a character count,
    because datasheets are line-oriented - one specification per line.
    Cutting mid-line destroys the label/value pairing that carries all the
    meaning.
    """
    lines = text.splitlines()
    chunks = []
    current = []
    current_len = 0

    for line in lines:
        current.append(line)
        current_len += len(line) + 1

        if current_len >= chunk_size:
            chunks.append("\n".join(current))

            # Keep the last few lines as the start of the next chunk.
            # That is the overlap.
            keep = []
            kept_len = 0
            for prev in reversed(current):
                if kept_len >= overlap:
                    break
                keep.insert(0, prev)
                kept_len += len(prev) + 1

            current = keep
            current_len = kept_len

    if current:
        chunks.append("\n".join(current))

    # Drop anything that is only whitespace.
    return [c for c in chunks if c.strip()]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--chunk-size", type=int, default=400,
                        help="target characters per chunk")
    parser.add_argument("--overlap", type=int, default=80,
                        help="characters carried into the next chunk")
    args = parser.parse_args()

    if not DOCS_DIR.exists():
        print(f"No documents at {DOCS_DIR}")
        raise SystemExit(1)

    print(f"Loading embedding model ({EMBED_MODEL})...")
    print("First run downloads ~90 MB. After that it works offline.\n")
    embedder = SentenceTransformer(EMBED_MODEL)

    # PersistentClient writes to disk, so the index survives between runs.
    client = chromadb.PersistentClient(path=DB_DIR)

    # Delete and recreate, so re-running does not stack duplicates on top
    # of the previous index.
    try:
        client.delete_collection(COLLECTION)
    except Exception:
        pass
    collection = client.create_collection(COLLECTION)

    all_ids, all_chunks, all_meta = [], [], []
    per_doc = {}

    for doc_path in sorted(DOCS_DIR.glob("*.txt")):
        doc_id = doc_path.stem
        text = doc_path.read_text(encoding="utf-8")
        chunks = chunk_text(text, args.chunk_size, args.overlap)
        per_doc[doc_id] = len(chunks)

        for i, chunk in enumerate(chunks):
            all_ids.append(f"{doc_id}::{i}")
            all_chunks.append(chunk)
            # METADATA is what lets you filter later - "only chunks from
            # e10" - and what tells you which document an answer came from.
            all_meta.append({"doc_id": doc_id, "chunk_index": i})

    print(f"Embedding {len(all_chunks)} chunks from {len(per_doc)} documents...")
    vectors = embedder.encode(all_chunks, show_progress_bar=True).tolist()

    collection.add(
        ids=all_ids,
        documents=all_chunks,
        embeddings=vectors,
        metadatas=all_meta,
    )

    lengths = [len(c) for c in all_chunks]
    print(f"\nIndexed into ./{DB_DIR}")
    print(f"  documents      {len(per_doc)}")
    print(f"  chunks         {len(all_chunks)}")
    print(f"  chunk size     {args.chunk_size} target, {args.overlap} overlap")
    print(f"  actual length  min {min(lengths)}, "
          f"avg {sum(lengths) // len(lengths)}, max {max(lengths)}")
    print("\nchunks per document:")
    for doc_id, count in per_doc.items():
        print(f"  {doc_id}  {count}")
    print("\nNext:  py search.py \"what is the system wattage of the track spot\"")


if __name__ == "__main__":
    main()
