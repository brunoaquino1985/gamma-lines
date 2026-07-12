# GAMMA LINES — gerador diário automático (Profit Pro / NTSL)

Gera todo dia útil, antes da abertura, o indicador **Gamma Lines** para
WINFUT/INDFUT a partir dos arquivos públicos da B3 (books de opções de
**BOVA11** e **IBOV** combinados).

## Como funciona

Todo dia útil às 05:45 (BRT), o GitHub Actions:

1. Baixa da B3 os dados do pregão anterior (D-1):
   - `COTAHIST_D*.ZIP` — strikes, vencimentos e prêmios das opções
   - `PR*.zip` (BVBG.086) — open interest de cada série + ajuste do INDFUT
   - IBOV de fechamento e CDI (BCB)
2. Roda o modelo de gamma exposure (`gamma_pipeline.py`):
   - forward e desconto por vencimento via paridade put-call
   - IV por série (Black-76) + smile quadrático para séries sem negócio
   - GEX por strike = Γ × OI × mult × S² × 1% (call +, put −)
   - books BOVA11 e IBOV mapeados para o eixo do índice e somados
   - **walls** = 8 strikes da grade de 1000 pts ao redor do spot,
     espessura pela concentração de gamma (3/2/2/1...)
   - **gamma flip** = zero da curva G(S) mais próximo do spot
   - **max/min gamma** = extremos da curva G(S) em ±12%
   - conversão para pontos do futuro: nível × (ajuste INDFUT ÷ IBOV)
3. Gera o código NTSL e salva em `output/`:
   - `output/latest.txt` — sempre o mais recente
   - `output/GAMMA_LINES_IND_dd_mm.txt` — cópia datada
   - `output/levels.json` — níveis para conferência
4. Às 07:30 roda de novo caso a B3 tenha atrasado os arquivos.

## Instalação (uma vez só)

1. Crie um repositório no GitHub (pode ser privado), ex.: `gamma-lines`.
2. Envie todos os arquivos desta pasta para o repositório
   (mantenha a estrutura, inclusive `.github/workflows/gamma-lines.yml`).
3. Na aba **Actions** do repositório, habilite os workflows
   ("I understand my workflows, go ahead and enable them").
4. Teste manualmente: **Actions → gamma-lines-daily → Run workflow**.
   Em ~2 minutos deve aparecer um commit com `output/latest.txt`.

Dica: em Settings → Actions → General, deixe
"Workflow permissions" = **Read and write permissions**
(necessário para o robô commitar o resultado).

## Uso no Profit

Abra `output/latest.txt`, copie o conteúdo e cole no editor de
indicadores do Profit (substituindo o código do dia anterior).
As linhas só plotam no dia da sessão e nos ativos WINFUT/INDFUT/WIN{cod}/IND{cod}.

## Arquivos

| arquivo | papel |
|---|---|
| `fetch_data.py` | download dos dados públicos da B3 (roda no Actions) |
| `gamma_pipeline.py` | parser + modelo GEX |
| `ntsl_generator.py` | template do código NTSL |
| `run_daily.py` | orquestra: dados → modelo → indicador |
| `.github/workflows/gamma-lines.yml` | agendamento diário |
