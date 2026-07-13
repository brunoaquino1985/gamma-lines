#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Volume profile (POC / VAH / VAL) do WIN a partir do arquivo oficial de
negócio-a-negócio de derivativos da B3:

    GET https://drp.b3.com.br/rapinegocios/tickercsv/{YYYY-MM-DD}?type=1

ZIP com um TXT ';'-separado (últimos ~20 pregões disponíveis):
DataReferencia;CodigoInstrumento;AcaoAtualizacao;PrecoNegocio;
QuantidadeNegociada;HoraFechamento;CodigoIdentificadorNegocio;
TipoSessaoPregao;DataNegocio;CodigoParticipanteComprador;
CodigoParticipanteVendedor;TipoDoCanal
(PrecoNegocio com vírgula decimal; preços do WIN em pontos de índice.)

Para não rebaixar o mesmo arquivo todo dia, o histograma diário de cada
sessão é persistido em output/profiles/{date}_{ticker}.json; o perfil
composto de 5 sessões é a soma dos histogramas armazenados.
"""
import datetime as dt
import io
import json
import os
import urllib.request
import zipfile

TICK_URL = "https://drp.b3.com.br/rapinegocios/tickercsv/{d}?type=1"
HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) gamma-lines/1.0"}
BIN = 5.0          # tick do WIN = 5 pontos
VA_PCT = 0.70      # área de valor de 70%


def fetch_day_histogram(date, ticker, workdir):
    """Baixa o ZIP do dia e monta {preco_bin: volume} só para `ticker`.
    Retorna dict ou None se arquivo indisponível."""
    url = TICK_URL.format(d=date.isoformat())
    zpath = os.path.join(workdir, f"ticks_{date.isoformat()}.zip")
    if not os.path.exists(zpath):
        req = urllib.request.Request(url, headers=HEADERS)
        try:
            with urllib.request.urlopen(req, timeout=900) as r, \
                    open(zpath, "wb") as f:
                while True:
                    chunk = r.read(1 << 20)
                    if not chunk:
                        break
                    f.write(chunk)
        except Exception:
            if os.path.exists(zpath):
                os.remove(zpath)
            return None
    hist = {}
    needle = ";" + ticker + ";"
    try:
        with zipfile.ZipFile(zpath) as z:
            name = z.namelist()[0]
            with z.open(name) as f:
                t = io.TextIOWrapper(f, encoding="latin-1", errors="ignore")
                header = t.readline()  # noqa: F841
                for line in t:
                    if needle not in line:
                        continue
                    parts = line.rstrip("\n").split(";")
                    if len(parts) < 8 or parts[1] != ticker:
                        continue
                    if parts[7] not in ("1", ""):   # sessão regular
                        continue
                    try:
                        px = float(parts[3].replace(".", "").replace(",", "."))
                        qty = int(parts[4])
                    except ValueError:
                        continue
                    b = round(px / BIN) * BIN
                    hist[b] = hist.get(b, 0) + qty
    except zipfile.BadZipFile:
        os.remove(zpath)
        return None
    return hist or None


def poc_va(hist):
    """POC, VAH, VAL de um histograma {preco: volume} (área de valor 70%)."""
    if not hist:
        return None
    prices = sorted(hist.keys())
    total = sum(hist.values())
    poc = max(prices, key=lambda p: (hist[p], -abs(p)))
    i = j = prices.index(poc)
    acc = hist[poc]
    while acc < total * VA_PCT and (i > 0 or j < len(prices) - 1):
        up = hist[prices[j + 1]] if j < len(prices) - 1 else -1
        dn = hist[prices[i - 1]] if i > 0 else -1
        if up >= dn:
            j += 1
            acc += hist[prices[j]]
        else:
            i -= 1
            acc += hist[prices[i]]
    return dict(poc=poc, vah=prices[j], val=prices[i], volume=total)


def _profile_path(outdir, date, ticker):
    return os.path.join(outdir, "profiles", f"{date.isoformat()}_{ticker}.json")


def ensure_profiles(dates, ticker, outdir, workdir):
    """Garante histogramas persistidos para as datas; retorna {date: hist}."""
    os.makedirs(os.path.join(outdir, "profiles"), exist_ok=True)
    out = {}
    for d in dates:
        p = _profile_path(outdir, d, ticker)
        if os.path.exists(p):
            with open(p, encoding="utf-8") as f:
                out[d] = {float(k): v for k, v in json.load(f).items()}
            continue
        h = fetch_day_histogram(d, ticker, workdir)
        if h:
            with open(p, "w", encoding="utf-8") as f:
                json.dump({str(k): v for k, v in h.items()}, f)
            out[d] = h
    return out


def build_vp_block(ref_date, ticker, outdir, workdir, ndays=5):
    """Bloco 'vp' para o levels.json.
    ref_date: sessão de referência (a última encerrada, a mesma do COTAHIST).
    Retorna dict com perfil 1d (ref_date) e composto ndays, ou None."""
    dates, d = [], ref_date
    while len(dates) < ndays:
        if d.weekday() < 5:
            dates.append(d)
        d -= dt.timedelta(days=1)
    hists = ensure_profiles(dates, ticker, outdir, workdir)
    if ref_date not in hists:
        return None
    one = poc_va(hists[ref_date])
    comp_hist = {}
    for h in hists.values():
        for p, v in h.items():
            comp_hist[p] = comp_hist.get(p, 0) + v
    comp = poc_va(comp_hist)
    # histograma reduzido p/ desenho no painel (bins de 100 pts)
    def squash(h, step=100.0):
        s = {}
        for p, v in h.items():
            b = round(p / step) * step
            s[b] = s.get(b, 0) + v
        return [[k, s[k]] for k in sorted(s)]
    return dict(
        ticker=ticker,
        session=ref_date.isoformat(),
        d1=one,
        comp=dict(days=len(hists), **comp) if comp else None,
        hist1d=squash(hists[ref_date]),
        histcomp=squash(comp_hist),
    )


if __name__ == "__main__":
    import sys
    ref = dt.date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 \
        else dt.date.today()
    blk = build_vp_block(ref, sys.argv[2] if len(sys.argv) > 2 else "WINQ26",
                         "output", "work")
    print(json.dumps({k: v for k, v in (blk or {}).items()
                      if not k.startswith("hist")}, indent=2))
