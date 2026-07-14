#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Backfill do backtest: reconstrói o mapa GAMMA LINES de cada sessão passada
(usando os arquivos da véspera, como o robô teria feito na época) e avalia
contra os ticks reais daquela sessão.

Uso (GitHub Actions): python backfill.py [N_SESSOES=20]
Limite prático: a B3 publica o negócio-a-negócio dos últimos ~20 pregões.
"""
import datetime as dt
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import fetch_data as fd                     # noqa: E402
import volume_profile as vp                 # noqa: E402
import backtest as bt                       # noqa: E402
from gamma_pipeline import run_model        # noqa: E402
from ntsl_generator import current_contract  # noqa: E402

WORK = os.path.join(HERE, "work")
OUT = os.path.join(HERE, "output")


def build_levels(session, ref, res, vp_block):
    """Réplica mínima do levels.json do run_daily (campos usados no backtest)."""
    lv = dict(
        session=f"{session:%Y-%m-%d}", ref=f"{ref:%Y-%m-%d}",
        walls=[dict(strike=k, width=w, fut=round(f, 3))
               for k, w, f in res["walls"]],
        gamma_flip=round(res["flip"][1], 3) if res["flip"][1] else None,
    )
    if res.get("prob"):
        p = res["prob"]
        lv["prob"] = dict(band_up=round(p["band_up_fut"], 3),
                          band_down=round(p["band_down_fut"], 3))
    if vp_block and vp_block.get("d1"):
        lv["vp"] = dict(d1=vp_block["d1"])
    return lv


def compute_map_for(session):
    """Monta o mapa da sessão `session` com os dados da véspera.
    Retorna levels dict ou None."""
    ref = fd.previous_business_day(session)
    cot = pr = None
    for _ in range(4):
        try:
            cot = fd.fetch_cotahist(ref)
            pr = fd.fetch_pr(ref)
            break
        except Exception as e:
            print(f"  ref {ref} indisponível ({e}); tentando anterior")
            ref = fd.previous_business_day(ref)
    if not (cot and pr):
        return None
    cdi = getattr(compute_map_for, "_cdi", None)
    if cdi is None:
        cdi = fd.fetch_cdi()
        compute_map_for._cdi = cdi
    ibov, src = fd.fetch_ibov_close(ref)
    if ibov is None:
        ibov = fd.estimate_ibov_from_carry(pr, ref, cdi)
        src = "carry_estimate"
    cot_txt = open(cot, encoding="latin-1").read()
    pr_txt = open(pr, encoding="utf-8", errors="ignore").read()
    res = run_model(cot_txt, pr_txt, ibov_close=ibov, r_annual=cdi,
                    ref_date=ref)
    ticker = f"WIN{current_contract(session)}"
    vp_block = None
    try:
        vp_block = vp.build_vp_block(ref, ticker, OUT, WORK, ndays=1)
    except Exception as e:
        print(f"  vp de {ref} indisponível: {e}")
    print(f"  mapa ok (ref {ref}, ibov {ibov:.0f} via {src})")
    return build_levels(session, ref, res, vp_block)


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    os.makedirs(WORK, exist_ok=True)
    os.makedirs(OUT, exist_ok=True)

    today = dt.date.today()
    d = today  # avalia só sessões já encerradas: começa em ontem
    sessions = []
    while len(sessions) < n and (today - d).days < n * 2 + 15:
        d -= dt.timedelta(days=1)
        if d.weekday() < 5:
            sessions.append(d)
    sessions.reverse()

    done = 0
    for s in sessions:
        rec_path = os.path.join(OUT, "backtest", f"{s:%Y-%m-%d}.json")
        if os.path.exists(rec_path):
            print(f"{s}: já avaliado, pulando")
            done += 1
            continue
        print(f"{s}: processando…")
        ticker = f"WIN{current_contract(s)}"
        # ticks da própria sessão (também popula o cache p/ vp do dia seguinte)
        hist = vp.fetch_day_histogram(s, ticker, WORK)
        if not hist:
            print("  sem ticks (feriado ou fora da janela da B3), pulando")
            continue
        zpath = os.path.join(WORK, f"ticks_{s.isoformat()}.zip")
        try:
            levels = compute_map_for(s)
        except Exception as e:
            print(f"  falha ao montar o mapa: {e}")
            continue
        if not levels:
            print("  sem dados da véspera, pulando")
            continue
        rec = bt.eval_and_store(OUT, levels, zpath, ticker)
        if rec:
            done += 1
            print(f"  avaliado: {len(rec['walls'])} toques de wall")

    stats = bt.rebuild_stats(OUT)
    print(json.dumps(stats, indent=2, ensure_ascii=False))
    print(f"backfill concluído: {done} sessões avaliadas")


if __name__ == "__main__":
    main()
