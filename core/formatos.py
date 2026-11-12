"""Formatação de números no padrão brasileiro (sem dependência do Streamlit)."""
import math


def _br(s: str) -> str:
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def _ok(v) -> bool:
    try:
        return v is not None and not math.isnan(float(v))
    except (TypeError, ValueError):
        return False


def fint(v) -> str:
    return _br(f"{float(v):,.0f}") if _ok(v) else "—"


def fnum(v, casas=1) -> str:
    return _br(f"{float(v):,.{casas}f}") if _ok(v) else "—"


def fbrl(v) -> str:
    return "R$ " + _br(f"{float(v):,.2f}") if _ok(v) else "—"


def fcurto(v, moeda=False) -> str:
    """Valor resumido para cartões: 1.729.273 → '1,73 mi'; R$ 102.492.956 → 'R$ 102,5 mi'."""
    if not _ok(v):
        return "—"
    v = float(v)
    pre = "R$ " if moeda else ""
    for limite, sufixo in ((1e9, "bi"), (1e6, "mi"), (1e3, "mil")):
        if abs(v) >= limite:
            n = v / limite
            casas = 2 if abs(n) < 10 else 1
            return f"{pre}{_br(f'{n:,.{casas}f}')} {sufixo}"
    return pre + (_br(f"{v:,.2f}") if moeda else _br(f"{v:,.0f}"))


def fpct(v, casas=1) -> str:
    return _br(f"{float(v) * 100:,.{casas}f}") + "%" if _ok(v) else "—"
