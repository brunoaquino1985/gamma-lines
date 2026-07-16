#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Gera o painel HTML diário (autocontido) do GAMMA LINES.
Tema: dark futurista com sidebar de navegação. Tom: professor de day trade."""
import json


def _fmt(x, dec=0):
    s = f"{x:,.{dec}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def _br_date(iso):
    """2026-07-13 -> 13/07/2026"""
    p = str(iso).split("-")
    return f"{p[2]}/{p[1]}/{p[0]}" if len(p) == 3 else str(iso)


def build_rationale(spot_fut, walls, mids, flip, maxg, ming, band_up, band_down):
    """Cenários operacionais no tom de um professor de day trade
    explicando para quem está começando.
    walls: [(strike, width, fut)] ordenado; mids: [fut]."""
    fmt = _fmt
    stars = {3: "★★★", 2: "★★", 1: "★"}
    acima = [w for w in walls if w[2] > spot_fut]
    abaixo = [w for w in walls if w[2] <= spot_fut]
    pos = spot_fut >= flip
    out = []

    def mid_below(level):
        c = [m for m in mids if m < level]
        return max(c) if c else None

    def mid_above(level):
        c = [m for m in mids if m > level]
        return min(c) if c else None

    if pos:
        out.append(("O regime de hoje: gamma POSITIVO",
                    f"Pense assim: os grandes bancos venderam opções e precisam se proteger. "
                    f"Com o preço de referência ({fmt(spot_fut)}) ACIMA do gamma flip ({fmt(flip)}), "
                    "a proteção deles funciona CONTRA o movimento — quando o mercado cai, eles compram; "
                    "quando sobe, eles vendem. Na prática, isso 'segura' o preço. É por isso que em dia "
                    "de gamma positivo o mercado tende a andar de lado entre as linhas, devolvendo os "
                    "exageros. Tradução para o iniciante: dia de comprar barato e vender caro perto das "
                    "linhas, e NÃO de perseguir rompimento."))
        if acima:
            r1 = acima[0]
            alvo1 = mid_below(r1[2])
            alvo2 = abaixo[-1][2] if abaixo else None
            txt = (f"A primeira parede acima do preço é {fmt(r1[2])} {stars[r1[1]]} — ali há uma "
                   "concentração grande de proteção dos bancos, que costuma agir como teto. A lição: "
                   f"se o preço subir até {fmt(r1[2])} e MOSTRAR REJEIÇÃO (candles com pavio para cima, "
                   "perda de força, velocidade caindo), arma-se a VENDA")
            if alvo1:
                txt += f", com primeiro alvo na mid wall {fmt(alvo1)}"
            if alvo2:
                txt += f" e alvo estendido na wall {fmt(alvo2)}"
            txt += (f". E onde o professor manda sair se der errado? Se o preço ACEITAR acima de "
                    f"{fmt(r1[2])} (fechar candles consistentes lá em cima), a tese morreu — não discuta "
                    f"com o mercado; a próxima referência passa a ser "
                    f"{fmt(acima[1][2]) if len(acima) > 1 else fmt(maxg)}.")
            out.append(("Cenário de VENDA (o trade de rejeição no teto)", txt))
        if abaixo:
            s1 = abaixo[-1]
            alvo1 = mid_above(s1[2])
            alvo2 = acima[0][2] if acima else None
            txt = (f"A parede de sustentação mais próxima é {fmt(s1[2])} {stars[s1[1]]}. Quando o preço "
                   "cai até uma wall e ela SEGURA (o mercado desacelera, aparecem compradores, candles "
                   "deixam pavio para baixo), arma-se a COMPRA na defesa do nível")
            if alvo1:
                txt += f", buscando primeiro a mid wall {fmt(alvo1)}"
            if alvo2:
                txt += f" e, se o fluxo ajudar, a wall {fmt(alvo2)}"
            txt += (f". Invalidação: perda consistente de {fmt(s1[2])} — abaixo disso quem comprou está "
                    f"errado e a referência vira {fmt(abaixo[-2][2]) if len(abaixo) > 1 else fmt(flip)}. "
                    "Regra de ouro: a wall é um PONTO DE DECISÃO, não uma promessa. Espere o preço "
                    "REAGIR nela antes de entrar.")
            out.append(("Cenário de COMPRA (o trade de defesa no suporte)", txt))
        out.append(("O sinal de perigo: perder o gamma flip",
                    f"O flip ({fmt(flip)}) é a linha onde o comportamento dos bancos INVERTE. Abaixo dele, "
                    "a proteção deles passa a EMPURRAR o movimento: eles vendem na queda e compram na alta, "
                    "jogando gasolina no fogo. Se o mercado perder o flip, esqueça a reversão à média — "
                    f"quedas aceleram em direção às walls de baixo e, no extremo, ao min gamma ({fmt(ming)}). "
                    "Erro clássico de iniciante nesse regime: comprar 'porque já caiu muito'. Não caia nessa."))
    else:
        out.append(("O regime de hoje: gamma NEGATIVO — atenção redobrada",
                    f"O preço de referência ({fmt(spot_fut)}) está ABAIXO do gamma flip ({fmt(flip)}). "
                    "Nesse regime a proteção dos bancos AMPLIFICA o movimento: eles vendem quando cai e "
                    "compram quando sobe. É o dia da tendência e da aceleração — rompimentos tendem a "
                    "andar, e tentar adivinhar fundo é receita de prejuízo. O iniciante sobrevive a esse "
                    "dia operando A FAVOR do movimento e com stop curto."))
        if abaixo:
            s1 = abaixo[-1]
            prox = abaixo[-2][2] if len(abaixo) > 1 else ming
            out.append(("Cenário de VENDA (continuação do movimento)",
                        f"Se o mercado perder a wall {fmt(s1[2])} {stars[s1[1]]}, abre-se espaço até "
                        f"{fmt(prox)} e, na extensão, até o min gamma ({fmt(ming)}). Em gamma negativo o "
                        "rompimento tende a ter continuidade — a entrada é no rompimento confirmado ou no "
                        "reteste por baixo. Invalidação: o preço voltar RÁPIDO para dentro do nível perdido "
                        "(rompimento falso, o famoso 'violinada')."))
        out.append(("Cenário de REVERSÃO (só com confirmação)",
                    f"Recuperar o flip ({fmt(flip)}) devolve o mercado ao regime calmo e aí sim compra em "
                    "recuo volta a fazer sentido, com alvos nas walls e mid walls acima. Enquanto o preço "
                    "estiver abaixo do flip, toda compra é contra-tendência — tamanho reduzido e stop curto, "
                    "ou simplesmente fique de fora. Não operar também é posição."))

    out.append(("As bandas do dia: o 'campo de jogo' esperado",
                f"O mercado de opções está precificando que o dia deve transcorrer entre {fmt(band_down)} e "
                f"{fmt(band_up)} (1 desvio-padrão). Como usar: toque na banda JUNTO com uma wall é o ponto "
                "de maior interesse do dia para reversão — dois motivos independentes apontando para o mesmo "
                "lugar. Já preço rodando FORA da banda avisa que o dia é atípico (notícia, fluxo forte): "
                "reduza a expectativa de reversão à média e respeite a tendência."))
    out.append(("Teto e piso do mapa",
                f"Max gamma ({fmt(maxg)}) e min gamma ({fmt(ming)}) são os extremos do posicionamento atual "
                "— pense neles como as bordas do tabuleiro. Historicamente, aproximações desses níveis "
                "atraem realização e defesa pesada dos grandes players. Não é nível de todo dia: quando o "
                "preço chega lá, algo relevante está acontecendo."))
    return out


GLOSSARY = [
    ("WALL (parede)", "Strike onde os bancos concentram proteção de opções. Funciona como ímã e barreira: "
     "o preço é atraído, mas tem dificuldade de atravessar. Mais estrelas = parede mais forte."),
    ("GAMMA FLIP", "A linha divisória de comportamento. Acima dela o mercado tende a andar de lado "
     "(regime calmo); abaixo, tende a acelerar (regime nervoso). É a linha mais importante do mapa."),
    ("MID WALL", "Ponto médio entre duas walls — costuma ser o primeiro alvo de quem opera a rejeição "
     "de uma parede."),
    ("BANDAS ±1σ", "O tamanho de movimento que o mercado de opções espera para o dia. Dentro delas, "
     "dia normal; fora delas, dia atípico."),
    ("POC", "Point of Control: o preço onde MAIS contratos foram negociados na sessão anterior. É a "
     "região de maior aceitação — o mercado 'gosta' desse preço e tende a revisitá-lo."),
    ("VAH / VAL", "Topo e fundo da área de valor (70% do volume da sessão anterior). Abrir dentro dela "
     "favorece dia de rotação; abrir fora favorece dia de tendência."),
    ("FLUXO ESTRANGEIRO", "Saldo de compras e vendas dos investidores estrangeiros na bolsa (defasado 2 "
     "pregões). Eles movem o índice: fluxo persistente numa direção dá sustentação ao movimento."),
    ("MAX / MIN GAMMA", "Extremos do mapa de posicionamento — teto e piso estatísticos onde a defesa "
     "dos grandes players costuma ser mais agressiva."),
]


def _ctx_sections(ctx):
    """HTML das abas 'Mercado global' e 'Notícias & agenda' (Onda 4)."""
    off = ("<div class='card'><div class='rd'>Indisponível nesta edição do "
           "painel — a fonte não respondeu na hora da geração.</div></div>")
    mk_html = news_html = cal_html = off
    ctx = ctx or {}

    if ctx.get("markets"):
        cards = ""
        for g in ctx["markets"]:
            rows = "".join(
                f"<tr><td class='tag'>{r['name']}</td>"
                f"<td class='num'>{_fmt(r['last'], 2 if r['last'] < 1000 else 0)}</td>"
                f"<td class='num' style='color:var(--{'pos' if r['var'] >= 0 else 'neg'})'>"
                f"{'+' if r['var'] >= 0 else '−'}{_fmt(abs(r['var']), 2)}%</td></tr>"
                for r in g["rows"])
            cards += (f"<div class='card'><h2>{g['label']}</h2>"
                      f"<table><tr><th>ativo</th><th>último</th><th>var.</th></tr>"
                      f"{rows}</table></div>")
        mk_html = f"<div class='grid'>{cards}</div>"

    if ctx.get("news"):
        items = "".join(
            f"<div class='rat'><div class='rd'><a href='{n['link']}' "
            f"target='_blank' style='color:var(--ink);text-decoration:none'>"
            f"{n['titulo']}</a><br><span class='muted' style='font-size:11px'>"
            f"{n['fonte']} · {n['hora']}</span></div></div>"
            for n in ctx["news"])
        news_html = (f"<div class='card'><h2>Manchetes que podem mexer com o "
                     f"pregão</h2>{items}</div>")

    if ctx.get("calendar"):
        rows = "".join(
            f"<tr><td class='num' style='font-size:14px'>{e['hora']}</td>"
            f"<td class='tag'>{e['moeda']}</td>"
            f"<td style='color:var(--gold)'>{'★' * e['impacto']}</td>"
            f"<td>{e['evento']}</td>"
            f"<td class='muted'>{e['projecao']}</td>"
            f"<td class='muted'>{e['anterior']}</td></tr>"
            for e in ctx["calendar"])
        cal_html = (f"<div class='card'><h2>Agenda econômica de hoje "
                    f"(horário de Brasília)</h2>"
                    f"<table><tr><th>hora</th><th>moeda</th><th>impacto</th>"
                    f"<th>evento</th><th>projeção</th><th>anterior</th></tr>"
                    f"{rows}</table>"
                    f"<div class='rd' style='margin-top:8px'>Regra do professor: "
                    f"nos minutos em torno de evento ★★★, o mapa perde força — "
                    f"spreads abrem e o preço atravessa níveis sem respeitar. "
                    f"Ou esteja fora, ou esteja com stop na mão.</div></div>")
    elif ctx.get("markets") or ctx.get("news"):
        cal_html = ("<div class='card'><h2>Agenda econômica de hoje</h2>"
                    "<div class='rd'>Sem eventos de impacto médio/alto nas "
                    "moedas principais para hoje.</div></div>")

    return mk_html, news_html + cal_html


def build_report(res, meta, session_str, flow=None, vp=None, bt=None,
                 ctx=None):
    prob = res.get("prob") or {}
    spot_fut = res["ibov_close"] * res["factor"]
    flip_fut = res["flip"][1]
    pos = spot_fut >= flip_fut
    regime = "GAMMA POSITIVO" if pos else "GAMMA NEGATIVO"
    regime_desc = ("regime calmo: as paredes tendem a segurar o preço"
                   if pos else
                   "regime nervoso: movimentos tendem a acelerar")

    walls = [dict(strike=k, width=w, fut=round(f, 1)) for k, w, f in res["walls"]]
    s_grid, curve = res["curve"]
    curve_fut = [s * res["factor"] for s in s_grid[::4]]
    curve_val = [v / 1e6 for v in curve[::4]]
    buckets = [dict(fut=b * res["factor"], net=v[0] / 1e6, absg=v[1] / 1e6,
                    wall=next((w["width"] for w in walls if w["strike"] == b), 0))
               for b, v in sorted(res["buckets"].items())]

    dens_x, dens_y = (prob.get("density_fut") or ([], []))

    data = dict(
        session=session_str, ref=str(res["ref_date"]),
        fut=res["fut_ticker"], fator=res["factor"],
        spot_fut=spot_fut, ibov=res["ibov_close"], bova=res["bova_spot"],
        fut_settle=res["fut_settle"],
        ibov_source=meta.get("ibov_source", "?"), cdi=meta.get("cdi"),
        regime=regime, regime_desc=regime_desc,
        flip=flip_fut, maxg=res["max_gamma"][1], ming=res["min_gamma"][1],
        walls=walls,
        mids=[round(f, 1) for _, f in res["mids"]],
        prob=dict(
            p_up=prob.get("p_up_expiry"), iv_atm=prob.get("iv_atm"),
            sigma_day=prob.get("sigma_day_frac"),
            band_up=prob.get("band_up_fut"), band_down=prob.get("band_down_fut"),
            expiry=prob.get("expiry"),
            pct=prob.get("pct_fut") or {},
        ),
        curve=dict(x=curve_fut, y=curve_val),
        buckets=buckets,
        dens=dict(x=dens_x, y=dens_y),
        n_series=res["n_series"],
        flow=flow, vp=vp,
    )

    p_up = prob.get("p_up_expiry")
    sig = prob.get("sigma_day_frac") or 0
    tiles = f"""
      <div class="tile"><div class="tl">Probabilidade de alta*</div>
        <div class="tv neon">{(p_up*100):.0f}%</div>
        <div class="ts">chance de fechar acima do preço atual até {_br_date(prob.get('expiry','-'))}</div></div>
      <div class="tile"><div class="tl">Movimento esperado hoje</div>
        <div class="tv neon">±{_fmt(spot_fut*sig)} <span class="unit">pts</span></div>
        <div class="ts">o "tamanho do dia" que as opções precificam (1σ)</div></div>
      <div class="tile"><div class="tl">Regime de gamma</div>
        <div class="tv {'pos' if pos else 'neg'}">{regime}</div>
        <div class="ts">{regime_desc} · flip em {_fmt(flip_fut)}</div></div>
      <div class="tile"><div class="tl">Parede principal</div>
        <div class="tv neon">{_fmt([w for w in walls if w['width']==3][0]['fut'] if any(w['width']==3 for w in walls) else 0)}</div>
        <div class="ts">a wall ★★★ — maior concentração de proteção dos bancos</div></div>
    """ if p_up is not None else "<div class='tile'><div class='tl'>Probabilidades indisponíveis</div></div>"

    flow_tiles = ""
    if flow:
        fx = flow["estrangeiro_dia_mi"]
        fx5 = flow["estrangeiro_5d_mi"]
        cls_d = "pos" if fx >= 0 else "neg"
        cls_5 = "pos" if fx5 >= 0 else "neg"
        flow_tiles = f"""
      <div class="tile"><div class="tl">Fluxo estrangeiro · {_br_date(flow['last_session'])}</div>
        <div class="tv {cls_d}">{'+' if fx >= 0 else '−'}R$ {_fmt(abs(fx))} <span class="unit">mi</span></div>
        <div class="ts">o dinheiro gringo {'entrou' if fx >= 0 else 'saiu'} nesse dia (dado com 2 pregões de atraso)</div></div>
      <div class="tile"><div class="tl">Fluxo estrangeiro · 5 sessões</div>
        <div class="tv {cls_5}">{'+' if fx5 >= 0 else '−'}R$ {_fmt(abs(fx5))} <span class="unit">mi</span></div>
        <div class="ts">21 sessões: {'+' if flow['estrangeiro_21d_mi'] >= 0 else '−'}R$ {_fmt(abs(flow['estrangeiro_21d_mi']))} mi</div></div>"""

    vp_tiles = ""
    if vp and vp.get("d1"):
        d1 = vp["d1"]
        comp = vp.get("comp")
        vp_tiles = f"""
      <div class="tile"><div class="tl">POC da sessão anterior · {vp['ticker']}</div>
        <div class="tv neon">{_fmt(d1['poc'])}</div>
        <div class="ts">área de valor {_fmt(d1['val'])} — {_fmt(d1['vah'])} (onde 70% do volume girou)</div></div>"""
        if comp:
            vp_tiles += f"""
      <div class="tile"><div class="tl">POC composto · {comp['days']} sessões</div>
        <div class="tv neon">{_fmt(comp['poc'])}</div>
        <div class="ts">área de valor {_fmt(comp['val'])} — {_fmt(comp['vah'])} (zona consolidada da semana)</div></div>"""

    greek_tiles = ""
    greek_card = ""
    fl = res.get("flows")
    if fl:
        vmi = fl["vanna_1pct"] / 1e6
        cmi = fl["charm_day"] / 1e6
        _money = lambda m: (f"R$ {_fmt(abs(m)/1000, 1)} bi" if abs(m) >= 1000
                            else f"R$ {_fmt(abs(m))} mi")
        # hedge = oposto da variação de delta dos dealers
        v_up = "vendem" if vmi > 0 else "compram"
        v_dn = "compram" if vmi > 0 else "vendem"
        c_act = "vender" if cmi > 0 else "comprar"
        c_cls = "neg" if cmi > 0 else "pos"
        greek_tiles = f"""
      <div class="tile"><div class="tl">Vanna — hedge por vol</div>
        <div class="tv neon">{_money(vmi)} <span class="unit">/ 1pt vol</span></div>
        <div class="ts">vol subindo → dealers {v_up}; vol caindo → {v_dn}</div></div>
      <div class="tile"><div class="tl">Charm — hedge do relógio</div>
        <div class="tv {c_cls}">{_money(cmi)} <span class="unit">/ dia</span></div>
        <div class="ts">a cada dia que passa os dealers tendem a {c_act} esse tanto</div></div>"""
        greek_card = f"""<div class="card">
<h2>Fluxos de hedge dos dealers — vanna e charm</h2>
<div class="rd">O gamma diz o que os bancos fazem quando o <b>preço</b> se move.
Mas eles também rebalanceiam quando a <b>volatilidade</b> muda (vanna) e quando
simplesmente <b>o tempo passa</b> (charm). Hoje o book indica: se a vol implícita
subir 1 ponto, os dealers precisam <b>{v_up} ~{_money(vmi)}</b> em índice
para se manterem neutros (e {v_dn} se a vol cair — é por isso que dia de vol
derretendo costuma virar rali lento e constante). Pela passagem do dia, o
decaimento do delta os obriga a <b>{c_act} ~{_money(cmi)}</b> — esse fluxo
de charm concentra-se na primeira hora e cresce muito na semana do vencimento.
Leitura prática: quando vanna e charm apontam para o mesmo lado do seu trade,
o "vento de fundo" dos hedges está a seu favor; contra, exija mais confirmação.</div>
</div>"""

    rows = []
    for w in walls:
        tag = {3: "WALL ★★★", 2: "WALL ★★", 1: "WALL ★"}[w["width"]]
        rows.append((w["fut"], tag, f"parede de proteção · strike {w['strike']:,}".replace(",", ".")))
    for m in data["mids"]:
        rows.append((m, "mid wall", "primeiro alvo entre paredes"))
    rows.append((data["maxg"], "MAX GAMMA", "teto estatístico do mapa"))
    rows.append((data["ming"], "MIN GAMMA", "piso estatístico do mapa"))
    rows.append((data["flip"], "GAMMA FLIP", "divisor de regime — a linha mais importante"))
    if prob.get("band_up_fut"):
        rows.append((prob["band_up_fut"], "banda +1σ", "limite superior esperado do dia"))
        rows.append((prob["band_down_fut"], "banda −1σ", "limite inferior esperado do dia"))
    if vp and vp.get("d1"):
        d1 = vp["d1"]
        rows.append((d1["poc"], "POC (1 sessão)", "preço mais negociado ontem — ímã de preço"))
        rows.append((d1["vah"], "VAH (1 sessão)", "topo da área de valor de ontem"))
        rows.append((d1["val"], "VAL (1 sessão)", "fundo da área de valor de ontem"))
        if vp.get("comp"):
            c = vp["comp"]
            rows.append((c["poc"], f"POC ({c['days']} sessões)", "preço mais negociado da semana"))
            rows.append((c["vah"], f"VAH ({c['days']} sessões)", "topo da área de valor semanal"))
            rows.append((c["val"], f"VAL ({c['days']} sessões)", "fundo da área de valor semanal"))
    rows.sort(key=lambda r: -r[0])
    table_rows = "\n".join(
        f"<tr><td class='num'>{_fmt(v,1)}</td><td class='tag'>{t}</td><td class='muted'>{d}</td></tr>"
        for v, t, d in rows)

    rationale = build_rationale(
        spot_fut, res["walls"], [f for _, f in res["mids"]], flip_fut,
        res["max_gamma"][1], res["min_gamma"][1],
        prob.get("band_up_fut") or spot_fut, prob.get("band_down_fut") or spot_fut)
    if vp and vp.get("d1"):
        d1 = vp["d1"]
        conf = [w for w in res["walls"]
                if abs(w[2] - d1["poc"]) <= 200 or abs(w[2] - d1["vah"]) <= 200
                or abs(w[2] - d1["val"]) <= 200]
        txt = (f"Ontem o mercado negociou mais no POC {_fmt(d1['poc'])}, com a área de valor entre "
               f"{_fmt(d1['val'])} e {_fmt(d1['vah'])}. A leitura que ensino sempre: se o dia ABRIR DENTRO "
               "dessa faixa, o mercado está 'confortável' — espere rotação e opere as bordas (compra no VAL, "
               "venda no VAH, alvo no POC). Se ABRIR FORA, o mercado rejeitou os preços de ontem — ou ele "
               "volta para testar o POC (movimento de retorno) ou engata tendência para longe dele.")
        if conf:
            txt += (" Detalhe importante hoje: há wall de gamma a menos de 200 pontos de "
                    + ", ".join(_fmt(w[2]) for w in conf[:2])
                    + " — quando volume e gamma apontam para o mesmo lugar, o nível vale em dobro.")
        rationale.append(("Volume profile: onde o mercado 'aceitou' negociar", txt))
    if flow:
        fx, fx5 = flow["estrangeiro_dia_mi"], flow["estrangeiro_5d_mi"]
        lado_d = "COMPRADOR" if fx >= 0 else "VENDEDOR"
        lado_5 = "comprando" if fx5 >= 0 else "vendendo"
        rationale.append(("Fluxo estrangeiro: quem está pagando a conta",
                          f"O estrangeiro — que é quem de fato move o nosso índice — apareceu {lado_d} em "
                          f"R$ {_fmt(abs(fx))} mi na sessão de {_br_date(flow['last_session'])} (o dado sai "
                          f"com 2 pregões de atraso) e vem {lado_5} R$ {_fmt(abs(fx5))} mi no acumulado de 5 "
                          "sessões. Como usar: fluxo persistente na MESMA direção do movimento valida "
                          "rompimentos; preço subindo com estrangeiro vendendo (ou o contrário) é movimento "
                          "com perna curta — desconfie."))
    rat_html = "\n".join(
        f"<div class='rat'><div class='rt'>{t}</div><div class='rd'>{d}</div></div>"
        for t, d in rationale)

    gloss_html = "\n".join(
        f"<div class='rat'><div class='rt' style='color:var(--cyan)'>{t}</div><div class='rd'>{d}</div></div>"
        for t, d in GLOSSARY)

    banner = (f"Mapa calculado com os dados do pregão de <b>{_br_date(res['ref_date'])}</b> "
              f"(fechamento) — preparado para a sessão de <b>{_br_date(session_str)}</b>.")

    # --- resumo do professor (visão geral) ---
    acima = [w for w in res["walls"] if w[2] > spot_fut]
    abaixo = [w for w in res["walls"] if w[2] <= spot_fut]
    r_teto = _fmt(acima[0][2]) if acima else _fmt(res["max_gamma"][1])
    r_piso = _fmt(abaixo[-1][2]) if abaixo else _fmt(res["min_gamma"][1])
    if flow:
        fx5 = flow["estrangeiro_5d_mi"]
        r_flow = ("com o gringo comprador na semana" if fx5 >= 0
                  else "com o gringo vendedor na semana")
    else:
        r_flow = "sem leitura de fluxo disponível"
    if pos:
        resumo = (f"Dia de gamma positivo {r_flow}: o mapa favorece <b>operar as bordas</b> — "
                  f"compra na defesa de {r_piso}, venda na rejeição de {r_teto}, sem perseguir "
                  "rompimento. Abra <b>A aula do dia</b> no menu para os cenários completos com "
                  "alvo e invalidação.")
    else:
        resumo = (f"Dia de gamma negativo {r_flow}: regime nervoso, movimentos tendem a "
                  f"<b>acelerar</b>. Opere a favor do movimento com stop curto; referências em "
                  f"{r_piso} (baixo) e {r_teto} (cima). Abra <b>A aula do dia</b> no menu para os "
                  "cenários completos.")

    bt_html = ""
    if bt and bt.get("n_days"):
        def pct(x):
            return f"{x*100:.0f}%" if x is not None else "—"
        wrows = ""
        for k, label in (("3", "WALL ★★★"), ("2", "WALL ★★"), ("1", "WALL ★")):
            g = (bt.get("walls") or {}).get(k) or {}
            wrows += (f"<tr><td class='tag'>{label}</td>"
                      f"<td class='num'>{g.get('toques', 0)}</td>"
                      f"<td class='num'>{g.get('rejeitou', 0)}</td>"
                      f"<td class='num'>{g.get('rompeu', 0)}</td>"
                      f"<td class='num'>{pct(g.get('taxa_rejeicao'))}</td></tr>")
        bd = bt.get("bands") or {}
        pc = bt.get("poc") or {}
        va = bt.get("va") or {}
        fl = bt.get("flip") or {}
        extras = []
        if bd.get("days"):
            extras.append(f"<b>Bandas ±1σ:</b> o dia ficou inteiro dentro do "
                          f"esperado em {pct(bd.get('taxa_dentro'))} das sessões "
                          f"({bd['inside']}/{bd['days']}).")
        if pc.get("days"):
            extras.append(f"<b>POC como ímã:</b> o preço voltou a negociar no "
                          f"POC da véspera em {pct(pc.get('taxa_ima'))} dos dias.")
        if va.get("open_inside"):
            extras.append(f"<b>Abertura dentro da área de valor:</b> virou dia "
                          f"de rotação em {pct(va.get('taxa_rotacao'))} das vezes "
                          f"({va['open_inside']} amostras).")
        if va.get("open_outside"):
            extras.append(f"<b>Abertura fora da área de valor:</b> virou dia de "
                          f"tendência em {pct(va.get('taxa_tendencia'))} das vezes "
                          f"({va['open_outside']} amostras).")
        if fl.get("crosses"):
            extras.append(f"<b>Perda do flip:</b> aconteceu {fl['crosses']}x; "
                          f"queda adicional média de "
                          f"{_fmt(fl['queda_media_extra']) if fl.get('queda_media_extra') else '—'} pts.")
        extras_html = "".join(f"<div class='rd' style='margin-top:6px'>{e}</div>"
                              for e in extras)
        bt_html = f"""<div class="card">
<h2>Auditoria dos últimos {bt['n_days']} pregões</h2>
<div class="rd" style="margin-bottom:10px">Aula de honestidade: todo dia o mapa
da véspera é comparado com o que o mercado REALMENTE fez ({_br_date(bt.get('desde'))}
a {_br_date(bt.get('ate'))}). Toque = preço chegou a 100 pts da linha; rejeição =
afastou 400 pts sem romper; rompimento = atravessou 200 pts. Amostra pequena
ainda merece desconfiança — os números amadurecem a cada sessão.</div>
<table><tr><th>linha</th><th>toques</th><th>rejeitou</th><th>rompeu</th><th>taxa de rejeição</th></tr>
{wrows}</table>
{extras_html}</div>"""

        # --- Onda 5: condicionais, gaps e relógio do pregão ---
        cond = bt.get("cond") or {}
        if cond:
            labels = (("pos", "Gamma POSITIVO"), ("neg", "Gamma NEGATIVO"),
                      ("comprador", "Gringo COMPRADOR (5 sessões)"),
                      ("vendedor", "Gringo VENDEDOR (5 sessões)"))
            crows = "".join(
                f"<tr><td class='tag'>{lab}</td>"
                f"<td class='num'>{cond[k]['toques']}</td>"
                f"<td class='num'>{cond[k]['rejeitou']}</td>"
                f"<td class='num'>{cond[k]['rompeu']}</td>"
                f"<td class='num'>{pct(cond[k]['taxa_rejeicao'])}</td></tr>"
                for k, lab in labels if k in cond)
            bt_html += f"""<div class="card">
<h2>Como as walls se comportam em cada cenário</h2>
<div class="rd" style="margin-bottom:10px">A mesma parede não vale o mesmo em
todo dia. Aqui está a taxa de rejeição das walls (todas juntas) separada pelo
regime de gamma do dia e pelo lado do fluxo estrangeiro conhecido na manhã —
é assim que estatística vira setup: opere a rejeição nos cenários em que ela
historicamente funciona.</div>
<table><tr><th>cenário</th><th>toques</th><th>rejeitou</th><th>rompeu</th><th>taxa de rejeição</th></tr>
{crows}</table></div>"""

        gaps = bt.get("gaps") or {}
        if any((g or {}).get("n") for g in gaps.values()):
            glabels = (("ate_300", "até 300 pts"), ("300_700", "300–700 pts"),
                       ("700_1500", "700–1.500 pts"),
                       ("acima_1500", "acima de 1.500 pts"))
            grows = "".join(
                f"<tr><td class='tag'>{lab}</td>"
                f"<td class='num'>{gaps[k]['n']}</td>"
                f"<td class='num'>{gaps[k]['fechou']}</td>"
                f"<td class='num'>{pct(gaps[k]['taxa_fechou'])}</td></tr>"
                for k, lab in glabels if gaps.get(k, {}).get("n"))
            bt_html += f"""<div class="card">
<h2>Gap de abertura — fecha ou não fecha?</h2>
<div class="rd" style="margin-bottom:10px">Gap = distância entre a abertura de
hoje e o fechamento de ontem. "Fechou" = em algum momento do dia o preço voltou
ao fechamento da véspera. A lição clássica: gap pequeno é ímã, gap grande é
tendência — confira o que os números REAIS dizem antes do primeiro trade.</div>
<table><tr><th>tamanho do gap</th><th>ocorrências</th><th>fechou no dia</th><th>taxa</th></tr>
{grows}</table></div>"""

        hourly = bt.get("hourly") or {}
        if hourly:
            hrows = "".join(
                f"<tr><td class='num' style='font-size:14px'>{h}h</td>"
                f"<td class='num'>{hourly[h]['toques']}</td>"
                f"<td class='num'>{pct(hourly[h]['taxa_rejeicao'])}</td>"
                f"<td class='num'>{hourly[h].get('vol_pct', 0)}%</td></tr>"
                for h in sorted(hourly.keys(), key=int))
            bt_html += f"""<div class="card">
<h2>Relógio do pregão — quando os níveis valem mais</h2>
<div class="rd" style="margin-bottom:10px">Hora do primeiro toque em cada wall
e o resultado, mais a fatia do volume negociado em cada hora. Use para escolher
a SUA janela: rejeição funciona melhor nas horas em que historicamente é mais
respeitada; hora de volume fraco (almoço) costuma dar sinal falso.</div>
<table><tr><th>hora</th><th>toques em wall</th><th>taxa de rejeição</th><th>% do volume do dia</th></tr>
{hrows}</table></div>"""
    else:
        bt_html = ("<div class='card'><h2>Auditoria dos pregões</h2>"
                   "<div class='rd'>As primeiras estatísticas aparecem aqui após a "
                   "próxima sessão auditada — todo dia o mapa da véspera é comparado "
                   "com o que o mercado realmente fez.</div></div>")

    regime_pill_cls = "pill-pos" if pos else "pill-neg"
    tiles_all = tiles + flow_tiles + vp_tiles + greek_tiles
    global_html, newscal_html = _ctx_sections(ctx)

    return (HTML_TMPL
            .replace("__GLOBALSEC__", global_html)
            .replace("__NEWSSEC__", newscal_html)
            .replace("__DATA__", json.dumps(data))
            .replace("__TILES__", tiles_all)
            .replace("__FLOWTILES__", flow_tiles or
                     "<div class='tile'><div class='tl'>Fluxo indisponível</div>"
                     "<div class='ts'>a B3 não publicou o dado desta janela</div></div>")
            .replace("__VPTILES__", vp_tiles or
                     "<div class='tile'><div class='tl'>Volume profile indisponível</div>"
                     "<div class='ts'>sem tick data para a sessão anterior</div></div>")
            .replace("__ROWS__", table_rows)
            .replace("__RATIONALE__", rat_html)
            .replace("__BTCARD__", bt_html)
            .replace("__GREEKCARD__", greek_card)
            .replace("__GLOSSARY__", gloss_html)
            .replace("__BANNER__", banner)
            .replace("__RESUMO__", resumo)
            .replace("__REGIME__", regime)
            .replace("__REGIMECLS__", regime_pill_cls)
            .replace("__FLIP__", _fmt(flip_fut))
            .replace("__SESSION__", _br_date(session_str)))


HTML_TMPL = r"""<!DOCTYPE html>
<html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>GAMMA LINES — __SESSION__</title>
<style>
:root{
  --page:#05070c; --surface:#0b101c; --surface2:#0e1524;
  --ink:#eaf2ff; --ink2:#9fb3d1; --muted:#5e7191;
  --grid:#16203a; --axis:#243354;
  --pos:#33b1ff; --neg:#ff5d5d; --mid:#1a2438; --accent:#00e5a0;
  --gold:#ffd75e; --cyan:#37e0ff; --magenta:#ff5dc8;
  --border:rgba(55,224,255,.14);
  --glow:0 0 18px rgba(55,224,255,.18);
  --sbw:236px;
}
*{box-sizing:border-box}
body{margin:0;color:var(--ink);
  font:14px/1.55 "Segoe UI",system-ui,-apple-system,sans-serif;
  background:
    radial-gradient(1200px 500px at 70% -10%, rgba(55,224,255,.07), transparent 60%),
    radial-gradient(900px 400px at 10% 110%, rgba(0,229,160,.05), transparent 60%),
    repeating-linear-gradient(0deg, transparent 0 39px, rgba(55,224,255,.025) 39px 40px),
    repeating-linear-gradient(90deg, transparent 0 39px, rgba(55,224,255,.02) 39px 40px),
    var(--page);}
.num,.tv,td.num{font-family:"Cascadia Code","Consolas",ui-monospace,monospace;
  font-variant-numeric:tabular-nums}
h2{font-size:12px;margin:0 0 12px;color:var(--cyan);text-transform:uppercase;
  letter-spacing:.18em;font-weight:600}
h2::before{content:"▸ ";color:var(--accent)}

/* ===== sidebar ===== */
.sidebar{position:fixed;left:0;top:0;bottom:0;width:var(--sbw);z-index:20;
  background:linear-gradient(180deg,#0c1322,#080d18);
  border-right:1px solid var(--border);display:flex;flex-direction:column;padding:18px 0}
.logo{padding:0 20px 14px;border-bottom:1px solid var(--grid)}
.logo h1{font-size:17px;margin:0;letter-spacing:.14em;text-transform:uppercase;
  background:linear-gradient(90deg,var(--cyan),var(--accent));
  -webkit-background-clip:text;background-clip:text;color:transparent}
.logo .d{color:var(--muted);font-size:11px;margin-top:2px}
.nav{flex:1;overflow:auto;padding:12px 10px}
.nav a{display:flex;align-items:center;gap:10px;padding:10px 12px;margin:2px 0;
  border-radius:10px;color:var(--ink2);text-decoration:none;font-size:13px;cursor:pointer;
  border:1px solid transparent;transition:all .15s}
.nav a .ic{width:20px;text-align:center;color:var(--muted)}
.nav a:hover{background:rgba(55,224,255,.06);color:var(--ink)}
.nav a.on{background:linear-gradient(90deg,rgba(55,224,255,.12),rgba(0,229,160,.05));
  color:var(--cyan);border-color:var(--border);box-shadow:var(--glow)}
.nav a.on .ic{color:var(--accent)}
.nav .sec{font-size:9.5px;color:var(--muted);text-transform:uppercase;letter-spacing:.2em;
  padding:14px 12px 4px}
.side-foot{padding:12px 20px 0;border-top:1px solid var(--grid);font-size:10.5px;color:var(--muted)}
.pill{display:block;text-align:center;margin-bottom:8px;padding:7px 10px;border-radius:9px;
  font-weight:700;font-size:12px;letter-spacing:.08em}
.pill-pos{color:var(--pos);background:rgba(51,177,255,.08);border:1px solid rgba(51,177,255,.3)}
.pill-neg{color:var(--neg);background:rgba(255,93,93,.08);border:1px solid rgba(255,93,93,.3)}

/* ===== conteúdo ===== */
.main{margin-left:var(--sbw);padding:24px 26px;max-width:1200px}
.pagehead{display:flex;align-items:baseline;gap:14px;flex-wrap:wrap;margin-bottom:6px}
.pagehead h3{font-size:20px;margin:0;color:var(--ink);letter-spacing:.06em;font-weight:600}
.pagehead .crumb{color:var(--muted);font-size:12px}
.sub{color:var(--muted);font-size:12px;margin:2px 0 16px}
.view{display:none;animation:fade .25s ease}
.view.on{display:block}
@keyframes fade{from{opacity:0;transform:translateY(4px)}to{opacity:1;transform:none}}
.banner{background:linear-gradient(90deg,rgba(0,229,160,.10),transparent 70%);
  border:1px solid var(--border);border-left:3px solid var(--accent);
  border-radius:12px;padding:12px 16px;margin:0 0 16px;font-size:13.5px;color:var(--ink2)}
.banner b{color:var(--accent)}
.prof{background:linear-gradient(90deg,rgba(55,224,255,.08),transparent 70%);
  border:1px solid var(--border);border-left:3px solid var(--cyan);
  border-radius:12px;padding:12px 16px;margin:0 0 16px;font-size:13.5px;color:var(--ink2)}
.prof b{color:var(--cyan)}
.tiles{display:grid;gap:14px;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));margin-bottom:16px}
.tile{background:linear-gradient(180deg,var(--surface2),var(--surface));
  border:1px solid var(--border);border-radius:14px;padding:16px 18px;box-shadow:var(--glow);
  position:relative;overflow:hidden}
.tile::after{content:"";position:absolute;inset:0 0 auto 0;height:2px;
  background:linear-gradient(90deg,transparent,var(--cyan),transparent);opacity:.55}
.tl{font-size:10px;color:var(--muted);text-transform:uppercase;letter-spacing:.16em}
.tv{font-size:32px;font-weight:700;margin:6px 0 4px;line-height:1.1}
.tv.neon{color:var(--cyan);text-shadow:0 0 22px rgba(55,224,255,.45)}
.tv.pos{color:var(--pos);text-shadow:0 0 22px rgba(51,177,255,.4)}
.tv.neg{color:var(--neg);text-shadow:0 0 22px rgba(255,93,93,.4)}
.unit{font-size:15px;color:var(--ink2);font-weight:400}
.ts{font-size:11.5px;color:var(--ink2)}
.card{background:linear-gradient(180deg,var(--surface2),var(--surface));
  border:1px solid var(--border);border-radius:14px;padding:18px;box-shadow:var(--glow);
  margin-bottom:16px}
.grid{display:grid;gap:16px;grid-template-columns:repeat(auto-fit,minmax(340px,1fr))}
.grid .card{margin-bottom:0}
svg{display:block;width:100%;height:auto}
table{width:100%;border-collapse:collapse;font-size:13px}
td,th{padding:7px 10px;border-bottom:1px solid var(--grid);text-align:left}
th{color:var(--muted);text-transform:uppercase;font-size:10px;letter-spacing:.14em}
td.num{font-weight:700;font-size:16px;color:var(--cyan)}
td.tag{color:var(--ink);white-space:nowrap}
.muted{color:var(--muted)}
.foot{color:var(--muted);font-size:11px;margin-top:20px;border-top:1px solid var(--grid);padding-top:12px}
.tip{position:fixed;pointer-events:none;background:#0e1524;color:var(--ink);
  border:1px solid var(--border);padding:6px 10px;border-radius:8px;font-size:12px;
  display:none;z-index:9;box-shadow:var(--glow)}
.legend{display:flex;gap:16px;font-size:11px;color:var(--ink2);margin-top:8px;flex-wrap:wrap}
.legend span::before{content:"";display:inline-block;width:10px;height:10px;border-radius:3px;
  margin-right:6px;vertical-align:-1px;background:var(--c);box-shadow:0 0 8px var(--c)}
.rat{padding:12px 0;border-bottom:1px solid var(--grid)} .rat:last-child{border-bottom:0}
.rt{font-weight:700;font-size:14px;margin-bottom:4px;color:var(--gold)}
.rd{font-size:13.5px;color:var(--ink2)}
.tvimg{width:100%;height:auto;border-radius:10px;border:1px solid var(--border);display:block}

/* ===== mobile ===== */
.burger{display:none}
@media (max-width:860px){
  .sidebar{transform:translateX(-100%);transition:transform .2s}
  .sidebar.open{transform:none;box-shadow:20px 0 60px rgba(0,0,0,.6)}
  .main{margin-left:0;padding:18px 14px}
  .burger{display:flex;position:fixed;left:12px;top:10px;z-index:30;width:40px;height:40px;
    align-items:center;justify-content:center;border-radius:10px;cursor:pointer;
    background:var(--surface2);border:1px solid var(--border);color:var(--cyan);font-size:18px}
  .pagehead{margin-top:44px}
}
</style></head><body>
<div class="burger" id="burger">&#9776;</div>

<aside class="sidebar" id="sidebar">
  <div class="logo"><h1>Gamma Lines</h1><div class="d">sessão de __SESSION__</div></div>
  <nav class="nav" id="nav">
    <div class="sec">Painel</div>
    <a data-v="aovivo"><span class="ic" id="lv-dot" style="color:#555">&#9679;</span> Ao Vivo</a>
    <a data-v="overview" class="on"><span class="ic">&#9673;</span> Visão geral</a>
    <a data-v="aula"><span class="ic">&#127891;</span> A aula do dia</a>
    <a data-v="niveis"><span class="ic">&#8801;</span> Níveis do dia</a>
    <div class="sec">Análises</div>
    <a data-v="stats"><span class="ic">&#10003;</span> Estatísticas das zonas</a>
    <a data-v="graficos"><span class="ic">&#8767;</span> Gráficos de gamma</a>
    <a data-v="fluxo"><span class="ic">$</span> Fluxo estrangeiro</a>
    <a data-v="vp"><span class="ic">&#9636;</span> Volume profile</a>
    <div class="sec">Contexto</div>
    <a data-v="global"><span class="ic">&#127758;</span> Mercado global</a>
    <a data-v="news"><span class="ic">&#128240;</span> Notícias &amp; agenda</a>
    <div class="sec">Extras</div>
    <a data-v="tv"><span class="ic">&#128200;</span> Mapa no TradingView</a>
    <a data-v="gloss"><span class="ic">?</span> Glossário</a>
  </nav>
  <div class="side-foot">
    <span class="pill __REGIMECLS__">__REGIME__</span>
    flip __FLIP__ · material educacional, não é recomendação
  </div>
</aside>

<main class="main">

<section class="view" id="v-aovivo">
  <div class="pagehead"><h3>Ao Vivo</h3><span class="crumb" id="lv-status">carregando…</span></div>
  <style>
  .lv-grid{display:grid;grid-template-columns:340px 1fr;gap:14px}
  @media(max-width:860px){.lv-grid{grid-template-columns:1fr}}
  #lv-price{font-size:42px;font-weight:800;color:var(--accent);line-height:1.05;text-shadow:0 0 18px rgba(55,224,255,.3)}
  #lv-delta{font-size:16px;font-weight:700;margin-top:2px}
  #lv-delta.pos{color:var(--pos)}#lv-delta.neg{color:var(--neg)}
  #lv-nearest{margin-top:8px;font-size:13px;color:var(--muted)}#lv-nearest b{color:var(--ink)}
  .lv-lvl{display:flex;align-items:center;gap:10px;padding:4px 8px;border-radius:8px;font-size:12.5px}
  .lv-lvl .p{font-variant-numeric:tabular-nums;font-weight:700;min-width:72px;text-align:right}
  .lv-lvl .tag{font-size:10.5px;letter-spacing:.5px;padding:1px 8px;border-radius:20px;border:1px solid}
  .lv-lvl .d{margin-left:auto;font-size:11px;color:var(--muted)}
  .lv-lvl.spot{background:rgba(55,224,255,.10);border:1px solid rgba(55,224,255,.35);margin:3px 0}
  .lv-lvl.spot .p{color:var(--accent)}
  .lv-w{color:#32cd32;border-color:rgba(50,205,50,.4)}.lv-f{color:var(--gold);border-color:rgba(255,215,0,.4)}
  .lv-v{color:#ff00ff;border-color:rgba(255,0,255,.4)}.lv-s{color:#c0c0c0;border-color:rgba(192,192,192,.35)}
  .lv-b{color:var(--accent);border-color:rgba(55,224,255,.35)}
  .lv-feed{display:flex;flex-direction:column;gap:10px;max-height:66vh;overflow-y:auto}
  .lv-msg{background:rgba(255,255,255,.025);border:1px solid rgba(255,255,255,.06);border-left:3px solid var(--accent);border-radius:10px;padding:9px 12px;font-size:13.5px}
  .lv-msg .h{display:flex;gap:8px;align-items:baseline;margin-bottom:2px}
  .lv-msg .t{color:var(--accent);font-weight:700;font-size:12.5px}
  .lv-msg .k{font-size:10px;letter-spacing:1px;text-transform:uppercase;color:var(--muted)}
  .lv-msg .px{margin-left:auto;font-size:12px;color:var(--muted)}
  .lv-msg.abertura{border-left-color:var(--gold)}.lv-msg.evento{border-left-color:var(--neg)}
  .lv-msg.fim{border-left-color:var(--muted)}
  .lv-msg .note{white-space:pre-wrap}
  </style>
  <div class="prof">Leituras geradas a cada ~5 minutos durante o pregão (9h–12h BRT), cruzando o
preço do WIN em tempo real com o mapa do dia e as estatísticas auditadas. Fora desse horário a
página mostra o histórico da última sessão.</div>
  <div class="lv-grid">
    <div>
      <div class="card" style="margin-bottom:14px"><h2>Última leitura</h2>
        <div id="lv-price">—</div><div id="lv-delta"></div><div id="lv-nearest"></div></div>
      <div class="card"><h2>Régua do dia</h2><div id="lv-ruler"></div></div>
    </div>
    <div class="card"><h2>Leituras do pregão</h2>
      <div class="lv-feed" id="lv-feed"><div style="color:var(--muted);padding:16px;text-align:center">carregando…</div></div></div>
  </div>
</section>

<section class="view on" id="v-overview">
  <div class="pagehead"><h3>Visão geral</h3><span class="crumb">o essencial antes do pregão</span></div>
  <div class="sub" id="sub"></div>
  <div class="banner">__BANNER__</div>
  <div class="prof"><b>Aula rápida antes do pregão:</b> este painel é o seu mapa do território. As
<b>walls</b> são as paredes onde os grandes players se defendem; o <b>flip</b> diz se o dia tende a ser
calmo ou nervoso; as <b>bandas</b> mostram o tamanho esperado do dia; o <b>POC</b> mostra onde o mercado
negociou ontem; e o <b>fluxo</b> mostra quem está colocando dinheiro. Nenhuma linha é sinal de entrada
sozinha — elas marcam os pontos de decisão onde você deve OBSERVAR a reação do preço antes de agir.</div>
  <div class="tiles">__TILES__</div>
  <div class="card"><h2>Resumo do professor</h2><div class="rd">__RESUMO__</div></div>
</section>

<section class="view" id="v-aula">
  <div class="pagehead"><h3>A aula do dia</h3><span class="crumb">cenários e como operá-los</span></div>
  <div class="card">__RATIONALE__</div>
</section>

<section class="view" id="v-niveis">
  <div class="pagehead"><h3>Níveis do dia</h3><span class="crumb">pontos do futuro, do maior para o menor</span></div>
  <div class="card"><table>
    <tr><th>nível</th><th>tipo</th><th>como usar</th></tr>
    __ROWS__</table></div>
</section>

<section class="view" id="v-stats">
  <div class="pagehead"><h3>Estatísticas das zonas</h3><span class="crumb">o mapa auditado contra o mercado real</span></div>
  __BTCARD__
</section>

<section class="view" id="v-graficos">
  <div class="pagehead"><h3>Gráficos de gamma</h3><span class="crumb">posicionamento dos dealers e distribuição</span></div>
  <div class="grid">
    <div class="card"><h2>Gamma dos dealers × nível do futuro</h2>
      <svg id="curve" viewBox="0 0 560 260"></svg>
      <div class="legend"><span style="--c:var(--pos)">gamma positivo (segura)</span>
        <span style="--c:var(--neg)">gamma negativo (acelera)</span>
        <span style="--c:var(--gold)">flip</span><span style="--c:var(--muted)">preço ref.</span></div></div>
    <div class="card"><h2>Concentração por strike (R$ mi)</h2>
      <svg id="bars" viewBox="0 0 560 260"></svg>
      <div class="legend"><span style="--c:var(--pos)">bancos long gamma</span>
        <span style="--c:var(--neg)">bancos short gamma</span><span style="--c:var(--muted)">★ = wall</span></div></div>
    <div class="card"><h2>Onde o mercado acha que fecha (distribuição)</h2>
      <svg id="dens" viewBox="0 0 560 240"></svg>
      <div class="legend"><span style="--c:var(--accent)">probabilidade</span>
        <span style="--c:var(--muted)">P10–P90</span><span style="--c:var(--pos)">±1σ dia</span></div></div>
  </div>
  __GREEKCARD__
</section>

<section class="view" id="v-fluxo">
  <div class="pagehead"><h3>Fluxo estrangeiro</h3><span class="crumb">quem está pagando a conta</span></div>
  <div class="tiles">__FLOWTILES__</div>
  <div class="card" id="cardflow" style="display:none"><h2>Fluxo estrangeiro por sessão (R$ mi)</h2>
    <svg id="flow" viewBox="0 0 560 240"></svg>
    <div class="legend"><span style="--c:var(--pos)">gringo comprando</span>
      <span style="--c:var(--neg)">gringo vendendo</span>
      <span style="--c:var(--muted)">à vista · defasagem D-2</span></div></div>
</section>

<section class="view" id="v-vp">
  <div class="pagehead"><h3>Volume profile</h3><span class="crumb">onde o mercado 'aceitou' negociar</span></div>
  <div class="tiles">__VPTILES__</div>
  <div class="card" id="cardvp" style="display:none"><h2>Volume profile do WIN (ontem × semana)</h2>
    <svg id="vp" viewBox="0 0 560 300"></svg>
    <div class="legend"><span style="--c:var(--pos)">volume de ontem</span>
      <span style="--c:var(--mid)">volume da semana</span>
      <span style="--c:var(--magenta)">POC</span><span style="--c:var(--muted)">VAH/VAL</span></div></div>
</section>

<section class="view" id="v-global">
  <div class="pagehead"><h3>Mercado global</h3><span class="crumb">o humor do mundo antes da abertura</span></div>
  <div class="prof"><b>Como ler:</b> a Ásia já fechou (é o "resultado da madrugada"); a Europa está
rodando agora; os futuros americanos dão o tom do risco. Dólar forte (DXY subindo) e VIX alto pedem
cautela com compra no Ibovespa; petróleo e minério puxam Petrobras e Vale, os pesos-pesados do índice.</div>
  __GLOBALSEC__
</section>

<section class="view" id="v-news">
  <div class="pagehead"><h3>Notícias &amp; agenda</h3><span class="crumb">o que pode mexer com o dia</span></div>
  __NEWSSEC__
</section>

<section class="view" id="v-tv">
  <div class="pagehead"><h3>Mapa no TradingView</h3><span class="crumb">WIN 15 min com as linhas desenhadas</span></div>
  <div class="card"><h2>Print do dia</h2>
    <!--TVSLOT-->
    <div class="rd" id="tvnote">O print do TradingView não está disponível nesta edição do painel —
    ele é gerado na entrega da manhã quando o computador com o TradingView está conectado.</div>
  </div>
</section>

<section class="view" id="v-gloss">
  <div class="pagehead"><h3>Glossário do professor</h3><span class="crumb">os termos do mapa, explicados</span></div>
  <div class="card">__GLOSSARY__</div>
</section>

<div class="foot" id="foot"></div>
</main>
<div class="tip" id="tip"></div>
<script>
const D = __DATA__;
const css = v => getComputedStyle(document.documentElement).getPropertyValue(v).trim();
const fmt = (x,d=0)=>x.toLocaleString('pt-BR',{minimumFractionDigits:d,maximumFractionDigits:d});
document.getElementById('sub').textContent =
  `dados de ${D.ref} · ${D.fut} ajuste ${fmt(D.fut_settle)} · IBOV ${fmt(D.ibov,2)} (${D.ibov_source}) · fator ${D.fator.toFixed(5)} · séries: ${D.n_series.bova} BOVA11 + ${D.n_series.ibov} IBOV`;
document.getElementById('foot').textContent =
  '*Probabilidade risk-neutral extraída da curva de opções (Breeden-Litzenberger). Este painel é material educacional gerado automaticamente a partir de dados públicos da B3 — leitura de cenário, não recomendação de investimento. Gerencie seu risco: nenhum mapa substitui o stop.';

// ---- navegação da sidebar
const nav = document.getElementById('nav');
const sidebar = document.getElementById('sidebar');
document.getElementById('burger').addEventListener('click',()=>sidebar.classList.toggle('open'));
nav.addEventListener('click', e => {
  const a = e.target.closest('a[data-v]'); if (!a) return;
  nav.querySelectorAll('a').forEach(x => x.classList.remove('on'));
  a.classList.add('on');
  document.querySelectorAll('.view').forEach(v => v.classList.remove('on'));
  document.getElementById('v-' + a.dataset.v).classList.add('on');
  sidebar.classList.remove('open');
  window.scrollTo({top:0});
});
// abre view pelo hash (#aovivo etc.)
if (location.hash) {
  const a = nav.querySelector(`a[data-v="${location.hash.slice(1)}"]`);
  if (a) a.click();
}

// ---- Ao Vivo (Supabase)
const LV_URL = "https://cbazccsoynzextabjnxq.supabase.co";
const LV_KEY = "sb_publishable_JXjiEY5de-UMyFPMQIrO_A_-oOuJN5H";
let lvSpot = null;
function lvRows(){
  const out = [{p:D.maxg, tag:"MAX G", cls:"lv-b"}];
  for (const w of D.walls) out.push({p:w.fut, tag:"WALL " + "★".repeat(w.width), cls:"lv-w"});
  if (D.prob && D.prob.band_up){ out.push({p:D.prob.band_up, tag:"+1σ", cls:"lv-b"});
    out.push({p:D.prob.band_down, tag:"−1σ", cls:"lv-b"}); }
  if (D.vp && D.vp.d1){ const d=D.vp.d1; out.push({p:d.poc, tag:"POC", cls:"lv-v"});
    out.push({p:d.vah, tag:"VAH", cls:"lv-s"}); out.push({p:d.val, tag:"VAL", cls:"lv-s"}); }
  out.push({p:D.flip, tag:"FLIP", cls:"lv-f"}); out.push({p:D.ming, tag:"MIN G", cls:"lv-b"});
  return out.filter(x=>x.p).sort((a,b)=>b.p-a.p);
}
function lvRuler(){
  const el = document.getElementById('lv-ruler'); if (!el) return;
  el.innerHTML = ''; let done = false;
  const spotRow = () => { const d = document.createElement('div'); d.className='lv-lvl spot';
    d.innerHTML = `<span class="p">${fmt(lvSpot)}</span><span class="tag lv-b">WIN AGORA</span>`; return d; };
  for (const r of lvRows()){
    if (lvSpot && !done && lvSpot >= r.p){ el.appendChild(spotRow()); done = true; }
    const div = document.createElement('div'); div.className = 'lv-lvl';
    const dist = lvSpot ? Math.round(Math.abs(lvSpot - r.p)) : null;
    div.innerHTML = `<span class="p">${fmt(r.p)}</span><span class="tag ${r.cls}">${r.tag}</span>` +
      (dist !== null ? `<span class="d">${fmt(dist)} pts</span>` : '');
    el.appendChild(div);
  }
  if (lvSpot && !done) el.appendChild(spotRow());
}
async function lvLoad(){
  try{
    const today = new Date(new Date().toLocaleString('en-US',{timeZone:'America/Sao_Paulo'})).toISOString().slice(0,10);
    const u = `${LV_URL}/rest/v1/gamma_live_readings?select=*&kind=neq.teste&order=ts.desc&limit=120&session=eq.${today}`;
    let data = await (await fetch(u, {headers:{apikey:LV_KEY, Authorization:'Bearer '+LV_KEY}})).json();
    if (!Array.isArray(data)) data = [];
    if (!data.length){
      const u2 = `${LV_URL}/rest/v1/gamma_live_readings?select=*&kind=neq.teste&order=ts.desc&limit=60`;
      data = await (await fetch(u2, {headers:{apikey:LV_KEY, Authorization:'Bearer '+LV_KEY}})).json();
      if (!Array.isArray(data)) data = [];
    }
    const feed = document.getElementById('lv-feed'), st = document.getElementById('lv-status'),
          dot = document.getElementById('lv-dot');
    if (!data.length){ feed.innerHTML = '<div style="color:var(--muted);padding:16px;text-align:center">Nenhuma leitura ainda — elas começam ~9h em dia de pregão.</div>';
      st.textContent = 'sem leituras'; lvRuler(); return; }
    const last = data[0];
    if (last.price){
      lvSpot = Number(last.price);
      document.getElementById('lv-price').textContent = fmt(lvSpot);
      const d = Number(last.delta||0), de = document.getElementById('lv-delta');
      de.textContent = (d>=0?'+':'−') + fmt(Math.abs(d)) + ' pts vs fechamento';
      de.className = d>=0?'pos':'neg';
      if (last.nearest) document.getElementById('lv-nearest').innerHTML =
        `nível mais próximo: <b>${last.nearest}</b>` + (last.distance!=null?` a <b>${fmt(Math.round(last.distance))} pts</b>`:'');
    }
    feed.innerHTML = '';
    for (const m of data){
      const t = new Date(m.ts).toLocaleTimeString('pt-BR',{timeZone:'America/Sao_Paulo',hour:'2-digit',minute:'2-digit'});
      const div = document.createElement('div'); div.className = 'lv-msg ' + (m.kind||'');
      div.innerHTML = `<div class="h"><span class="t">${t}</span><span class="k">${m.kind||''}</span>` +
        (m.price?`<span class="px">${fmt(m.price)}</span>`:'') + `</div><div class="note"></div>`;
      div.querySelector('.note').textContent = m.note || '';
      feed.appendChild(div);
    }
    const mins = (Date.now() - new Date(last.ts).getTime())/60000,
          tl = new Date(last.ts).toLocaleTimeString('pt-BR',{timeZone:'America/Sao_Paulo',hour:'2-digit',minute:'2-digit'});
    st.textContent = (mins<=7?'AO VIVO · ':'') + 'última leitura ' + tl;
    dot.style.color = mins<=7 ? 'var(--pos)' : mins<=20 ? 'var(--gold)' : '#555';
    lvRuler();
  }catch(e){ console.log('aovivo', e); }
}
lvLoad(); setInterval(lvLoad, 30000);

const tip = document.getElementById('tip');
function showTip(ev,html){tip.innerHTML=html;tip.style.display='block';
  tip.style.left=(ev.clientX+12)+'px';tip.style.top=(ev.clientY-10)+'px';}
function hideTip(){tip.style.display='none';}
const NS='http://www.w3.org/2000/svg';
function el(p,t,a){const e=document.createElementNS(NS,t);
  for(const k in a)e.setAttribute(k,a[k]);p.appendChild(e);return e;}

// ---- curva G(S)
(function(){
  const svg=document.getElementById('curve'),W=560,H=260,m={l:46,r:10,t:10,b:26};
  const xs=D.curve.x, ys=D.curve.y;
  const x0=Math.min(...xs),x1=Math.max(...xs);
  const ymax=Math.max(...ys.map(Math.abs))*1.08;
  const X=v=>m.l+(v-x0)/(x1-x0)*(W-m.l-m.r);
  const Y=v=>m.t+(1-(v+ymax)/(2*ymax))*(H-m.t-m.b);
  for(let g=-2;g<=2;g++){const yv=ymax/2*g;
    el(svg,'line',{x1:m.l,x2:W-m.r,y1:Y(yv),y2:Y(yv),stroke:g===0?css('--axis'):css('--grid'),'stroke-width':1});
    el(svg,'text',{x:m.l-6,y:Y(yv)+4,'text-anchor':'end',fill:css('--muted'),'font-size':10}).textContent=fmt(yv/1000,1)+' bi';}
  const flipX=X(D.flip), spotX=X(D.spot_fut);
  if(D.flip>=x0&&D.flip<=x1){el(svg,'line',{x1:flipX,x2:flipX,y1:m.t,y2:H-m.b,stroke:css('--gold'),'stroke-width':1.5,'stroke-dasharray':'4 3'});}
  if(D.spot_fut>=x0&&D.spot_fut<=x1){el(svg,'line',{x1:spotX,x2:spotX,y1:m.t,y2:H-m.b,stroke:css('--muted'),'stroke-width':1.5});}
  let dPos='';
  xs.forEach((xv,i)=>{const p=`${X(xv)},${Y(ys[i])}`;dPos+=(i?' L':'M')+p;});
  el(svg,'path',{d:dPos,fill:'none',stroke:css('--pos'),'stroke-width':2});
  xs.forEach((xv,i)=>{ if(ys[i]<0) el(svg,'circle',{cx:X(xv),cy:Y(ys[i]),r:1.6,fill:css('--neg')}); });
  for(let i=0;i<=4;i++){const xv=x0+(x1-x0)*i/4;
    el(svg,'text',{x:X(xv),y:H-8,'text-anchor':'middle',fill:css('--muted'),'font-size':10}).textContent=fmt(xv/1000,0)+'k';}
  const hot=el(svg,'rect',{x:m.l,y:m.t,width:W-m.l-m.r,height:H-m.t-m.b,fill:'transparent'});
  hot.addEventListener('mousemove',ev=>{
    const r=svg.getBoundingClientRect();
    const fx=x0+((ev.clientX-r.left)/r.width*W-m.l)/(W-m.l-m.r)*(x1-x0);
    let bi=0,bd=1e18;xs.forEach((xv,i)=>{const d=Math.abs(xv-fx);if(d<bd){bd=d;bi=i;}});
    showTip(ev,`nível <b>${fmt(xs[bi])}</b><br>gamma ${fmt(ys[bi])} R$ mi/1%`);});
  hot.addEventListener('mouseleave',hideTip);
})();

// ---- barras de GEX por strike
(function(){
  const svg=document.getElementById('bars'),W=560,H=260,m={l:46,r:10,t:10,b:26};
  const bs=D.buckets.filter(b=>Math.abs(b.fut/D.spot_fut-1)<=0.05);
  const vmax=Math.max(...bs.map(b=>Math.abs(b.net)))*1.1||1;
  const n=bs.length,bw=(W-m.l-m.r)/n;
  const Y=v=>m.t+(1-(v+vmax)/(2*vmax))*(H-m.t-m.b);
  el(svg,'line',{x1:m.l,x2:W-m.r,y1:Y(0),y2:Y(0),stroke:css('--axis')});
  bs.forEach((b,i)=>{
    const x=m.l+i*bw+1,w=Math.max(bw-2,2);
    const y=b.net>=0?Y(b.net):Y(0),h=Math.abs(Y(b.net)-Y(0))||1;
    const r=el(svg,'rect',{x,y,width:w,height:h,rx:3,
      fill:b.net>=0?css('--pos'):css('--neg'),opacity:b.wall?1:.4});
    r.addEventListener('mousemove',ev=>showTip(ev,
      `<b>${fmt(b.fut)}</b>${b.wall?' · WALL'+'★'.repeat(b.wall):''}<br>net ${fmt(b.net)} · bruto ${fmt(b.absg)} R$ mi`));
    r.addEventListener('mouseleave',hideTip);
    if(b.wall)el(svg,'text',{x:x+w/2,y:m.t+10,'text-anchor':'middle','font-size':9,
      fill:css('--gold')}).textContent='★'.repeat(b.wall);
    if(i%2===0)el(svg,'text',{x:x+w/2,y:H-8,'text-anchor':'middle',fill:css('--muted'),
      'font-size':9}).textContent=fmt(b.fut/1000,0)+'k';});
  const sx=m.l+((D.spot_fut-bs[0].fut)/(bs[n-1].fut-bs[0].fut))*(W-m.l-m.r-bw)+bw/2;
  el(svg,'line',{x1:sx,x2:sx,y1:m.t,y2:H-m.b,stroke:css('--muted'),'stroke-width':1.5,'stroke-dasharray':'2 3'});
})();

// ---- densidade implícita
(function(){
  const svg=document.getElementById('dens'),W=560,H=240,m={l:14,r:10,t:12,b:26};
  const xs=D.dens.x,ys=D.dens.y;
  if(!xs.length){el(svg,'text',{x:W/2,y:H/2,'text-anchor':'middle',fill:css('--muted')}).textContent='indisponível';return;}
  const x0=Math.min(...xs),x1=Math.max(...xs),ymax=Math.max(...ys)*1.1;
  const X=v=>m.l+(v-x0)/(x1-x0)*(W-m.l-m.r);
  const Y=v=>m.t+(1-v/ymax)*(H-m.t-m.b);
  const band=(a,b,color,op)=>{if(a&&b)el(svg,'rect',{x:X(Math.max(a,x0)),y:m.t,
    width:Math.max(X(Math.min(b,x1))-X(Math.max(a,x0)),0),height:H-m.t-m.b,fill:color,opacity:op});};
  band(D.prob.pct.p10,D.prob.pct.p90,css('--mid'),.6);
  band(D.prob.band_down,D.prob.band_up,css('--pos'),.14);
  let d='';xs.forEach((xv,i)=>{d+=(i?' L':'M')+X(xv)+','+Y(ys[i]);});
  el(svg,'path',{d,fill:'none',stroke:css('--accent'),'stroke-width':2});
  const mark=(v,label,color)=>{if(!v||v<x0||v>x1)return;
    el(svg,'line',{x1:X(v),x2:X(v),y1:m.t,y2:H-m.b,stroke:color,'stroke-width':1,'stroke-dasharray':'3 3'});
    el(svg,'text',{x:X(v),y:m.t+9,'text-anchor':'middle','font-size':9,fill:css('--ink2')}).textContent=label;};
  mark(D.spot_fut,'ref',css('--muted'));mark(D.prob.pct.p50,'P50',css('--accent'));
  mark(D.prob.pct.p10,'P10',css('--muted'));mark(D.prob.pct.p90,'P90',css('--muted'));
  for(let i=0;i<=4;i++){const xv=x0+(x1-x0)*i/4;
    el(svg,'text',{x:X(xv),y:H-8,'text-anchor':'middle',fill:css('--muted'),'font-size':10}).textContent=fmt(xv/1000,0)+'k';}
})();

// ---- fluxo estrangeiro por sessão
(function(){
  if(!D.flow||!D.flow.series||!D.flow.series.length)return;
  document.getElementById('cardflow').style.display='';
  const svg=document.getElementById('flow'),W=560,H=240,m={l:52,r:10,t:12,b:30};
  const s=D.flow.series;
  const vmax=Math.max(...s.map(r=>Math.abs(r.estrangeiro)))*1.15||1;
  const n=s.length,bw=(W-m.l-m.r)/n;
  const Y=v=>m.t+(1-(v+vmax)/(2*vmax))*(H-m.t-m.b);
  for(let g=-2;g<=2;g++){const yv=vmax/2*g;
    el(svg,'line',{x1:m.l,x2:W-m.r,y1:Y(yv),y2:Y(yv),stroke:g===0?css('--axis'):css('--grid'),'stroke-width':1});
    el(svg,'text',{x:m.l-6,y:Y(yv)+4,'text-anchor':'end',fill:css('--muted'),'font-size':10}).textContent=fmt(yv,0);}
  s.forEach((r,i)=>{
    const x=m.l+i*bw+2,w=Math.max(bw-4,2);
    const y=r.estrangeiro>=0?Y(r.estrangeiro):Y(0),h=Math.abs(Y(r.estrangeiro)-Y(0))||1;
    const rect=el(svg,'rect',{x,y,width:w,height:h,rx:3,
      fill:r.estrangeiro>=0?css('--pos'):css('--neg')});
    rect.addEventListener('mousemove',ev=>showTip(ev,
      `<b>${r.session.split('-').reverse().join('/')}</b><br>estrangeiro ${fmt(r.estrangeiro,1)} mi<br>institucional ${fmt(r.institucional,1)} mi · PF ${fmt(r.pessoa_fisica,1)} mi`));
    rect.addEventListener('mouseleave',hideTip);
    if(i%3===0)el(svg,'text',{x:x+w/2,y:H-8,'text-anchor':'middle',fill:css('--muted'),
      'font-size':9}).textContent=r.session.slice(8)+'/'+r.session.slice(5,7);});
})();

// ---- volume profile (horizontal: preço no eixo Y)
(function(){
  if(!D.vp||!D.vp.hist1d||!D.vp.hist1d.length)return;
  document.getElementById('cardvp').style.display='';
  const svg=document.getElementById('vp'),W=560,H=300,m={l:60,r:10,t:12,b:24};
  const h1=D.vp.hist1d,hc=D.vp.histcomp||[];
  const all=h1.concat(hc);
  const p0=Math.min(...all.map(r=>r[0])),p1=Math.max(...all.map(r=>r[0]));
  const v1max=Math.max(...h1.map(r=>r[1]))||1;
  const vcmax=hc.length?Math.max(...hc.map(r=>r[1])):1;
  const Y=p=>m.t+(1-(p-p0)/(p1-p0||1))*(H-m.t-m.b);
  const bh=Math.max((H-m.t-m.b)/((p1-p0)/100+1)-1,2);
  hc.forEach(([p,v])=>{el(svg,'rect',{x:m.l,y:Y(p)-bh/2,width:(W-m.l-m.r)*v/vcmax,
    height:bh,fill:css('--mid'),opacity:.95});});
  h1.forEach(([p,v])=>{const r=el(svg,'rect',{x:m.l,y:Y(p)-bh/2,width:(W-m.l-m.r)*v/v1max,
    height:bh,rx:2,fill:css('--pos'),opacity:.7});
    r.addEventListener('mousemove',ev=>showTip(ev,`<b>${fmt(p)}</b><br>vol. sessão ${fmt(v)}`));
    r.addEventListener('mouseleave',hideTip);});
  const mark=(v,label,color,dash)=>{if(v==null||v<p0||v>p1)return;
    el(svg,'line',{x1:m.l,x2:W-m.r,y1:Y(v),y2:Y(v),stroke:color,'stroke-width':1.4,'stroke-dasharray':dash||''});
    el(svg,'text',{x:W-m.r,y:Y(v)-3,'text-anchor':'end','font-size':9,fill:color}).textContent=label+' '+fmt(v);};
  const d1=D.vp.d1||{};
  mark(d1.poc,'POC',css('--magenta'));mark(d1.vah,'VAH',css('--muted'),'4 3');mark(d1.val,'VAL',css('--muted'),'4 3');
  if(D.vp.comp){mark(D.vp.comp.poc,'POC sem.',css('--magenta'),'2 3');}
  mark(D.spot_fut,'ref',css('--ink2'),'1 3');
  for(let i=0;i<=4;i++){const pv=p0+(p1-p0)*i/4;
    el(svg,'text',{x:m.l-6,y:Y(pv)+4,'text-anchor':'end',fill:css('--muted'),'font-size':10}).textContent=fmt(pv/1000,1)+'k';}
})();
</script></body></html>
"""
