"""Extrai do Supabase os números usados no relatório e no roteiro.

Uso:
    pip install -r requirements.txt
    python extrair_numeros.py              # últimos 7 dias
    python extrair_numeros.py --dias 0     # todo o histórico

Lê DATABASE_URL de .streamlit/secrets.toml ou da variável de ambiente.
Copie TODA a saída e cole na conversa para preencher o relatório.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))

from core import kpis  # noqa: E402
from core import transform as T  # noqa: E402
from core.formatos import fbrl, fint, fnum, fpct  # noqa: E402


def database_url() -> str:
    url = os.getenv("DATABASE_URL")
    seg = RAIZ / ".streamlit" / "secrets.toml"
    if not url and seg.exists():
        m = re.search(r'DATABASE_URL\s*=\s*"([^"]+)"', seg.read_text(encoding="utf-8"))
        url = m.group(1) if m else None
    if not url:
        sys.exit("Defina DATABASE_URL em .streamlit/secrets.toml ou na variável de ambiente.")
    return url


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dias", type=float, default=7, help="0 = todo o histórico")
    a = ap.parse_args()

    from sqlalchemy import create_engine, text
    eng = create_engine(database_url(), connect_args={"connect_timeout": 15, "sslmode": "require"})
    fim = datetime.now(timezone.utc)
    ini = fim - timedelta(days=a.dias) if a.dias > 0 else datetime(2000, 1, 1, tzinfo=timezone.utc)
    p = {"ini": ini, "fim": fim}

    def q(sql, params=None):
        with eng.connect() as c:
            return pd.read_sql(text(sql), c, params=params or {})

    print(f"=== PERÍODO: {ini:%d/%m/%Y %H:%M} → {fim:%d/%m/%Y %H:%M} UTC ===\n")
    print(q("""SELECT 'machines' t, COUNT(*) n FROM machines UNION ALL
               SELECT 'production_events', COUNT(*) FROM production_events UNION ALL
               SELECT 'sales_orders', COUNT(*) FROM sales_orders UNION ALL
               SELECT 'machine_telemetry', COUNT(*) FROM machine_telemetry UNION ALL
               SELECT 'wear_events', COUNT(*) FROM wear_events UNION ALL
               SELECT 'parts_wear', COUNT(*) FROM parts_wear""").to_string(index=False), "\n")

    maq = T.tratar_maquinas(q("SELECT * FROM machines"))
    prod_all = T.tratar_producao(q("SELECT * FROM production_events WHERE ended_at >= :ini AND ended_at < :fim", p), maq)
    vend = T.tratar_vendas(q("SELECT * FROM sales_orders WHERE created_at >= :ini AND created_at < :fim", p), prod_all)
    tele = T.tratar_telemetria(q("""
        SELECT m.machine_code, COUNT(*) n_leituras, AVG(temperature_c) temp_media, MAX(temperature_c) temp_max,
               AVG(vibration_mm_s) vib_media, MAX(vibration_mm_s) vib_max, AVG(energy_kw) energia_media_kw,
               AVG(pressure_bar) pressao_media, AVG(rpm) rpm_medio,
               SUM(CASE WHEN t.machine_status='ATENCAO' THEN 1 ELSE 0 END) n_atencao,
               SUM(CASE WHEN t.machine_status='CRITICO' THEN 1 ELSE 0 END) n_critico
        FROM machine_telemetry t JOIN machines m USING (machine_id)
        WHERE recorded_at >= :ini AND recorded_at < :fim GROUP BY 1""", p), maq)
    ultima = T.tratar_telemetria(q("""SELECT DISTINCT ON (machine_id) m.machine_code, t.*
        FROM machine_telemetry t JOIN machines m USING (machine_id)
        ORDER BY machine_id, recorded_at DESC"""), maq)
    desg = T.tratar_desgaste_atual(q("SELECT * FROM parts_wear"), maq)

    resumo = kpis.resumo_telemetria(tele)
    pm = kpis.producao_por(prod_all, "machine_code")
    risco = kpis.indice_risco_maquinas(resumo, desg, pm)
    k = kpis.kpis_executivos(prod_all, vend, maq, ultima, desg)

    print("=== VISÃO EXECUTIVA ===")
    for nome, v in [("Produzido", fint(k["produzido"])), ("Rejeitado", fint(k["rejeitado"])),
                    ("Taxa de rejeição", fpct(k["taxa_rejeicao"], 2)), ("Pedidos", fint(k["pedidos"])),
                    ("Faturamento", fbrl(k["faturamento"])), ("Ticket médio", fbrl(k["ticket_medio"])),
                    ("Máquinas", k["maquinas"]), ("Máquinas atenção/crítica (agora)", k["maquinas_alerta"]),
                    ("Componentes ≥75%", k["componentes_alerta"]), ("Componentes ≥90%", k["componentes_criticos"])]:
        print(f"{nome}: {v}")

    def tab(titulo, df, cols):
        print(f"\n=== {titulo} ===")
        print(df[cols].to_string(index=False) if not df.empty else "(sem dados)")

    tab("PRODUTIVIDADE POR MÁQUINA", kpis.produtividade_maquinas(prod_all),
        ["machine_code", "produzido", "taxa_rejeicao", "aprovadas_por_hora", "uso_capacidade", "custo_rejeitados"])
    tab("TURNOS", kpis.producao_por(prod_all, "shift_name"),
        ["shift_name", "produzido", "taxa_rejeicao", "aprovadas_por_hora", "custo_rejeitados"])
    tab("VENDAS POR REGIÃO", kpis.vendas_por(vend, "customer_region"),
        ["customer_region", "faturamento", "qtd_vendida", "participacao"])
    tab("VENDAS POR CANAL", kpis.vendas_por(vend, "sales_channel"),
        ["sales_channel", "faturamento", "ticket_medio", "participacao"])
    tab("PRODUÇÃO × VENDAS", kpis.producao_vs_vendas(prod_all, vend),
        ["product_name", "aprovado", "vendido", "giro_venda"])
    tab("FINANCEIRO POR PRODUTO", kpis.financeiro_por_produto(prod_all, vend),
        ["product_name", "custo_unit_medio", "faturamento", "margem_bruta_estimada", "margem_pct", "custo_rejeitados"])
    tab("TELEMETRIA", resumo, ["machine_code", "temp_media", "vib_media", "pct_alerta", "pct_critico"])
    tab("DESGASTE ATUAL", desg, ["componente", "wear_pct", "situacao", "estimated_remaining_hours"])
    tab("ÍNDICE DE RISCO", risco, ["machine_code", "indice_risco", "desgaste_max", "pct_alerta"])

    print("\n=== 12 RESPOSTAS ===")
    for r in kpis.responder_perguntas(prod_all, vend, resumo, desg, risco):
        print(f"{r['n']:>2}. {r['pergunta']}\n    → {r['resposta']} | {r['evidencia']}")
    print("\n=== RECOMENDAÇÕES ===")
    for r in kpis.gerar_recomendacoes(prod_all, vend, desg, risco):
        print(f"* {r['titulo']} | {r['base']}")


if __name__ == "__main__":
    pd.set_option("display.width", 200)
    pd.set_option("display.float_format", lambda v: f"{v:,.3f}")
    main()
