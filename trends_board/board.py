"""Orquestador del tablero.

Llama a cada fuente de forma aislada (una fuente caída NO tumba al resto),
guarda los datos como JSON (capa de datos / histórico) y genera una vista HTML
para abrir en el navegador.

Uso:
    .venv/bin/python trends_board/board.py
"""

from __future__ import annotations

import json
import sys
import webbrowser
from html import escape
from pathlib import Path

# permite ejecutar tanto desde la raíz como desde trends_board/
sys.path.insert(0, str(Path(__file__).resolve().parent))

from contract import SourceResult, now_iso  # noqa: E402
from sources import x_chile, google_trends, reddit, noticias, efemerides  # noqa: E402
import config  # noqa: E402

OUTPUT_DIR = Path(__file__).resolve().parent / "output"

# Registro de fuentes activas. Sumar una fuente = agregar una línea aquí.
FUENTES = [
    x_chile,
    google_trends,
    reddit,
]


def recolectar() -> list[SourceResult]:
    """Ejecuta cada fuente aislada. Un except de último recurso por si una
    fuente lanza algo que no previó su propio try/except."""
    resultados: list[SourceResult] = []
    for modulo in FUENTES:
        try:
            resultados.append(modulo.fetch())
        except Exception as exc:  # red de seguridad final
            from contract import error_item

            nombre = getattr(modulo, "FUENTE", modulo.__name__)
            resultados.append(
                SourceResult(
                    fuente=nombre,
                    items=[error_item(nombre, f"excepción no controlada: {exc}")],
                    ok=False,
                    detalle=str(exc),
                )
            )
    return resultados


def guardar_json(resultados: list[SourceResult], fecha: str,
                 noticias_res=None, efemerides_res=None) -> Path:
    """Guarda el export estructurado. Escribe el JSON con fecha (histórico) y
    además `trends_latest.json` (archivo fijo, siempre el más reciente) — pensado
    para adjuntar a una IA o, tras el deploy, servirse por URL (GET)."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "fecha": fecha,
        "generado": now_iso(),
        "fuentes": [r.to_dict() for r in resultados],
    }
    if noticias_res is not None:
        payload["noticias"] = noticias_res.to_dict()
    if efemerides_res is not None:
        payload["efemerides"] = efemerides_res.to_dict()

    texto = json.dumps(payload, ensure_ascii=False, indent=2)
    ruta = OUTPUT_DIR / f"trends_{fecha}.json"
    ruta.write_text(texto, encoding="utf-8")
    (OUTPUT_DIR / "trends_latest.json").write_text(texto, encoding="utf-8")
    return ruta


def cargar_json(fecha: str) -> dict | None:
    """Carga el snapshot de un día (para comparar 'qué es nuevo hoy')."""
    ruta = OUTPUT_DIR / f"trends_{fecha}.json"
    if not ruta.exists():
        return None
    return json.loads(ruta.read_text(encoding="utf-8"))


def _item_html(it, pos_override: int | None = None) -> str:
    """Renderiza un TrendItem como <li>. Conserva las clases 'sensible'/'error'
    y 'pos' del contrato original. `pos_override` renumera dentro de un grupo."""
    if it.error:
        return (
            '<li class="item error">'
            '<span class="warn" aria-hidden="true">⚠️</span>'
            f'<span class="msg">{escape(it.tema)}</span></li>'
        )

    pos = pos_override if pos_override is not None else (
        it.orden if it.orden is not None else ""
    )
    nombre = escape(it.tema)
    if it.link:
        nombre = (
            f'<a class="name" href="{escape(it.link)}" target="_blank" '
            f'rel="noopener">{nombre}</a>'
        )
    else:
        nombre = f'<span class="name">{nombre}</span>'

    warn = (
        '<span class="warn" title="keyword sensible — revisar criterio" '
        'aria-label="sensible">⚠️</span>'
        if it.sensible
        else ""
    )
    chip = f'<span class="vol">{escape(it.volumen)}</span>' if it.volumen else ""
    cls = "item sensible" if it.sensible else "item"
    return (
        f'<li class="{cls}">'
        f'<span class="pos">{pos}</span>'
        f'<span class="body">{nombre}{warn}</span>'
        f"{chip}</li>"
    )


def _grouped_html(items) -> str:
    """Render de dos niveles: grupo (etiqueta) → comunidad (subreddit) → posts
    renumerados dentro de cada comunidad. Los items deben venir consecutivos por
    grupo (así los entrega la fuente Reddit)."""
    from itertools import groupby

    out = []
    for grupo, giter in groupby(items, key=lambda it: it.grupo):
        gitems = list(giter)
        out.append(f'<li class="group-head">{escape(grupo or "Otros")}</li>')

        normales = [it for it in gitems if not it.error]
        errores = [it for it in gitems if it.error]

        # bucket por comunidad (subreddit), preservando orden de aparición
        subs: dict[str, list] = {}
        for it in normales:
            subs.setdefault(it.fuente, []).append(it)

        for sub, sus_items in subs.items():
            filas = "".join(
                _item_html(it, pos_override=n) for n, it in enumerate(sus_items, 1)
            )
            out.append(
                f'<li class="subgroup"><div class="sub-head">{escape(sub)}</div>'
                f'<ol class="sub-list">{filas}</ol></li>'
            )
        for it in errores:
            out.append(f'<li class="subgroup">{_item_html(it)}</li>')

    return "".join(out)


# Íconos SVG por fuente (inline, monocromo con currentColor)
_ICONOS_FUENTE = {
    "x": '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M18.244 2.25h3.308'
         "l-7.227 8.26 8.502 11.24h-6.66l-5.214-6.817L4.99 21.75H1.68l7.73-8.835"
         'L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/></svg>',
    "google": '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M16 6l2.29 '
              "2.29-4.88 4.88-4-4L2 16.59 3.41 18l6-6 4 4 6.3-6.29L22 12V6z\"/></svg>",
    "reddit": '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M21 6h-2v9H6v2'
              "c0 .55.45 1 1 1h11l4 4V7c0-.55-.45-1-1-1zm-4 6V3c0-.55-.45-1-1-1H3c-.55"
              ' 0-1 .45-1 1v14l4-4h10c.55 0 1-.45 1-1z"/></svg>',
}


def _icono_fuente(fuente: str) -> str:
    f = fuente.lower()
    if "google" in f:
        return _ICONOS_FUENTE["google"]
    if "reddit" in f:
        return _ICONOS_FUENTE["reddit"]
    if f.startswith("x ") or f == "x" or "x chile" in f:
        return _ICONOS_FUENTE["x"]
    return ""


def _col_html(r: SourceResult) -> str:
    """Renderiza una fuente como una columna (surface-container M3).
    Si los items traen `grupo`, agrupa por comunidad (caso Reddit)."""
    estado_cls = "ok" if r.ok else "down"
    # ícono de la fuente si está OK; advertencia si la fuente cayó
    marca = _icono_fuente(r.fuente) if r.ok else "⚠"
    titulo_estado = "ok" if r.ok else "fuente con problemas"

    agrupado = any(it.grupo for it in r.items)
    cuerpo = _grouped_html(r.items) if agrupado else "".join(
        _item_html(it) for it in r.items
    )
    lista_cls = "items grouped" if agrupado else "items"

    return (
        '<section class="col">'
        '<header class="col-head">'
        f'<span class="status {estado_cls}" title="{titulo_estado}">{marca}</span>'
        f"<h2>{escape(r.fuente)}</h2>"
        f'<span class="count">{len(r.items)}</span>'
        "</header>"
        f'<ol class="{lista_cls}">{cuerpo}</ol>'
        "</section>"
    )


def _cuentas_html(cuentas: dict) -> str:
    """Sección de marcadores (cuentas a revisar a mano, no se scrapean).

    Render único en JS: embebe las cuentas fijas (de cuentas.txt) como datos y el
    JS las dibuja JUNTO con las agregadas por el botón (localStorage), agrupadas
    por RED (Instagram, LinkedIn…) en columnas. Así no se duplican encabezados.
    """
    if not cuentas:
        return ""
    total = sum(len(v) for v in cuentas.values())
    fijas = [
        {"nombre": nombre, "url": url, "cat": categoria}
        for categoria, entradas in cuentas.items()
        for nombre, url in entradas
    ]
    fijas_json = json.dumps(fijas, ensure_ascii=False)
    opciones = "".join(f'<option value="{escape(c)}">' for c in cuentas)
    return (
        '<section class="col accounts">'
        '<header class="col-head">'
        '<span class="status star" title="bookmarks">★</span>'
        "<h2>Cuentas a revisar</h2>"
        f'<span class="count" id="acc-count">{total}</span>'
        '<button id="acc-add-btn" class="acc-add" type="button" '
        'title="Agregar cuenta" aria-label="Agregar cuenta">+ Agregar</button>'
        "</header>"
        '<form id="acc-form" class="acc-form" hidden>'
        '<input id="acc-url" class="acc-in" type="url" '
        'placeholder="Pega la URL…" required>'
        '<input id="acc-name" class="acc-in" placeholder="Nombre (opcional)">'
        '<input id="acc-cat" class="acc-in" list="acc-cats" '
        'placeholder="Categoría" value="Instagram">'
        f'<datalist id="acc-cats">{opciones}</datalist>'
        '<div class="acc-form-actions">'
        '<button type="submit" class="acc-btn">Agregar</button>'
        '<button type="button" id="acc-cancel" class="acc-btn ghost">Cancelar</button>'
        "</div></form>"
        '<div id="acc-grid" class="acc-grid"></div>'
        f'<script>var CUENTAS_FIJAS={fijas_json};</script>'
        "</section>"
    )


def _ig_card_html() -> str:
    """Tarjeta compacta de Instagram para apilar bajo Google Trends.
    El JS de cuentas la rellena (mount #acc-ig)."""
    return (
        '<section class="col accounts-ig">'
        '<header class="col-head">'
        '<span class="status star" title="instagram">★</span>'
        "<h2>Instagram</h2>"
        '<span class="count" id="acc-ig-count"></span>'
        "</header>"
        '<div id="acc-ig" class="acc-body"></div>'
        "</section>"
    )


def _noticias_html(res) -> str:
    """Hero carrusel de noticias (estilo Mercado Negro): imagen grande con título
    superpuesto + tag del medio, flechas y tira de miniaturas debajo."""
    if not res or not res.items:
        return ""
    items = [it for it in res.items if not it.error and it.imagen]
    if not items:
        items = [it for it in res.items if not it.error]
    if not items:
        return ""
    slides, thumbs = [], []
    for i, it in enumerate(items):
        bg = f"background-image:url('{escape(it.imagen)}')" if it.imagen else ""
        act = " active" if i == 0 else ""
        slides.append(
            f'<a class="hero-slide{act}" data-i="{i}" href="{escape(it.link)}" '
            f'target="_blank" rel="noopener" style="{bg}">'
            '<div class="hero-overlay">'
            f'<span class="hero-tag">{escape(it.fuente)}</span>'
            f'<h2 class="hero-title">{escape(it.tema)}</h2>'
            '<span class="hero-cta">Leer más ›</span>'
            "</div></a>"
        )
        thumbs.append(
            f'<button class="hero-thumb{act}" type="button" data-i="{i}" '
            f'style="{bg}" aria-label="{escape(it.tema[:50])}"></button>'
        )
    return (
        '<section class="hero">'
        '<div class="hero-stage" id="hero-stage">'
        f'{"".join(slides)}'
        '<button class="hero-arrow next" id="hero-next" type="button" '
        'aria-label="Siguiente">›</button>'
        '<button class="hero-arrow prev" id="hero-prev" type="button" '
        'aria-label="Anterior">‹</button>'
        "</div>"
        f'<div class="hero-thumbs" id="hero-thumbs">{"".join(thumbs)}</div>'
        "</section>"
    )


def _efemerides_html(res) -> str:
    """Efemérides de la semana: una tarjeta por día (eventos + conmemoraciones)."""
    if not res or not res.items:
        return ""
    from itertools import groupby

    dias = []
    for grupo, giter in groupby(res.items, key=lambda it: it.grupo):
        lineas = []
        for it in giter:
            if it.error:
                continue
            if it.fuente == "conmemoración":
                lineas.append(f'<li class="efem-dia-li conmem">🎉 {escape(it.tema)}</li>')
            else:
                anio = f'<span class="efem-anio">{escape(it.fuente)}</span> '
                texto = escape(it.tema)
                if it.link:
                    texto = (
                        f'<a href="{escape(it.link)}" target="_blank" rel="noopener">{texto}</a>'
                    )
                lineas.append(f'<li class="efem-dia-li">{anio}{texto}</li>')
        dias.append(
            '<div class="efem-card">'
            f'<div class="efem-dia">{escape(grupo or "")}</div>'
            f'<ul class="efem-list">{"".join(lineas)}</ul>'
            "</div>"
        )
    return (
        '<section class="feed-wide">'
        '<header class="col-head">'
        '<span class="status star" title="efemérides">🗓️</span>'
        "<h2>Efemérides de la semana</h2>"
        "</header>"
        f'<div class="efem-grid">{"".join(dias)}</div>'
        "</section>"
    )


# --- Material Design 3: tokens, tipografía, layout (modo oscuro por defecto) ---
_FONTS = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
    '<link rel="stylesheet" '
    'href="https://fonts.googleapis.com/css2?'
    'family=Roboto:wght@400;500&'
    'family=Roboto+Flex:opsz,wght@8..144,400;8..144,500;8..144,700&display=swap">'
)

_CSS = """
*,*::before,*::after{box-sizing:border-box;}
/* Paleta Material Design 3 oficial (baseline violeta) */
:root,[data-theme="dark"]{
  --bg:#0F0F11; --surface:#1C1B1F; --surface-container:#211F26;
  --surface-container-high:#2B2930;
  --primary:#D0BCFF; --on-primary:#381E72;
  --primary-tint:rgba(208,188,255,.16);
  --sensible:#FFB951; --sensible-bg:#3B2A00;
  --sensible-border:rgba(255,185,81,.34);
  --error:#F2B8B8; --error-bg:rgba(242,184,184,.10);
  --error-border:rgba(242,184,184,.32);
  --on-surface:#E6E1E5; --on-surface-variant:#CAC4D0;
  --outline:rgba(147,143,153,.30); --state:rgba(230,225,229,.08);
}
[data-theme="light"]{
  --bg:#FEF7FF; --surface:#FFFBFE; --surface-container:#ECE6F0;
  --surface-container-high:#E6E0E9;
  --primary:#6750A4; --on-primary:#FFFFFF;
  --primary-tint:rgba(103,80,164,.12);
  --sensible:#7A5900; --sensible-bg:#FFDEA8;
  --sensible-border:rgba(122,89,0,.30);
  --error:#B3261E; --error-bg:rgba(179,38,30,.09);
  --error-border:rgba(179,38,30,.26);
  --on-surface:#1C1B1F; --on-surface-variant:#49454F;
  --outline:rgba(121,116,126,.28); --state:rgba(28,27,31,.06);
}
html{color-scheme:dark light;}
body{
  margin:0; background:var(--bg); color:var(--on-surface);
  font-family:"Roboto","Roboto Flex",system-ui,sans-serif;
  font-size:14px; line-height:1.45; -webkit-font-smoothing:antialiased;
}
/* Header fijo (M3 top app bar) */
.appbar{
  position:sticky; top:0; z-index:10;
  display:flex; align-items:center; gap:16px; flex-wrap:wrap;
  padding:14px 20px; background:var(--surface);
  border-bottom:1px solid var(--outline);
}
.appbar h1{
  margin:0; font-family:"Roboto Flex",sans-serif; font-weight:400;
  font-size:26px; letter-spacing:0;  /* M3 Display Small (compacto) */
}
.appbar .meta{
  margin:2px 0 0; color:var(--on-surface-variant);
  font-size:12px; letter-spacing:.3px;  /* M3 Label */
}
.appbar-main{margin-right:auto;}
.badges{display:flex; gap:8px; flex-wrap:wrap;}
.badge{
  display:inline-flex; align-items:center; gap:6px;
  padding:5px 12px; border-radius:8px;
  background:var(--surface-container-high); color:var(--on-surface-variant);
  font-size:12px; font-weight:500; letter-spacing:.3px;
}
.badge b{color:var(--on-surface); font-family:"Roboto Flex",sans-serif;}
.badge.down{
  background:var(--error-bg); color:var(--error);
  border:1px solid var(--error-border);
}
/* Toggle de tema (M3 icon button) */
.toggle{
  width:40px; height:40px; border:none; border-radius:50%;
  background:transparent; color:var(--on-surface-variant);
  font-size:18px; cursor:pointer; line-height:1;
  display:inline-flex; align-items:center; justify-content:center;
  transition:background .15s;
}
.toggle:hover{background:var(--state);}
/* Grid 3 columnas desktop / stack mobile (mobile-first) */
.grid{
  display:grid; grid-template-columns:1fr; gap:16px;
  padding:16px 16px 0; max-width:1500px; margin:0 auto;
}
@media(min-width:768px){
  .grid{grid-template-columns:repeat(3,1fr); padding:20px 20px 0;}
}
.col{
  background:var(--surface-container); border-radius:16px;
  border:1px solid var(--outline); overflow:hidden;
}
.col-head{
  display:flex; align-items:center; gap:10px;
  padding:14px 16px; border-bottom:1px solid var(--outline);
  position:sticky; top:0; background:var(--surface-container);
}
.col-head h2{
  margin:0; font-family:"Roboto Flex",sans-serif; font-weight:500;
  font-size:15px; letter-spacing:.1px; margin-right:auto;  /* M3 Title */
}
.status{
  width:26px; height:26px; border-radius:50%; flex:0 0 auto;
  display:inline-flex; align-items:center; justify-content:center;
  font-size:13px; font-weight:700;
}
.status svg{width:15px; height:15px;}
.status.ok{background:var(--primary-tint); color:var(--primary);}
.status.down{background:var(--error-bg); color:var(--error);}
.count{
  font-family:"Roboto Flex",sans-serif; font-weight:500; font-size:13px;
  color:var(--on-surface-variant);
  background:var(--surface-container-high); border-radius:8px;
  padding:2px 9px; min-width:26px; text-align:center;
}
/* Items */
.items{list-style:none; margin:0; padding:6px;}
.item{
  position:relative; display:flex; align-items:baseline; gap:12px;
  padding:9px 10px; border-radius:12px; transition:background .12s;
}
.item + .item{margin-top:1px;}
.item:hover{background:var(--state);}  /* state layer M3 ~8% */
.pos{
  flex:0 0 auto; width:22px; text-align:right;
  font-family:"Roboto Flex",sans-serif; font-variant-numeric:tabular-nums;
  font-size:12px; color:var(--on-surface-variant); padding-top:1px;
}
.body{flex:1 1 auto; min-width:0;}
.name{
  color:var(--on-surface); text-decoration:none;
  word-break:break-word; line-height:1.35;
}
a.name:hover{text-decoration:underline; text-underline-offset:2px;}
.warn{margin-left:6px; font-size:12px; filter:grayscale(.1);}
.vol{
  flex:0 0 auto; align-self:center;
  font-family:"Roboto Flex",sans-serif; font-weight:500; font-size:11px;
  letter-spacing:.4px; color:var(--primary);
  background:var(--primary-tint); border-radius:8px; padding:3px 9px;
  white-space:nowrap;
}
/* Sensible: fondo ámbar suave + borde, NO se oculta */
.item.sensible{
  background:var(--sensible-bg);
  box-shadow:inset 0 0 0 1px var(--sensible-border);
}
.item.sensible:hover{background:var(--sensible-bg); filter:brightness(1.08);}
.item.sensible .name{color:var(--on-surface);}
.item.sensible .pos{color:var(--sensible);}
/* Error: fondo rojo suave + mensaje */
.item.error{
  background:var(--error-bg); color:var(--error);
  box-shadow:inset 0 0 0 1px var(--error-border);
  align-items:flex-start;
}
.item.error .msg{font-size:13px; line-height:1.4;}
.item.error:hover{background:var(--error-bg);}
/* Agrupación por comunidad (Reddit) */
.items.grouped{padding:6px 6px 10px;}
.group-head{
  list-style:none; margin:14px 8px 4px;
  font-family:"Roboto Flex",sans-serif; font-weight:700; font-size:11px;
  letter-spacing:1.2px; text-transform:uppercase; color:var(--primary);
}
.items.grouped > .group-head:first-child{margin-top:4px;}
.subgroup{list-style:none; margin:0 0 6px;}
.sub-head{
  display:flex; align-items:center; gap:6px;
  margin:6px 10px 2px; padding-bottom:3px;
  font-family:"Roboto Flex",sans-serif; font-weight:500; font-size:12px;
  color:var(--on-surface-variant); letter-spacing:.2px;
  border-bottom:1px solid var(--outline);
}
.sub-head::before{
  content:""; width:6px; height:6px; border-radius:50%;
  background:var(--on-surface-variant); flex:0 0 auto; opacity:.6;
}
.sub-list{list-style:none; margin:0; padding:0;}
/* Cuentas a revisar: tarjeta apilada bajo X, agrupada por RED */
.status.star{background:rgba(255,183,77,.16); color:var(--sensible);}
.acc-grid{
  display:grid; gap:16px;
  grid-template-columns:repeat(auto-fill, minmax(240px, 1fr));
}
.acc-net{
  background:var(--surface-container); border:1px solid var(--outline);
  border-radius:16px; padding:6px;
}
.acc-net-head{
  display:flex; align-items:center; gap:8px; padding:10px 12px 8px;
}
.acc-net-head h3{
  margin:0; font-family:"Roboto Flex",sans-serif; font-weight:700;
  font-size:12px; letter-spacing:1px; text-transform:uppercase;
  color:var(--primary); margin-right:auto;
}
.acc-net-head .n{
  font-family:"Roboto Flex",sans-serif; font-size:12px; font-weight:500;
  color:var(--on-surface-variant); background:var(--surface-container-high);
  border-radius:7px; padding:1px 8px;
}
.acc-cat{
  font-family:"Roboto Flex",sans-serif; font-weight:500; font-size:10.5px;
  letter-spacing:.6px; text-transform:uppercase; color:var(--on-surface-variant);
  margin:8px 10px 3px;
}
.acc-list{display:flex; flex-direction:column; gap:4px;}
.acc, .acc-row{
  display:flex; align-items:center; gap:11px;
  padding:8px 10px; border-radius:12px; text-decoration:none;
  color:var(--on-surface); transition:background .12s;
}
.acc:hover, .acc-row:hover{background:var(--state);}
.acc-avatar{
  flex:0 0 auto; width:34px; height:34px; border-radius:50%;
  display:inline-flex; align-items:center; justify-content:center;
  background:var(--surface-container-high); color:var(--primary);
  font-family:"Roboto Flex",sans-serif; font-weight:700; font-size:14px;
}
.acc-main{display:flex; flex-direction:column; min-width:0; flex:1 1 auto;}
.acc-name{
  font-family:"Roboto Flex",sans-serif; font-weight:500; font-size:13.5px;
  line-height:1.25; color:var(--on-surface);
  white-space:nowrap; overflow:hidden; text-overflow:ellipsis;
}
.acc-sub{
  font-size:11px; color:var(--on-surface-variant); letter-spacing:.2px;
  white-space:nowrap; overflow:hidden; text-overflow:ellipsis;
}
/* Banner de data desactualizada */
.stale{
  max-width:1500px; margin:10px auto 0; padding:10px 16px;
  background:var(--error-bg); border:1px solid var(--error-border);
  color:var(--error); border-radius:12px; font-size:13px; letter-spacing:.2px;
}
.stale b{color:var(--error);}
/* Botón "+" para agregar cuenta */
.acc-add{
  flex:0 0 auto; padding:6px 14px; border-radius:20px;
  border:1px solid var(--outline); background:var(--surface-container-high);
  color:var(--on-surface); font-size:13px; font-weight:500; line-height:1;
  font-family:"Roboto Flex",sans-serif; cursor:pointer;
  transition:background .12s, border-color .12s;
}
.acc-add:hover{background:var(--state); border-color:var(--primary);}
/* Formulario de agregar */
.acc-form{
  display:flex; flex-wrap:wrap; gap:8px; align-items:center;
  max-width:680px; margin-bottom:14px; padding:12px 14px;
  border:1px solid var(--outline); border-radius:12px;
  background:var(--surface-container);
}
.acc-form .acc-in{flex:1 1 180px;}
.acc-in{
  width:100%; padding:8px 10px; border-radius:9px;
  border:1px solid var(--outline); background:var(--surface-container);
  color:var(--on-surface); font-family:inherit; font-size:13px;
}
.acc-in:focus{outline:none; border-color:var(--primary);}
.acc-form-actions{display:flex; gap:8px; margin-top:2px;}
.acc-btn{
  flex:1 1 auto; padding:8px 10px; border-radius:9px; border:none;
  background:var(--primary); color:var(--on-primary);
  font-family:"Roboto Flex",sans-serif; font-weight:500; font-size:13px;
  cursor:pointer; transition:filter .12s;
}
.acc-btn:hover{filter:brightness(1.08);}
.acc-btn.ghost{
  background:transparent; color:var(--on-surface-variant);
  border:1px solid var(--outline);
}
/* Fila de cuenta agregada por el usuario (con botón borrar) */
.acc-row{justify-content:space-between;}
.acc-link{display:flex; align-items:center; gap:11px; flex:1 1 auto;
  min-width:0; text-decoration:none; color:inherit;}
.acc-del{
  flex:0 0 auto; width:24px; height:24px; border-radius:50%; border:none;
  background:transparent; color:var(--on-surface-variant); cursor:pointer;
  font-size:13px; opacity:0; transition:opacity .12s, background .12s;
}
.acc-row:hover .acc-del{opacity:1;}
.acc-del:hover{background:var(--error-bg); color:var(--error);}
footer.note{
  max-width:1400px; margin:0 auto; padding:4px 20px 28px;
  color:var(--on-surface-variant); font-size:12px; letter-spacing:.2px;
}
/* Columna apilada: trend + tarjeta secundaria debajo (cuentas / Instagram) */
.col-stack{display:flex; flex-direction:column; gap:16px; min-width:0;}
.accounts-ig .acc-body{padding:6px;}
.accounts-ig .acc-list{display:flex; flex-direction:column; gap:4px;}
/* Tarjeta de cuentas apilada bajo X (columna angosta) */
.col.accounts .acc-grid{display:block; padding:6px;}
.col.accounts .acc-net{background:transparent; border:none; padding:0; margin-bottom:8px;}
.col.accounts .acc-net-head{padding:8px 10px 4px;}
.col.accounts .acc-form{margin:8px; max-width:none;}
/* Secciones a todo el ancho (efemérides y noticias) */
.feed-wide{max-width:1500px; margin:18px auto 0; padding:0 20px;}
.feed-wide > .col-head{
  background:transparent; border:none; padding:4px 0 12px; position:static;
}
/* Efemérides de la semana */
.efem-grid{
  display:grid; gap:14px;
  grid-template-columns:repeat(auto-fill, minmax(240px, 1fr));
}
.efem-card{
  background:var(--surface-container); border:1px solid var(--outline);
  border-radius:16px; padding:12px 14px;
}
.efem-dia{
  font-family:"Roboto Flex",sans-serif; font-weight:700; font-size:12px;
  letter-spacing:.8px; text-transform:uppercase; color:var(--primary);
  margin-bottom:8px;
}
.efem-list{list-style:none; margin:0; padding:0; display:flex;
  flex-direction:column; gap:7px;}
.efem-dia-li{font-size:12.5px; line-height:1.35; color:var(--on-surface-variant);}
.efem-dia-li a{color:var(--on-surface); text-decoration:none;}
.efem-dia-li a:hover{text-decoration:underline;}
.efem-anio{
  font-family:"Roboto Flex",sans-serif; font-weight:700; color:var(--primary);
  font-variant-numeric:tabular-nums; margin-right:2px;
}
.efem-dia-li.conmem{color:var(--sensible);}
/* TOP: hero de noticias + tendencias de X al lado */
.top{
  display:grid; grid-template-columns:1fr; gap:16px;
  max-width:1500px; margin:0 auto; padding:16px 16px 0;
}
@media(min-width:900px){.top{grid-template-columns:1.9fr 1fr; padding:20px 20px 0;}}
/* Hero carrusel (estilo Mercado Negro) */
.hero{display:flex; flex-direction:column; gap:10px; min-width:0;}
.hero-stage{
  position:relative; border-radius:18px; overflow:hidden;
  aspect-ratio:16/10; background:var(--surface-container-high);
}
.hero-slide{
  position:absolute; inset:0; display:none; text-decoration:none;
  background-size:cover; background-position:center;
}
.hero-slide.active{display:block;}
.hero-overlay{
  position:absolute; inset:0; display:flex; flex-direction:column;
  justify-content:flex-end; gap:12px; padding:28px;
  background:linear-gradient(to top, rgba(0,0,0,.88) 0%, rgba(0,0,0,.35) 45%, rgba(0,0,0,0) 75%);
}
.hero-tag{
  align-self:flex-start; background:rgba(0,0,0,.55); color:#fff;
  font-family:"Roboto Flex",sans-serif; font-weight:600; font-size:11px;
  letter-spacing:1px; text-transform:uppercase; padding:4px 10px; border-radius:4px;
}
.hero-title{
  margin:0; color:#fff; font-family:"Roboto Flex",sans-serif; font-weight:700;
  font-size:27px; line-height:1.15; max-width:82%; text-shadow:0 1px 14px rgba(0,0,0,.55);
  display:-webkit-box; -webkit-line-clamp:3; -webkit-box-orient:vertical; overflow:hidden;
}
.hero-cta{
  align-self:flex-start; color:#fff; font-weight:600; font-size:13px;
  background:#E5392B; padding:8px 16px; border-radius:8px;
}
.hero-arrow{
  position:absolute; right:14px; width:40px; height:40px; border-radius:50%;
  border:none; background:rgba(255,255,255,.92); color:#111; font-size:22px;
  line-height:1; cursor:pointer; display:flex; align-items:center; justify-content:center;
}
.hero-arrow.next{top:calc(50% - 46px);}
.hero-arrow.prev{top:calc(50% + 6px);}
.hero-arrow:hover{background:#fff;}
.hero-thumbs{display:flex; gap:8px; overflow-x:auto; scrollbar-width:none; padding-bottom:2px;}
.hero-thumbs::-webkit-scrollbar{display:none;}
.hero-thumb{
  flex:0 0 92px; height:58px; border-radius:8px; border:2px solid transparent;
  background-size:cover; background-position:center; cursor:pointer; padding:0;
  background-color:var(--surface-container-high); opacity:.55;
  transition:opacity .12s, border-color .12s;
}
.hero-thumb.active{opacity:1; border-color:var(--primary);}
.hero-thumb:hover{opacity:1;}
"""

_SCRIPT = """
<script>
(function(){
  var KEY='trends-theme', root=document.documentElement,
      btn=document.getElementById('theme-toggle');
  function icon(t){return t==='light'?'\\u263E':'\\u2600\\uFE0F';} // luna / sol
  try{var s=localStorage.getItem(KEY); if(s) root.setAttribute('data-theme',s);}catch(e){}
  btn.querySelector('.icon').textContent=icon(root.getAttribute('data-theme'));
  btn.addEventListener('click',function(){
    var next=root.getAttribute('data-theme')==='light'?'dark':'light';
    root.setAttribute('data-theme',next);
    try{localStorage.setItem(KEY,next);}catch(e){}
    btn.querySelector('.icon').textContent=icon(next);
  });
})();
</script>
"""

# Aviso de data vieja: compara la fecha de los datos (DATA_FECHA, inyectada por
# render_html) con la fecha de HOY en el navegador. Si no coinciden, muestra el
# banner rojo. Así nunca trabajas sobre data de otro día sin darte cuenta.
_SCRIPT_FRESCURA = """
<script>
(function(){
  if(typeof DATA_FECHA==='undefined') return;
  var d=new Date();
  var hoy=d.getFullYear()+'-'+String(d.getMonth()+1).padStart(2,'0')+'-'
          +String(d.getDate()).padStart(2,'0');
  if(DATA_FECHA!==hoy){
    var b=document.getElementById('stale-banner');
    var s=document.getElementById('stale-date');
    if(s) s.textContent=DATA_FECHA;
    if(b) b.hidden=false;
  }
})();
</script>
"""

# Hero carrusel de noticias: slide activo + miniaturas + flechas + autoplay.
_SCRIPT_CARRUSEL = """
<script>
(function(){
  var stage=document.getElementById('hero-stage'),
      thumbs=document.getElementById('hero-thumbs'),
      prev=document.getElementById('hero-prev'),
      next=document.getElementById('hero-next');
  if(!stage) return;
  var slides=stage.querySelectorAll('.hero-slide'),
      ths=thumbs?thumbs.querySelectorAll('.hero-thumb'):[];
  if(!slides.length) return;
  var cur=0, n=slides.length, timer=null;
  function show(i){
    cur=(i+n)%n;
    slides.forEach(function(s,j){s.classList.toggle('active',j===cur);});
    ths.forEach(function(t,j){t.classList.toggle('active',j===cur);});
    var at=ths[cur]; if(at&&at.scrollIntoView) at.scrollIntoView({inline:'nearest',block:'nearest'});
  }
  function reset(){ if(timer) clearInterval(timer); timer=setInterval(function(){show(cur+1);},6000); }
  if(prev) prev.addEventListener('click',function(e){e.preventDefault();show(cur-1);reset();});
  if(next) next.addEventListener('click',function(e){e.preventDefault();show(cur+1);reset();});
  ths.forEach(function(t){t.addEventListener('click',function(){
    show(parseInt(this.getAttribute('data-i'),10)); reset();
  });});
  show(0); reset();
})();
</script>
"""

# Botón "Agregar cuenta": guarda en localStorage del navegador y dibuja las
# cuentas en el panel. No escribe en cuentas.txt (file:// no puede), pero
# persiste entre recargas. Para cuentas permanentes/compartibles está cuentas.txt.
_SCRIPT_CUENTAS = """
<script>
(function(){
  var KEY='trends-cuentas-extra';
  var form=document.getElementById('acc-form'),
      addBtn=document.getElementById('acc-add-btn'),
      cancel=document.getElementById('acc-cancel'),
      urlI=document.getElementById('acc-url'),
      nameI=document.getElementById('acc-name'),
      catI=document.getElementById('acc-cat'),
      grid=document.getElementById('acc-grid'),
      countEl=document.getElementById('acc-count');
  if(!form||!grid) return;
  var FIJAS=(typeof CUENTAS_FIJAS!=='undefined')?CUENTAS_FIJAS:[];
  function esc(s){return String(s).replace(/[&<>"]/g,function(c){
    return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];});}
  function load(){try{return JSON.parse(localStorage.getItem(KEY)||'[]');}catch(e){return [];}}
  function store(a){try{localStorage.setItem(KEY,JSON.stringify(a));}catch(e){}}
  function tipo(u){
    if(u.indexOf('/newsletters/')>-1) return 'newsletter';
    if(u.indexOf('/company/')>-1) return 'empresa';
    if(u.indexOf('linkedin.com/in/')>-1) return 'perfil';
    if(u.indexOf('instagram.com')>-1) return 'instagram';
    return 'link';
  }
  function red(u){
    if(u.indexOf('instagram.com')>-1) return 'Instagram';
    if(u.indexOf('linkedin.com')>-1) return 'LinkedIn';
    if(u.indexOf('tiktok.com')>-1) return 'TikTok';
    if(u.indexOf('youtube.com')>-1||u.indexOf('youtu.be')>-1) return 'YouTube';
    if(u.indexOf('x.com')>-1||u.indexOf('twitter.com')>-1) return 'X';
    try{return new URL(u).hostname.replace('www.','');}catch(e){return 'Otros';}
  }
  function host(u){try{return new URL(u).hostname.replace('www.','');}catch(e){return u;}}
  function nombreDe(u){var p=u.replace(/\\/+$/,'').split('/');return p[p.length-1]||u;}
  function card(it,idx){
    var nm=it.nombre||nombreDe(it.url);
    var del=(idx!==null)?'<button class="acc-del" data-i="'+idx+'" title="Quitar">\\u2715</button>':'';
    return '<div class="acc-row">'
      +'<a class="acc-link" href="'+esc(it.url)+'" target="_blank" rel="noopener">'
      +'<span class="acc-avatar">'+esc((nm[0]||'+').toUpperCase())+'</span>'
      +'<span class="acc-main"><span class="acc-name">'+esc(nm)+'</span>'
      +'<span class="acc-sub">'+esc(host(it.url))+' \\u00b7 '+tipo(it.url)+'</span></span></a>'
      +del+'</div>';
  }
  function listaPorCat(cats, r){
    var h='';
    Object.keys(cats).forEach(function(c){
      if(c && c.toLowerCase()!==r.toLowerCase())
        h+='<div class="acc-cat">'+esc(c)+'</div>';
      h+='<div class="acc-list">';
      cats[c].forEach(function(o){h+=card(o.it,o.idx);});
      h+='</div>';
    });
    return h;
  }
  function bind(root){
    if(!root) return;
    root.querySelectorAll('.acc-del').forEach(function(b){
      b.addEventListener('click',function(){
        var a=load(); a.splice(parseInt(this.getAttribute('data-i'),10),1); store(a); render();
      });
    });
  }
  function render(){
    var extra=load();
    var todas=FIJAS.map(function(it){return {it:it,idx:null};})
      .concat(extra.map(function(it,i){return {it:it,idx:i};}));
    if(countEl) countEl.textContent=todas.length;
    // agrupa por RED -> dentro, por categoría (preservando orden de aparición)
    var redes={}, ordenRed=[];
    todas.forEach(function(o){
      var r=red(o.it.url);
      if(!redes[r]){redes[r]={}; ordenRed.push(r);}
      var c=o.it.cat||'Otros';
      (redes[r][c]=redes[r][c]||[]).push(o);
    });
    // Instagram va a su tarjeta bajo Google; el resto a la banda de cuentas
    var igBox=document.getElementById('acc-ig'),
        igCount=document.getElementById('acc-ig-count');
    if(igBox){
      var cats=redes['Instagram'], n=0;
      if(cats){Object.keys(cats).forEach(function(c){n+=cats[c].length;});}
      igBox.innerHTML=cats?listaPorCat(cats,'Instagram'):'';
      if(igCount) igCount.textContent=n||'';
      bind(igBox);
    }
    var h='';
    ordenRed.forEach(function(r){
      if(r==='Instagram' && igBox) return;  // ya renderizada bajo Google
      var cats=redes[r], total=0;
      Object.keys(cats).forEach(function(c){total+=cats[c].length;});
      h+='<section class="acc-net"><div class="acc-net-head">'
        +'<h3>'+esc(r)+'</h3><span class="n">'+total+'</span></div>';
      h+=listaPorCat(cats,r);
      h+='</section>';
    });
    if(grid){ grid.innerHTML=h; bind(grid); }
  }
  addBtn.addEventListener('click',function(){
    form.hidden=!form.hidden; if(!form.hidden) urlI.focus();
  });
  cancel.addEventListener('click',function(){form.hidden=true; form.reset();});
  form.addEventListener('submit',function(e){
    e.preventDefault();
    var url=urlI.value.trim(); if(!url) return;
    var a=load();
    a.push({url:url, nombre:nameI.value.trim(), cat:(catI.value.trim()||'')});
    store(a); render(); form.reset(); form.hidden=true;
  });
  render();
})();
</script>
"""


def render_html(resultados: list[SourceResult], fecha: str,
                noticias_res=None, efemerides_res=None) -> Path:
    # localizar fuentes por nombre (orden robusto)
    def _buscar(clave):
        for r in resultados:
            if clave in r.fuente.lower():
                return r
        return None

    r_x = _buscar("x chile") or _buscar("x ")
    r_google = _buscar("google")
    r_reddit = _buscar("reddit")
    otras = [r for r in resultados if r not in (r_x, r_google, r_reddit)]

    cuentas_card = _cuentas_html(config.cargar_cuentas())

    # TOP: hero de noticias (Mercado Negro style) + tendencias de X al lado
    hero = _noticias_html(noticias_res)
    col_x = _col_html(r_x) if r_x else ""
    top = f'<div class="top">{hero}{col_x}</div>'

    # GRID inferior: Google (+Instagram), Reddit, Cuentas + cualquier otra fuente
    celdas = []
    if r_google:
        celdas.append(
            f'<div class="col-stack">{_col_html(r_google)}{_ig_card_html()}</div>'
        )
    if r_reddit:
        celdas.append(_col_html(r_reddit))
    celdas.append(cuentas_card)
    for r in otras:
        celdas.append(_col_html(r))
    columnas = "".join(celdas)
    badges = "".join(
        f'<span class="badge {"ok" if r.ok else "down"}">'
        f'{escape(r.fuente)} <b>{sum(1 for it in r.items if not it.error)}</b>'
        "</span>"
        for r in resultados
    )
    sensibles = sum(1 for r in resultados for it in r.items if it.sensible)

    html = (
        "<!doctype html>\n"
        '<html lang="es" data-theme="dark"><head><meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        '<meta http-equiv="Cache-Control" content="no-store, max-age=0">\n'
        f"<title>Tablero de Tendencias — {fecha}</title>\n"
        f"{_FONTS}<style>{_CSS}</style></head>\n"
        "<body>\n"
        '<header class="appbar">\n'
        '  <div class="appbar-main">\n'
        "    <h1>¿De qué se está hablando hoy?</h1>\n"
        f'    <p class="meta">{fecha} · generado {now_iso()[11:16]} · '
        f"{sensibles} sensible(s) ⚠️</p>\n"
        "  </div>\n"
        f'  <div class="badges">{badges}</div>\n'
        '  <button id="theme-toggle" class="toggle" type="button" '
        'aria-label="Cambiar tema claro/oscuro"><span class="icon">☀️</span></button>\n'
        "</header>\n"
        '<div id="stale-banner" class="stale" hidden>⚠️ <b>Data desactualizada</b> — '
        'estás viendo lo recolectado el <span id="stale-date"></span>. '
        "Corre el tablero para actualizar.</div>\n"
        f"{top}\n"
        f'<main class="grid">{columnas}</main>\n'
        f'{_efemerides_html(efemerides_res)}\n'
        '<footer class="note">⚠️ = keyword sensible: resalta para revisar criterio, '
        "no descarta ni clasifica nada automáticamente. "
        "Herramienta interna de monitoreo.</footer>\n"
        f"{_SCRIPT}"
        f'<script>var DATA_FECHA="{fecha}";</script>'
        f"{_SCRIPT_FRESCURA}{_SCRIPT_CUENTAS}{_SCRIPT_CARRUSEL}"
        "</body></html>"
    )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    # Solo un archivo fijo: evita acumular HTML con fecha (que confunden en el
    # navegador). El histórico de datos vive en los JSON con fecha.
    ruta = OUTPUT_DIR / "trends_latest.html"
    ruta.write_text(html, encoding="utf-8")
    return ruta


def _abrir_navegador(uri: str) -> None:
    """Abre el tablero en el navegador de config.NAVEGADOR (ej. Vivaldi).
    Cae al navegador por defecto del sistema si no se encuentra."""
    import shutil

    binario = getattr(config, "NAVEGADOR", "") or ""
    ruta_bin = shutil.which(binario) if binario else None
    if ruta_bin:
        try:
            webbrowser.get(f"{ruta_bin} %s").open(uri)
            return
        except webbrowser.Error:
            pass
    webbrowser.open(uri)  # fallback: navegador por defecto


def _fetch_aislado(modulo):
    """Corre una fuente extra (noticias/efemérides) sin tumbar el tablero."""
    try:
        return modulo.fetch()
    except Exception as exc:  # red de seguridad
        nombre = getattr(modulo, "FUENTE", modulo.__name__)
        return SourceResult(fuente=nombre, items=[], ok=False, detalle=str(exc))


def main(abrir: bool = True) -> None:
    fecha = now_iso()[:10]
    resultados = recolectar()
    noticias_res = _fetch_aislado(noticias)
    efemerides_res = _fetch_aislado(efemerides)
    ruta_json = guardar_json(resultados, fecha, noticias_res, efemerides_res)
    # render_html escribe el archivo fijo trends_latest.html (marcador estable
    # en el navegador) -> nunca quedas mirando un archivo viejo por error.
    ruta_html = render_html(resultados, fecha, noticias_res, efemerides_res)

    # Copia lista para servir (deploy en Vercel): public/index.html + json.
    # Vercel sirve el directorio public/ como raíz del sitio.
    public = OUTPUT_DIR.parent.parent / "public"
    public.mkdir(parents=True, exist_ok=True)
    (public / "index.html").write_text(ruta_html.read_text(encoding="utf-8"), encoding="utf-8")
    (public / "trends_latest.json").write_text(
        (OUTPUT_DIR / "trends_latest.json").read_text(encoding="utf-8"), encoding="utf-8"
    )

    total = sum(len(r.items) for r in resultados)
    caidas = [r.fuente for r in resultados if not r.ok]
    print(f"Tablero generado para {fecha}: {total} items de {len(resultados)} fuente(s).")
    if caidas:
        print(f"  ⚠️ Fuentes con problemas: {', '.join(caidas)}")
    print(f"  JSON: {ruta_json}")
    print(f"  HTML: {ruta_html}  ← marca este en el navegador")
    print(f"  Deploy: {public}/  (index.html + trends_latest.json)")

    if abrir:
        _abrir_navegador(ruta_html.as_uri())


if __name__ == "__main__":
    main(abrir="--no-open" not in sys.argv)
