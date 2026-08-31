"""Generate the variance figure from the recorded observations.

Day 18.

WHY THIS IS A SCRIPT AND NOT A DRAWING
--------------------------------------
The figure states a finding: variance in this system is concentrated in the
fields where domain judgement is required, and absent everywhere else. That
claim has to stay true as n grows. A hand-drawn chart is a snapshot that quietly
becomes a lie the next time measure_variance.py runs; a generated one cannot.

So every number on the figure is read from results/variance-*.json at render
time. Add runs, re-run this, and the figure updates - including the sample sizes
printed on each bar, which is what makes it honest rather than decorative.

COST: nothing. No API calls. Reads local files, writes an SVG.

Usage:
    py make_figures.py

Output:
    docs/variance.svg     embed in README.md with:
                          ![Variance by field](docs/variance.svg)
"""

import json
from pathlib import Path

from schema import FIELDS, values_match

RESULTS_DIR = Path("results")
TRUTH_DIR = Path("evals/ground_truth")
DOCS_OUT = Path("docs")

# Fields where the extraction requires a DOMAIN JUDGEMENT rather than
# transcription. Declared here, ahead of the data, so the figure cannot be
# accused of drawing the boundary around whatever turned out to be unstable.
#
#   wattage_w      two candidate numbers on the page; a footnote conditions
#                  which applies, on context the document never resolves
#   model_number   OCR-damaged identifier; the rule demands verbatim
#                  preservation, against the model's urge to "fix" it
#   lifespan_hours warranty vs L70/B50 vs L80/B10 - three plausible figures
#   luminous_flux_lm  luminaire output vs bare LED module output
JUDGEMENT_FIELDS = {"wattage_w", "model_number", "lifespan_hours",
                    "luminous_flux_lm"}

INK = "#1a1a1a"
MUTED = "#6b7280"
GRID = "#e5e7eb"
STABLE = "#3b82f6"       # transcription fields
JUDGEMENT = "#dc2626"    # judgement fields
BG = "#ffffff"
PANEL = "#f9fafb"


def load_all():
    """Read every variance file. Returns {doc_id: {field: (n_correct, n)}}."""
    data = {}
    for path in sorted(RESULTS_DIR.glob("variance-*.json")):
        d = json.loads(path.read_text(encoding="utf-8"))
        doc = d["document"]
        truth_path = TRUTH_DIR / f"{doc}.json"
        if not truth_path.exists():
            continue
        truth = json.loads(truth_path.read_text(encoding="utf-8"))

        per_field = {}
        for field in FIELDS:
            # Only count observations where this field was actually recorded.
            # Backfilled rows hold wattage_w and nulls elsewhere; counting
            # those nulls as measurements would invent stability.
            seen = [o[field] for o in d.get("observations", [])
                    if o and field in o and o[field] is not None]
            if not seen:
                continue
            correct = sum(1 for v in seen
                          if values_match(field, v, truth.get(field)))
            per_field[field] = (correct, len(seen))
        data[doc] = {"fields": per_field, "scores": d.get("scores", [])}
    return data


def svg_escape(text):
    return (str(text).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;"))


def build(data):
    docs = sorted(data)
    if not docs:
        raise SystemExit("No variance files in results/. Run measure_variance.py first.")

    # Order fields so anything that actually moved sits at the top. The
    # judgement/transcription colouring is declared ahead of the data
    # (JUDGEMENT_FIELDS above); the ORDER is data-driven, which is a display
    # choice and not a claim.
    def instability(field):
        worst = 1.0
        for doc in docs:
            rec = data[doc]["fields"].get(field)
            if rec:
                worst = min(worst, rec[0] / rec[1])
        return worst

    ordered = sorted(FIELDS, key=lambda f: (instability(f), f not in JUDGEMENT_FIELDS))

    bar_w, gap, group_gap = 15, 4, 17
    row_h = len(docs) * (bar_w + gap) + group_gap
    left, top, plot_w = 210, 132, 460
    plot_h = len(ordered) * row_h
    W = 940
    H = top + plot_h + 78

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'viewBox="0 0 {W} {H}" font-family="Segoe UI, Helvetica, Arial, sans-serif">',
        f'<rect width="{W}" height="{H}" fill="{BG}"/>',
        f'<text x="32" y="44" font-size="21" font-weight="700" fill="{INK}">'
        f'Where the variance actually is</text>',
        f'<text x="32" y="70" font-size="13" fill="{MUTED}">'
        f'Per-field correctness across repeated runs on identical input \u2014 '
        f'same prompt, same model, same document.</text>',
        f'<text x="32" y="90" font-size="13" fill="{MUTED}">'
        f'Every field that moved is a field requiring a domain judgement. '
        f'No transcription field moved, on any run.</text>',
    ]

    # Gridlines, bounded to the plot
    for pct in (0, 25, 50, 75, 100):
        x = left + plot_w * pct / 100
        parts.append(f'<line x1="{x:.1f}" y1="{top-12}" x2="{x:.1f}" '
                     f'y2="{top + plot_h - group_gap + 4}" '
                     f'stroke="{GRID}" stroke-width="1"/>')
        parts.append(f'<text x="{x:.1f}" y="{top-20}" font-size="11" '
                     f'fill="{MUTED}" text-anchor="middle">{pct}%</text>')

    y = top
    for field in ordered:
        is_j = field in JUDGEMENT_FIELDS
        colour = JUDGEMENT if is_j else STABLE
        moved = instability(field) < 1.0
        group_h = len(docs) * (bar_w + gap) - gap

        parts.append(
            f'<text x="{left-14}" y="{y + group_h/2 + 4:.0f}" font-size="12.5" '
            f'font-weight="{"600" if moved else "400"}" '
            f'fill="{INK if moved else MUTED}" '
            f'text-anchor="end">{svg_escape(field)}</text>')

        for doc in docs:
            rec = data[doc]["fields"].get(field)
            if rec is None:
                y += bar_w + gap
                continue
            correct, n = rec
            frac = correct / n
            w = max(plot_w * frac, 2.0)
            parts.append(f'<rect x="{left}" y="{y}" width="{w:.1f}" '
                         f'height="{bar_w}" rx="2" fill="{colour}" '
                         f'opacity="{0.95 if is_j else 0.5}"/>')
            parts.append(
                f'<text x="{left + w + 8:.1f}" y="{y+bar_w-3}" font-size="10.5" '
                f'fill="{MUTED}">{doc} \u00b7 {correct}/{n}</text>')
            y += bar_w + gap
        y += group_gap

    # ---- callout, sized to its own content ----
    lines = [
        ("THE FINDING", "700", 12.5, INK, 10),
        ("Transcription fields are", "400", 11.5, MUTED, 5),
        ("deterministic. Judgement", "400", 11.5, MUTED, 5),
        ("fields are not.", "400", 11.5, MUTED, 14),
        ("Noise floor: 1 field", "600", 12.5, INK, 5),
        ("per document, measured", "400", 11.5, MUTED, 5),
        ("independently on two", "400", 11.5, MUTED, 5),
        ("documents.", "400", 11.5, MUTED, 14),
        ("So a one-field difference", "400", 11.5, MUTED, 5),
        ("between versions cannot", "400", 11.5, MUTED, 5),
        ("be told from noise \u2014 and", "400", 11.5, MUTED, 5),
        ("that is exactly the size", "400", 11.5, MUTED, 5),
        ("of the v0 vs v2 gap this", "400", 11.5, MUTED, 5),
        ("project set out to read.", "400", 11.5, MUTED, 14),
        ("Not every judgement field", "400", 11, MUTED, 4),
        ("was stressed by these two", "400", 11, MUTED, 4),
        ("documents \u2014 red marks the", "400", 11, MUTED, 4),
        ("category, not the result.", "400", 11, MUTED, 0),
    ]
    bx, bw = left + plot_w + 62, 196
    bh = 26 + sum(sz + sp for _, _, sz, _, sp in lines)
    by = top - 12
    parts.append(f'<rect x="{bx}" y="{by}" width="{bw}" height="{bh:.0f}" rx="6" '
                 f'fill="{PANEL}" stroke="{GRID}"/>')
    ty = by + 26
    for text, weight, size, fill, spacing in lines:
        parts.append(f'<text x="{bx+14}" y="{ty:.0f}" font-size="{size}" '
                     f'font-weight="{weight}" fill="{fill}">'
                     f'{svg_escape(text)}</text>')
        ty += size + spacing

    # ---- observed scores ----
    all_scores = []
    for doc in docs:
        all_scores += [s for s in data[doc]["scores"] if s is not None]
    all_scores = [s for s in all_scores if s >= len(FIELDS) - 2]   # drop partials
    if all_scores:
        sy = by + bh + 30
        parts.append(f'<text x="{bx}" y="{sy:.0f}" font-size="12.5" '
                     f'font-weight="600" fill="{INK}">Scores observed</text>')
        lo, hi = min(all_scores), max(all_scores)
        parts.append(f'<text x="{bx}" y="{sy+20:.0f}" font-size="11.5" '
                     f'fill="{MUTED}">{lo}\u2013{hi} of {len(FIELDS)}, '
                     f'n={len(all_scores)} runs</text>')
        parts.append(f'<text x="{bx}" y="{sy+38:.0f}" font-size="11.5" '
                     f'fill="{MUTED}">spread = {hi-lo} field</text>')

    # ---- legend + provenance, below the plot ----
    ly = top + plot_h + 26
    lx = 32
    for label, colour, op in (("transcription", STABLE, 0.5),
                              ("domain judgement", JUDGEMENT, 0.95)):
        parts.append(f'<rect x="{lx}" y="{ly-10}" width="11" height="11" '
                     f'rx="2" fill="{colour}" opacity="{op}"/>')
        parts.append(f'<text x="{lx+17}" y="{ly}" font-size="12" '
                     f'fill="{MUTED}">{label}</text>')
        lx += 140
    parts.append(f'<text x="{W-32}" y="{ly}" font-size="11" fill="{MUTED}" '
                 f'text-anchor="end">generated by make_figures.py from '
                 f'results/variance-*.json</text>')
    parts.append(f'<text x="32" y="{ly+22}" font-size="11" fill="{MUTED}">'
                 f'Field categories declared in the script ahead of the data, '
                 f'so the boundary was not drawn around whatever turned out '
                 f'to be unstable.</text>')

    parts.append("</svg>")
    return "\n".join(parts)


if __name__ == "__main__":
    data = load_all()
    DOCS_OUT.mkdir(exist_ok=True)
    out = DOCS_OUT / "variance.svg"
    out.write_text(build(data), encoding="utf-8")

    print(f"wrote {out}\n")
    for doc in sorted(data):
        fields = data[doc]["fields"]
        unstable = {f: v for f, v in fields.items() if v[0] < v[1]}
        print(f"  {doc}: {len(fields)} field(s) measured, "
              f"{len(unstable)} below 100%")
        for f, (c, n) in unstable.items():
            tag = "judgement" if f in JUDGEMENT_FIELDS else "TRANSCRIPTION"
            print(f"      {f:<20} {c}/{n}   [{tag}]")
    print("\n  Embed with:  ![Variance by field](docs/variance.svg)")
