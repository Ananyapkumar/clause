"""Turn one CSV export from Google Sheets into the eval files.

Why this exists
---------------
Authoring 30+ datasheets as individual .txt files, each with its own .json
ground truth, is slow and error-prone. A spreadsheet is far easier to edit.

But the documents must NOT live only in a sheet. The repository has to stay
self-contained: anyone can clone it and run `py evaluate.py` with no
credentials and no network. That is a large part of why the project reads
as professional, and it is also what makes the eval reproducible - git
tracks every change to a document, so if a score moves you can see why.

So: author in the sheet, sync to files, commit the files.

It also removes the entire class of formatting bugs that cost three
sessions - you type 50 in a cell, this writes 50 unquoted. No more
"50 W" versus 50, no more "False" versus false.

Cost: nothing. Standard library only, no API, no authentication.

Sheet columns (exact names, first row):
    id, document_text, model_number, wattage_w, luminous_flux_lm,
    cct_k, cri, beam_angle_deg, ip_rating, lifespan_hours, dimmable

Usage:
    1. In Google Sheets: File > Download > Comma Separated Values
    2. Save it as evals/eval_sheet.csv
    3. py import_from_sheet.py
"""

import csv
import json
from pathlib import Path

from schema import FIELDS

CSV_IN = Path("evals/eval_sheet.csv")
DOCS_DIR = Path("evals/documents")
TRUTH_DIR = Path("evals/ground_truth")

TEXT_FIELDS = {"model_number", "ip_rating"}
BOOL_FIELDS = {"dimmable"}

TRUE_WORDS = {"true", "yes", "y", "1", "dimmable"}
FALSE_WORDS = {"false", "no", "n", "0", "non-dimmable", "not dimmable"}


def convert(field: str, raw: str):
    """Turn one spreadsheet cell into a correctly typed JSON value.

    Everything arrives from CSV as text. This is where "50" becomes 50 and
    "false" becomes False - the step that stops formatting mistakes ever
    reaching the ground truth again.
    """
    value = (raw or "").strip()

    # Empty cell means the document does not state it.
    if not value or value.lower() in {"null", "none", "n/a", "-"}:
        return None

    if field in TEXT_FIELDS:
        return value

    if field in BOOL_FIELDS:
        low = value.lower()
        if low in TRUE_WORDS:
            return True
        if low in FALSE_WORDS:
            return False
        raise ValueError(f"{field}: cannot read {value!r} as true/false")

    # Numeric. Strip anything that is not part of a number, so a stray
    # unit or thousands separator does not break the import.
    cleaned = value.replace(",", "").replace(" ", "")
    cleaned = "".join(c for c in cleaned if c.isdigit() or c in ".-")
    if not cleaned:
        raise ValueError(f"{field}: no number found in {value!r}")

    number = float(cleaned)
    # Write whole numbers as ints so the JSON reads 4000, not 4000.0.
    return int(number) if number.is_integer() else number


def main() -> None:
    if not CSV_IN.exists():
        print(f"No file at {CSV_IN}")
        print("Download your sheet as CSV and save it there first.")
        raise SystemExit(1)

    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    TRUTH_DIR.mkdir(parents=True, exist_ok=True)

    written = 0
    problems = []

    # utf-8-sig strips the invisible marker Google puts at the start of a
    # CSV export. Without it the first column name reads as "﻿id".
    with open(CSV_IN, newline="", encoding="utf-8-sig") as f:
        for line_no, row in enumerate(csv.DictReader(f), start=2):

            case_id = (row.get("id") or "").strip()
            document = (row.get("document_text") or "").strip()

            if not case_id and not document:
                continue                       # blank row, skip quietly

            if not case_id or not document:
                problems.append(f"row {line_no}: needs both id and document_text")
                continue

            truth = {}
            row_failed = False
            for field in FIELDS:
                try:
                    truth[field] = convert(field, row.get(field, ""))
                except ValueError as err:
                    problems.append(f"row {line_no} ({case_id}): {err}")
                    row_failed = True

            if row_failed:
                continue

            (DOCS_DIR / f"{case_id}.txt").write_text(document + "\n", encoding="utf-8")
            (TRUTH_DIR / f"{case_id}.json").write_text(
                json.dumps(truth, indent=2) + "\n", encoding="utf-8"
            )
            written += 1

    if problems:
        print(f"{len(problems)} problem(s) - those rows were skipped:\n")
        for p in problems:
            print(f"  - {p}")
        print()

    print(f"Wrote {written} case(s):")
    print(f"  {DOCS_DIR}/*.txt")
    print(f"  {TRUTH_DIR}/*.json")
    if written:
        print("\nCheck the output, then:  py evaluate.py --limit 2")


if __name__ == "__main__":
    main()
