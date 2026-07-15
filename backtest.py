#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Backtest das zonas do GAMMA LINES: compara o mapa previsto de cada sessão
com o que o mercado realmente fez (ticks do WIN da própria sessão).

Definições (em pontos do WIN/IND):
  TOQUE     — o preço chega a <=100 pts de uma wall.
  ROMPIMENTO— depois do toque, o preço ultrapassa a wall em >=200 pts.
  REJEIÇÃO  — depois do toque, o preço se afasta >=400 pts de volta para o
              lado de onde veio, antes de romper.
  NEUTRO    — a sessão termina sem definir (nem rejeitou, nem rompeu).
Bandas: sessão "dentro" se máxima <= banda_sup e mínima >= banda_inf.
POC: "imã" se o preço negociou a <=50 pts do POC em algum momento.
Área de valor: abertura dentro/fora; dia de rotação se fecha dentro.
Flip: se a sessão cruzou o flip para baixo, mede a queda adicional.

v2 (Onda 5): cada registro guarda também o regime de gamma do dia, o lado
do fluxo estrangeiro conhecido na manhã, a hora do primeiro toque em cada
wall e o volume por hora — permitindo estatísticas condicionais, de gap e
o "relógio do pregão".
"""
import csv
import datetime as dt
import io
import json
import os
import zipfile

TOUCH_TOL = 100.0
BREAK_TOL = 200.0
REJECT_TGT = 400.0
POC_TOL = 50.0
REC_VERSION = 2


# ---------------------------------------------------------------- ticks
def minute_bars(zpath, ticker):
    """Barras de 1 min [(hhmm, high, low, close, volume)] da sessão regular."""
    bars = {}
    needle = ";" + ticker + ";"
    with zipfile.ZipFile(zpath) as z:
        name = z.namelist()[0]
        with z.open(name) as f:
            t = io.TextIOWrapper(f, encoding="latin-1", errors="ignore")
            t.readline()
            for line in t:
                if needle not in line:
                    continue
                p = line.rstrip("\n").split(";")
                if len(p) < 8 or p[1] != ticker or p[7] not in ("1", ""):
                    continue
                try:
                    px = float(p[3].replace(".", "").replace(",", "."))
                    hhmm = int(p[5][:4])
                except (ValueError, IndexError):
                    continue
                try:
                    qty = int(p[4])
                except (ValueError, IndexError):
                    qty = 1
                b = bars.get(hhmm)
                if b is None:
                    bars[hhmm] = [px, px, px, qty]
                else:
                    if px > b[0]:
                        b[0] = px
                    if px < b[1]:
                        b[1] = px
                    b[2] = px
                    b[3] += qty
    return [(k, v[0], v[1], v[2], v[3]) for k, v in sorted(bars.items())]


# ------------------------------------------------------- fluxo (contexto)
def flow_side_for(csv_path, session_str):
    """Lado do fluxo estrangeiro conhecido na manhã da sessão: soma das
    últimas 5 leituras ANTERIORES à sessão. 'comprador'/'vendedor'/None."""
    try:
        rows = []
        with open(csv_path, encoding="utf-8") as f:
            for r in csv.DictReader(f):
                if r.get("session") and r["session"] < session_str:
                    rows.append(float(r["estrangeiro_saldo_mi"]))
        if not rows:
            return None
        s = sum(rows[-5:])
        return "comprador" if s >= 0 else "vendedor"
    except Exception:
        return None


# ---------------------------------------------------------------- avaliação
def _eval_level(bars, level, open_px):
    """Avalia um nível: primeiro toque -> rejeição/rompimento/neutro.
    Retorna None se nunca tocou."""
    side = 1.0 if open_px >= level else -1.0     # lado de onde o preço vem
    touched = False
    touch_hhmm = None
    outcome = "neutro"
    mfe = 0.0                                     # excursão máxima pós-toque
    prev_close = open_px
    for i, (hhmm, hi, lo, close, _q) in enumerate(bars):
        # faixa efetiva da barra inclui o fechamento anterior (cobre gaps)
        ehi, elo = max(hi, prev_close), min(lo, prev_close)
        prev_close = close
        if not touched:
            near = (elo - TOUCH_TOL) <= level <= (ehi + TOUCH_TOL)
            if near:
                touched = True
                touch_hhmm = hhmm
                # recalcula o lado com o fechamento anterior (mais fiel)
                if i > 0:
                    prev_close = bars[i - 1][3]
                    if abs(prev_close - level) > TOUCH_TOL:
                        side = 1.0 if prev_close >= level else -1.0
            continue
        # depois do toque
        beyond = (level - elo) if side > 0 else (ehi - level)
        back = (ehi - level) if side > 0 else (level - elo)
        if back > mfe:
            mfe = back
        if beyond >= BREAK_TOL:
            outcome = "rompeu"
            break
        if back >= REJECT_TGT:
            outcome = "rejeitou"
            break
    if not touched:
        return None
    return dict(outcome=outcome, side=("acima" if side > 0 else "abaixo"),
                mfe=round(mfe, 1), hora=touch_hhmm)


def eval_session(levels, bars, flow_side=None):
    """levels: dict no formato do levels.json; bars: minute_bars da sessão.
    Retorna o registro da sessão (ou None se sem barras)."""
    if not bars:
        return None
    open_px = bars[0][3]
    hi = max(b[1] for b in bars)
    lo = min(b[2] for b in bars)
    close_px = bars[-1][3]

    regime = None
    try:
        spot = float(levels["ibov_close"]) * float(levels["fator"])
        flip_v = levels.get("gamma_flip")
        if flip_v:
            regime = "pos" if spot >= float(flip_v) else "neg"
    except Exception:
        pass

    vol_h = {}
    for hhmm, _h, _l, _c, q in bars:
        h = hhmm // 100
        if 9 <= h <= 18:
            vol_h[str(h)] = vol_h.get(str(h), 0) + q

    rec = dict(v=REC_VERSION, session=levels.get("session"), open=open_px,
               high=hi, low=lo, close=close_px, regime=regime,
               fluxo=flow_side, vol_h=vol_h, walls=[], bands=None,
               flip=None, poc=None, va=None)

    for w in levels.get("walls") or []:
        r = _eval_level(bars, float(w["fut"]), open_px)
        if r:
            r["width"] = w["width"]
            r["level"] = w["fut"]
            rec["walls"].append(r)

    prob = levels.get("prob") or {}
    bu, bd = prob.get("band_up"), prob.get("band_down")
    if bu and bd:
        rec["bands"] = dict(inside=bool(hi <= bu and lo >= bd),
                            broke_up=bool(hi > bu), broke_down=bool(lo < bd))

    flip = levels.get("gamma_flip")
    if flip:
        crossed = lo < flip <= max(open_px, hi)
        extra = round(flip - lo, 1) if crossed else None
        rec["flip"] = dict(crossed_down=bool(crossed), extra_drop=extra)

    vp = levels.get("vp") or {}
    d1 = vp.get("d1") or {}
    if d1.get("poc"):
        poc = float(d1["poc"])
        # preço é contínuo: se o POC está dentro do range da sessão, foi tocado
        touched = (lo - POC_TOL) <= poc <= (hi + POC_TOL)
        rec["poc"] = dict(touched=bool(touched))
    if d1.get("vah") and d1.get("val"):
        vah, val = float(d1["vah"]), float(d1["val"])
        oi = val <= open_px <= vah
        ci = val <= close_px <= vah
        rec["va"] = dict(open_inside=bool(oi), close_inside=bool(ci))
    return rec


# ---------------------------------------------------------------- agregação
def _wall_bucket():
    return dict(toques=0, rejeitou=0, rompeu=0, neutro=0)


def _wall_rate(g):
    dec = g["rejeitou"] + g["rompeu"]
    return dict(toques=g["toques"], rejeitou=g["rejeitou"],
                rompeu=g["rompeu"], neutro=g["neutro"],
                taxa_rejeicao=round(g["rejeitou"] / dec, 3) if dec else None)


def aggregate(records):
    """Consolida os registros diários em estatísticas."""
    st = dict(n_days=len(records),
              walls={1: _wall_bucket(), 2: _wall_bucket(), 3: _wall_bucket()},
              bands=dict(days=0, inside=0),
              poc=dict(days=0, touched=0),
              va=dict(open_inside=0, rot_when_inside=0,
                      open_outside=0, trend_when_outside=0),
              flip=dict(crosses=0, drops=[]))
    cond = dict(pos=_wall_bucket(), neg=_wall_bucket(),
                comprador=_wall_bucket(), vendedor=_wall_bucket())
    hourly = {}
    vol_total = {}

    for r in records:
        for w in r.get("walls") or []:
            g = st["walls"].get(int(w["width"]))
            if g is not None:
                g["toques"] += 1
                g[w["outcome"]] = g.get(w["outcome"], 0) + 1
            for key in (r.get("regime"), r.get("fluxo")):
                if key in cond:
                    cond[key]["toques"] += 1
                    cond[key][w["outcome"]] = cond[key].get(w["outcome"], 0) + 1
            hh = w.get("hora")
            if hh:
                hb = str(int(hh) // 100)
                hg = hourly.setdefault(hb, _wall_bucket())
                hg["toques"] += 1
                hg[w["outcome"]] = hg.get(w["outcome"], 0) + 1
        for h, q in (r.get("vol_h") or {}).items():
            vol_total[h] = vol_total.get(h, 0) + q
        if r.get("bands"):
            st["bands"]["days"] += 1
            if r["bands"]["inside"]:
                st["bands"]["inside"] += 1
        if r.get("poc"):
            st["poc"]["days"] += 1
            if r["poc"]["touched"]:
                st["poc"]["touched"] += 1
        if r.get("va"):
            if r["va"]["open_inside"]:
                st["va"]["open_inside"] += 1
                if r["va"]["close_inside"]:
                    st["va"]["rot_when_inside"] += 1
            else:
                st["va"]["open_outside"] += 1
                if not r["va"]["close_inside"]:
                    st["va"]["trend_when_outside"] += 1
        f = r.get("flip")
        if f and f.get("crossed_down"):
            st["flip"]["crosses"] += 1
            if f.get("extra_drop"):
                st["flip"]["drops"].append(f["extra_drop"])

    # --- gaps (registros consecutivos, ordenados por sessão) ---
    buckets = [("ate_300", 0, 300), ("300_700", 300, 700),
               ("700_1500", 700, 1500), ("acima_1500", 1500, 1e12)]
    gaps = {k: dict(n=0, fechou=0) for k, _a, _b in buckets}
    srt = sorted(records, key=lambda r: r.get("session") or "")
    for prev, cur in zip(srt, srt[1:]):
        try:
            pc = float(prev["close"])
            gap = float(cur["open"]) - pc
        except (KeyError, TypeError, ValueError):
            continue
        ag = abs(gap)
        filled = (cur["low"] <= pc) if gap > 0 else (cur["high"] >= pc)
        for k, a, b in buckets:
            if a <= ag < b:
                gaps[k]["n"] += 1
                if filled:
                    gaps[k]["fechou"] += 1
                break

    # taxas prontas para o painel
    out = dict(n_days=st["n_days"], walls={})
    for w, g in st["walls"].items():
        out["walls"][str(w)] = _wall_rate(g)
    b = st["bands"]
    out["bands"] = dict(days=b["days"], inside=b["inside"],
                        taxa_dentro=round(b["inside"] / b["days"], 3)
                        if b["days"] else None)
    p = st["poc"]
    out["poc"] = dict(days=p["days"], touched=p["touched"],
                      taxa_ima=round(p["touched"] / p["days"], 3)
                      if p["days"] else None)
    v = st["va"]
    out["va"] = dict(
        open_inside=v["open_inside"],
        taxa_rotacao=round(v["rot_when_inside"] / v["open_inside"], 3)
        if v["open_inside"] else None,
        open_outside=v["open_outside"],
        taxa_tendencia=round(v["trend_when_outside"] / v["open_outside"], 3)
        if v["open_outside"] else None)
    fl = st["flip"]
    out["flip"] = dict(crosses=fl["crosses"],
                       queda_media_extra=round(sum(fl["drops"]) /
                                               len(fl["drops"]), 1)
                       if fl["drops"] else None)

    out["cond"] = {k: _wall_rate(g) for k, g in cond.items()
                   if g["toques"] > 0}
    for k, g in gaps.items():
        g["taxa_fechou"] = round(g["fechou"] / g["n"], 3) if g["n"] else None
    out["gaps"] = gaps
    tv = sum(vol_total.values()) or 0
    out["hourly"] = {
        h: dict(_wall_rate(hourly.get(h, _wall_bucket())),
                vol_pct=round(vol_total.get(h, 0) / tv * 100, 1) if tv else 0)
        for h in sorted(set(list(hourly.keys()) + list(vol_total.keys())),
                        key=int)}
    return out


# ------------------------------------------------------- persistência
def bt_dir(outdir):
    d = os.path.join(outdir, "backtest")
    os.makedirs(d, exist_ok=True)
    return d


def save_record(outdir, rec):
    p = os.path.join(bt_dir(outdir), f"{rec['session']}.json")
    json.dump(rec, open(p, "w", encoding="utf-8"), indent=1)
    return p


def record_is_current(outdir, session_str):
    """True se já existe registro desta sessão na versão atual (v2)."""
    p = os.path.join(bt_dir(outdir), f"{session_str}.json")
    if not os.path.exists(p):
        return False
    try:
        return json.load(open(p)).get("v", 1) >= REC_VERSION
    except Exception:
        return False


def rebuild_stats(outdir):
    d = bt_dir(outdir)
    records = []
    for fn in sorted(os.listdir(d)):
        if fn.endswith(".json"):
            try:
                records.append(json.load(open(os.path.join(d, fn))))
            except Exception:
                pass
    stats = aggregate(records)
    stats["desde"] = records[0]["session"] if records else None
    stats["ate"] = records[-1]["session"] if records else None
    json.dump(stats, open(os.path.join(outdir, "stats.json"), "w",
                          encoding="utf-8"), indent=2, ensure_ascii=False)
    return stats


def eval_and_store(outdir, levels, tick_zip, ticker, flow_side=None):
    """Avalia um mapa contra o zip de ticks da própria sessão e persiste."""
    if flow_side is None:
        flow_side = flow_side_for(
            os.path.join(outdir, "flow_history.csv"),
            str(levels.get("session") or ""))
    bars = minute_bars(tick_zip, ticker)
    rec = eval_session(levels, bars, flow_side=flow_side)
    if rec is None:
        return None
    save_record(outdir, rec)
    return rec
