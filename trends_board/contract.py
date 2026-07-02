"""Contrato de datos compartido entre todas las fuentes.

Toda fuente del tablero (X, Reddit, Google Trends...) devuelve una lista de
`TrendItem`. Si una fuente falla, NO revienta el tablero: devuelve un item de
error visible (ver `error_item`). Esto es el "aislamiento de fallos por fuente".
"""

from __future__ import annotations

from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone


@dataclass
class TrendItem:
    """Un tema/tendencia de una fuente.

    Campos del contrato original (sección 4 del plan):
      fuente, tema, volumen, link
    + extras que se decidieron en la auditoría:
      orden    -> posición en el ranking (1 = lo más arriba)
      sensible -> True si el tema coincide con la lista de keywords sensibles
      error    -> True si este item representa un fallo de la fuente
    """

    fuente: str
    tema: str
    link: str
    volumen: str | None = None
    orden: int | None = None
    sensible: bool = False
    error: bool = False
    grupo: str | None = None  # agrupación opcional dentro de la fuente (ej. Reddit por comunidad)
    imagen: str | None = None  # URL de miniatura (noticias / efemérides)

    def to_dict(self) -> dict:
        return asdict(self)


def error_item(fuente: str, detalle: str) -> TrendItem:
    """Item que representa el fallo de una fuente, para que sea visible en el
    tablero en vez de tumbar la corrida completa."""
    return TrendItem(
        fuente=fuente,
        tema=f"⚠️ La fuente falló: {detalle}",
        link="",
        error=True,
    )


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


@dataclass
class SourceResult:
    """Resultado de ejecutar una fuente: sus items + metadata de la corrida."""

    fuente: str
    items: list[TrendItem] = field(default_factory=list)
    ok: bool = True
    detalle: str = ""

    def to_dict(self) -> dict:
        return {
            "fuente": self.fuente,
            "ok": self.ok,
            "detalle": self.detalle,
            "items": [it.to_dict() for it in self.items],
        }
