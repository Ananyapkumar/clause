"""Does retrieval actually reduce context on this corpus? Measure before spending.

Day 13. No API calls. Free to run.

The point: retrieval is supposed to send LESS text. Before spending 12 API
requests measuring accuracy, check whether it even achieves that. If the
retrieved context is not smaller, retrieval cannot be a win and the eval run
would only confirm something already visible for free.
"""

import argparse
from pathlib import Path

from retrieve import build_context, full_document

DOCS_DIR = Path("evals/documents")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--k", type=int, default=2,
                        help="chunks retrieved per field")
    args = parser.parse_args()

    print(f"Retrieval survey - k={args.k} chunks per field, 9 fields\n")
    print(f"{'doc':<6} {'full':>7} {'retrieved':>10} {'chunks':>7} {'change':>9}")
    print("-" * 44)

    total_full = 0
    total_retrieved = 0
    wins = 0

    for doc_path in sorted(DOCS_DIR.glob("*.txt")):
        doc_id = doc_path.stem
        full = full_document(doc_id)
        result = build_context(doc_id, k_per_field=args.k)

        change = result["context_chars"] / len(full) - 1
        total_full += len(full)
        total_retrieved += result["context_chars"]
        if result["context_chars"] < len(full):
            wins += 1

        flag = "" if change < 0 else "  <- LARGER"
        print(f"{doc_id:<6} {len(full):>7} {result['context_chars']:>10} "
              f"{result['chunks_used']:>7} {change:>+8.1%}{flag}")

    print("-" * 44)
    overall = total_retrieved / total_full - 1
    print(f"{'TOTAL':<6} {total_full:>7} {total_retrieved:>10} "
          f"{'':>7} {overall:>+8.1%}")
    print(f"\nDocuments where retrieval sent LESS: {wins} of 12")

    if overall >= 0:
        print("\nRetrieval is not reducing context on this corpus.")
        print("Spending API requests to measure its accuracy would only")
        print("confirm what is already visible for free.")


if __name__ == "__main__":
    main()
