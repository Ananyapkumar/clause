"""The extraction schema for lighting product datasheets.

Project 1, from Day 5 onward.

SCHEMA DECISIONS - documented deliberately, not to be silently changed.
These are judgement calls a domain expert makes. Writing them down is
what makes the eval set defensible.

  model_number      Full order code where present, otherwise the model name.
  wattage_w         SYSTEM wattage (includes driver losses), not LED load.
  lifespan_hours    L80/B10 rated life. NOT warranty hours.
  luminous_flux_lm  LUMINAIRE output, not bare LED module output.

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


# Field names in a fixed order, so every report and comparison lines up.
FIELDS = list(LightingDatasheet.model_fields.keys())
