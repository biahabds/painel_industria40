# 📡 Radar Industrial 4.0 — Painel de BI

Painel gerencial interativo do **Desafio Industrial 4.0** (Desenvolvimento de Business Intelligence).
Consulta diretamente o PostgreSQL do Supabase alimentado pelo simulador do professor, trata os dados
com **Python + Pandas** e apresenta indicadores com **Streamlit + Plotly**, atualizando sozinho por
**polling**.

## Arquitetura

```
Simulador do professor (Python) ──INSERT──▶ Supabase PostgreSQL (6 tabelas)
                                                 │  SQL somente leitura (readonly_user, SSL)
                                                 ▼
                         core/db.py      SQLAlchemy + psycopg 3, consultas SQL, cache curto (ttl)
                                                 ▼
                         core/transform.py   Pandas: tipos, limpeza, fuso de Brasília, JOINs, colunas derivadas
                                                 ▼
                         core/kpis.py        Indicadores, 12 respostas, índice de risco, recomendações
                                                 ▼
                         paginas/*.py        9 páginas Streamlit + Plotly (filtros na barra lateral)
                                                 ▲
                         app.py              st.fragment(run_every=N s) → polling automático
```

| Pasta/arquivo | Função |
|---|---|
| `app.py` | Configuração, barra lateral (filtros + atualização), navegação, tratamento de erros |
| `core/db.py` | Conexão, todas as consultas SQL (texto exibido na página *Dados e conexão*) |
| `core/transform.py` | Tratamento com Pandas e relacionamentos entre tabelas |
| `core/kpis.py` | Cálculo dos indicadores e respostas (funções puras, testáveis) |
| `core/formatos.py`, `core/ui.py` | Formatação pt‑BR, identidade visual, componentes |
| `paginas/` | Executivo, Produção, Vendas, Produção×Vendas, Máquinas, Manutenção, Financeiro, Respostas, Dados |
| `tests/` | Teste offline com dados sintéticos no formato do banco |

## Como executar

```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
#   → cole em DATABASE_URL a string somente leitura do PDF do professor
streamlit run app.py
```

### Publicar no Streamlit Community Cloud
1. Suba a pasta para um repositório no GitHub (o `.gitignore` já impede o envio do `secrets.toml`).
2. Em share.streamlit.io → *New app* → escolha o repositório e `app.py`.
3. Em *Advanced settings → Secrets* cole: `DATABASE_URL = "postgresql://..."`.
4. Coloque o link gerado no relatório de entrega.

## Atualização automática — mecanismo: **polling**
Cada página roda dentro de `st.fragment(run_every=N)`. A cada N segundos (5, 10, 15, 30 ou 60,
escolhido na barra lateral) o bloco é reexecutado, o período relativo ("últimas 24 h") avança e as
consultas vão ao banco. As funções de consulta têm cache de 4–15 s, para não sobrecarregar o
Supabase. **Não é** assinatura nativa Supabase Realtime: é consulta periódica (polling).
A faixa no topo mostra a última telemetria gravada no banco e quantas leituras chegaram no último minuto.

## Indicadores e fórmulas
| Indicador | Fórmula / origem |
|---|---|
| Quantidade produzida / rejeitada | `SUM(qty_produced)` / `SUM(qty_rejected)` em `production_events` |
| Taxa de rejeição | rejeitados ÷ produzidos |
| Pedidos | `COUNT(*)` em `sales_orders` (todos os status) |
| Faturamento | `SUM(total_amount)` com `order_status ≠ 'CANCELADO'` |
| Ticket médio | faturamento ÷ pedidos não cancelados |
| Máquinas em atenção/crítica | status da leitura de telemetria mais recente de cada máquina (`DISTINCT ON`) |
| Componentes com desgaste elevado | `parts_wear.wear_pct ≥ warning_threshold_pct (75%)`; crítico ≥ 90% |
| Aprovadas por hora | (produzido − rejeitado) ÷ horas operando, sendo horas operando = (`ended_at − started_at`) − `downtime_minutes` |
| Uso da capacidade | produção por hora operando ÷ `nominal_capacity_per_hour` |
| OEE estimado | disponibilidade × desempenho × qualidade (por lote) |
| Giro de venda | vendido (não cancelado) ÷ aprovado |
| Custo estimado de produção | `qty_produced × unit_cost` |
| Custo dos rejeitados | `qty_rejected × unit_cost` |
| CPV estimado | `qty_sold × unit_cost` do lote ligado por `batch_id` (fallback: custo médio do produto) |
| Margem bruta estimada | receita − CPV estimado (**não é lucro líquido**) |
| Índice de risco (0–100) | 40% desgaste máx. + 30% % leituras em alerta + 15% vibração média/7 + 15% rejeição/10% |

## Tratamento de erros e ausência de dados
- Sem `DATABASE_URL` ou falha de conexão → mensagem clara e botão *Tentar novamente*.
- Falha momentânea durante o polling → nova tentativa automática (2 tentativas por consulta) e aviso; o próximo ciclo tenta de novo.
- Período/filtros sem registros → aviso "Nenhum registro encontrado…" em cada gráfico/tabela.
- Divisões por zero retornam "—" em vez de erro.

## Teste offline
```bash
python tests/teste_offline.py
```
Executa todas as páginas com dados sintéticos gerados pela mesma lógica do simulador e também com
o banco vazio. Serve apenas para validar o código; o painel **sempre** consulta o Supabase.
