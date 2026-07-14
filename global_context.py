#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Onda 4 — contexto global do dia para o painel GAMMA LINES.

Blocos (cada um falha de forma independente, sem travar o pipeline):
  markets  — fechamento da Ásia, Europa em andamento, EUA (futuros),
             pares de moedas com o dólar e commodities (Yahoo Finance)
  calendar — agenda econômica do dia com impacto (ForexFactory, gratuito)
  news     — manchetes de mercado das últimas ~18h (RSS InfoMoney/MoneyTimes)
"""
import datetime as dt
import json
import re
import sys

import requests

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
BRT = dt.timezone(dt.timedelta(hours=-3))

# (símbolo Yahoo, nome exibido)
GROUPS = [
    ("asia", "Ásia — fechamento", [
        ("^N225", "Nikkei 225 (Japão)"),
        ("^HSI", "Hang Seng (Hong Kong)"),
        ("000001.SS", "Xangai Composto (China)"),
        ("^KS11", "KOSPI (Coreia)"),
    ]),
    ("europa", "Europa — em andamento", [
        ("^STOXX50E", "Euro Stoxx 50"),
        ("^GDAXI", "DAX (Alemanha)"),
        ("^FTSE", "FTSE 100 (Reino Unido)"),
        ("^FCHI", "CAC 40 (França)"),
    ]),
    ("eua", "EUA — futuros e risco", [
        ("ES=F", "S&P 500 futuro"),
        ("NQ=F", "Nasdaq 100 futuro"),
        ("YM=F", "Dow Jones futuro"),
        ("^VIX", "VIX (medo)"),
    ]),
    ("moedas", "Dólar × moedas", [
        ("USDBRL=X", "USD/BRL"),
        ("DX-Y.NYB", "DXY (índice do dólar)"),
        ("EURUSD=X", "EUR/USD"),
        ("USDJPY=X", "USD/JPY"),
        ("USDCNY=X", "USD/CNY"),
    ]),
    ("commodities", "Commodities", [
        ("BZ=F", "Petróleo Brent"),
        ("CL=F", "Petróleo WTI"),
        ("GC=F", "Ouro"),
        ("SI=F", "Prata"),
        ("HG=F", "Cobre"),
        ("TIO=F", "Minério de ferro (SGX)"),
    ]),
]

NEWS_FEEDS = [
    ("InfoMoney", "https://www.infomoney.com.br/feed/"),
    ("Money Times", "https://www.moneytimes.com.br/feed/"),
]
NEWS_KEYWORDS = [
    "ibovespa", "bolsa", "b3", "dólar", "dolar", "fed", "copom", "juro",
    "selic", "inflaç", "ipca", "payroll", "china", "petróleo", "petroleo",
    "tarifa", "trump", "pib", "minério", "minerio", "vale", "petrobras",
    "estrangeiro", "treasur", "recessão", "recessao", "fiscal", "câmbio",
    "cambio", "commodit", "wall street", "s&p",
]


def _yahoo_quote(sym):
    r = requests.get(
        f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}",
        params={"range": "5d", "interval": "1d"}, headers=UA, timeout=15)
    r.raise_for_status()
    meta = r.json()["chart"]["result"][0]["meta"]
    price = meta.get("regularMarketPrice")
    prev = meta.get("chartPreviousClose") or meta.get("previousClose")
    if price is None or not prev:
        return None
    return dict(last=round(price, 4 if price < 50 else 2),
                var=round((price / prev - 1) * 100, 2))


def fetch_markets():
    out = []
    for key, label, symbols in GROUPS:
        rows = []
        for sym, name in symbols:
            try:
                q = _yahoo_quote(sym)
                if q:
                    rows.append(dict(name=name, **q))
            except Exception as e:
                print(f"[warn] quote {sym}: {e}", file=sys.stderr)
        if rows:
            out.append(dict(key=key, label=label, rows=rows))
    return out or None


def fetch_calendar(session):
    """Agenda do dia (ForexFactory, semana corrente) — horários em BRT."""
    r = requests.get("https://nfs.faireconomy.media/ff_calendar_thisweek.json",
                     headers=UA, timeout=20)
    r.raise_for_status()
    events = []
    for ev in r.json():
        try:
            when = dt.datetime.fromisoformat(ev["date"]).astimezone(BRT)
        except Exception:
            continue
        if when.date() != session:
            continue
        impact = ev.get("impact", "")
        if impact not in ("High", "Medium"):
            continue
        if ev.get("country") not in ("USD", "EUR", "CNY", "GBP", "JPY"):
            continue
        events.append(dict(
            hora=when.strftime("%H:%M"),
            moeda=ev.get("country", ""),
            impacto={"High": 3, "Medium": 2}.get(impact, 1),
            evento=ev.get("title", ""),
            projecao=ev.get("forecast") or "—",
            anterior=ev.get("previous") or "—",
        ))
    events.sort(key=lambda e: e["hora"])
    return events or None


def _parse_rss(xml):
    items = []
    for m in re.finditer(r"<item>(.*?)</item>", xml, re.S):
        blk = m.group(1)

        def tag(t):
            mm = re.search(rf"<{t}>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</{t}>",
                           blk, re.S)
            return mm.group(1).strip() if mm else ""
        items.append(dict(title=tag("title"), link=tag("link"),
                          pub=tag("pubDate")))
    return items


def fetch_news(max_items=8):
    now = dt.datetime.now(dt.timezone.utc)
    cand = []
    for source, url in NEWS_FEEDS:
        try:
            r = requests.get(url, headers=UA, timeout=20)
            r.raise_for_status()
            for it in _parse_rss(r.text):
                if not it["title"] or not it["link"]:
                    continue
                try:
                    pub = dt.datetime.strptime(
                        it["pub"], "%a, %d %b %Y %H:%M:%S %z")
                except Exception:
                    pub = now
                age_h = (now - pub).total_seconds() / 3600
                if age_h > 18:
                    continue
                low = it["title"].lower()
                score = sum(1 for k in NEWS_KEYWORDS if k in low)
                if score == 0:
                    continue
                cand.append(dict(
                    titulo=it["title"], link=it["link"], fonte=source,
                    hora=pub.astimezone(BRT).strftime("%d/%m %H:%M"),
                    _score=score, _age=age_h))
        except Exception as e:
            print(f"[warn] rss {source}: {e}", file=sys.stderr)
    cand.sort(key=lambda c: (-c["_score"], c["_age"]))
    seen, out = set(), []
    for c in cand:
        key = c["titulo"][:60]
        if key in seen:
            continue
        seen.add(key)
        out.append({k: v for k, v in c.items() if not k.startswith("_")})
        if len(out) >= max_items:
            break
    return out or None


def build_context(session):
    """session: datetime.date da sessão. Nunca levanta exceção."""
    ctx = {}
    try:
        ctx["markets"] = fetch_markets()
    except Exception as e:
        print(f"[warn] markets: {e}", file=sys.stderr)
        ctx["markets"] = None
    try:
        ctx["calendar"] = fetch_calendar(session)
    except Exception as e:
        print(f"[warn] calendar: {e}", file=sys.stderr)
        ctx["calendar"] = None
    try:
        ctx["news"] = fetch_news()
    except Exception as e:
        print(f"[warn] news: {e}", file=sys.stderr)
        ctx["news"] = None
    return ctx if any(ctx.values()) else None


if __name__ == "__main__":
    print(json.dumps(build_context(dt.date.today()), indent=1,
                     ensure_ascii=False)[:4000])
