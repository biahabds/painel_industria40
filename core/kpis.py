"""Cálculo dos indicadores (KPIs) e das respostas gerenciais.

Funções puras de Pandas: recebem DataFrames já tratados (core.transform) e
devolvem números ou DataFrames prontos para gráficos. Não dependem do Streamlit.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from core.formatos import fbrl, fint, fnum, fpct
from core.transform import ORDEM_TURNOS, safe_div

LIMIAR_SIGNIFICANCIA_GAP = 0.10  # diferença > 10% entre produção aprovada e venda = significativa


# ----------------------------------------------------------------------------
# A. Visão executiva
# ----------------------------------------------------------------------------
def kpis_executivos(prod, vendas, maquinas, status_atual, desgaste) -> dict:
    produzido = float(prod["qty_produced"].sum()) if not prod.empty else 0.0
    rejeitado = float(prod["qty_rejected"].sum()) if not prod.empty else 0.0
    pedidos = int(len(vendas)) if not vendas.empty else 0
    pedidos_validos = int(vendas["valido"].sum()) if not vendas.empty else 0
    faturamento = float(vendas["receita_valida"].sum()) if not vendas.empty else 0.0
    if status_atual is not None and not status_atual.empty:
        em_alerta = int(status_atual["machine_status"].isin(["ATENCAO", "CRITICO"]).sum())
        criticas = int((status_atual["machine_status"] == "CRITICO").sum())
    else:
        em_alerta, criticas = 0, 0
    if desgaste is not None and not desgaste.empty:
        comp_alerta = int((desgaste["situacao"] != "NORMAL").sum())
        comp_criticos = int((desgaste["situacao"] == "CRÍTICO").sum())
    else:
        comp_alerta, comp_criticos = 0, 0
    return {
        "produzido": produzido,
        "rejeitado": rejeitado,
        "aprovado": produzido - rejeitado,
        "taxa_rejeicao": safe_div(rejeitado, produzido),
        "pedidos": pedidos,
        "pedidos_validos": pedidos_validos,
        "faturamento": faturamento,
        "ticket_medio": safe_div(faturamento, pedidos_validos),
        "maquinas": int(len(maquinas)),
        "maquinas_alerta": em_alerta,
        "maquinas_criticas": criticas,
        "componentes_alerta": comp_alerta,
        "componentes_criticos": comp_criticos,
    }


# ----------------------------------------------------------------------------
# B. Produção
# ----------------------------------------------------------------------------
def producao_por(prod: pd.DataFrame, chave: str) -> pd.DataFrame:
    if prod.empty:
        return pd.DataFrame()
    g = prod.groupby(chave, dropna=False).agg(
        lotes=("batch_id", "count"),
        produzido=("qty_produced", "sum"),
        rejeitado=("qty_rejected", "sum"),
        aprovado=("qty_approved", "sum"),
        ciclo_medio_s=("cycle_time_seconds", "mean"),
        parada_total_min=("downtime_minutes", "sum"),
        parada_media_min=("downtime_minutes", "mean"),
        tempo_operando_min=("tempo_operando_min", "sum"),
        energia_kwh=("energy_kwh", "sum"),
        custo_producao=("custo_producao", "sum"),
        custo_rejeitados=("custo_rejeitados", "sum"),
        oee_medio=("oee", "mean"),
    ).reset_index()
    g["taxa_rejeicao"] = safe_div(g["rejeitado"], g["produzido"])
    g["aprovadas_por_hora"] = safe_div(g["aprovado"], g["tempo_operando_min"] / 60)
    g["kwh_por_unidade"] = safe_div(g["energia_kwh"], g["produzido"])
    if chave == "shift_name":
        g["shift_name"] = pd.Categorical(g["shift_name"], ORDEM_TURNOS, ordered=True)
        g = g.sort_values("shift_name")
    elif chave == "hora":
        g = g.sort_values("hora")
    else:
        g = g.sort_values("produzido", ascending=False)
    return g.reset_index(drop=True)


def produtividade_maquinas(prod: pd.DataFrame) -> pd.DataFrame:
    """Comparação de produtividade: volume, unidades aprovadas/hora, uso da capacidade, OEE."""
    if prod.empty:
        return pd.DataFrame()
    g = producao_por(prod, "machine_code")
    cap = prod.groupby("machine_code")["nominal_capacity_per_hour"].first()
    g = g.merge(cap.rename("capacidade_nominal_h"), left_on="machine_code", right_index=True)
    g["uso_capacidade"] = safe_div(g["produzido"] / (g["tempo_operando_min"] / 60),
                                   g["capacidade_nominal_h"])
    return g.sort_values("aprovadas_por_hora", ascending=False).reset_index(drop=True)


def serie_temporal(df: pd.DataFrame, col_tempo: str, valores: dict, freq: str) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    return (df.set_index(col_tempo).groupby(pd.Grouper(freq=freq))
            .agg(**valores).reset_index())


def escolher_frequencia(inicio, fim) -> str:
    horas = (fim - inicio).total_seconds() / 3600
    if horas <= 3:
        return "5min"
    if horas <= 36:
        return "1h"
    if horas <= 24 * 10:
        return "6h"
    return "1D"


# ----------------------------------------------------------------------------
# C. Vendas
# ----------------------------------------------------------------------------
def vendas_por(vendas: pd.DataFrame, chave: str) -> pd.DataFrame:
    if vendas.empty:
        return pd.DataFrame()
    g = vendas.groupby(chave, dropna=False).agg(
        pedidos=("order_number", "count"),
        pedidos_validos=("valido", "sum"),
        qtd_vendida=("qtd_valida", "sum"),
        faturamento=("receita_valida", "sum"),
        cpv_estimado=("cpv_estimado", "sum"),
    ).reset_index()
    g["ticket_medio"] = safe_div(g["faturamento"], g["pedidos_validos"])
    g["participacao"] = safe_div(g["faturamento"], g["faturamento"].sum())
    return g.sort_values("faturamento", ascending=False).reset_index(drop=True)


def pedidos_por_status(vendas: pd.DataFrame) -> pd.DataFrame:
    if vendas.empty:
        return pd.DataFrame()
    g = vendas.groupby("order_status").agg(pedidos=("order_number", "count"),
                                           valor=("total_amount", "sum")).reset_index()
    g["percentual"] = safe_div(g["pedidos"], g["pedidos"].sum())
    return g.sort_values("pedidos", ascending=False)


# ----------------------------------------------------------------------------
# D. Produção x Vendas
# ----------------------------------------------------------------------------
def producao_vs_vendas(prod: pd.DataFrame, vendas: pd.DataFrame) -> pd.DataFrame:
    p = (prod.groupby("product_name")[["qty_produced", "qty_approved"]].sum()
         if not prod.empty else pd.DataFrame(columns=["qty_produced", "qty_approved"]))
    v = (vendas.groupby("product_name")[["qtd_valida"]].sum()
         if not vendas.empty else pd.DataFrame(columns=["qtd_valida"]))
    df = p.join(v, how="outer").fillna(0).reset_index()
    if df.empty:
        return df
    df = df.rename(columns={"qty_produced": "produzido", "qty_approved": "aprovado",
                            "qtd_valida": "vendido"})
    df["saldo_aprovado_menos_vendido"] = df["aprovado"] - df["vendido"]
    df["giro_venda"] = safe_div(df["vendido"], df["aprovado"])  # % do aprovado que foi vendido
    df["participacao_demanda"] = safe_div(df["vendido"], df["vendido"].sum())
    return df.sort_values("saldo_aprovado_menos_vendido", ascending=False).reset_index(drop=True)


def producao_vs_vendas_periodo(prod, vendas, freq: str) -> pd.DataFrame:
    a = serie_temporal(prod, "ended_at", {"aprovado": ("qty_approved", "sum")}, freq) \
        if not prod.empty else pd.DataFrame(columns=["ended_at", "aprovado"])
    b = serie_temporal(vendas, "created_at", {"vendido": ("qtd_valida", "sum")}, freq) \
        if not vendas.empty else pd.DataFrame(columns=["created_at", "vendido"])
    a = a.rename(columns={"ended_at": "periodo"})
    b = b.rename(columns={"created_at": "periodo"})
    df = a.merge(b, on="periodo", how="outer").fillna(0).sort_values("periodo")
    if df.empty:
        return df
    df["diferenca"] = df["aprovado"] - df["vendido"]
    df["giro_venda"] = safe_div(df["vendido"], df["aprovado"])
    return df


# ----------------------------------------------------------------------------
# E/F. Máquinas e desgaste
# ----------------------------------------------------------------------------
def resumo_telemetria(tele_agg: pd.DataFrame) -> pd.DataFrame:
    """Recebe a agregação por máquina feita em SQL e calcula % de leituras em alerta."""
    if tele_agg is None or tele_agg.empty:
        return pd.DataFrame()
    df = tele_agg.copy()
    df["pct_alerta"] = safe_div(df["n_atencao"] + df["n_critico"], df["n_leituras"])
    df["pct_critico"] = safe_div(df["n_critico"], df["n_leituras"])
    return df.sort_values("pct_alerta", ascending=False).reset_index(drop=True)


def indice_risco_maquinas(resumo_tele: pd.DataFrame, desgaste: pd.DataFrame,
                          prod_maq: pd.DataFrame) -> pd.DataFrame:
    """Índice de risco 0–100 combinando sinais (premissa da equipe):
    40% desgaste máximo dos componentes, 30% % de leituras de telemetria em alerta,
    15% vibração média normalizada (7 mm/s = crítico), 15% taxa de rejeição normalizada (10%).
    """
    maqs = set()
    for d in (resumo_tele, desgaste, prod_maq):
        if d is not None and not d.empty:
            maqs |= set(d["machine_code"].dropna())
    if not maqs:
        return pd.DataFrame()
    df = pd.DataFrame({"machine_code": sorted(maqs)})
    if desgaste is not None and not desgaste.empty:
        w = desgaste.groupby("machine_code").agg(desgaste_max=("wear_pct", "max"),
                                                 menor_vida_h=("estimated_remaining_hours", "min"))
        df = df.merge(w, on="machine_code", how="left")
    if resumo_tele is not None and not resumo_tele.empty:
        df = df.merge(resumo_tele[["machine_code", "pct_alerta", "vib_media", "temp_media"]],
                      on="machine_code", how="left")
    if prod_maq is not None and not prod_maq.empty:
        df = df.merge(prod_maq[["machine_code", "taxa_rejeicao"]], on="machine_code", how="left")
    for c in ["desgaste_max", "pct_alerta", "vib_media", "taxa_rejeicao", "menor_vida_h", "temp_media"]:
        if c not in df.columns:
            df[c] = np.nan
    df["indice_risco"] = (
        0.40 * (df["desgaste_max"].fillna(0) / 100).clip(0, 1)
        + 0.30 * df["pct_alerta"].fillna(0).clip(0, 1)
        + 0.15 * (df["vib_media"].fillna(0) / 7).clip(0, 1)
        + 0.15 * (df["taxa_rejeicao"].fillna(0) / 0.10).clip(0, 1)
    ) * 100
    return df.sort_values("indice_risco", ascending=False).reset_index(drop=True)


def taxa_desgaste_por_hora(hist: pd.DataFrame) -> pd.DataFrame:
    """Velocidade de desgaste (p.p./hora) por componente no período — base da previsão."""
    if hist is None or hist.empty:
        return pd.DataFrame()
    out = []
    for comp, g in hist.sort_values("measured_at").groupby("componente"):
        if len(g) < 2:
            continue
        horas = (g["measured_at"].iloc[-1] - g["measured_at"].iloc[0]).total_seconds() / 3600
        if horas <= 0:
            continue
        delta = g["wear_pct"].iloc[-1] - g["wear_pct"].iloc[0]
        out.append({"componente": comp, "pp_por_hora": delta / horas,
                    "desgaste_atual": g["wear_pct"].iloc[-1]})
    df = pd.DataFrame(out)
    if df.empty:
        return df
    taxa = df["pp_por_hora"].where(df["pp_por_hora"] > 0)
    df["horas_ate_90pct"] = ((90 - df["desgaste_atual"]).clip(lower=0) / taxa)
    return df.sort_values("horas_ate_90pct").reset_index(drop=True)


# ----------------------------------------------------------------------------
# G. Financeiro
# ----------------------------------------------------------------------------
def financeiro_por_produto(prod: pd.DataFrame, vendas: pd.DataFrame) -> pd.DataFrame:
    rec = vendas_por(vendas, "product_name") if not vendas.empty else pd.DataFrame(
        columns=["product_name", "faturamento", "cpv_estimado", "qtd_vendida"])
    cus = (prod.groupby("product_name").agg(
        custo_producao=("custo_producao", "sum"),
        custo_rejeitados=("custo_rejeitados", "sum"),
        produzido=("qty_produced", "sum")).reset_index()
           if not prod.empty else pd.DataFrame(columns=["product_name", "custo_producao",
                                                        "custo_rejeitados", "produzido"]))
    if not prod.empty:
        cus["custo_unit_medio"] = safe_div(cus["custo_producao"], cus["produzido"])
    df = cus.merge(rec[["product_name", "faturamento", "cpv_estimado", "qtd_vendida"]],
                   on="product_name", how="outer").fillna(0)
    if df.empty:
        return df
    df["preco_medio"] = safe_div(df["faturamento"], df["qtd_vendida"])
    df["margem_bruta_estimada"] = df["faturamento"] - df["cpv_estimado"]
    df["margem_pct"] = safe_div(df["margem_bruta_estimada"], df["faturamento"])
    df["margem_apos_refugo"] = df["margem_bruta_estimada"] - df["custo_rejeitados"]
    return df.sort_values("faturamento", ascending=False).reset_index(drop=True)


# ----------------------------------------------------------------------------
# Etapa 3 — Perguntas gerenciais
# ----------------------------------------------------------------------------
def _top(df, col, asc=False):
    if df is None or df.empty or col not in df.columns or df[col].dropna().empty:
        return None
    return df.sort_values(col, ascending=asc).dropna(subset=[col]).iloc[0]


def responder_perguntas(prod, vendas, tele_resumo, desgaste, risco, min_unid_hora=200) -> list[dict]:
    """Devolve as 12 respostas com o valor que as sustenta (evidência)."""
    R = []
    pm = produtividade_maquinas(prod)
    r = _top(pm, "aprovadas_por_hora")
    R.append({"n": 1, "pergunta": "Qual máquina apresenta maior produtividade?",
              "resposta": r["machine_code"] if r is not None else "—",
              "evidencia": (f"{fint(r['aprovadas_por_hora'])} unidades aprovadas por hora de operação; "
                            f"{fint(r['produzido'])} unidades no período") if r is not None else "Sem dados"})

    r = _top(pm, "taxa_rejeicao")
    R.append({"n": 2, "pergunta": "Qual máquina possui maior índice de rejeição?",
              "resposta": r["machine_code"] if r is not None else "—",
              "evidencia": (f"Taxa de rejeição de {fpct(r['taxa_rejeicao'], 2)} "
                            f"({fint(r['rejeitado'])} rejeitadas)") if r is not None else "Sem dados"})

    pt = producao_por(prod, "shift_name")
    if not pt.empty:
        pt = pt.assign(score=pt["aprovadas_por_hora"].rank() + (-pt["taxa_rejeicao"]).rank())
    r = _top(pt, "score")
    R.append({"n": 3, "pergunta": "Qual turno apresenta melhor desempenho?",
              "resposta": str(r["shift_name"]) if r is not None else "—",
              "evidencia": (f"{fint(r['aprovadas_por_hora'])} aprovadas/h e rejeição de "
                            f"{fpct(r['taxa_rejeicao'], 2)} (melhor combinação de volume e qualidade)")
              if r is not None else "Sem dados"})

    ph = producao_por(prod, "hora")
    r = _top(ph, "produzido")
    R.append({"n": 4, "pergunta": "Qual horário apresenta maior volume de produção?",
              "resposta": f"{int(r['hora']):02d}h" if r is not None else "—",
              "evidencia": f"{fint(r['produzido'])} unidades produzidas nessa faixa (horário de Brasília)"
              if r is not None else "Sem dados"})

    ph_ok = ph[ph["produzido"] >= min_unid_hora] if not ph.empty else ph
    r = _top(ph_ok if not ph_ok.empty else ph, "taxa_rejeicao", asc=True)
    R.append({"n": 5, "pergunta": "Qual horário apresenta menor taxa de rejeição?",
              "resposta": f"{int(r['hora']):02d}h" if r is not None else "—",
              "evidencia": f"Rejeição de {fpct(r['taxa_rejeicao'], 2)} sobre {fint(r['produzido'])} unidades"
              if r is not None else "Sem dados"})

    vp = vendas_por(vendas, "product_name")
    r = _top(vp, "faturamento")
    R.append({"n": 6, "pergunta": "Qual produto gera maior faturamento?",
              "resposta": r["product_name"] if r is not None else "—",
              "evidencia": f"{fbrl(r['faturamento'])} ({fpct(r['participacao'])} do total)"
              if r is not None else "Sem dados"})

    vr = vendas_por(vendas, "customer_region")
    r = _top(vr, "faturamento")
    R.append({"n": 7, "pergunta": "Qual região apresenta maior volume de vendas?",
              "resposta": r["customer_region"] if r is not None else "—",
              "evidencia": f"{fbrl(r['faturamento'])} e {fint(r['qtd_vendida'])} unidades"
              if r is not None else "Sem dados"})

    vc = vendas_por(vendas, "sales_channel")
    if not vc.empty:
        vc = vc.assign(margem_pct=safe_div(vc["faturamento"] - vc["cpv_estimado"], vc["faturamento"]))
    r = _top(vc, "faturamento")
    R.append({"n": 8, "pergunta": "Qual canal comercial apresenta melhor resultado?",
              "resposta": r["sales_channel"] if r is not None else "—",
              "evidencia": (f"{fbrl(r['faturamento'])} de faturamento, ticket médio "
                            f"{fbrl(r['ticket_medio'])}, margem estimada {fpct(r['margem_pct'])}")
              if r is not None else "Sem dados"})

    pv = producao_vs_vendas(prod, vendas)
    if not pv.empty and pv["aprovado"].sum() > 0:
        apr, ven = pv["aprovado"].sum(), pv["vendido"].sum()
        gap = safe_div(apr - ven, apr)
        sig = "Sim" if abs(gap) > LIMIAR_SIGNIFICANCIA_GAP else "Não"
        R.append({"n": 9, "pergunta": "Existe diferença significativa entre produção e vendas?",
                  "resposta": sig,
                  "evidencia": (f"Aprovado {fint(apr)} × vendido {fint(ven)} → diferença de {fpct(gap)} "
                                f"do aprovado (limiar adotado: {fpct(LIMIAR_SIGNIFICANCIA_GAP, 0)}). "
                                "Não equivale a estoque físico.")})
    else:
        R.append({"n": 9, "pergunta": "Existe diferença significativa entre produção e vendas?",
                  "resposta": "—", "evidencia": "Sem dados"})

    r = _top(risco, "indice_risco")
    R.append({"n": 10, "pergunta": "Qual máquina apresenta sinais de possível problema?",
              "resposta": r["machine_code"] if r is not None else "—",
              "evidencia": (f"Índice de risco {fint(r['indice_risco'])}/100 — desgaste máx. "
                            f"{fnum(r['desgaste_max'])}%, {fpct(r['pct_alerta'])} das leituras em alerta, "
                            f"vibração média {fnum(r['vib_media'], 2)} mm/s")
              if r is not None else "Sem dados"})

    # desgaste já vem ordenado: maior % primeiro e, em empate, menos horas restantes
    r = desgaste.iloc[0] if desgaste is not None and not desgaste.empty else None
    R.append({"n": 11, "pergunta": "Qual componente necessita de maior atenção?",
              "resposta": r["componente"] if r is not None else "—",
              "evidencia": (f"Desgaste de {fnum(r['wear_pct'])}% ({r['situacao']}), "
                            f"~{fint(r['estimated_remaining_hours'])} h restantes estimadas")
              if r is not None else "Sem dados"})

    fp = financeiro_por_produto(prod, vendas)
    r = _top(fp, "custo_unit_medio") if "custo_unit_medio" in fp.columns else None
    R.append({"n": 12, "pergunta": "Qual produto apresenta maior custo estimado de fabricação?",
              "resposta": r["product_name"] if r is not None else "—",
              "evidencia": (f"Custo unitário médio {fbrl(r['custo_unit_medio'])}; "
                            f"custo total no período {fbrl(r['custo_producao'])}")
              if r is not None else "Sem dados"})
    return R


def gerar_recomendacoes(prod, vendas, desgaste, risco) -> list[dict]:
    """Cinco+ recomendações montadas a partir dos números do período filtrado."""
    rec = []
    pt = producao_por(prod, "shift_name")
    if not pt.empty and len(pt) > 1:
        pior = pt.sort_values("taxa_rejeicao").iloc[-1]
        melhor = pt.sort_values("taxa_rejeicao").iloc[0]
        rec.append({"titulo": f"Reforçar controle de qualidade no turno {pior['shift_name']}",
                    "base": (f"Rejeição de {fpct(pior['taxa_rejeicao'], 2)} contra {fpct(melhor['taxa_rejeicao'], 2)} "
                             f"no turno {melhor['shift_name']}; custo do refugo do turno "
                             f"{fbrl(pior['custo_rejeitados'])}."),
                    "acao": "Inspeção extra no início do turno, revisão de setup e treinamento da equipe."})
    if risco is not None and not risco.empty:
        r = risco.iloc[0]
        rec.append({"titulo": f"Priorizar manutenção preventiva da {r['machine_code']}",
                    "base": (f"Maior índice de risco ({fint(r['indice_risco'])}/100), desgaste máximo "
                             f"{fnum(r['desgaste_max'])}% e {fpct(r['pct_alerta'])} das leituras em alerta."),
                    "acao": "Agendar parada planejada em horário de baixa produção antes de atingir 90%."})
    if desgaste is not None and not desgaste.empty:
        n75 = int((desgaste["wear_pct"] >= 75).sum())
        top = desgaste.iloc[0]
        rec.append({"titulo": "Comprar peças de reposição com antecedência",
                    "base": (f"{n75} componente(s) acima de 75%; o mais desgastado é {top['componente']} "
                             f"com {fnum(top['wear_pct'])}%."),
                    "acao": "Manter estoque mínimo de rolamentos, correias e motores conforme a previsão de vida útil."})
    fp = financeiro_por_produto(prod, vendas)
    lider_margem = None
    if not fp.empty and fp["faturamento"].sum() > 0:
        lider_margem = fp.sort_values("margem_bruta_estimada", ascending=False).iloc[0]["product_name"]
    pv = producao_vs_vendas(prod, vendas)
    if not pv.empty:
        # O produto priorizado por margem não entra aqui, para as recomendações não se contradizerem.
        cand = pv[pv["product_name"] != lider_margem] if len(pv) > 1 else pv
        sobra = cand.sort_values("giro_venda").iloc[0]
        giro_geral = safe_div(pv["vendido"].sum(), pv["aprovado"].sum())
        rec.append({"titulo": f"Ajustar o plano de produção à demanda, começando por {sobra['product_name']}",
                    "base": (f"No geral só {fpct(giro_geral)} do volume aprovado foi vendido; "
                             f"{sobra['product_name']} tem o menor giro entre os demais produtos "
                             f"({fpct(sobra['giro_venda'])}, saldo de {fint(sobra['saldo_aprovado_menos_vendido'])} unidades)."),
                    "acao": "Reduzir lotes programados desse item e liberar capacidade para itens de maior giro."})
    if lider_margem is not None:
        m = fp.sort_values("margem_bruta_estimada", ascending=False).iloc[0]
        rec.append({"titulo": f"Priorizar {m['product_name']} no mix comercial",
                    "base": (f"Maior margem bruta estimada: {fbrl(m['margem_bruta_estimada'])} "
                             f"({fpct(m['margem_pct'])})."),
                    "acao": "Direcionar campanhas e capacidade para o produto de melhor resultado."})
    vc = vendas_por(vendas, "sales_channel")
    if not vc.empty:
        c = vc.iloc[0]
        rec.append({"titulo": f"Fortalecer o canal {c['sales_channel']}",
                    "base": f"Maior faturamento ({fpct(c['participacao'])} do total) e ticket médio {fbrl(c['ticket_medio'])}.",
                    "acao": "Replicar as condições comerciais desse canal nos demais."})
    return rec
