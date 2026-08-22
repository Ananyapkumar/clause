"""Check that the model's citations actually appear in the document.

Day 10.

The model returns extracted values AND the lines it claims to have read
them from. This checks the claim: does that text really exist in the
document?

If it does not, the model invented the citation - and we flag it, even if
the value itself happens to be correct. A right answer with a fabricated
source is not a right answer you can trust.

Nothing here calls an API. It costs nothing to run.
"""

import re


def normalise(text: str) -> str:
    """Flatten whitespace so formatting differences do not cause false alarms.

    Datasheets are full of alignment padding:

        System wattage              18 W

    A model may return that with single spaces. Both mean the same thing,
    so we collapse every run of whitespace to one space and lowercase
    before comparing.

    This is a DESIGN DECISION, and it errs generous on purpose. Being too
    strict would flag honest citations as hallucinations, which is worse
    than occasionally missing a sloppy one. We are looking for invented
    text, not imperfect transcription.
    """
    return re.sub(r"\s+", " ", text).strip().lower()


def verify_citations(document: str, citations: list[str]) -> dict:
    """Check every quoted line against the source document.

    Returns a summary plus the quotes that could not be found.
    """
    haystack = normalise(document)

    verified = 0
    unverified = []

    for quote in citations:
        needle = normalise(quote)

        # An empty citation cannot be verified and must not count as a pass.
        if not needle:
            unverified.append({"verbatim": quote, "reason": "empty citation"})
            continue

        if needle in haystack:
            verified += 1
        else:
            unverified.append({
                "verbatim": quote,
                "reason": "text not found in document",
            })

    total = len(citations)
    return {
        "total_citations": total,
        "verified": verified,
        "unverified": len(unverified),
        # Guard against dividing by zero when the model cited nothing.
        "verified_rate": verified / total if total else 0.0,
        "unverified_details": unverified,
    }


def count_filled_fields(result_fields: dict) -> int:
    """How many non-null values were extracted?

    Compared against the number of citations, this shows whether the model
    is citing its work at all. Nine values and zero citations means the
    extraction is entirely unsupported - unfalsifiable rather than wrong.
    """
    return sum(
        1
        for field, value in result_fields.items()
        if field != "citations" and value is not None
    )
