#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Backtest das zonas do GAMMA LINES: compara o mapa previsto de cada sessão
com o que o mercado realmente fez (ticks do WIN da própria sessão).

Definições (v1, em pontos do WIN/IND):
  TOQUE     — o preço chega a <=100 pts de uma wall.
  ROMPIMENTO— depois do toque, o preço ultrapassa a wall em >=200 pts.
  REJEIÇÃO  — depois do toque, o preço se afasta >=400 pts de volta para o
              lado de onde veio, antes de romper.
  NEUTRO    — a sessão termina sem definir (nem rejeitou, nem rompeu).
Bandas: sessão "dentro" se máxima <= banda_sup e mínima >= banda_inf.
POC: "imã" se o preço negociou a <=50 pts do POC em algum momento.
Área de valor: abertura dentro/fora; dia de rotação se fecha dentro.
Flip: se a sessão cruzou o flip para baixo, mede a queda adicional.
"""
import datetime as dt
import io
import json
import os
import zipfile

TOUCH_TOL = 100.0
BREAK_TOL = 200.0
REJECT_TGT = 400.0
POC_TOL = 50.0


# ---------------------------------------------------------------- ticks
def minute_bars(zpath, ticker):
    """Barras de 1 minuto [(hhmm, high, low, close)] da sessão regular."""
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
                b = bars.get(hhmm)
                if b is None:
                    bars[hhmm] = [px, px, px]
                else:
                    if px > b[0]:
                        b[0] = px
                    if px < b[1]:
                        b[1] = px
                    b[2] = px
    return [(k, v[0], v[1], v[2]) for k, v in sorted(bars.items())]


# ---------------------------------------------------------------- avaliação
def _eval_level(bars, level, open_px):
    """Avalia um nível: primeiro toque -> rejeição/rompimento/neutro.
    Retorna None se nunca tocou."""
    side = 1.0 if open_px >= level else -1.0     # lado de onde o preço vem
    touched = False
    outcome = "neutro"
    mfe = 0.0                                     # excursão máxima pós-toque
    prev_close = open_px
    for i, (_, hi, lo, close) in enumerate(bars):
        # faixa efetiva da barra inclui o fechamento anterior (cobre gaps)
        ehi, elo = max(hi, prev_close), min(lo, prev_close)
        prev_close = close
        if not touched:
            near = (elo - TOUCH_TOL) <= level <= (ehi + TOUCH_TOL)
            if near:
                touched = True
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
                mfe=round(mfe, 1))


def eval_session(levels, bars):
    """levels: dict no formato do levels.json; bars: minute_bars da sessão.
    Retorna o registro da sessão (ou None se sem barras)."""
    if not bars:
        return None
    open_px = bars[0][3]
    hi = max(b[1] for b in bars)
    lo = min(b[2] for b in bars)
    close_px = bars[-1][3]
    rec = dict(session=levels.get("session"), open=open_px, high=hi,
               low=lo, close=close_px, walls=[], bands=None, flip=None,
               poc=None, va=None)

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
def aggregate(records):
    """Consolida os registros diários em estatísticas."""
    st = dict(n_days=len(records),
              walls={1: dict(toques=0, rejeitou=0, rompeu=0, neutro=0),
                     2: dict(toques=0, rejeitou=0, rompeu=0, neutro=0),
                     3: dict(toques=0, rejeitou=0, rompeu=0, neutro=0)},
              bands=dict(days=0, inside=0),
              poc=dict(days=0, touched=0),
              va=dict(open_inside=0, rot_when_inside=0,
                      open_outside=0, trend_when_outside=0),
              flip=dict(crosses=0, drops=[]))
    for r in records:
        for w in r.get("walls") or []:
            g = st["walls"].get(int(w["width"]))
            if g is None:
                continue
            g["toques"] += 1
            g[w["outcome"]] = g.get(w["outcome"], 0) + 1
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

    # taxas prontas para o painel
    out = dict(n_days=st["n_days"], walls={}, )
    for w, g in st["walls"].items():
        dec = g["rejeitou"] + g["rompeu"]
        out["walls"][str(w)] = dict(
            toques=g["toques"], rejeitou=g["rejeitou"], rompeu=g["rompeu"],
            neutro=g["neutro"],
            taxa_rejeicao=round(g["rejeitou"] / dec, 3) if dec else None)
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


def eval_and_store(outdir, levels, tick_zip, ticker):
    """Avalia um mapa contra o zip de ticks da própria sessão e persiste."""
    bars = minute_bars(tick_zip, ticker)
    rec = eval_session(levels, bars)
    if rec is None:
        return None
    save_record(outdir, rec)
    return rec
