"""Teste offline: executa app.py e TODAS as páginas com dados sintéticos,
substituindo Streamlit/Plotly/SQLAlchemy por stubs que validam as colunas usadas
nos gráficos. Uso: python tests/teste_offline.py"""
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

RAIZ = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(RAIZ), str(RAIZ / "tests")]

import pandas as pd  # noqa: E402

# ---------------- stubs ----------------
chamadas = {"graficos": 0, "metricas": 0, "tabelas": 0, "erros": []}


class Ctx(MagicMock):
    def __enter__(self): return self
    def __exit__(self, *a): return False


class Col:
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def __getattr__(self, nome): return getattr(st, nome)


def _cols(spec, *a, **k):
    n = spec if isinstance(spec, int) else len(spec)
    return [Col() for _ in range(n)]


st = types.ModuleType("streamlit")
st.set_page_config = lambda *a, **k: None
st.markdown = st.caption = st.code = st.info = st.warning = st.error = st.success = lambda *a, **k: None
st.divider = lambda *a, **k: None
st.columns = _cols
st.sidebar = Ctx()
st.sidebar.__enter__ = lambda s=None: st
st.expander = st.container = st.spinner = lambda *a, **k: Col()
st.tabs = lambda nomes: [Col() for _ in nomes]
st.selectbox = lambda label, opts, index=0, **k: list(opts)[index]
st.multiselect = lambda label, opts, default=None, **k: default or []
st.radio = lambda label, opts, **k: list(opts)[0]
st.toggle = lambda label, value=False, **k: value
st.select_slider = lambda label, opts, value=None, **k: value
st.number_input = lambda label, mn, mx, val, *a, **k: val
st.date_input = lambda label, value=None, **k: value
st.button = lambda *a, **k: False
st.rerun = lambda: None


def _metric(label, value, delta=None, **k):
    chamadas["metricas"] += 1
    assert isinstance(value, str), (label, value)


st.metric = _metric


def _df(df, **k):
    chamadas["tabelas"] += 1
    assert isinstance(df, pd.DataFrame)


st.dataframe = _df


def _plot(fig, **k):
    chamadas["graficos"] += 1


st.plotly_chart = _plot
st.fragment = lambda run_every=None: (lambda f: f)
st.cache_data = MagicMock(); st.cache_data.side_effect = lambda **k: (lambda f: f)
st.cache_data.clear = lambda: None
st.cache_resource = st.cache_data
st.errors = MagicMock()
st.secrets = {}
paginas_registradas = []
st.Page = lambda fn, **k: paginas_registradas.append((k["title"], fn))
st.navigation = lambda p: MagicMock()
sys.modules["streamlit"] = st

# SQLAlchemy stub (o db é substituído abaixo)
sa = types.ModuleType("sqlalchemy"); sa.create_engine = sa.text = sa.bindparam = MagicMock()
sae = types.ModuleType("sqlalchemy.exc"); sae.SQLAlchemyError = Exception
sys.modules["sqlalchemy"], sys.modules["sqlalchemy.exc"] = sa, sae


# Plotly stub que confere se as colunas existem
class Fig(MagicMock):
    pass


def _px(nome):
    def f(df=None, *a, **k):
        for chave in ("x", "y", "color", "names", "values"):
            v = k.get(chave)
            vs = v if isinstance(v, list) else [v]
            for c in vs:
                if isinstance(c, str) and df is not None:
                    assert c in df.columns, f"px.{nome}: coluna '{c}' não existe. Colunas: {list(df.columns)}"
        return Fig()
    return f


px = types.ModuleType("plotly.express")
for n in ["bar", "line", "box", "area", "pie", "scatter"]:
    setattr(px, n, _px(n))
go = types.ModuleType("plotly.graph_objects")
go.Figure = lambda *a, **k: Fig(); go.Indicator = MagicMock()
go.layout = types.SimpleNamespace(Template=MagicMock()); go.Layout = MagicMock()
pio = types.ModuleType("plotly.io"); pio.templates = MagicMock()
plotly = types.ModuleType("plotly"); plotly.express, plotly.graph_objects, plotly.io = px, go, pio
sys.modules.update({"plotly": plotly, "plotly.express": px, "plotly.graph_objects": go, "plotly.io": pio})

# ---------------- dados sintéticos no lugar do banco ----------------
import dados_sinteticos  # noqa: E402

D = dados_sinteticos.gerar()
from core import db  # noqa: E402


def _filtra(df, col, ini, fim):
    return df[(df[col] >= ini) & (df[col] < fim)]


db.maquinas = lambda: D["maquinas"]
db.opcoes_filtros = lambda: {"produtos": sorted(D["producao"]["product_name"].unique()),
                             "turnos": ["MANHA", "NOITE", "TARDE"],
                             "canais": sorted(D["vendas"]["sales_channel"].unique()),
                             "regioes": sorted(D["vendas"]["customer_region"].unique())}
db.producao = lambda i, f: _filtra(D["producao"], "ended_at", i, f)
db.vendas = lambda i, f: _filtra(D["vendas"], "created_at", i, f)
db.telemetria_resumo = lambda i, f: D["resumo"]
db.telemetria_serie = lambda i, f, b: D["serie"]
db.telemetria_ultima = lambda: D["ultima"]
db.desgaste_atual = lambda: D["parts"]
db.desgaste_historico = lambda i, f, b: D["wear"]
db.pulso = lambda: pd.DataFrame([dict(ultima_telemetria=D["fim"], telemetria_1min=4, ultima_producao=D["fim"],
                                      producao_5min=40, ultima_venda=D["fim"], ultimo_desgaste=D["fim"],
                                      agora_banco=D["fim"])])
db.contagens = lambda: pd.DataFrame({"tabela": db.TABELAS, "registros": [4, 1, 2, 3, 4, 5]})
db.colunas = lambda: pd.DataFrame({"tabela": ["machines"], "coluna": ["machine_id"], "tipo": ["uuid"],
                                   "aceita_nulo": ["NO"]})
db.chaves_estrangeiras = lambda: pd.DataFrame()
db.amostra = lambda t, n=10: D["telemetria"].head(n)
db._database_url = lambda: "postgresql://u:p@aws-0-us-east-2.pooler.supabase.com:5432/postgres"

# Ajusta o "agora" do app para o fim dos dados sintéticos
import datetime as _dt  # noqa: E402


class _FakeDT(_dt.datetime):
    @classmethod
    def now(cls, tz=None):
        return D["fim"].astimezone(tz) if tz else D["fim"].replace(tzinfo=None)


import importlib  # noqa: E402

app_src = (RAIZ / "app.py").read_text(encoding="utf-8")
ns = {"__name__": "app"}
exec(compile(app_src, "app.py", "exec"), ns)
ns["datetime"] = _FakeDT

for titulo, fn in paginas_registradas:
    try:
        fn()
        print(f"OK   {titulo}")
    except Exception as e:
        import traceback
        chamadas["erros"].append(titulo)
        print(f"ERRO {titulo}: {type(e).__name__}: {e}")
        traceback.print_exc()

print("\n", {k: v for k, v in chamadas.items()})

# ---------------- respostas e recomendações ----------------
from core import dados, kpis  # noqa: E402

ctx = ns["montar_contexto"]()
prod, vend, desg = dados.producao(ctx), dados.vendas(ctx), dados.desgaste_atual(ctx)
tele = kpis.resumo_telemetria(dados.telemetria_resumo(ctx))
risco = kpis.indice_risco_maquinas(tele, desg, kpis.producao_por(prod, "machine_code"))
print(f"\nPeríodo: {ctx.ini} → {ctx.fim} | lotes {len(prod)} | pedidos {len(vend)}")
for r in kpis.responder_perguntas(prod, vend, tele, desg, risco):
    print(f"{r['n']:>2}. {r['pergunta']}\n    → {r['resposta']} | {r['evidencia']}")
print()
for r in kpis.gerar_recomendacoes(prod, vend, desg, risco):
    print("*", r["titulo"], "|", r["base"])
print("\nTurnos:\n", kpis.producao_por(prod, "shift_name")[["shift_name", "produzido", "taxa_rejeicao", "aprovadas_por_hora"]])
print("\nFinanceiro:\n", kpis.financeiro_por_produto(prod, vend)[["product_name", "custo_unit_medio", "faturamento", "margem_pct"]])
print("\nProd x vendas:\n", kpis.producao_vs_vendas(prod, vend)[["product_name", "aprovado", "vendido", "giro_venda"]])

# ---------------- cenário: banco sem registros ----------------
print("\n--- Cenário sem registros ---")
vazio = pd.DataFrame()
db.producao = db.vendas = lambda i, f: vazio
db.telemetria_resumo = lambda i, f: vazio
db.telemetria_serie = db.desgaste_historico = lambda i, f, b: vazio
db.telemetria_ultima = db.desgaste_atual = lambda: vazio
for titulo, fn in paginas_registradas:
    try:
        fn(); print(f"OK   {titulo}")
    except Exception as e:
        import traceback; traceback.print_exc()
        chamadas["erros"].append("vazio:" + titulo); print(f"ERRO {titulo}: {e}")
sys.exit(1 if chamadas["erros"] else 0)
