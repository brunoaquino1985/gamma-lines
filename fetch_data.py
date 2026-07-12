#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Baixa os arquivos públicos da B3 necessários para o modelo GAMMA LINES.
Roda dentro do GitHub Actions (internet aberta).

Saídas em ./work/:
  COTAHIST_D{ref}.TXT     — cotações do pregão de referência (D-1)
  PR{ref}.xml             — BVBG.086 com open interest
  market.json             — IBOV close, CDI, metadados
"""
import datetime as dt
import io
import json
import os
import sys
import time
import zipfile

import requests

HDRS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/126.0 Safari/537.36"}

WORK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "work")


def get(url, tries=4, timeout=120, **kw):
    last = None
    for i in range(tries):
        try:
            r = requests.get(url, headers=HDRS, timeout=timeout, **kw)
            if r.status_code == 200 and len(r.content) > 200:
                return r
            last = f"HTTP {r.status_code} len={len(r.content)}"
        except Exception as e:  # noqa
            last = repr(e)
        time.sleep(5 * (i + 1))
    raise RuntimeError(f"falha ao baixar {url}: {last}")


def fetch_cotahist(ref: dt.date) -> str:
    url = (f"https://bvmf.bmfbovespa.com.br/InstDados/SerHist/"
           f"COTAHIST_D{ref:%d%m%Y}.ZIP")
    r = get(url)
    zf = zipfile.ZipFile(io.BytesIO(r.content))
    name = zf.namelist()[0]
    txt = zf.read(name).decode("latin-1")
    if f"{ref:%Y%m%d}" not in txt[:600]:
        raise RuntimeError("COTAHIST não é do pregão esperado")
    out = os.path.join(WORK, f"COTAHIST_D{ref:%d%m%Y}.TXT")
    open(out, "w", encoding="latin-1").write(txt)
    return out


def fetch_pr(ref: dt.date) -> str:
    url = (f"https://www.b3.com.br/pesquisapregao/download?"
           f"filelist=PR{ref:%y%m%d}.zip")
    r = get(url)
    outer = zipfile.ZipFile(io.BytesIO(r.content))
    inner_name = [n for n in outer.namelist() if n.lower().endswith(".zip")][0]
    inner = zipfile.ZipFile(io.BytesIO(outer.read(inner_name)))
    xmls = sorted(inner.namelist())
    # último arquivo da sequência = snapshot final
    data = inner.read(xmls[-1]).decode("utf-8", errors="ignore")
    out = os.path.join(WORK, f"PR{ref:%y%m%d}.xml")
    open(out, "w", encoding="utf-8").write(data)
    return out


def fetch_ibov_close(ref: dt.date) -> float:
    """IBOV de fechamento do pregão de referência."""
    errors = []
    # fonte 1: cotacao.b3.com.br (histórico intradiário/diário público)
    try:
        u = "https://cotacao.b3.com.br/mds/api/v1/DailyFluctuationHistory/IBOV"
        j = get(u, timeout=60).json()
        for item in j.get("TradgFlr", {}).get("date", []):
            d = item.get("ts", "")[:10]
            if d == f"{ref:%Y-%m-%d}":
                px = item.get("SctyQtn", {}).get("curPrc")
                if px:
                    return float(px)
        errors.append("cotacao.b3: data não encontrada")
    except Exception as e:
        errors.append(f"cotacao.b3: {e!r}")
    # fonte 2: chart do TradingView público? Não. Usa sistemaswebb3 (b3 site)
    try:
        import base64
        payload = base64.b64encode(json.dumps(
            {"index": "IBOV", "language": "pt-br"}).encode()).decode()
        u = ("https://sistemaswebb3-listados.b3.com.br/indexStatisticsProxy/"
             f"IndexCall/GetPortfolioDay/{payload}")
        j = get(u, timeout=60).json()
        # estrutura varia; procura o dia
        raise RuntimeError("layout não tratado")
    except Exception as e:
        errors.append(f"sistemaswebb3: {e!r}")
    # fonte 3: stooq CSV (^BVP)
    try:
        u = "https://stooq.com/q/d/l/?s=%5Ebvp&i=d"
        txt = get(u, timeout=60).text
        for line in txt.splitlines()[1:]:
            parts = line.split(",")
            if parts and parts[0] == f"{ref:%Y-%m-%d}":
                return float(parts[4])
        errors.append("stooq: data não encontrada")
    except Exception as e:
        errors.append(f"stooq: {e!r}")
    raise RuntimeError("IBOV close indisponível: " + " | ".join(errors))


def fetch_cdi() -> float:
    """CDI anualizado (SGS 4389), fração decimal. Fallback: 0.14."""
    try:
        u = ("https://api.bcb.gov.br/dados/serie/bcdata.sgs.4389/"
             "dados/ultimos/1?formato=json")
        j = get(u, timeout=60).json()
        return float(j[-1]["valor"].replace(",", ".")) / 100.0
    except Exception:
        return 0.14


def previous_business_day(d: dt.date) -> dt.date:
    x = d - dt.timedelta(days=1)
    while x.weekday() >= 5:
        x -= dt.timedelta(days=1)
    return x


def main():
    os.makedirs(WORK, exist_ok=True)
    # sessão = hoje (dia útil); referência = pregão anterior
    session = dt.date.today()
    if len(sys.argv) > 1:
        session = dt.datetime.strptime(sys.argv[1], "%Y-%m-%d").date()
    if session.weekday() >= 5:
        print("fim de semana — nada a fazer")
        sys.exit(78)  # neutral
    # anda para trás até achar um pregão com arquivos publicados
    # (cobre feriados da B3 sem precisar de calendário)
    ref = previous_business_day(session)
    cot = pr = None
    for _ in range(5):
        try:
            cot = fetch_cotahist(ref)
            pr = fetch_pr(ref)
            break
        except Exception as e:
            print(f"pregão {ref} indisponível ({e}); tentando anterior")
            ref = previous_business_day(ref)
    if not (cot and pr):
        raise RuntimeError("nenhum pregão com arquivos disponíveis")
    print("ok COTAHIST:", cot)
    print("ok PR:", pr)
    ibov = fetch_ibov_close(ref)
    print("ok IBOV close:", ibov)
    cdi = fetch_cdi()
    print("ok CDI:", cdi)

    meta = dict(session=f"{session:%Y-%m-%d}", ref=f"{ref:%Y-%m-%d}",
                ibov_close=ibov, cdi=cdi,
                cotahist=os.path.basename(cot), pr=os.path.basename(pr))
    json.dump(meta, open(os.path.join(WORK, "market.json"), "w"), indent=2)
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
