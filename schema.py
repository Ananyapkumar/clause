"""The extraction schema for lighting product datasheets.

Project 1, from Day 5 onward.

SCHEMA DECISIONS - documented deliberately, not to be silently changed.
These are judgement calls a domain expert makes. Writing them down is
what makes the eval set defensible.

  model_number      Full order code where present, otherwise the model name.
  wattage_w         SYSTEM wattage (includes driver losses), not LED load.
  lifespan_hours    L80/B10 rated life. NOT warranty hours.
  luminous_flux_lm  LUMINAIRE output, not bare LED module output.

DECISIONS ADDED DAY 16 - forced by harder eval cases.

  OCR noise (e14) - REVISED after the Day 16 measurement
    Normalise unambiguous OCR substitutions (lowercase-L for 1, capital-O
    for 0, "rn" for "m") in NUMERIC fields. PRESERVE identifiers verbatim.

      wattage_w, luminous_flux_lm, cct_k, cri, beam_angle_deg,
      lifespan_hours, ip_rating  -> normalise
      model_number               -> exactly as printed

    Reasoning: a wrong wattage is a design error a reviewer is likely to
    catch, because it will not reconcile with the rest of the schedule. A
    silently "corrected" order code is a procurement error that reconciles
    with nothing and surfaces only when the wrong product arrives. The
    asymmetry in consequence justifies the asymmetry in handling.

    HOW THIS RULE CAME ABOUT - worth recording. The first version of this
    decision normalised everything, including model_number. The Day 16 run
    disagreed: the model normalised all seven numeric fields correctly and
    preserved the order code verbatim. On review the model's behaviour was
    the better engineering choice and the ground truth was corrected to
    match it.

    This is the second time the eval has caught an error in the answer key
    rather than in the system. The first was mechanical; this one was a
    judgement error.

  Footnotes that qualify the table (e16)
    A footnote that CORRECTS or QUALIFIES a table value takes precedence
    over the table.

    lifespan_hours: the table shows 100 kh; the footnote states that is
    L70/B50 and gives L80/B10 as 70 kh. The existing L80/B10 rule points
    at the footnote, not the table. -> 70000.

    wattage_w: the table shows 200 W; the footnote states units supplied
    after January 2026 draw 185 W and that the table value applies to
    pre-2026 stock. Take the currently-supplied product -> 185.

    Consistent with the e11 precedent, where a revision note superseded
    figures printed on the same page. GENUINELY AMBIGUOUS: the document
    never states which stock it describes. Documented so the choice is
    auditable rather than arbitrary.

CANDIDATE FIELD - noted, NOT adopted:
  dimming_protocol (DALI / 0-10V / TRIAC / phase)
  Deliberately deferred. Adding a field mid-week invalidates every
  ground-truth file already written and breaks version comparison.
  Revisit at a version boundary, not inside one.

JSON CONVENTIONS
  - Numbers bare: 4940, never "4,940 lm" and never "4940 lm"
  - Units live in the field NAME, never in the value
  - Missing values: null (unquoted). Not "N/A", not "", not "none"
  - dimmable: boolean true/false
  - Dates, where they occur: YYYY-MM-DD

RANGE CONSTRAINTS - added Day 8, in response to a real failure.
On one run the model returned wattage_w = 1.8e+201 with every other
field null. Pydantic accepted it: "a number, or nothing" was satisfied.
Validation passed, retry never fired, and a nonsense answer was returned
as a well-formed response.

Bounds below are domain judgement, chosen to be generous enough that no
legitimate luminaire is rejected. Rejecting a real datasheet is worse
than accepting an absurd value, so these err wide.

  wattage_w         0 - 2000     downlight through large floodlight
  luminous_flux_lm  0 - 200000   high bay / stadium at the top end
  cct_k             1000 - 10000 below ~1800K and above ~6500K is exotic
  cri               0 - 100      PHYSICALLY bounded - CRI cannot exceed 100
  beam_angle_deg    0 - 360
  lifespan_hours    0 - 500000

Effect: an out-of-range value now fails validation, which triggers the
existing retry with the error fed back to the model. The recovery
machinery built on Day 2 finally has something to recover from.
"""

from typing import Optional

from pydantic import BaseModel, Field


class LightingDatasheet(BaseModel):
    """Nine fields extracted from a lighting product datasheet."""

    model_number: Optional[str] = Field(
        default=None,
        description=(
            "Full order code if the datasheet gives one (e.g. 'LP-6060-40-90-DALI'). "
            "If no order code exists, use the model name. Text as printed."
        ),
    )

    wattage_w: Optional[float] = Field(
        default=None,
        ge=0,
        le=2000,
        description=(
            "SYSTEM wattage in watts - total power draw including driver losses. "
            "NOT the LED load / LED module power. If both appear, take system. "
            "Bare number, no unit. Must be between 0 and 2000."
        ),
    )

    luminous_flux_lm: Optional[int] = Field(
        default=None,
        ge=0,
        le=200_000,
        description=(
            "LUMINAIRE output in lumens - light leaving the fitting. "
            "NOT raw LED module flux. Bare number, no separators, no unit. "
            "Must be between 0 and 200000."
        ),
    )

    cct_k: Optional[int] = Field(
        default=None,
        ge=1000,
        le=10_000,
        description=(
            "Correlated colour temperature in kelvin, e.g. 4000. "
            "If the datasheet lists several, use the variant being specified. "
            "Bare number. Must be between 1000 and 10000."
        ),
    )

    cri: Optional[int] = Field(
        default=None,
        ge=0,
        le=100,
        description=(
            "Colour rendering index, e.g. 80 or 90. Bare number. "
            "Must be between 0 and 100 - CRI cannot exceed 100."
        ),
    )

    beam_angle_deg: Optional[int] = Field(
        default=None,
        ge=0,
        le=360,
        description=(
            "Beam angle in degrees, e.g. 120. Bare number, no degree symbol. "
            "Must be between 0 and 360."
        ),
    )

    ip_rating: Optional[str] = Field(
        default=None,
        description=(
            "Ingress protection code as printed, e.g. 'IP20', 'IP65'. "
            "A code, not a number - kept as text."
        ),
    )

    lifespan_hours: Optional[int] = Field(
        default=None,
        ge=0,
        le=500_000,
        description=(
            "L80/B10 rated life in hours, e.g. 60000. "
            "NOT the warranty period. If both appear, take rated life. "
            "Bare number, no separators. Must be between 0 and 500000."
        ),
    )

    dimmable: Optional[bool] = Field(
        default=None,
        description=(
            "true if the datasheet states the product is dimmable by any means. "
            "false if it explicitly states non-dimmable. null if not mentioned."
        ),
    )

    # CITATIONS - attempt 2, flat list of strings.
    #
    # Attempt 1 used a nested Citation model (field + verbatim). That was a
    # mistake: Pydantic emits nested models as $defs/$ref in the JSON schema,
    # and the API returned an EMPTY list every time - the model never filled
    # it. Extraction quality also degraded and cost per document rose 4x.
    #
    # A flat list[str] emits no $defs. We lose the field->quote mapping, but
    # we keep the thing that matters: did the model quote text that actually
    # exists in the document?
    citations: list[str] = Field(
        default_factory=list,
        description=(
            "REQUIRED. For each value you extracted, copy the exact line from "
            "the datasheet you read it from, character for character. One "
            "string per line quoted, e.g. 'System wattage              18 W'. "
            "Do not paraphrase or reformat. Never leave this empty."
        ),
    )


# The nine extracted fields, in a fixed order. Deliberately EXCLUDES
# 'citations' - that is evidence about the extraction, not an extracted
# value, and it is not scored against ground truth.
FIELDS = [f for f in LightingDatasheet.model_fields if f != "citations"]


def values_match(field: str, predicted, expected) -> bool:
    """Compare one field value against ground truth.

    Lives here rather than in evaluate.py because more than one script needs
    it, and two scripts scoring the same data differently is how you get two
    different numbers for the same run.

    That happened on Day 17. A helper inside verify_agent.py compared
    str(185.0) against str(185), reported a mismatch that did not exist, and
    briefly looked like a model failure. One scoring function, one home.

    Deliberately strict: a datasheet value is either right or it is not.
    The only tolerance is case and surrounding whitespace on the text fields.
    """
    # null == null is a correct answer: "this document does not state it".
    if predicted is None and expected is None:
        return True
    if predicted is None or expected is None:
        return False

    if field in ("model_number", "ip_rating"):
        return str(predicted).strip().upper() == str(expected).strip().upper()

    if field == "dimmable":
        return bool(predicted) == bool(expected)

    # Numeric: compare AS NUMBERS, so 185 and 185.0 match.
    try:
        return float(predicted) == float(expected)
    except (TypeError, ValueError):
        return str(predicted).strip() == str(expected).strip()


# =============================================================
# ABLATION SUPPORT
# =============================================================
# The first ablation attempt was INVALID. It removed the domain rules from
# the prompt but left them in the field descriptions above - and those
# descriptions are sent to the model as part of the JSON schema on every
# call. So the rules were present in both conditions, and the scores were
# identical, which is exactly what you would predict from removing nothing.
#
# A control that does not control is not a control.
#
# These neutral descriptions strip every lighting judgement while keeping
# enough to identify the field. Formatting guidance stays, because the
# ablation is testing DOMAIN knowledge, not output format.

NEUTRAL_DESCRIPTIONS = {
    "citations": (
        "One entry per non-null field, containing the exact source text you "
        "read that value from, copied character for character."
    ),
    "model_number": "The product model number or order code, as printed.",
    "wattage_w": "Power in watts. Bare number, no unit.",
    "luminous_flux_lm": "Light output in lumens. Bare number, no separators.",
    "cct_k": "Colour temperature in kelvin. Bare number.",
    "cri": "Colour rendering index. Bare number.",
    "beam_angle_deg": "Beam angle in degrees. Bare number.",
    "ip_rating": "Ingress protection code as printed, e.g. 'IP20'.",
    "lifespan_hours": "Lifespan in hours. Bare number, no separators.",
    "dimmable": "true if dimmable, false if not, null if not mentioned.",
}


def build_json_schema(
    use_domain_rules: bool = True,
    use_citations: bool = False,
) -> dict:
    """The JSON schema sent to the model.

    use_domain_rules=False replaces every field description with a neutral
    one, so the model is told WHICH field to fill but not HOW to resolve
    the ambiguities a lighting datasheet contains.

    Range constraints are kept in both conditions - they are guardrails
    against nonsense output, not domain guidance about which figure to pick.
    """
    schema = LightingDatasheet.model_json_schema()

    # CITATIONS ARE OFF BY DEFAULT - Day 10 finding.
    #
    # Asking the model to extract AND quote its sources measurably degraded
    # extraction on complex documents:
    #
    #   E02 (simple)          9/9 fields, 9/9 citations verified, 0% hallucination
    #   E01 (complex, traps)  1/9 fields, 0 citations, wattage_w = 1500.0000000000002
    #
    # E01's wattage error appeared in all three citation runs and never
    # before. The mechanism works; the cost is unacceptable on hard inputs.
    #
    # Enable with:  py evaluate.py --with-citations
    if not use_citations:
        schema.get("properties", {}).pop("citations", None)
        if "required" in schema:
            schema["required"] = [r for r in schema["required"] if r != "citations"]

    if use_domain_rules:
        return schema

    for field, neutral in NEUTRAL_DESCRIPTIONS.items():
        if field in schema.get("properties", {}):
            schema["properties"][field]["description"] = neutral

    return schema
