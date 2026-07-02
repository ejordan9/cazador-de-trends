"""Fuente: posts 'hot' de subreddits clave vía feed RSS de Reddit.

No usa la API OAuth (Reddit bloquea el endpoint .json sin auth con 403, y la
creación de apps a veces falla). El feed RSS `r/<sub>/hot.rss` sigue abierto y
no requiere credenciales — encaja con la filosofía de minimizar dependencias.

Limitación: el RSS no trae score ni nº de comentarios, así que `volumen` queda
en None. El orden del feed 'hot' ya es el ranking, así que se usa como posición.

Contrato: expone `fetch() -> SourceResult`. Nunca lanza hacia arriba. Cada
subreddit falla de forma aislada: si uno cae, los demás igual aparecen.
"""

from __future__ import annotations

import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import requests

# permite correr este archivo standalone (python sources/reddit.py)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from contract import SourceResult, TrendItem, error_item, now_iso  # noqa: E402
import config  # noqa: E402

FUENTE = "Reddit"
RAW_DIR = Path(__file__).resolve().parent.parent / "output" / "raw"
ATOM = {"a": "http://www.w3.org/2005/Atom"}

POSTS_POR_SUB = 5      # cuántos posts 'hot' traer por subreddit
DELAY_SEGUNDOS = 2.0   # fallback si Reddit no manda cabeceras de rate-limit
MAX_ESPERA = 20        # tope de espera por reset, para no colgar la corrida
REINTENTOS = 3         # intentos ante 429 antes de rendirse con ese sub


def _save_raw(sub: str, xml_text: str) -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    fecha = now_iso()[:10]
    (RAW_DIR / f"reddit_{sub}_{fecha}.xml").write_text(xml_text, encoding="utf-8")


def _es_sensible(tema: str) -> bool:
    t = tema.lower()
    return any(kw in t for kw in config.KEYWORDS_SENSIBLES)


def _parse_sub(sub: str, xml_text: str, grupo: str) -> list[TrendItem]:
    root = ET.fromstring(xml_text)
    items: list[TrendItem] = []
    for orden, entry in enumerate(root.findall("a:entry", ATOM), start=1):
        titulo = entry.findtext("a:title", namespaces=ATOM)
        link_el = entry.find("a:link", ATOM)
        if not titulo or link_el is None:
            continue
        tema = titulo.strip()
        # subreddit real del post (en multireddits varía por entry); cae al
        # string del feed si el feed no trae <category>
        cat = entry.find("a:category", ATOM)
        sub_real = cat.get("term") if cat is not None else sub
        items.append(
            TrendItem(
                fuente=f"r/{sub_real}",  # comunidad real (subtítulo en el tablero)
                tema=tema,               # sin prefijo: el subreddit ya se muestra aparte
                link=link_el.get("href", ""),
                volumen=None,  # el RSS no expone score
                orden=orden,
                sensible=_es_sensible(tema),
                grupo=grupo,
            )
        )
    return items


def _segundos_reset(resp: requests.Response) -> float:
    """Cuántos segundos esperar según las cabeceras de rate-limit de Reddit.
    Devuelve 0 si todavía queda cuota."""
    try:
        restante = float(resp.headers.get("x-ratelimit-remaining", "1"))
    except ValueError:
        restante = 1.0
    if restante >= 1:
        return 0.0
    try:
        reset = float(resp.headers.get("x-ratelimit-reset", DELAY_SEGUNDOS))
    except ValueError:
        reset = DELAY_SEGUNDOS
    return min(reset + 1, MAX_ESPERA)


def _fetch_sub(sub: str, grupo: str) -> tuple[list[TrendItem], str | None, float]:
    """Devuelve (items, error, espera_sugerida).

    Respeta x-ratelimit-* de Reddit: ante 429 espera lo que indique el header
    `reset` (no un delay fijo). `espera_sugerida` es cuánto conviene pausar
    antes del siguiente subreddit para no volver a chocar el límite.
    """
    url = f"https://www.reddit.com/r/{sub}/hot.rss?limit={POSTS_POR_SUB}"
    ultimo_error = ""
    for intento in range(REINTENTOS + 1):
        try:
            resp = requests.get(
                url,
                headers={"User-Agent": config.USER_AGENT},
                timeout=config.REQUEST_TIMEOUT,
            )
        except requests.RequestException as exc:
            ultimo_error = str(exc)
            time.sleep(DELAY_SEGUNDOS)
            continue

        espera = _segundos_reset(resp)
        if resp.status_code == 429:
            ultimo_error = "429 Too Many Requests"
            if intento < REINTENTOS:
                time.sleep(espera or DELAY_SEGUNDOS * (intento + 2))
                continue
            return [], ultimo_error, espera
        try:
            resp.raise_for_status()
            _save_raw(sub, resp.text)
            return _parse_sub(sub, resp.text, grupo), None, espera
        except (requests.RequestException, ET.ParseError) as exc:
            return [], str(exc), espera
    return [], ultimo_error, MAX_ESPERA


def fetch() -> SourceResult:
    todos: list[TrendItem] = []
    caidos: list[str] = []

    grupos = list(config.SUBREDDITS.items())  # [(etiqueta, query), ...]
    for i, (grupo, query) in enumerate(grupos):
        items, err, espera = _fetch_sub(query, grupo)
        if err:
            caidos.append(query)
            ei = error_item(FUENTE, f"{grupo} ({query}): {err}")
            ei.grupo = grupo
            todos.append(ei)
        else:
            todos.extend(items)
        # pausa adaptativa antes del siguiente grupo según el header de Reddit
        if i < len(grupos) - 1:
            time.sleep(espera or DELAY_SEGUNDOS)

    ok = len(caidos) < len(grupos)  # ok si al menos un grupo respondió
    detalle = f"grupos caídos: {', '.join(caidos)}" if caidos else ""
    return SourceResult(fuente=FUENTE, items=todos, ok=ok, detalle=detalle)


if __name__ == "__main__":
    res = fetch()
    print(f"[{res.fuente}] ok={res.ok} items={len(res.items)} {res.detalle}")
    grupo_actual = None
    for it in res.items:
        if it.grupo != grupo_actual:
            grupo_actual = it.grupo
            print(f"  ── {grupo_actual} ──")
        flag = " 🔶" if it.sensible else ""
        print(f"     [{it.fuente}] {it.tema[:55]}{flag}")
