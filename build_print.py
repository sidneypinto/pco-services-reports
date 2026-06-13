#!/usr/bin/env python3
"""Assemble `print.html` from the individual service-order report templates.

Each source report (`main-so.html`, `audio-so.html`, ...) is a self-contained
Liquid + HTML document with its OWN <style> block. Those style blocks reuse the
same class names (.col, .col-time, ...) with DIFFERENT values, so they cannot be
dropped into one global stylesheet as-is — the last one would win and corrupt the
others. This script scopes each report's CSS under a unique wrapper class and then
emits the requested number of copies, each on its own page.
"""
import re
from pathlib import Path

HERE = Path(__file__).parent

# (source file, wrapper class, how many copies to print)
REPORTS = [
    ("main-so.html",   "rpt-main",   8),
    ("audio-so.html",  "rpt-audio",  3),
    ("cg3-so.html",    "rpt-cg3",    1),
    ("pixera-so.html", "rpt-pixera", 2),
]

COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)


def split_blocks(css):
    """Split a flat/at-rule CSS string into top-level (prelude, body) blocks."""
    blocks, prelude, depth, body, i = [], "", 0, "", 0
    n = len(css)
    while i < n:
        ch = css[i]
        if ch == "{":
            if depth == 0:
                # prelude collected; start capturing the brace body
                depth = 1
                body = ""
            else:
                depth += 1
                body += ch
        elif ch == "}":
            depth -= 1
            if depth == 0:
                blocks.append((prelude.strip(), body))
                prelude, body = "", ""
            else:
                body += ch
        else:
            if depth == 0:
                prelude += ch
            else:
                body += ch
        i += 1
    return blocks


def scope_selector(sel, wrap):
    sel = sel.strip()
    if sel == "*":
        return f".{wrap} *"
    if sel in ("html", "body", "html, body"):
        return f".{wrap}"
    return f".{wrap} {sel}"


def scope_selector_list(prelude, wrap):
    return ", ".join(scope_selector(s, wrap) for s in prelude.split(","))


def scope_css(css, wrap):
    css = COMMENT_RE.sub("", css)
    out = []
    for prelude, body in split_blocks(css):
        if not prelude:
            continue
        if prelude.startswith("@page"):
            # hoisted to a single global @page rule; drop the per-report copy
            continue
        if prelude.startswith("@media"):
            inner = "\n".join(
                f"  {scope_selector_list(p, wrap)} {{{b}}}"
                for p, b in split_blocks(body)
            )
            out.append(f"{prelude} {{\n{inner}\n}}")
        else:
            out.append(f"{scope_selector_list(prelude, wrap)} {{{body}}}")
    return "\n".join(out)


def parse_report(path):
    text = path.read_text()
    s = text.index("<style>")
    e = text.index("</style>") + len("</style>")
    pre = text[:s]                                   # leading Liquid assigns
    css = text[s + len("<style>"): text.index("</style>")]
    markup = text[e:]                                # body markup + footer
    return pre, css, markup


def main():
    scoped_styles, instances = [], []
    for fname, wrap, count in REPORTS:
        pre, css, markup = parse_report(HERE / fname)
        scoped_styles.append(
            f"    /* ===== {fname} ===== */\n{scope_css(css, wrap)}"
        )
        for _ in range(count):
            instances.append(
                f"{pre}\n<div class=\"report-page {wrap}\">\n{markup}\n</div>"
            )

    styles = "\n\n".join(scoped_styles)
    body = "\n\n".join(instances)

    out = f"""<style>
  /* ---- Global page setup (shared by every report) ---- */
  @page {{
    size: letter portrait;
    margin: 0.18in;
  }}

  * {{
    box-sizing: border-box;
  }}

  html,
  body {{
    margin: 0;
    padding: 0;
    background: #ffffff;
  }}

  /* Each report starts on a fresh page; this also puts the required page
     break between consecutive reports. The first one stays on page 1. */
  .report-page {{
    page-break-before: always;
    break-before: page;
  }}

  .report-page:first-child {{
    page-break-before: avoid;
    break-before: avoid;
  }}

  /* ---- Per-report styles, scoped so the four reports don't clash ---- */
{styles}
</style>

{body}
"""
    (HERE / "print.html").write_text(out)
    total = sum(c for _, _, c in REPORTS)
    print(f"Wrote print.html — {total} report pages "
          + ", ".join(f"{c}x {f}" for f, _, c in REPORTS))


if __name__ == "__main__":
    main()
