"""GAMMA LINES — gera output/tv.png: sessão anterior (ticks) + mapa do dia.

Roda dentro do GitHub Actions (matplotlib), sem depender de screenshot.
"""
import os
import sys


def render(out_dir, work_dir, res, meta, vp, btm, ticker):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    tz = os.path.join(work_dir, f"ticks_{meta['ref']}.zip")
    if not os.path.exists(tz):
        # baixa os ticks da sessão anterior (mesma fonte do volume profile)
        import urllib.request
        url = f"https://drp.b3.com.br/rapinegocios/tickercsv/{meta['ref']}?type=1"
        req = urllib.request.Request(
            url, headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) gamma-lines/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=900) as r, open(tz, "wb") as f:
                while True:
                    chunk = r.read(1 << 20)
                    if not chunk:
                        break
                    f.write(chunk)
        except Exception as e:
            if os.path.exists(tz):
                os.remove(tz)
            print(f"[tv.png] download de ticks falhou: {e}", file=sys.stderr)
            return False
    bars = btm.minute_bars(tz, ticker)
    if len(bars) < 30:
        print("[tv.png] poucas barras — pulando", file=sys.stderr)
        return False

    # agrega em candles de 15 minutos (mesmo visual do TradingView)
    cds = []
    prev_close = None
    for hhmm, hi, lo, cl, _v in bars:
        slot = (hhmm // 100) * 100 + (hhmm % 100) // 15 * 15
        if not cds or cds[-1][0] != slot:
            cds.append([slot, prev_close if prev_close is not None else cl,
                        hi, lo, cl])
        else:
            c = cds[-1]
            c[2] = max(c[2], hi)
            c[3] = min(c[3], lo)
            c[4] = cl
        prev_close = cl

    xs = list(range(len(cds)))
    labs = [c[0] for c in cds]
    lo_px, hi_px = min(c[3] for c in cds), max(c[2] for c in cds)
    pad = (hi_px - lo_px) * 0.35 + 200
    y0, y1 = lo_px - pad, hi_px + pad

    fmt = lambda v: f"{v:,.0f}".replace(",", ".")
    fig, ax = plt.subplots(figsize=(12.6, 7.1), dpi=110)
    fig.patch.set_facecolor("#070b11")
    ax.set_facecolor("#0d1420")

    def hl(y, color, ls, label, lw):
        if not (y0 <= y <= y1):
            return
        ax.axhline(y, color=color, ls=ls, lw=lw, alpha=0.9)
        ax.annotate(" " + label, (len(xs) - 1, y), color=color, fontsize=8.5,
                    va="bottom", ha="right",
                    xycoords=("data", "data"))

    for k, w, f in res["walls"]:
        hl(f, "#32cd32", "-", f"WALL {'★' * w} {fmt(f)}", 0.7 + 0.6 * w)
    for _, f in res["mids"]:
        hl(f, "#2a6b4f", ":", f"mid {fmt(f)}", 0.8)
    if res["flip"][1]:
        hl(res["flip"][1], "#ffd700", "-", f"GAMMA FLIP {fmt(res['flip'][1])}", 1.6)
    p = res.get("prob") or {}
    if p.get("band_up_fut"):
        hl(p["band_up_fut"], "#00ced1", "--", f"+1σ {fmt(p['band_up_fut'])}", 1.0)
        hl(p["band_down_fut"], "#00ced1", "--", f"−1σ {fmt(p['band_down_fut'])}", 1.0)
    if vp and vp.get("d1"):
        d1 = vp["d1"]
        hl(d1["poc"], "#ff00ff", "-", f"POC {fmt(d1['poc'])}", 1.4)
        hl(d1["vah"], "#c0c0c0", "--", f"VAH {fmt(d1['vah'])}", 0.9)
        hl(d1["val"], "#c0c0c0", "--", f"VAL {fmt(d1['val'])}", 0.9)

    up, dn = "#089981", "#f23645"
    for i, (_t, o, h, l, c) in enumerate(cds):
        col = up if c >= o else dn
        ax.plot([i, i], [l, h], color=col, lw=0.9, zorder=5)
        ax.add_patch(plt.Rectangle((i - 0.32, min(o, c)), 0.64,
                     max(abs(c - o), (hi_px - lo_px) * 0.0015),
                     facecolor=col, edgecolor=col, lw=0.5, zorder=6))

    ax.set_ylim(y0, y1)
    ax.set_xlim(-1, len(xs))
    step = max(1, len(xs) // 9)
    ax.set_xticks(xs[::step])
    ax.set_xticklabels([f"{l // 100:02d}:{l % 100:02d}" for l in labs[::step]],
                       color="#7b8ba1", fontsize=8.5)
    ax.tick_params(colors="#7b8ba1", labelsize=8.5)
    for s in ax.spines.values():
        s.set_color("#1b2433")
    ax.grid(color="#141d2c", lw=0.5)
    ax.set_title(f"{ticker} 15 min — sessão de {meta['ref']}  ·  GAMMA LINES para {meta['session']}",
                 color="#dbe7f4", fontsize=11, pad=10)
    fig.tight_layout()
    path = os.path.join(out_dir, "tv.png")
    fig.savefig(path, facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"[tv.png] gerado: {path}")
    return True
