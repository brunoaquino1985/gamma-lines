#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Gera o código NTSL (Profit Pro) no formato do indicador GAMMA LINES."""
import datetime as dt

MONTH_CODE = {2: "G", 4: "J", 6: "M", 8: "Q", 10: "V", 12: "Z"}


def ind_expiry(year, month):
    """Vencimento IND/WIN: quarta-feira mais próxima do dia 15 do mês par."""
    d15 = dt.date(year, month, 15)
    # weekday(): Mon=0 ... Wed=2
    delta = (2 - d15.weekday()) % 7
    cand1 = d15 + dt.timedelta(days=delta)
    cand2 = d15 - dt.timedelta(days=(d15.weekday() - 2) % 7)
    return min(cand1, cand2, key=lambda d: abs((d - d15).days))


def current_contract(session_date):
    """Código do contrato IND/WIN vigente na data da sessão (ex.: Q26)."""
    y, m = session_date.year, session_date.month
    for _ in range(8):
        if m % 2 == 0:
            exp = ind_expiry(y, m)
            if session_date <= exp:
                return f"{MONTH_CODE[m]}{y % 100:02d}"
        m += 1
        if m > 12:
            m, y = 1, y + 1
    raise RuntimeError("contrato não encontrado")


def fmt(x, dec=3):
    return f"{x:.{dec}f}"


def fmt_pts(x):
    """177839.785 -> '177.840' (rótulo em pontos, milhar com ponto)."""
    return f"{x:,.0f}".replace(",", ".")


def generate_ntsl(res, session_date):
    """res: saída de run_model (níveis já em pontos do futuro).

    Formato com rótulos nativos (HorizontalLineCustom) aprovado em 16/07/2026.
    Obs.: HorizontalLineCustom conflita com Plot() no mesmo indicador — não
    misturar os dois formatos.
    """
    code = current_contract(session_date)
    walls = res["walls"]            # [(strike_idx, width, nível_fut)]
    mids = res["mids"]              # [(m_idx, nível_fut)]
    maxg = res["max_gamma"][1]
    ming = res["min_gamma"][1]
    flip = res["flip"][1]

    lines = []                      # (valor, cor, width, style, label, fonte)
    for k, w, fut in walls:
        lines.append((fut, "clWall", w, 0, f"WALL {'*' * w} {fmt_pts(fut)}", 10))
    for m, fut in mids:
        lines.append((fut, "clMidWall", 1, 0, "mid", 8))
    lines.append((maxg, "clMaxGamma", 3, 0, f"MAX GAMMA {fmt_pts(maxg)}", 10))
    lines.append((ming, "clMinGamma", 3, 0, f"MIN GAMMA {fmt_pts(ming)}", 10))
    lines.append((flip, "clFlip", 2, 0, f"GAMMA FLIP {fmt_pts(flip)}", 10))
    prob = res.get("prob")
    if prob:
        # bandas de 1 desvio-padrão do dia (IV ATM do vencimento curto)
        lines.append((prob["band_up_fut"], "clBanda", 1, 2,
                      f"BANDA +1DP {fmt_pts(prob['band_up_fut'])}", 10))
        lines.append((prob["band_down_fut"], "clBanda", 1, 2,
                      f"BANDA -1DP {fmt_pts(prob['band_down_fut'])}", 10))
    vp = res.get("vp")
    if vp and vp.get("d1"):
        # volume profile da sessão anterior (POC cheio, VAH/VAL tracejadas)
        lines.append((vp["d1"]["poc"], "clPoc", 2, 0,
                      f"POC {fmt_pts(vp['d1']['poc'])}", 10))
        lines.append((vp["d1"]["vah"], "clVA", 1, 2,
                      f"VAH {fmt_pts(vp['d1']['vah'])}", 10))
        lines.append((vp["d1"]["val"], "clVA", 1, 2,
                      f"VAL {fmt_pts(vp['d1']['val'])}", 10))

    sty = {0: "psSolid", 1: "psDot", 2: "psDash"}

    out = []
    out.append("var")
    out.append("  clWall : integer;")
    out.append("  clMidWall : integer;")
    out.append("  clFlip : integer;")
    out.append("  clMaxGamma : integer;")
    out.append("  clMinGamma : integer;")
    out.append("  clBanda : integer;")
    out.append("  clPoc : integer;")
    out.append("  clVA : integer;")
    out.append("")
    out.append("BEGIN")
    out.append("  clWall := clLime;")
    out.append("  clMidWall := clGray;")
    out.append("  clFlip := clYellow;")
    out.append("  clMaxGamma := clGreen;")
    out.append("  clMinGamma := clRed;")
    out.append("  clBanda := clAqua;")
    out.append("  clPoc := clFuchsia;")
    out.append("  clVA := clSilver;")
    out.append("")
    d = session_date
    assets = [f'"WINFUT"', f'"INDFUT"', f'"WIN{code}"', f'"IND{code}"']
    cond = " or ".join(f"(GetAsset() = {a})" for a in assets)
    out.append(f"  if ((Date = ELDate({d.year}, {d.month:02d}, {d.day:02d})) "
               f"and ({cond})) then")
    out.append("    begin")
    for val, color, w, st, label, fs in lines:
        out.append(f"      HorizontalLineCustom({fmt(val)}, {color}, {w}, "
                   f"{sty[st]}, \"{label}\", {fs}, tpTopRight);")
    out.append("    end;")
    out.append("END;")
    return "\n".join(out)


if __name__ == "__main__":
    print(current_contract(dt.date(2026, 7, 13)))
