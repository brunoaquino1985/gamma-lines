#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Roda o modelo GEX e gera o indicador NTSL do dia.
Uso: python run_daily.py           (usa work/market.json gerado por fetch_data.py)

Saídas em ./output/:
  latest.txt                      — código NTSL da sessão corrente
  GAMMA_LINES_IND_{dd_mm}.txt     — cópia datada
  levels.json                     — níveis em JSON (para conferência)
"""
import datetime as dt
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from gamma_pipeline import run_model          # noqa: E402
from ntsl_generator import generate_ntsl      # noqa: E402
from report_html import build_report          # noqa: E402

WORK = os.path.join(HERE, "work")
OUT = os.path.join(HERE, "output")


def main():
    meta = json.load(open(os.path.join(WORK, "market.json")))
    session = dt.datetime.strptime(meta["session"], "%Y-%m-%d").date()
    ref = dt.datetime.strptime(meta["ref"], "%Y-%m-%d").date()

    cot = open(os.path.join(WORK, meta["cotahist"]), encoding="latin-1").read()
    pr = open(os.path.join(WORK, meta["pr"]), encoding="utf-8",
              errors="ignore").read()

    res = run_model(cot, pr, ibov_close=meta["ibov_close"],
                    r_annual=meta["cdi"], ref_date=ref)
    code = generate_ntsl(res, session)

    os.makedirs(OUT, exist_ok=True)
    open(os.path.join(OUT, "latest.txt"), "w").write(code)
    dated = os.path.join(OUT, f"GAMMA_LINES_IND_{session:%d_%m}.txt")
    open(dated, "w").write(code)

    levels = dict(
        session=meta["session"], ref=meta["ref"],
        fut=res["fut_ticker"], fut_settle=res["fut_settle"],
        ibov_close=res["ibov_close"], bova11=res["bova_spot"],
        fator=res["factor"],
        walls=[dict(strike=k, width=w, fut=round(f, 3))
               for k, w, f in res["walls"]],
        midwalls=[round(f, 3) for _, f in res["mids"]],
        gamma_flip=round(res["flip"][1], 3) if res["flip"][1] else None,
        max_gamma=round(res["max_gamma"][1], 3),
        min_gamma=round(res["min_gamma"][1], 3),
        series=res["n_series"],
    )
    if res.get("prob"):
        p = res["prob"]
        levels["prob"] = dict(
            expiry=p["expiry"], iv_atm=round(p["iv_atm"], 4),
            p_up_expiry=round(p["p_up_expiry"], 4),
            sigma_day=round(p["sigma_day_frac"], 5),
            band_up=round(p["band_up_fut"], 3),
            band_down=round(p["band_down_fut"], 3),
            pct={k: round(v, 1) for k, v in p["pct_fut"].items()},
        )
    html = build_report(res, meta, meta["session"])
    open(os.path.join(OUT, "report.html"), "w", encoding="utf-8").write(html)
    json.dump(levels, open(os.path.join(OUT, "levels.json"), "w"),
              indent=2, ensure_ascii=False)
    print(json.dumps(levels, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
