# Tablero Agregador de Tendencias

Recolector de trends de varias fuentes en una sola vista. Ver `../plan_tablero_tendencias.md` para el contexto completo.

## Correr

```bash
# desde la raíz del proyecto
.venv/bin/python trends_board/board.py            # recolecta y abre el HTML (en Vivaldi)
.venv/bin/python trends_board/board.py --no-open  # solo recolecta, no abre navegador

# probar una fuente aislada
.venv/bin/python trends_board/sources/x_chile.py
```

**Marca en el navegador `output/trends_latest.html`** — siempre apunta a la última
corrida, así nunca abres data vieja por error.

Salidas en `output/`:
- `trends_latest.html` — **archivo fijo** con la corrida más reciente (el que se marca).
- `trends_YYYY-MM-DD.html` — vista del día (histórico).
- `trends_YYYY-MM-DD.json` — capa de datos (histórico, base para comparar día a día).
- `raw/<fuente>_YYYY-MM-DD.*` — respuesta cruda, para depurar cuando una fuente se rompa.

## Actualización automática (systemd user timer)

Corre solo cada mañana (08:30) y deja `trends_latest.html` fresco:

```bash
systemctl --user list-timers trends-board.timer   # ver próxima corrida
systemctl --user start trends-board.service       # correr ahora
journalctl --user -u trends-board.service         # logs
```

Unidades en `~/.config/systemd/user/trends-board.{service,timer}`. Tiene
`Persistent=true`: si el laptop estaba apagado a las 08:30, corre al encender.
Para cambiar la hora: editar `OnCalendar` en el `.timer` + `systemctl --user daemon-reload`.

Si la data mostrada no es de hoy, el tablero muestra un **banner rojo de alerta**.

## Cuentas a revisar (marcadores manuales)

Columna lateral con perfiles/newsletters que se revisan a mano (no se scrapean).
Dos formas de gestionarlas:
- **`cuentas.txt`** — texto plano, una URL por línea bajo su `# categoría`. Fuente
  permanente, editable en cualquier editor. Formato: `Nombre | url`  o solo `url`.
- **Botón "+"** en el panel — guarda en el navegador (localStorage). Rápido, pero
  vive solo en ese navegador (file:// no puede escribir en disco).

## Arquitectura

- `contract.py` — `TrendItem` (incl. campo `grupo`) y `SourceResult`: el contrato que toda fuente respeta.
- `config.py` — qué se monitorea (país, top-N, subreddits por grupo, keywords sensibles, cuentas, navegador). Editar acá, no el código.
- `cuentas.txt` — lista editable de cuentas a revisar (la lee `config.cargar_cuentas()`).
- `sources/` — una fuente por archivo. Cada una expone `fetch() -> SourceResult` y **nunca** lanza hacia arriba: si falla, devuelve `ok=False` con un item de error visible.
- `board.py` — orquesta las fuentes, guarda JSON, renderiza HTML (Material 3) y abre el navegador.

## Sumar una fuente

1. Crear `sources/mi_fuente.py` con `FUENTE = "..."` y `def fetch() -> SourceResult`.
2. Importarla y agregarla a la lista `FUENTES` en `board.py`.

## Estado

- [x] **Fase 1.1 — X Chile** (getdaytrends, scraping sin API key).
- [x] **Fase 1.3 — Google Trends** (feed RSS oficial, sin key, con volumen).
- [x] **Fase 1.2 — Reddit** (feed RSS `r/<sub>/hot.rss`, sin credenciales).

**Fase 1 completa.** Las 3 fuentes corren y combinan en un solo tablero, con diseño
Material 3, Reddit agrupado por comunidad, columna de cuentas, archivo `latest`
fijo, banner anti-data-vieja y corrida automática diaria.

## Notas

- El marcado 🔶 "sensible" **no descarta ni clasifica nada**: solo resalta para que el analista revise. El criterio editorial sigue siendo humano (ver sección 3 del plan).
- El volumen de tweets no está en la página de listado de getdaytrends; quedaría como mejora (1 request extra por trend a la página de detalle).
- **Reddit:** se usa el feed RSS, no la API OAuth. El endpoint `.json` sin auth devuelve 403 y la creación de apps falló; el RSS sigue abierto y sin credenciales. No trae score (volumen=None); el orden de `hot` es el ranking.
- **Rate limit de Reddit:** el RSS limita a ~1 request cada 12s (`x-ratelimit-*`). El código lo respeta automáticamente (espera el `reset` del header, con reintento). Para no tardar minutos se usa una estrategia **híbrida** en `config.SUBREDDITS`: lo relevante al trabajo (Chile, Marketing, OutOfTheLoop) va separado con cuota propia; el resto se agrupa en multireddits (`a+b+c`) para ahorrar requests. ~5 requests ≈ 1 min. Cada post conserva su subreddit real (vía `<category>`), aunque venga de un multireddit.
- **Reddit agrupado por comunidad:** `config.SUBREDDITS` es un dict `{etiqueta de grupo: query}`. En el tablero, la columna de Reddit se muestra en dos niveles: encabezado de grupo (ej. *Chile*, *Marketing*) → subtítulo por subreddit (`r/chile`, `r/RepublicadeChile`) → posts renumerados dentro de cada comunidad. El campo `grupo` del `TrendItem` (en `contract.py`) habilita esto de forma genérica; el resto de fuentes lo dejan en None y se renderizan como lista plana.
