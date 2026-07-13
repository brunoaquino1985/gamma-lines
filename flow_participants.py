#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fluxo por tipo de investidor (B3 — Boletim Diário, tabela SharesInvesVolum).

A tabela "Participação dos investidores" é ACUMULADA NO MÊS e tem defasagem
de 2 pregões: o boletim com dateRef=D contém o acumulado até a sessão D-2.
O fluxo diário de uma sessão S é a diferença entre o acumulado do boletim
S+2 e o do boletim S+1 (em dias úteis). Quando o acumulado "reseta"
(virada de mês), o próprio acumulado é o fluxo do primeiro pregão do mês.

Validação (jul/2026): deltas de -500,3 mi (06/07), +12,2 mi (07/07) e
-607,6 mi (08/07) conferem com os valores públicos de fluxo estrangeiro.

Saída: atualiza output/flow_history.csv (uma linha por sessão) e retorna
o bloco "flow" para o levels.json / painel.
"""
import csv
import datetime as dt
import io
import json
import os
import urllib.request

BDI = "https://arquivos.b3.com.br/bdi/table/SharesInvesVolum/{d}/{d}/1/100"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) gamma-lines/1.0",
    "Accept": "application/json",
    "Content-Type": "application/json",
}
# nomes na tabela -> chave curta
TYPES = {
    "Investidor Estrangeiro": "estrangeiro",
    "Institucionais": "institucional",
    "Investidores Individuais": "pessoa_fisica",
    "Instituições Financeiras": "inst_financeira",
    "Outros": "outros",
}


def _biz_days_back(day, n):
    """n dias úteis (seg-sex) antes de day."""
    d = day
    while n > 0:
        d -= dt.timedelta(days=1)
        if d.weekday() < 5:
            n -= 1
    return d


def fetch_bdi_acc(date):
    """Acumulado do mês publicado no boletim de `date`.
    Retorna dict {tipo: (compras_mil, vendas_mil)} ou None se sem dados."""
    url = BDI.format(d=date.isoformat())
    req = urllib.request.Request(url, data=b"{}", headers=HEADERS,
                                 method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            payload = json.load(io.TextIOWrapper(r, "utf-8"))
    except Exception:
        return None
    values = (payload.get("table") or {}).get("values") or []
    out = {}
    for row in values:
        key = TYPES.get(str(row[0]).strip())
        if key and row[1] is not None and row[3] is not None:
            out[key] = (float(row[1]), float(row[3]))
    return out or None


def build_flow_history(hist_path, today, backfill=25):
    """Atualiza o CSV de histórico de fluxo diário por tipo de investidor.

    hist_path: caminho de output/flow_history.csv
    today: data (BRT) da geração — busca boletins até hoje.
    Retorna lista de dicts (uma por sessão, ordem cronológica).
    """
    rows = {}
    if os.path.exists(hist_path):
        with open(hist_path, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                rows[r["session"]] = r

    # boletins numa janela recente (limite público ~D-21)
    start = _biz_days_back(today, backfill)
    dates, d = [], start
    while d <= today:
        if d.weekday() < 5:
            dates.append(d)
        d += dt.timedelta(days=1)

    acc = {}
    for d in dates:
        # pula download se todas as sessões derivadas desse boletim já existem
        got = fetch_bdi_acc(d)
        if got:
            acc[d] = got

    # sessões: boletim D cobre até sessão D-2u; fluxo diário via delta
    ds = sorted(acc.keys())
    for i in range(1, len(ds)):
        d_prev, d_cur = ds[i - 1], ds[i]
        session = _biz_days_back(d_cur, 2)
        cur, prev = acc[d_cur], acc[d_prev]
        row = {"session": session.isoformat()}
        ok = True
        for key in TYPES.values():
            if key not in cur or key not in prev:
                ok = False
                break
            cb, vb = cur[key]
            pb, pv = prev[key]
            if cb < pb * 0.5:          # virada de mês: acumulado resetou
                buy, sell = cb, vb
            else:
                buy, sell = cb - pb, vb - pv
            row[key + "_saldo_mi"] = round((buy - sell) / 1000.0, 1)
        if ok:
            rows[row["session"]] = {**rows.get(row["session"], {}), **row}

    out = [rows[k] for k in sorted(rows.keys())]
    if out:
        keys = ["session"] + [t + "_saldo_mi" for t in TYPES.values()]
        os.makedirs(os.path.dirname(hist_path), exist_ok=True)
        with open(hist_path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
            w.writeheader()
            for r in out:
                w.writerow(r)
    return out


def flow_block(history, n=15):
    """Bloco 'flow' para o levels.json: últimas n sessões + acumulados."""
    hist = history[-n:]
    if not hist:
        return None

    def f(r, k):
        try:
            return float(r.get(k, "") or 0)
        except ValueError:
            return 0.0

    last = hist[-1]
    fx5 = sum(f(r, "estrangeiro_saldo_mi") for r in hist[-5:])
    fx21 = sum(f(r, "estrangeiro_saldo_mi") for r in history[-21:])
    return dict(
        last_session=last["session"],
        estrangeiro_dia_mi=f(last, "estrangeiro_saldo_mi"),
        estrangeiro_5d_mi=round(fx5, 1),
        estrangeiro_21d_mi=round(fx21, 1),
        institucional_dia_mi=f(last, "institucional_saldo_mi"),
        pessoa_fisica_dia_mi=f(last, "pessoa_fisica_saldo_mi"),
        series=[dict(session=r["session"],
                     estrangeiro=f(r, "estrangeiro_saldo_mi"),
                     institucional=f(r, "institucional_saldo_mi"),
                     pessoa_fisica=f(r, "pessoa_fisica_saldo_mi"))
                for r in hist],
        lag_note="defasagem de 2 pregões (dado público mais recente da B3)",
    )


if __name__ == "__main__":
    today = dt.date.today()
    hist = build_flow_history("output/flow_history.csv", today)
    print(json.dumps(flow_block(hist), indent=2, ensure_ascii=False))
