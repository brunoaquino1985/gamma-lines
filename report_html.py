#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Gera o painel HTML diário (autocontido) do GAMMA LINES."""
import json


def _fmt(x, dec=0):
    s = f"{x:,.{dec}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def _br_date(iso):
    """2026-07-13 -> 13/07/2026"""
    p = str(iso).split("-")
    return f"{p[2]}/{p[1]}/{p[0]}" if len(p) == 3 else str(iso)


def build_rationale(spot_fut, walls, mids, flip, maxg, ming, band_up, band_down):
    """Gera cenários operacionais condicionais a partir do mapa de gamma.
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
        out.append(("Contexto",
                    f"Preço de referência ({fmt(spot_fut)}) ACIMA do gamma flip ({fmt(flip)}): "
                    "os dealers estão long gamma e o hedge deles vai contra o movimento — "
                    "compra em queda, venda em alta. Dia com viés de compressão: as walls "
                    "tendem a segurar e o preço tende a rodar entre elas."))
        if acima:
            r1 = acima[0]
            alvo1 = mid_below(r1[2])
            alvo2 = abaixo[-1][2] if abaixo else None
            txt = (f"Possível VENDA em rejeição na wall {fmt(r1[2])} {stars[r1[1]]}")
            if alvo1:
                txt += f", buscando a mid wall {fmt(alvo1)}"
            if alvo2:
                txt += f" e, na extensão, a wall {fmt(alvo2)}"
            txt += (f". Invalidação: aceitação consistente acima de {fmt(r1[2])} "
                    f"(aí a próxima referência vira {fmt(acima[1][2]) if len(acima) > 1 else fmt(maxg)}).")
            out.append(("Cenário de venda", txt))
        if abaixo:
            s1 = abaixo[-1]
            alvo1 = mid_above(s1[2])
            alvo2 = acima[0][2] if acima else None
            txt = (f"Possível COMPRA em defesa da wall {fmt(s1[2])} {stars[s1[1]]}")
            if alvo1:
                txt += f", buscando a mid wall {fmt(alvo1)}"
            if alvo2:
                txt += f" e, na extensão, a wall {fmt(alvo2)}"
            txt += (f". Invalidação: perda consistente de {fmt(s1[2])} "
                    f"(abaixo disso a referência vira {fmt(abaixo[-2][2]) if len(abaixo) > 1 else fmt(flip)}).")
            out.append(("Cenário de compra", txt))
        out.append(("Cenário de quebra de regime",
                    f"Perda do gamma flip ({fmt(flip)}) muda o jogo: os dealers passam a "
                    "short gamma e o hedge deles passa a EMPURRAR o movimento. Abaixo do flip, "
                    f"quedas tendem a acelerar em direção às walls inferiores e ao min gamma ({fmt(ming)}). "
                    "Evitar comprar 'porque caiu' nesse regime."))
    else:
        out.append(("Contexto",
                    f"Preço de referência ({fmt(spot_fut)}) ABAIXO do gamma flip ({fmt(flip)}): "
                    "dealers short gamma — o hedge deles amplifica o movimento (vende queda, "
                    "compra alta). Dia com viés de aceleração: rompimentos tendem a estender "
                    "e reversões exigem confirmação."))
        if abaixo:
            s1 = abaixo[-1]
            prox = abaixo[-2][2] if len(abaixo) > 1 else ming
            out.append(("Cenário de venda (continuação)",
                        f"Perda da wall {fmt(s1[2])} {stars[s1[1]]} abre espaço até {fmt(prox)} "
                        f"e, na extensão, o min gamma ({fmt(ming)}). Em gamma negativo o "
                        "rompimento tende a andar — a invalidação é o retorno rápido para dentro do nível perdido."))
        out.append(("Cenário de reversão",
                    f"Recuperar o flip ({fmt(flip)}) devolve o mercado ao regime de compressão "
                    "e favorece compra em recuo, com alvos nas walls/mid walls acima. "
                    "Enquanto abaixo do flip, compras são contra-tendência."))

    out.append(("Bandas do dia",
                f"O mercado de opções precifica o dia entre {fmt(band_down)} e {fmt(band_up)} (±1σ). "
                "Toque na banda COM confluência de wall é o ponto de maior interesse para reversão; "
                "preço rodando fora da banda sinaliza dia atípico — reduzir expectativa de reversão à média."))
    out.append(("Extremos do mapa",
                f"Max gamma ({fmt(maxg)}) e min gamma ({fmt(ming)}) funcionam como teto e piso "
                "estatísticos do posicionamento atual: aproximações desses níveis historicamente "
                "atraem realização/defesa forte dos books."))
    return out


def build_report(res, meta, session_str, flow=None, vp=None):
    prob = res.get("prob") or {}
    spot_fut = res["ibov_close"] * res["factor"]
    flip_fut = res["flip"][1]
    regime = "GAMMA POSITIVO" if spot_fut >= flip_fut else "GAMMA NEGATIVO"
    regime_desc = ("mercado acima do flip: hedge das tesourarias comprime o preço "
                   "(tendência de reversão à média entre as walls)"
                   if spot_fut >= flip_fut else
                   "mercado abaixo do flip: hedge das tesourarias amplifica o "
                   "movimento (tendência de aceleração)")

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
      <div class="tile"><div class="tl">P(fechar acima do spot)*</div>
        <div class="tv">{(p_up*100):.0f}%</div>
        <div class="ts">até {prob.get('expiry','-')} (opções BOVA11)</div></div>
      <div class="tile"><div class="tl">Movimento esperado do dia (±1σ)</div>
        <div class="tv">±{_fmt(spot_fut*sig)} pts</div>
        <div class="ts">IV ATM {prob.get('iv_atm',0)*100:.1f}% a.a. → {sig*100:.2f}% no dia</div></div>
      <div class="tile"><div class="tl">Regime de gamma</div>
        <div class="tv {'pos' if spot_fut>=flip_fut else 'neg'}">{regime}</div>
        <div class="ts">flip em {_fmt(flip_fut)} · ref. {_fmt(spot_fut)}</div></div>
      <div class="tile"><div class="tl">Wall principal</div>
        <div class="tv">{_fmt([w for w in walls if w['width']==3][0]['fut'] if any(w['width']==3 for w in walls) else 0)}</div>
        <div class="ts">maior concentração de gamma do book</div></div>
    """ if p_up is not None else "<div class='tile'><div class='tl'>Probabilidades indisponíveis</div></div>"

    tiles2 = ""
    if flow:
        fx = flow["estrangeiro_dia_mi"]
        fx5 = flow["estrangeiro_5d_mi"]
        cls_d = "pos" if fx >= 0 else "neg"
        cls_5 = "pos" if fx5 >= 0 else "neg"
        tiles2 += f"""
      <div class="tile"><div class="tl">Fluxo estrangeiro (sessão {_br_date(flow['last_session'])})</div>
        <div class="tv {cls_d}">{'+' if fx >= 0 else '−'}R$ {_fmt(abs(fx))} mi</div>
        <div class="ts">mercado à vista · {flow['lag_note']}</div></div>
      <div class="tile"><div class="tl">Fluxo estrangeiro acumulado 5 sessões</div>
        <div class="tv {cls_5}">{'+' if fx5 >= 0 else '−'}R$ {_fmt(abs(fx5))} mi</div>
        <div class="ts">21 sessões: {'+' if flow['estrangeiro_21d_mi'] >= 0 else '−'}R$ {_fmt(abs(flow['estrangeiro_21d_mi']))} mi</div></div>"""
    if vp and vp.get("d1"):
        d1 = vp["d1"]
        comp = vp.get("comp")
        tiles2 += f"""
      <div class="tile"><div class="tl">POC da sessão anterior ({vp['ticker']})</div>
        <div class="tv">{_fmt(d1['poc'])}</div>
        <div class="ts">área de valor {_fmt(d1['val'])} – {_fmt(d1['vah'])}</div></div>"""
        if comp:
            tiles2 += f"""
      <div class="tile"><div class="tl">POC composto {comp['days']} sessões</div>
        <div class="tv">{_fmt(comp['poc'])}</div>
        <div class="ts">área de valor {_fmt(comp['val'])} – {_fmt(comp['vah'])}</div></div>"""

    rows = []
    for w in walls:
        tag = {3: "WALL ★★★", 2: "WALL ★★", 1: "WALL ★"}[w["width"]]
        rows.append((w["fut"], tag, f"strike {w['strike']:,}".replace(",", ".")))
    for m in data["mids"]:
        rows.append((m, "mid wall", "ponto médio entre walls"))
    rows.append((data["maxg"], "MAX GAMMA", "teto do perfil de gamma (±12%)"))
    rows.append((data["ming"], "MIN GAMMA", "piso do perfil de gamma (±12%)"))
    rows.append((data["flip"], "GAMMA FLIP", "troca de sinal do gamma líquido"))
    if prob.get("band_up_fut"):
        rows.append((prob["band_up_fut"], "banda +1σ", "movimento esperado do dia"))
        rows.append((prob["band_down_fut"], "banda −1σ", "movimento esperado do dia"))
    if vp and vp.get("d1"):
        d1 = vp["d1"]
        rows.append((d1["poc"], "POC (1 sessão)", "preço mais negociado da sessão anterior"))
        rows.append((d1["vah"], "VAH (1 sessão)", "topo da área de valor (70% do volume)"))
        rows.append((d1["val"], "VAL (1 sessão)", "base da área de valor (70% do volume)"))
        if vp.get("comp"):
            c = vp["comp"]
            rows.append((c["poc"], f"POC ({c['days']} sessões)", "preço mais negociado do composto"))
            rows.append((c["vah"], f"VAH ({c['days']} sessões)", "topo da área de valor composta"))
            rows.append((c["val"], f"VAL ({c['days']} sessões)", "base da área de valor composta"))
    rows.sort(key=lambda r: -r[0])
    table_rows = "\n".join(
        f"<tr><td class='num'>{_fmt(v,1)}</td><td>{t}</td><td class='muted'>{d}</td></tr>"
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
        txt = (f"POC da sessão anterior em {_fmt(d1['poc'])}, com área de valor entre "
               f"{_fmt(d1['val'])} e {_fmt(d1['vah'])}. Abertura DENTRO da área de valor favorece "
               "rotação (operar as extremidades VAL/VAH); abertura FORA favorece teste do POC "
               "ou continuação (dia de tendência).")
        if conf:
            txt += (" Confluência relevante: wall de gamma a menos de 200 pts de "
                    + ", ".join(_fmt(w[2]) for w in conf[:2])
                    + " reforça esses níveis.")
        rationale.append(("Volume profile", txt))
    if flow:
        fx, fx5 = flow["estrangeiro_dia_mi"], flow["estrangeiro_5d_mi"]
        lado_d = "COMPRADOR" if fx >= 0 else "VENDEDOR"
        lado_5 = "comprador" if fx5 >= 0 else "vendedor"
        rationale.append(("Fluxo estrangeiro",
                          f"Estrangeiro {lado_d} de R$ {_fmt(abs(fx))} mi na sessão de "
                          f"{_br_date(flow['last_session'])} (dado mais recente, D-2) e {lado_5} de "
                          f"R$ {_fmt(abs(fx5))} mi no acumulado de 5 sessões. Fluxo persistente na "
                          "mesma direção dá suporte a rompimentos nessa direção; fluxo contra o "
                          "movimento do preço sugere movimento menos sustentável."))
    rat_html = "\n".join(
        f"<div class='rat'><div class='rt'>{t}</div><div class='rd'>{d}</div></div>"
        for t, d in rationale)

    banner = (f"Mapa calculado com os dados do pregão de <b>{_br_date(res['ref_date'])}</b> "
              f"(fechamento) — para uso na sessão de <b>{_br_date(session_str)}</b>.")

    tiles2_html = f'<div class="tiles">{tiles2}</div>' if tiles2 else ""
    return HTML_TMPL.replace("__DATA__", json.dumps(data)) \
                    .replace("__TILES2__", tiles2_html) \
                    .replace("__TILES__", tiles) \
                    .replace("__ROWS__", table_rows) \
                    .replace("__RATIONALE__", rat_html) \
                    .replace("__BANNER__", banner) \
                    .replace("__SESSION__", _br_date(session_str))


HTML_TMPL = r"""<!DOCTYPE html>
<html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Gamma Lines — __SESSION__</title>
<style>
:root{
  --surface:#fcfcfb; --page:#f9f9f7; --ink:#0b0b0b; --ink2:#52514e;
  --muted:#898781; --grid:#e1e0d9; --axis:#c3c2b7;
  --pos:#2a78d6; --neg:#e34948; --mid:#f0efec; --accent:#1baf7a;
  --border:rgba(11,11,11,.10);
}
@media (prefers-color-scheme: dark){
  :root{ --surface:#1a1a19; --page:#0d0d0d; --ink:#fff; --ink2:#c3c2b7;
    --muted:#898781; --grid:#2c2c2a; --axis:#383835;
    --pos:#3987e5; --neg:#e66767; --mid:#383835; --accent:#199e70;
    --border:rgba(255,255,255,.10); }
}
*{box-sizing:border-box} body{margin:0;background:var(--page);color:var(--ink);
  font:14px/1.45 system-ui,-apple-system,"Segoe UI",sans-serif;padding:20px}
h1{font-size:19px;margin:0} h2{font-size:14px;margin:0 0 8px;color:var(--ink2)}
.sub{color:var(--muted);font-size:12px;margin:4px 0 16px}
.grid{display:grid;gap:14px;grid-template-columns:repeat(auto-fit,minmax(320px,1fr))}
.card{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:14px}
.tiles{display:grid;gap:14px;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));margin-bottom:14px}
.tile{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:12px 14px}
.tl{font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:.04em}
.tv{font-size:26px;font-weight:650;margin:2px 0}
.tv.pos{color:var(--pos)} .tv.neg{color:var(--neg)}
.ts{font-size:11px;color:var(--ink2)}
svg{display:block;width:100%;height:auto}
table{width:100%;border-collapse:collapse;font-size:13px}
td,th{padding:5px 8px;border-bottom:1px solid var(--grid);text-align:left}
td.num{font-variant-numeric:tabular-nums;font-weight:600}
.muted{color:var(--muted)} .foot{color:var(--muted);font-size:11px;margin-top:16px}
.tip{position:fixed;pointer-events:none;background:var(--ink);color:var(--page);
  padding:4px 8px;border-radius:6px;font-size:12px;display:none;z-index:9}
.legend{display:flex;gap:14px;font-size:11px;color:var(--ink2);margin-top:6px;flex-wrap:wrap}
.legend span::before{content:"";display:inline-block;width:10px;height:10px;border-radius:3px;
  margin-right:5px;vertical-align:-1px;background:var(--c)}
.banner{background:var(--surface);border:1px solid var(--border);border-left:4px solid var(--accent);
  border-radius:10px;padding:10px 14px;margin:0 0 14px;font-size:13px;color:var(--ink2)}
.banner b{color:var(--ink)}
.rat{padding:8px 0;border-bottom:1px solid var(--grid)} .rat:last-child{border-bottom:0}
.rt{font-weight:650;font-size:13px;margin-bottom:2px}
.rd{font-size:13px;color:var(--ink2)}
</style></head><body>
<h1>GAMMA LINES — sessão __SESSION__</h1>
<div class="sub" id="sub"></div>
<div class="banner">__BANNER__</div>
<div class="tiles">__TILES__</div>
__TILES2__
<div class="card" style="margin-bottom:14px"><h2>Racional operacional do dia (cenários condicionais)</h2>
__RATIONALE__</div>
<div class="grid">
  <div class="card"><h2>Gamma líquido dos dealers × nível do futuro</h2>
    <svg id="curve" viewBox="0 0 560 260"></svg>
    <div class="legend"><span style="--c:var(--pos)">gamma positivo</span>
      <span style="--c:var(--neg)">gamma negativo</span>
      <span style="--c:#eda100">flip</span><span style="--c:var(--muted)">preço ref.</span></div></div>
  <div class="card"><h2>GEX líquido por strike (R$ mi)</h2>
    <svg id="bars" viewBox="0 0 560 260"></svg>
    <div class="legend"><span style="--c:var(--pos)">dealers long gamma</span>
      <span style="--c:var(--neg)">dealers short gamma</span><span style="--c:var(--muted)">★ = wall</span></div></div>
  <div class="card"><h2>Distribuição implícita até o vencimento curto</h2>
    <svg id="dens" viewBox="0 0 560 240"></svg>
    <div class="legend"><span style="--c:var(--accent)">densidade</span>
      <span style="--c:var(--muted)">P10–P90</span><span style="--c:var(--pos)">±1σ dia</span></div></div>
  <div class="card"><h2>Níveis do dia (pontos do futuro)</h2>
    <div style="max-height:300px;overflow:auto"><table>
      <tr><th>nível</th><th>tipo</th><th class="muted">descrição</th></tr>
      __ROWS__</table></div></div>
  <div class="card" id="cardflow" style="display:none"><h2>Fluxo estrangeiro por sessão (R$ mi)</h2>
    <svg id="flow" viewBox="0 0 560 240"></svg>
    <div class="legend"><span style="--c:var(--pos)">comprador</span>
      <span style="--c:var(--neg)">vendedor</span>
      <span style="--c:var(--muted)">mercado à vista · defasagem D-2</span></div></div>
  <div class="card" id="cardvp" style="display:none"><h2>Volume profile do WIN (sessão anterior × composto)</h2>
    <svg id="vp" viewBox="0 0 560 300"></svg>
    <div class="legend"><span style="--c:var(--pos)">volume sessão anterior</span>
      <span style="--c:var(--mid)">volume composto</span>
      <span style="--c:#e87ba4">POC</span><span style="--c:var(--muted)">VAH/VAL</span></div></div>
</div>
<div class="foot" id="foot"></div>
<div class="tip" id="tip"></div>
<script>
const D = __DATA__;
const css = v => getComputedStyle(document.documentElement).getPropertyValue(v).trim();
const fmt = (x,d=0)=>x.toLocaleString('pt-BR',{minimumFractionDigits:d,maximumFractionDigits:d});
document.getElementById('sub').textContent =
  `gerado com dados de ${D.ref} · ${D.fut} ajuste ${fmt(D.fut_settle)} · IBOV ${fmt(D.ibov,2)} (${D.ibov_source}) · fator ${D.fator.toFixed(5)} · séries: ${D.n_series.bova} BOVA11 + ${D.n_series.ibov} IBOV`;
document.getElementById('foot').textContent =
  '*Probabilidade risk-neutral extraída da curva de opções (Breeden-Litzenberger); leitura de cenário, não recomendação de investimento. Gerado automaticamente a partir de dados públicos da B3.';
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
  if(D.flip>=x0&&D.flip<=x1){el(svg,'line',{x1:flipX,x2:flipX,y1:m.t,y2:H-m.b,stroke:'#eda100','stroke-width':1.5,'stroke-dasharray':'4 3'});}
  if(D.spot_fut>=x0&&D.spot_fut<=x1){el(svg,'line',{x1:spotX,x2:spotX,y1:m.t,y2:H-m.b,stroke:css('--muted'),'stroke-width':1.5});}
  let dPos='',dNeg='';
  xs.forEach((xv,i)=>{const p=`${X(xv)},${Y(ys[i])}`;dPos+=(i?' L':'M')+p;});
  el(svg,'path',{d:dPos,fill:'none',stroke:css('--pos'),'stroke-width':2});
  // pontos negativos realçados
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
      fill:b.net>=0?css('--pos'):css('--neg'),opacity:b.wall?1:.45});
    r.addEventListener('mousemove',ev=>showTip(ev,
      `<b>${fmt(b.fut)}</b>${b.wall?' · WALL'+'★'.repeat(b.wall):''}<br>net ${fmt(b.net)} · bruto ${fmt(b.absg)} R$ mi`));
    r.addEventListener('mouseleave',hideTip);
    if(b.wall)el(svg,'text',{x:x+w/2,y:m.t+10,'text-anchor':'middle','font-size':9,
      fill:css('--ink2')}).textContent='★'.repeat(b.wall);
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
  band(D.prob.band_down,D.prob.band_up,css('--pos'),.15);
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
  // composto (fundo, escala própria)
  hc.forEach(([p,v])=>{el(svg,'rect',{x:m.l,y:Y(p)-bh/2,width:(W-m.l-m.r)*v/vcmax,
    height:bh,fill:css('--mid'),opacity:.9});});
  // sessão anterior (frente)
  h1.forEach(([p,v])=>{const r=el(svg,'rect',{x:m.l,y:Y(p)-bh/2,width:(W-m.l-m.r)*v/v1max,
    height:bh,rx:2,fill:css('--pos'),opacity:.75});
    r.addEventListener('mousemove',ev=>showTip(ev,`<b>${fmt(p)}</b><br>vol. sessão ${fmt(v)}`));
    r.addEventListener('mouseleave',hideTip);});
  const mark=(v,label,color,dash)=>{if(v==null||v<p0||v>p1)return;
    el(svg,'line',{x1:m.l,x2:W-m.r,y1:Y(v),y2:Y(v),stroke:color,'stroke-width':1.4,'stroke-dasharray':dash||''});
    el(svg,'text',{x:W-m.r,y:Y(v)-3,'text-anchor':'end','font-size':9,fill:color}).textContent=label+' '+fmt(v);};
  const d1=D.vp.d1||{};
  mark(d1.poc,'POC','#e87ba4');mark(d1.vah,'VAH',css('--muted'),'4 3');mark(d1.val,'VAL',css('--muted'),'4 3');
  if(D.vp.comp){mark(D.vp.comp.poc,'POC comp.','#d55181','2 3');}
  mark(D.spot_fut,'ref',css('--ink2'),'1 3');
  for(let i=0;i<=4;i++){const pv=p0+(p1-p0)*i/4;
    el(svg,'text',{x:m.l-6,y:Y(pv)+4,'text-anchor':'end',fill:css('--muted'),'font-size':10}).textContent=fmt(pv/1000,1)+'k';}
})();
</script></body></html>
"""
