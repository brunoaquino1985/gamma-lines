#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GAMMA LINES — pipeline de gamma exposure (GEX) para futuros de Ibovespa.

Fontes (arquivos públicos B3):
  - COTAHIST_DDDMMYYYY.TXT : strikes, vencimentos, prêmios de fechamento (opções BOVA11 e IBOV)
  - BVBG.086 (PR / pesquisa por pregão) : open interest por série + ajuste do INDFUT
  - IBOV close : cotacao.b3.com.br (produção) ou informado manualmente

Modelo:
  1. Junta specs (COTAHIST) com OI (PR) para os books BOVA11 e IBOV.
  2. Por vencimento: infere forward e fator de desconto via paridade put-call
     (regressão C-P = a - b*K  =>  DF = b, F = a/b), sem precisar de dividendos.
  3. IV por série (Black-76 sobre o forward); smile quadrático em log-moneyness
     para séries sem prêmio confiável.
  4. GEX por strike: Γ × OI × mult × S² × 0.01  (call +, put −, convenção dealer).
  5. Mapeia tudo para o eixo do futuro: nível_fut = (K / S_book) × INDFUT_ajuste.
  6. Walls = top-8 buckets da grade de 1000 pts × fator; larguras 3/2/2/1...
  7. Curva G(S): gamma líquido total em função do nível do índice
     -> flip = cruzamento de zero mais próximo do spot
     -> max/min gamma = extremos da curva no range ±12%.
  8. Gera código NTSL no formato do indicador original.
"""
import io, math, re, sys, zipfile, datetime as dt
from collections import defaultdict

SQRT2PI = math.sqrt(2.0 * math.pi)

def norm_pdf(x): return math.exp(-0.5 * x * x) / SQRT2PI

def norm_cdf(x): return 0.5 * math.erfc(-x / math.sqrt(2.0))

# ----------------------------------------------------------------------------
# Parsers
# ----------------------------------------------------------------------------

def parse_cotahist(text):
    """Retorna (opções, spots). Opções: lista de dicts para BOVA*/IBOV* (tipmerc 070/080)."""
    opts, spots = [], {}
    for line in text.splitlines():
        if not line.startswith("01"):
            continue
        ticker = line[12:24].strip()
        tipmerc = line[24:27]
        if tipmerc == "010" and ticker == "BOVA11":
            spots["BOVA11"] = int(line[108:121]) / 100.0
        if tipmerc not in ("070", "080"):
            continue
        if not (ticker.startswith("BOVA") or ticker.startswith("IBOV")):
            continue
        und = "BOVA" if ticker.startswith("BOVA") else "IBOV"
        strike = int(line[188:201]) / 100.0
        expiry = dt.datetime.strptime(line[202:210], "%Y%m%d").date()
        premium = int(line[108:121]) / 100.0     # PREULT
        trades = int(line[147:152])
        volume = int(line[170:188]) / 100.0
        opts.append(dict(ticker=ticker, und=und,
                         cp="C" if tipmerc == "070" else "P",
                         strike=strike, expiry=expiry,
                         premium=premium, trades=trades, volume=volume))
    return opts, spots


def parse_pr_oi(text):
    """Extrai OI por ticker e dados do futuro (INDQ..) do XML BVBG.086."""
    oi, fut = {}, {}
    for m in re.finditer(r"<PricRpt>(.*?)</PricRpt>", text, re.S):
        blk = m.group(1)
        tk = re.search(r"<TckrSymb>([^<]+)</TckrSymb>", blk)
        if not tk:
            continue
        tk = tk.group(1)
        o = re.search(r"<OpnIntrst>(\d+)</OpnIntrst>", blk)
        if o and (tk.startswith("BOVA") or tk.startswith("IBOV")):
            oi[tk] = int(o.group(1))
        if re.match(r"^(IND|WIN)[FGHJKMNQUVXZ]\d\d$", tk):
            d = {}
            for tag in ("AdjstdQt", "LastPric", "PrvsAdjstdQt"):
                mm = re.search(rf"<{tag}[^>]*>([\d.]+)</{tag}>", blk)
                if mm:
                    d[tag] = float(mm.group(1))
            oi_f = re.search(r"<OpnIntrst>(\d+)</OpnIntrst>", blk)
            if oi_f:
                d["OI"] = int(oi_f.group(1))
            fut[tk] = d
    return oi, fut

# ----------------------------------------------------------------------------
# Paridade put-call -> forward e fator de desconto por vencimento
# ----------------------------------------------------------------------------

def fit_forward(pairs, spot_hint, r_annual, T):
    """pairs: lista (K, C, P, w). Regressão ponderada C-P = a - b*K.
    Retorna (F, DF). Fallback: F = spot*(1+r)^T, DF = (1+r)^-T."""
    df_fb = (1.0 + r_annual) ** (-T)
    f_fb = spot_hint / df_fb
    good = [(k, c - p, w) for k, c, p, w in pairs
            if c > 0 and p > 0 and 0.7 * spot_hint < k < 1.3 * spot_hint]
    if len(good) < 3:
        return f_fb, df_fb
    sw = sum(w for _, _, w in good)
    mk = sum(k * w for k, _, w in good) / sw
    my = sum(y * w for _, y, w in good) / sw
    cov = sum(w * (k - mk) * (y - my) for k, y, w in good)
    var = sum(w * (k - mk) ** 2 for k, _, w in good)
    if var <= 0:
        return f_fb, df_fb
    b = -cov / var                      # = DF
    a = my + b * mk                     # = DF * F
    if not (0.5 < b <= 1.02):           # regressão degenerada
        return f_fb, df_fb
    return a / b, b

# ----------------------------------------------------------------------------
# Black-76
# ----------------------------------------------------------------------------

def black76(F, K, T, sigma, DF, cp):
    if sigma <= 0 or T <= 0:
        intr = max(F - K, 0.0) if cp == "C" else max(K - F, 0.0)
        return DF * intr
    v = sigma * math.sqrt(T)
    d1 = (math.log(F / K) + 0.5 * v * v) / v
    d2 = d1 - v
    if cp == "C":
        return DF * (F * norm_cdf(d1) - K * norm_cdf(d2))
    return DF * (K * norm_cdf(-d2) - F * norm_cdf(-d1))


def implied_vol(price, F, K, T, DF, cp):
    if price <= 0 or T <= 0:
        return None
    intr = DF * (max(F - K, 0.0) if cp == "C" else max(K - F, 0.0))
    if price <= intr + 1e-12:
        return None
    lo, hi = 1e-3, 5.0
    if black76(F, K, T, hi, DF, cp) < price:
        return None
    for _ in range(80):
        mid = 0.5 * (lo + hi)
        if black76(F, K, T, mid, DF, cp) > price:
            hi = mid
        else:
            lo = mid
    return 0.5 * (lo + hi)


def gamma_black(S, F, K, T, sigma, DF):
    """Gamma spot (d²V/dS²) usando F = S/DF_carry -> Γ = DF*φ(d1)*(F/S)²/(F σ √T)."""
    if sigma <= 0 or T <= 0 or S <= 0:
        return 0.0
    v = sigma * math.sqrt(T)
    d1 = (math.log(F / K) + 0.5 * v * v) / v
    return DF * norm_pdf(d1) * (F / S) ** 2 / (F * v)

# ----------------------------------------------------------------------------
# Smile quadrático por vencimento
# ----------------------------------------------------------------------------

def fit_smile(points):
    """points: (logmoneyness, iv, w). Ajusta iv = c0 + c1*x + c2*x²."""
    if len(points) < 3:
        med = sorted(p[1] for p in points)[len(points) // 2] if points else 0.25
        return lambda x, m=med: m
    import statistics
    n = len(points)
    if n < 6:
        med = statistics.median(p[1] for p in points)
        return lambda x, m=med: m
    sw = sum(w for _, _, w in points)
    X = [[w, w * x, w * x * x] for x, _, w in points]
    # normal equations 3x3
    A = [[0.0] * 3 for _ in range(3)]
    B = [0.0] * 3
    for (x, y, w) in points:
        basis = (1.0, x, x * x)
        for i in range(3):
            B[i] += w * y * basis[i]
            for j in range(3):
                A[i][j] += w * basis[i] * basis[j]
    # solve
    try:
        for i in range(3):
            p = A[i][i]
            if abs(p) < 1e-12:
                raise ZeroDivisionError
            for j in range(i + 1, 3):
                f = A[j][i] / p
                for k in range(3):
                    A[j][k] -= f * A[i][k]
                B[j] -= f * B[i]
        c2 = B[2] / A[2][2]
        c1 = (B[1] - A[1][2] * c2) / A[1][1]
        c0 = (B[0] - A[0][1] * c1 - A[0][2] * c2) / A[0][0]
    except ZeroDivisionError:
        med = statistics.median(p[1] for p in points)
        return lambda x, m=med: m
    lo = min(p[1] for p in points) * 0.5
    hi = max(p[1] for p in points) * 1.5
    return lambda x: min(max(c0 + c1 * x + c2 * x * x, lo, 0.05), hi, 3.0)

# ----------------------------------------------------------------------------
# Núcleo do modelo
# ----------------------------------------------------------------------------

def build_book(opts, oi_map, spot, ref_date, r_annual, min_T_days=1, max_T_days=270):
    """Prepara séries com OI, IV e gregos para um book (BOVA ou IBOV)."""
    by_exp = defaultdict(list)
    for o in opts:
        oi = oi_map.get(o["ticker"], 0)
        T = (o["expiry"] - ref_date).days
        if oi <= 0 or not (min_T_days <= T <= max_T_days):
            continue
        o = dict(o, oi=oi, T=T / 365.0)
        by_exp[o["expiry"]].append(o)

    series = []
    for exp, lst in sorted(by_exp.items()):
        T = lst[0]["T"]
        calls = {o["strike"]: o for o in lst if o["cp"] == "C" and o["trades"] > 0}
        puts = {o["strike"]: o for o in lst if o["cp"] == "P" and o["trades"] > 0}
        pairs = [(k, calls[k]["premium"], puts[k]["premium"],
                  min(calls[k]["trades"], puts[k]["trades"]))
                 for k in set(calls) & set(puts)]
        F, DF = fit_forward(pairs, spot, r_annual, T)
        pts = []
        for o in lst:
            if o["trades"] <= 0 or o["premium"] <= 0:
                continue
            iv = implied_vol(o["premium"], F, o["strike"], T, DF, o["cp"])
            if iv and 0.05 < iv < 2.5:
                x = math.log(o["strike"] / F)
                # OTM tem IV mais limpa; pondera por negócios
                w = o["trades"] * (2.0 if (o["cp"] == "C") == (o["strike"] >= F) else 1.0)
                pts.append((x, iv, w))
        smile = fit_smile(pts)
        for o in lst:
            x = math.log(o["strike"] / F)
            iv_own = None
            if o["trades"] > 0 and o["premium"] > 0:
                iv_own = implied_vol(o["premium"], F, o["strike"], T, DF, o["cp"])
                if iv_own is not None and not (0.05 < iv_own < 2.5):
                    iv_own = None
            iv = iv_own if iv_own is not None else smile(x)
            series.append(dict(o, F=F, DF=DF, iv=iv))
    return series


def gex_of_series(s, S):
    g = gamma_black(S, s["F"] * (S / s["S0"]) if False else s["F"], s["strike"],
                    s["T"], s["iv"], s["DF"])
    return g


def net_gamma_curve(series, spot, mult, s_grid):
    """Gamma líquido dealer (call +, put −) em R$ por 1% de movimento, para cada S."""
    out = []
    for S in s_grid:
        tot = 0.0
        for s in series:
            F = s["F"] * (S / spot)          # forward se move com o spot
            g = gamma_black(S, F, s["strike"], s["T"], s["iv"], s["DF"])
            sgn = 1.0 if s["cp"] == "C" else -1.0
            tot += sgn * g * s["oi"] * mult * S * S * 0.01
        out.append(tot)
    return out


def strike_gex(series, spot, mult):
    """GEX por strike no spot atual (para walls)."""
    m = defaultdict(lambda: [0.0, 0.0, 0.0])   # strike -> [net, abs, oi]
    for s in series:
        g = gamma_black(spot, s["F"], s["strike"], s["T"], s["iv"], s["DF"])
        v = g * s["oi"] * mult * spot * spot * 0.01
        sgn = 1.0 if s["cp"] == "C" else -1.0
        e = m[s["strike"]]
        e[0] += sgn * v
        e[1] += abs(v)
        e[2] += s["oi"]
    return m

# ----------------------------------------------------------------------------
# Orquestração
# ----------------------------------------------------------------------------

def run_model(cot_text, pr_text, ibov_close, r_annual, ref_date,
              fut_pref=None, debug=True):
    opts, spots = parse_cotahist(cot_text)
    oi_map, futs = parse_pr_oi(pr_text)
    bova_spot = spots.get("BOVA11")

    # futuro de referência: o IND com maior OI (contrato cheio, vencimento corrente)
    ind = {k: v for k, v in futs.items() if k.startswith("IND") and "AdjstdQt" in v}
    fut_tk = fut_pref or max(ind, key=lambda k: ind[k].get("OI", 0))
    fut_settle = ind[fut_tk]["AdjstdQt"]
    factor = fut_settle / ibov_close

    bova = build_book([o for o in opts if o["und"] == "BOVA"], oi_map,
                      bova_spot, ref_date, r_annual)
    ibov = build_book([o for o in opts if o["und"] == "IBOV"], oi_map,
                      ibov_close, ref_date, r_annual)

    # --- GEX por strike, mapeado ao eixo do índice ---------------------------
    gx_i = strike_gex(ibov, ibov_close, 1.0)          # R$1 por ponto
    gx_b = strike_gex(bova, bova_spot, 1.0)           # R$ por ação

    idx_gex = defaultdict(lambda: [0.0, 0.0])          # nível_indice -> [net, abs]
    for k, (net, ab, oi) in gx_i.items():
        idx_gex[k][0] += net
        idx_gex[k][1] += ab
    for k, (net, ab, oi) in gx_b.items():
        lvl = k / bova_spot * ibov_close               # strike BOVA -> nível IBOV
        idx_gex[lvl][0] += net
        idx_gex[lvl][1] += ab

    # --- buckets de 1000 pontos (grade de strikes do índice) ----------------
    buckets = defaultdict(lambda: [0.0, 0.0])
    for lvl, (net, ab) in idx_gex.items():
        b = round(lvl / 1000.0) * 1000
        buckets[b][0] += net
        buckets[b][1] += ab

    # walls: os 8 strikes da grade de 1000 pts mais próximos do spot
    # (mesma construção do indicador original: banda contínua ao redor do preço)
    grid = sorted(buckets.keys())
    walls = sorted(grid, key=lambda b: abs(b - ibov_close))[:8]
    walls = sorted(walls)
    # completa a banda caso a grade tenha buracos
    lo_w, hi_w = walls[0], walls[-1]
    walls = [lo_w + i * 1000 for i in range((hi_w - lo_w) // 1000 + 1)][:8]
    ordered = sorted(walls, key=lambda b: -buckets.get(b, [0, 0])[1])
    width = {b: (3 if i == 0 else 2 if i <= 2 else 1)
             for i, b in enumerate(ordered)}
    window = [(b, buckets.get(b, [0.0, 0.0])) for b in
              sorted(b for b in grid if abs(b / ibov_close - 1) <= 0.08)]

    mids = [(walls[i] + walls[i + 1]) / 2.0 for i in range(len(walls) - 1)]

    # --- curva G(S) ----------------------------------------------------------
    lo, hi = ibov_close * 0.88, ibov_close * 1.12
    n = 241
    s_grid = [lo + (hi - lo) * i / (n - 1) for i in range(n)]
    curve_i = net_gamma_curve(ibov, ibov_close, 1.0, s_grid)
    # book BOVA avaliado no eixo do índice: S_bova = S_idx * (bova/ibov)
    ratio = bova_spot / ibov_close
    s_grid_b = [S * ratio for S in s_grid]
    curve_b = net_gamma_curve(bova, bova_spot, 1.0, s_grid_b)
    curve = [a + b for a, b in zip(curve_i, curve_b)]

    # flip: cruzamento de zero mais próximo do spot
    flip = None
    best = 1e18
    for i in range(n - 1):
        a, b = curve[i], curve[i + 1]
        if a == 0 or a * b < 0:
            s0 = s_grid[i] + (s_grid[i + 1] - s_grid[i]) * (0 - a) / (b - a) if b != a else s_grid[i]
            if abs(s0 - ibov_close) < best:
                best = abs(s0 - ibov_close)
                flip = s0
    imax = max(range(n), key=lambda i: curve[i])
    imin = min(range(n), key=lambda i: curve[i])

    res = dict(
        ref_date=ref_date, fut_ticker=fut_tk, fut_settle=fut_settle,
        ibov_close=ibov_close, bova_spot=bova_spot, factor=factor,
        walls=[(w, width[w], w * factor) for w in walls],
        mids=[(m, m * factor) for m in mids],
        flip=(flip, flip * factor if flip else None),
        max_gamma=(s_grid[imax], s_grid[imax] * factor),
        min_gamma=(s_grid[imin], s_grid[imin] * factor),
        n_series=dict(bova=len(bova), ibov=len(ibov)),
        curve=(s_grid, curve),
        buckets={b: tuple(v) for b, v in sorted(window)},
    )
    if debug:
        print(f"[{ref_date}] fut={fut_tk} ajuste={fut_settle:.0f} IBOV={ibov_close:.2f} "
              f"BOVA11={bova_spot:.2f} fator={factor:.7f}")
        print(f"séries com OI: BOVA={len(bova)}  IBOV={len(ibov)}")
        print("buckets (nível: netGEX/absGEX em R$mm):")
        for b, (netv, abv) in sorted(window):
            mark = " <WALL" + str(width.get(b, "")) + ">" if b in width else ""
            print(f"  {b:>7}: net {netv/1e6:>8.1f}  abs {abv/1e6:>8.1f}{mark}")
        print(f"flip:  {res['flip']}")
        print(f"maxG:  {res['max_gamma']}   minG: {res['min_gamma']}")
    return res
