"""Formateo de fechas y reglas de recurrencia en español, sin depender de locales."""

from datetime import datetime

DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MESES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]
DIAS_RRULE = {
    "MO": "lunes", "TU": "martes", "WE": "miércoles", "TH": "jueves",
    "FR": "viernes", "SA": "sábados", "SU": "domingos",
}


def formatear_fecha(dt: datetime) -> str:
    """'lunes 13 de julio de 2026 a las 08:00'"""
    return (
        f"{DIAS[dt.weekday()]} {dt.day} de {MESES[dt.month - 1]} de {dt.year}"
        f" a las {dt:%H:%M}"
    )


def _params_rrule(rrule: str) -> dict:
    rrule = rrule.strip()
    if rrule.upper().startswith("RRULE:"):
        rrule = rrule[6:]
    params = {}
    for parte in rrule.split(";"):
        if "=" in parte:
            clave, valor = parte.split("=", 1)
            params[clave.strip().upper()] = valor.strip().upper()
    return params


def describir_recurrencia(rrule: str, hora: datetime) -> str:
    """Descripción en español de una RRULE. Ante algo exótico, devuelve la regla cruda."""
    params = _params_rrule(rrule)
    freq = params.get("FREQ", "")
    intervalo = int(params.get("INTERVAL", "1"))
    sufijo_hora = f" a las {hora:%H:%M}"

    if freq == "DAILY":
        base = "todos los días" if intervalo == 1 else f"cada {intervalo} días"
        return base + sufijo_hora

    if freq == "WEEKLY":
        dias = [DIAS_RRULE.get(d, d) for d in params.get("BYDAY", "").split(",") if d]
        dias_txt = " y ".join(dias) if dias else DIAS[hora.weekday()]
        if intervalo == 1:
            return f"todos los {dias_txt}{sufijo_hora}"
        return f"cada {intervalo} semanas, los {dias_txt}{sufijo_hora}"

    if freq == "MONTHLY":
        dia_mes = params.get("BYMONTHDAY", str(hora.day))
        base = "todos los meses" if intervalo == 1 else f"cada {intervalo} meses"
        return f"{base} el día {dia_mes}{sufijo_hora}"

    if freq == "YEARLY":
        return (
            f"todos los años el {hora.day} de {MESES[hora.month - 1]}{sufijo_hora}"
        )

    return rrule
