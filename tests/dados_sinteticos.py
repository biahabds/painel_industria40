"""Gera DataFrames no MESMO formato que o banco devolve, reproduzindo a lógica do
simulador do professor. Uso exclusivo em testes offline dos cálculos — o painel
sempre consulta o Supabase."""
import random
import uuid
from datetime import date, datetime, timedelta, timezone

import pandas as pd

PRODUTOS = [("PRD-100", "Componente Automotivo A", 85, 32), ("PRD-200", "Conjunto Mecânico B", 145, 61),
            ("PRD-300", "Peça Industrial C", 210, 94), ("PRD-400", "Módulo Eletrônico D", 320, 155),
            ("PRD-500", "Kit de Montagem E", 58, 21)]
COMPONENTES = [("ROLAMENTO", "Rolamento principal"), ("MOTOR", "Motor elétrico"),
               ("CORREIA", "Correia de transmissão")]


def _turno(h):
    return "MANHA" if 6 <= h < 14 else "TARDE" if 14 <= h < 22 else "NOITE"


def _fator(h):
    if 7 <= h < 11: return 1.08
    if 11 <= h < 14: return 0.98
    if 14 <= h < 18: return 1.03
    if h >= 22 or h < 6: return 0.78
    return 0.92


def gerar(dias=7, seed=42):
    random.seed(seed)
    fim = datetime(2026, 11, 12, 18, 0, tzinfo=timezone.utc)
    ini = fim - timedelta(days=dias)
    maq = pd.DataFrame([
        (str(uuid.uuid4()), " CNC-01", "Centro de Usinagem CNC 01", "USINAGEM", "CNC", 120, date(2021, 3, 15), "OPERANDO", ini),
        (str(uuid.uuid4()), " PRE-01", "Prensa Hidráulica 01", "ESTAMPARIA", "PRENSA", 180, date(2020, 8, 10), "OPERANDO", ini),
        (str(uuid.uuid4()), " MON-01", "Linha de Montagem 01", "MONTAGEM", "MONTAGEM", 95, date(2022, 1, 20), "OPERANDO", ini),
        (str(uuid.uuid4()), " PIN-01", "Cabine de Pintura 01", "ACABAMENTO", "PINTURA", 80, date(2021, 11, 5), "OPERANDO", ini),
    ], columns=["machine_id", "machine_code", "machine_name", "production_line", "machine_type",
                "nominal_capacity_per_hour", "installed_at", "machine_status", "created_at"])

    prod, vend, tele, wear = [], [], [], []
    t = ini.replace(minute=0)
    while t <= fim:
        for _, m in maq.iterrows():
            p = random.choice(PRODUTOS)
            q = max(1, int(random.gauss(m.nominal_capacity_per_hour * _fator(t.hour) / 2,
                                        m.nominal_capacity_per_hour * .08)))
            pr = .065 if (t.hour >= 22 or t.hour < 6) else .035
            rej = sum(random.random() < pr for _ in range(q))
            b = str(uuid.uuid4())
            prod.append(dict(production_id=len(prod) + 1, batch_id=b, machine_id=m.machine_id, product_code=p[0],
                             product_name=p[1], shift_name=_turno(t.hour), qty_produced=q, qty_rejected=rej,
                             downtime_minutes=round(random.uniform(0, 8), 2),
                             cycle_time_seconds=round(random.uniform(12, 95), 2),
                             energy_kwh=round(random.uniform(3, 24), 3),
                             unit_cost=round(p[3] * random.uniform(.92, 1.13), 2),
                             started_at=t - timedelta(minutes=random.randint(15, 29)), ended_at=t, recorded_at=t))
            if random.random() < .82:
                qs = random.randint(max(1, int(q * .15)), max(2, int(q * .75)))
                pu = p[2] * random.uniform(.94, 1.12)
                vend.append(dict(order_id=len(vend) + 1, order_number=f"PED-{uuid.uuid4().hex[:12].upper()}",
                                 batch_id=b, product_code=p[0], product_name=p[1],
                                 sales_channel=random.choice(["E-COMMERCE", "DISTRIBUIDOR", "VENDA_DIRETA", "REPRESENTANTE"]),
                                 qty_sold=qs, unit_price=round(pu, 2), total_amount=round(qs * pu, 2),
                                 order_status=random.choices(["FATURADO", "PENDENTE", "ENVIADO", "CANCELADO"],
                                                             [65, 15, 17, 3])[0],
                                 customer_region=random.choice(["SUDESTE", "SUL", "CENTRO-OESTE", "NORDESTE", "NORTE"]),
                                 created_at=t))
        t += timedelta(hours=1)

    t = ini
    while t <= fim:
        for _, m in maq.iterrows():
            temp, vib = random.uniform(58, 87), random.uniform(.35, 5.8)
            st = "CRITICO" if temp >= 90 or vib >= 7 else "ATENCAO" if temp >= 80 or vib >= 4.5 else "OPERANDO"
            tele.append(dict(machine_id=m.machine_id, machine_code=m.machine_code, temperature_c=temp,
                             vibration_mm_s=vib, energy_kw=random.uniform(2, 15), pressure_bar=random.uniform(4, 10),
                             rpm=random.randint(800, 3500), machine_status=st, recorded_at=t))
        t += timedelta(minutes=5)

    snap = {}
    t = ini.replace(minute=0)
    while t <= fim:
        for _, m in maq.iterrows():
            for cc, cn in COMPONENTES:
                k = (m.machine_id, cc)
                w = random.uniform(8, 42) if k not in snap else min(99.5, snap[k] + random.uniform(.02, .2))
                # força um componente a ficar crítico para testar alertas
                if m.machine_code.strip() == "PRE-01" and cc == "ROLAMENTO" and k not in snap:
                    w = 74
                snap[k] = w
                wear.append(dict(machine_id=m.machine_id, component_code=cc, component_name=cn, wear_pct=w,
                                 estimated_remaining_hours=max(5, (100 - w) * random.uniform(18, 30)),
                                 measured_at=t))
        t += timedelta(hours=1)
    parts = pd.DataFrame([dict(component_id=i, machine_id=k[0], component_code=k[1],
                               component_name=dict(COMPONENTES)[k[1]], wear_pct=round(w, 2),
                               warning_threshold_pct=75.0, critical_threshold_pct=90.0,
                               estimated_remaining_hours=max(5, (100 - w) * 24), last_inspection_at=fim)
                          for i, (k, w) in enumerate(snap.items(), 1)])
    tele = pd.DataFrame(tele)
    # Agregação equivalente ao SQL "telemetria_resumo"
    resumo = tele.groupby("machine_code").agg(
        n_leituras=("temperature_c", "size"), temp_media=("temperature_c", "mean"),
        temp_max=("temperature_c", "max"), vib_media=("vibration_mm_s", "mean"),
        vib_max=("vibration_mm_s", "max"), energia_media_kw=("energy_kw", "mean"),
        pressao_media=("pressure_bar", "mean"), rpm_medio=("rpm", "mean"),
        n_atencao=("machine_status", lambda s: (s == "ATENCAO").sum()),
        n_critico=("machine_status", lambda s: (s == "CRITICO").sum())).reset_index()
    ultima = tele.sort_values("recorded_at").groupby("machine_id").tail(1)
    serie = tele.rename(columns={"recorded_at": "bucket"})
    return dict(maquinas=maq, producao=pd.DataFrame(prod), vendas=pd.DataFrame(vend), telemetria=tele,
                resumo=resumo, ultima=ultima, serie=serie, parts=parts, wear=pd.DataFrame(wear),
                ini=ini, fim=fim)
