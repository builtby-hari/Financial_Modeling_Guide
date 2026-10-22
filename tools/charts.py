"""Render the guide's charts from JSON specs, standard library only.

Usage: python3 tools/charts.py            # renders docs/charts/specs/*.json -> docs/charts/*.svg
       python3 tools/charts.py name ...   # renders only the named specs

Each chart is a self-contained SVG on a light card, so it reads the same on GitHub (light or dark)
and in Obsidian. Spec format (all numbers are the worked-example numbers from the module):

  {"type": "bar" | "waterfall" | "line" | "heatmap" | "football" | "stacked",
   "title": "...", "subtitle": "...", "source": "Module 07, made-up numbers",
   "fmt": {"prefix": "$", "suffix": "M", "decimals": 0},  # value labels and axis
   ...type-specific fields, see the render_* functions...}
"""

import html
import json
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SPECS = os.path.join(ROOT, "docs", "charts", "specs")
OUT = os.path.join(ROOT, "docs", "charts")

NAVY, TEAL, SLATE, RED, INK, MUTED, GRID, AXIS = (
    "#1f3a5f", "#14b8a6", "#94a3b8", "#c2410c", "#1e293b", "#475569", "#e2e8f0", "#94a3b8")
SERIES = [NAVY, TEAL, SLATE, "#0e7490", "#64748b", "#5eead4"]
FONT = "Helvetica, Arial, sans-serif"
W = 760


def esc(s):
    return html.escape(str(s), quote=True)


def fmt(v, f):
    f = f or {}
    d = f.get("decimals", 0)
    neg = v < 0
    s = f"{abs(v):,.{d}f}"
    s = f"{f.get('prefix', '')}{s}{f.get('suffix', '')}"
    return f"({s})" if neg and f.get("paren") else ("-" + s if neg else s)


def nice_ticks(lo, hi, n=5):
    if hi == lo:
        hi = lo + 1
    raw = (hi - lo) / n
    mag = 10 ** math.floor(math.log10(raw))
    step = min((m * mag for m in (1, 2, 2.5, 5, 10) if m * mag >= raw), default=10 * mag)
    start = math.floor(lo / step) * step
    ticks, t = [], start
    while t <= hi + step * 0.001:
        ticks.append(round(t, 10))
        t += step
    if ticks[-1] < hi:
        ticks.append(ticks[-1] + step)
    return ticks


def text(x, y, s, size=12, fill=INK, anchor="start", weight="normal", extra=""):
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-family="{FONT}" font-size="{size}" fill="{fill}" '
            f'text-anchor="{anchor}" font-weight="{weight}"{extra}>{esc(s)}</text>')


class Frame:
    """Card, title block and a plot area; y maps values to pixels."""

    def __init__(self, spec, height=440, left=78, right=28, bottom=64, legend=None):
        self.spec, self.h = spec, height
        self.parts = []
        top = (74 if spec.get("subtitle") else 58) + 22
        if legend:
            top += 24
        self.x0, self.x1, self.y0, self.y1 = left, W - right, top, height - bottom
        self.legend = legend

    def scale(self, lo, hi):
        self.ticks = nice_ticks(min(lo, 0) if lo >= 0 else lo, hi)
        self.lo, self.hi = self.ticks[0], self.ticks[-1]

    def y(self, v):
        return self.y1 - (v - self.lo) / (self.hi - self.lo) * (self.y1 - self.y0)

    def axes(self, f, y_label=None):
        p = self.parts
        for t in self.ticks:
            yy = self.y(t)
            p.append(f'<line x1="{self.x0}" x2="{self.x1}" y1="{yy:.1f}" y2="{yy:.1f}" stroke="{GRID}"/>')
            p.append(text(self.x0 - 8, yy + 4, fmt(t, f), 11, MUTED, "end"))
        if self.lo < 0 < self.hi:
            p.append(f'<line x1="{self.x0}" x2="{self.x1}" y1="{self.y(0):.1f}" y2="{self.y(0):.1f}" stroke="{AXIS}"/>')
        if y_label:
            cy = (self.y0 + self.y1) / 2
            p.append(text(18, cy, y_label, 11, MUTED, "middle", extra=f' transform="rotate(-90 18 {cy:.1f})"'))

    def svg(self):
        s, h = self.spec, self.h
        head = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {h}" width="{W}" height="{h}" '
                f'role="img" aria-label="{esc(s["title"])}">',
                f'<rect x="1" y="1" width="{W - 2}" height="{h - 2}" rx="12" fill="#ffffff" stroke="#d0d7de" stroke-width="1.5"/>',
                f'<rect x="28" y="20" width="40" height="4" rx="2" fill="{TEAL}"/>',
                text(28, 46, s["title"], 17, NAVY, weight="bold")]
        if s.get("subtitle"):
            head.append(text(28, 64, s["subtitle"], 12, MUTED))
        if self.legend:
            lx = 28
            ly = (74 if s.get("subtitle") else 58) + 4
            for name, color in self.legend:
                head.append(f'<rect x="{lx}" y="{ly}" width="12" height="12" rx="2" fill="{color}"/>')
                head.append(text(lx + 18, ly + 10, name, 11, INK))
                lx += 40 + 7.2 * len(name)
        foot = [text(W - 20, h - 12, s.get("source", "Made-up numbers for illustration"), 10, SLATE, "end")]
        return "\n".join(head + self.parts + foot + ["</svg>"]) + "\n"


def wrap_label(s, width=14):
    words, lines, cur = str(s).split(), [], ""
    for w in words:
        if cur and len(cur) + 1 + len(w) > width:
            lines.append(cur)
            cur = w
        else:
            cur = (cur + " " + w).strip()
    lines.append(cur)
    return lines[:3]


def x_labels(fr, centers, labels, slot):
    width = max(6, int(slot / 6.2))
    for cx, lab in zip(centers, labels):
        for i, line in enumerate(wrap_label(lab, width)):
            fr.parts.append(text(cx, fr.y1 + 18 + 13 * i, line, 11, INK, "middle"))


def render_bar(s):
    """categories: [...]; series: [{"name", "values": [...]}]; labels: true to print values."""
    cats, series, f = s["categories"], s["series"], s.get("fmt")
    legend = [(x["name"], SERIES[i % 6]) for i, x in enumerate(series)] if len(series) > 1 else None
    fr = Frame(s, legend=legend)
    vals = [v for x in series for v in x["values"]]
    lo_, hi_ = min(vals + [0]), max(vals + [0])
    fr.scale(lo_ - (hi_ - lo_) * 0.06 if lo_ < 0 else lo_, hi_ + (hi_ - lo_) * 0.06)
    fr.axes(f, s.get("y_label"))
    slot = (fr.x1 - fr.x0) / len(cats)
    bw = min(56, slot * 0.7 / len(series))
    centers = []
    for i, _ in enumerate(cats):
        cx = fr.x0 + slot * (i + 0.5)
        centers.append(cx)
        for j, ser in enumerate(series):
            v = ser["values"][i]
            x = cx - bw * len(series) / 2 + j * bw
            y_top, y_bot = sorted((fr.y(v), fr.y(0)))
            color = ser.get("color") or (SERIES[j % 6] if len(series) > 1 else (RED if v < 0 and s.get("neg_red", True) else NAVY))
            fr.parts.append(f'<rect x="{x + 1:.1f}" y="{y_top:.1f}" width="{bw - 2:.1f}" height="{max(y_bot - y_top, 0.5):.1f}" rx="2" fill="{color}"/>')
            if s.get("labels", True):
                ly = y_top - 5 if v >= 0 else y_bot + 13
                fr.parts.append(text(x + bw / 2, ly, fmt(v, f), 10.5, INK, "middle"))
    x_labels(fr, centers, cats, slot)
    return fr.svg()


def render_waterfall(s):
    """steps: [{"label", "value", "total": true|false}]; a total bar is drawn from zero at its value."""
    steps, f = s["steps"], s.get("fmt")
    fr = Frame(s)
    run, bars = 0.0, []
    for st in steps:
        if st.get("total"):
            bars.append((st["label"], 0.0, st["value"], "total"))
            run = st["value"]
        else:
            bars.append((st["label"], run, run + st["value"], "up" if st["value"] >= 0 else "down"))
            run += st["value"]
    vals = [b for x in bars for b in x[1:3]]
    lo = min(vals)
    if s.get("floor") is not None:
        lo = s["floor"]
    fr.scale(lo if lo < 0 or s.get("floor") is not None else 0, max(vals) + (max(vals) - min(min(vals), 0)) * 0.06)
    if s.get("floor") is not None:
        fr.lo = s["floor"]
        fr.ticks = [t for t in fr.ticks if t >= fr.lo]
    fr.axes(f, s.get("y_label"))
    slot = (fr.x1 - fr.x0) / len(bars)
    bw = min(64, slot * 0.66)
    centers, prev_end = [], None
    for i, (lab, a, b, kind) in enumerate(bars):
        cx = fr.x0 + slot * (i + 0.5)
        centers.append(cx)
        a_ = max(a, fr.lo)
        ya, yb = sorted((fr.y(a_), fr.y(b)))
        color = {"total": NAVY, "up": TEAL, "down": RED}[kind]
        fr.parts.append(f'<rect x="{cx - bw / 2:.1f}" y="{ya:.1f}" width="{bw:.1f}" height="{max(yb - ya, 0.5):.1f}" rx="2" fill="{color}"/>')
        v = b if kind == "total" else b - a
        label = fmt(v, f) if kind == "total" else ("+" if v >= 0 else "") + fmt(v, f)
        fr.parts.append(text(cx, ya - 5, label, 10.5, INK, "middle"))
        if prev_end is not None:
            yy = fr.y(prev_end[1])
            fr.parts.append(f'<line x1="{prev_end[0]:.1f}" x2="{cx - bw / 2:.1f}" y1="{yy:.1f}" y2="{yy:.1f}" stroke="{SLATE}" stroke-dasharray="3 3"/>')
        prev_end = (cx + bw / 2, b)
    x_labels(fr, centers, [b[0] for b in bars], slot)
    return fr.svg()


def render_line(s):
    """x: [...] (numbers or labels); series: [{"name", "values"}]; x_label; markers: true."""
    xs, series, f = s["x"], s["series"], s.get("fmt")
    legend = [(x["name"], SERIES[i % 6]) for i, x in enumerate(series)] if len(series) > 1 else None
    fr = Frame(s, legend=legend)
    vals = [v for x in series for v in x["values"] if v is not None]
    lo, hi = min(vals), max(vals)
    pad = (hi - lo) * 0.08 or 1
    fr.scale(lo - pad if lo < 0 or s.get("tight") else min(0, lo), hi + pad)
    if s.get("tight"):
        fr.ticks = nice_ticks(lo - pad, hi + pad)
        fr.lo, fr.hi = fr.ticks[0], fr.ticks[-1]
    fr.axes(f, s.get("y_label"))
    n = len(xs)
    px = lambda i: fr.x0 + (fr.x1 - fr.x0) * (i / (n - 1) if n > 1 else 0.5)
    for j, ser in enumerate(series):
        pts = [(px(i), fr.y(v)) for i, v in enumerate(ser["values"]) if v is not None]
        color = SERIES[j % 6]
        dash = ' stroke-dasharray="6 4"' if ser.get("dashed") else ""
        fr.parts.append(f'<polyline fill="none" stroke="{color}" stroke-width="2.5"{dash} points="'
                        + " ".join(f"{a:.1f},{b:.1f}" for a, b in pts) + '"/>')
        if s.get("markers", n <= 12):
            for a, b in pts:
                fr.parts.append(f'<circle cx="{a:.1f}" cy="{b:.1f}" r="3.5" fill="{color}"/>')
    step = max(1, n // 10)
    xf = s.get("x_fmt")
    for i in range(0, n, step):
        lab = fmt(xs[i], xf) if xf and isinstance(xs[i], (int, float)) else xs[i]
        fr.parts.append(text(px(i), fr.y1 + 18, lab, 11, INK, "middle"))
    if s.get("x_label"):
        fr.parts.append(text((fr.x0 + fr.x1) / 2, fr.y1 + 40, s["x_label"], 11, MUTED, "middle"))
    return fr.svg()


def render_stacked(s):
    """categories; series: [{"name", "values"}] stacked bottom to top; total labels on top."""
    cats, series, f = s["categories"], s["series"], s.get("fmt")
    fr = Frame(s, legend=[(x["name"], SERIES[i % 6]) for i, x in enumerate(series)])
    totals = [sum(x["values"][i] for x in series) for i in range(len(cats))]
    fr.scale(0, max(totals) * 1.06)
    fr.axes(f, s.get("y_label"))
    slot = (fr.x1 - fr.x0) / len(cats)
    bw = min(64, slot * 0.6)
    centers = []
    for i, _ in enumerate(cats):
        cx = fr.x0 + slot * (i + 0.5)
        centers.append(cx)
        base = 0.0
        for j, ser in enumerate(series):
            v = ser["values"][i]
            ya, yb = fr.y(base + v), fr.y(base)
            fr.parts.append(f'<rect x="{cx - bw / 2:.1f}" y="{ya:.1f}" width="{bw:.1f}" height="{max(yb - ya, 0):.1f}" fill="{SERIES[j % 6]}"/>')
            base += v
        fr.parts.append(text(cx, fr.y(base) - 5, fmt(base, f), 10.5, INK, "middle"))
    x_labels(fr, centers, cats, slot)
    return fr.svg()


def render_football(s):
    """rows: [{"label", "low", "high"}]; marker: {"label", "value"} draws a vertical reference line."""
    rows, f = s["rows"], s.get("fmt")
    h = 120 + 46 * len(rows) + (24 if s.get("subtitle") else 0)
    fr = Frame(s, height=h + 30, left=190, bottom=56)
    vals = [v for r in rows for v in (r["low"], r["high"])] + ([s["marker"]["value"]] if s.get("marker") else [])
    ticks = nice_ticks(min(vals) * 0.95, max(vals) * 1.05)
    lo, hi = ticks[0], ticks[-1]
    px = lambda v: fr.x0 + (v - lo) / (hi - lo) * (fr.x1 - fr.x0)
    for t in ticks:
        fr.parts.append(f'<line x1="{px(t):.1f}" x2="{px(t):.1f}" y1="{fr.y0}" y2="{fr.y1}" stroke="{GRID}"/>')
        fr.parts.append(text(px(t), fr.y1 + 16, fmt(t, f), 11, MUTED, "middle"))
    rh = (fr.y1 - fr.y0) / len(rows)
    for i, r in enumerate(rows):
        cy = fr.y0 + rh * (i + 0.5)
        fr.parts.append(text(fr.x0 - 12, cy + 4, r["label"], 12, INK, "end"))
        x_a, x_b = px(r["low"]), px(r["high"])
        fr.parts.append(f'<rect x="{x_a:.1f}" y="{cy - 11:.1f}" width="{max(x_b - x_a, 2):.1f}" height="22" rx="3" fill="{SERIES[i % 2]}"/>')
        fr.parts.append(text(x_a - 5, cy + 4, fmt(r["low"], f), 10.5, INK, "end"))
        fr.parts.append(text(x_b + 5, cy + 4, fmt(r["high"], f), 10.5, INK))
    if s.get("marker"):
        m = s["marker"]
        xm = px(m["value"])
        fr.parts.append(f'<line x1="{xm:.1f}" x2="{xm:.1f}" y1="{fr.y0 - 4}" y2="{fr.y1}" stroke="{RED}" stroke-width="2" stroke-dasharray="5 4"/>')
        fr.parts.append(text(xm, fr.y0 - 12, f'{m["label"]}: {fmt(m["value"], f)}', 11, RED, "middle", "bold"))
    return fr.svg()


def render_heatmap(s):
    """rows/cols: labels with row_title/col_title; values: matrix; base: [r, c] to outline."""
    rows, cols, m, f = s["rows"], s["cols"], s["values"], s.get("fmt")
    cw, ch = min(150, (W - 220) / len(cols)), 36
    h = 150 + ch * len(rows) + (16 if s.get("subtitle") else 0)
    fr = Frame(s, height=int(h), left=150, bottom=30)
    flat = [v for r in m for v in r]
    lo, hi = min(flat), max(flat)
    x0 = fr.x0 + ((fr.x1 - fr.x0) - cw * len(cols)) / 2
    y0 = fr.y0 + 26
    fr.parts.append(text(x0 + cw * len(cols) / 2, y0 - 12, s.get("col_title", ""), 11, MUTED, "middle", "bold"))
    fr.parts.append(text(x0 - 70, y0 + ch * len(rows) / 2, s.get("row_title", ""), 11, MUTED, "middle", "bold",
                         f' transform="rotate(-90 {x0 - 70:.1f} {y0 + ch * len(rows) / 2:.1f})"'))
    cf = s.get("label_fmt")
    for j, c in enumerate(cols):
        fr.parts.append(text(x0 + cw * (j + 0.5), y0 + ch * len(rows) + 16, fmt(c, cf) if cf and isinstance(c, (int, float)) else c, 11, INK, "middle"))
    rf = s.get("row_fmt")
    for i, r in enumerate(rows):
        fr.parts.append(text(x0 - 8, y0 + ch * (i + 0.5) + 4, fmt(r, rf) if rf and isinstance(r, (int, float)) else r, 11, INK, "end"))
        for j, v in enumerate(m[i]):
            t = (v - lo) / (hi - lo) if hi > lo else 0.5
            fill = mix("#f0fdfa", "#0f766e", t)
            ink = "#ffffff" if t > 0.55 else INK
            fr.parts.append(f'<rect x="{x0 + cw * j:.1f}" y="{y0 + ch * i:.1f}" width="{cw - 2:.1f}" height="{ch - 2:.1f}" rx="3" fill="{fill}"/>')
            fr.parts.append(text(x0 + cw * (j + 0.5), y0 + ch * (i + 0.5) + 4, fmt(v, f), 11.5, ink, "middle"))
    if s.get("base"):
        bi, bj = s["base"]
        fr.parts.append(f'<rect x="{x0 + cw * bj - 1:.1f}" y="{y0 + ch * bi - 1:.1f}" width="{cw:.1f}" height="{ch:.1f}" rx="3" fill="none" stroke="{NAVY}" stroke-width="2.5"/>')
    return fr.svg()


def mix(a, b, t):
    ca = [int(a[i:i + 2], 16) for i in (1, 3, 5)]
    cb = [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(ca, cb))


RENDER = {"bar": render_bar, "waterfall": render_waterfall, "line": render_line,
          "stacked": render_stacked, "football": render_football, "heatmap": render_heatmap}


def main(names):
    files = sorted(f for f in os.listdir(SPECS) if f.endswith(".json"))
    if names:
        files = [f for f in files if f[:-5] in names]
    for fn in files:
        with open(os.path.join(SPECS, fn)) as fh:
            spec = json.load(fh)
        svg = RENDER[spec["type"]](spec)
        with open(os.path.join(OUT, fn[:-5] + ".svg"), "w") as fh:
            fh.write(svg)
        print("wrote", fn[:-5] + ".svg")


if __name__ == "__main__":
    main(sys.argv[1:])
