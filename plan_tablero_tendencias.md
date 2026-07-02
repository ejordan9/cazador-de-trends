# Tablero Agregador de Tendencias — Plan + Aprendizajes

> Documento de traspaso. Pensado para que otra IA (o yo mismo en otra sesión) retome el trabajo sin perder contexto.
> Autor del flujo: Enmanuel (analista de social listening, cliente Entel / agencia Tooldata).
> Fecha de redacción: 11/06/2026.

---

## 1. Objetivo

Reducir el tiempo de búsqueda manual al armar el status diario **"¿De qué se está hablando hoy?"**.

**NO se busca** automatizar el status completo. Se busca un **tablero agregador** que junte las tendencias de varias fuentes en una sola vista, para no tener que abrir 5 pestañas distintas.

Principio rector: *"Si en un tablero ya veo las tendencias de 3 sitios, son 3 sitios menos que buscar."*

---

## 2. Diagnóstico del flujo (qué se automatiza y qué no)

El trabajo de armar el status tiene dos mitades muy distintas:

| Mitad | Tarea | ¿Automatizable? |
|-------|-------|-----------------|
| **Recolección** | Mirar trends de X/TikTok/Reddit, copiar hashtag + link | ✅ Sí |
| **Criterio editorial** | Decidir contexto, flag de sensibilidad, descartes, detección de patrones | ❌ No (y no debería serlo — es el valor del analista) |

**La meta NO es que un script escriba el status.** Es que entregue la materia prima ordenada para aplicar criterio en ~15 min en vez de ~90.

---

## 3. Lo que NO se automatiza (a propósito)

- La decisión `monitoreo vs. oportunidad de contenido`. La revisa siempre el analista.
- El descarte de temas difusos (ej: "Nakamura" se descartó hoy por no tener nada representativo).
- La detección de patrones nuevos (ej: el meme de "El grupo de Chile" — nace de la lectura humana, luego se vuelve regla).

---

## 4. Arquitectura propuesta (modular)

Diseño modular desde el inicio: **cada fuente es una función que devuelve la misma estructura**, para poder sumar fuentes sin reescribir el resto.

### Estructura de datos común (contrato entre módulos)

Cada fuente devuelve una lista de items con este shape:

```python
{
    "fuente": "X Chile",        # str: nombre legible de la fuente
    "tema": "#VolveriasConTuEx2",  # str: hashtag / título / keyword
    "volumen": "12 mil",        # str|None: volumen aprox si está disponible
    "link": "https://..."       # str: link directo al trend o búsqueda
}
```

### Layout de carpetas

```
trends_board/
├── sources/
│   ├── x_chile.py        # getdaytrends.com/es/chile (scraping, SIN API key)
│   ├── reddit.py         # Reddit API (r/chile, r/peliculas, r/popculturechat)
│   └── google_trends.py  # pytrends (Google Trends Chile)
├── board.py              # orquesta: llama cada fuente, junta y renderiza
└── output/
    └── trends_YYYY-MM-DD.html
```

---

## 5. Roadmap por fases

### Fase 1 — Recolector de trends (Python puro) ← EMPEZAR AQUÍ
- Scraping de `getdaytrends.com/es/chile/` para X.
- Reddit API para subreddits clave.
- pytrends para Google Trends Chile.
- Output: tablero (formato a definir — ver sección 7) con `fuente | tema | volumen | link`.
- **Solo recolecta y muestra. No clasifica nada.**

### Fase 2 — Enriquecedor de contexto (Claude API) [OPCIONAL / futuro]
- Por cada tema, llamada a API que sugiere: contexto 1-2 líneas + flag tentativo (`sensible / liviano / marca`).
- Output: mismo tablero + columnas `contexto_borrador` y `flag_sugerido`.
- **Son BORRADORES.** El analista valida, no ejecuta a ciegas.

### Fase 3 — Generador de plantilla [OPCIONAL / futuro]
- Apps Script toma el tablero ya revisado y genera el markdown del status en el formato exacto.
- Copy-paste final.

---

## 6. Orden de implementación (más fácil primero)

1. **Scraper getdaytrends (X Chile)** — el más fácil. HTML público, sin login, sin API key. `requests` + `BeautifulSoup`, ~30 líneas.
2. **Reddit API** — requiere credenciales (gratis), pero API estable y documentada.
3. **Google Trends (pytrends)** — gratis, sin key, pero la librería es no-oficial y a veces se rompe con cambios de Google.

> Nota sobre fuentes pagas descartadas: la **API oficial de X ya no tiene tier gratuito útil** (desde feb 2026 es pay-per-use, ~$0.005/lectura, sin asignación gratis para prototipar). Por eso se opta por **scraping de páginas públicas de trends** en lugar de la API oficial. Terceros como TwitterAPI.io / GetXAPI existen (centavos al mes) pero rompen la filosofía open-source y suman dependencia externa.

---

## 7. Decisiones PENDIENTES (resolver antes de codear)

Enmanuel va a delegar la implementación a otra IA. Antes de arrancar, definir:

- [ ] **Formato de salida del tablero:** HTML local (abrir en Brave) / CSV-Sheet filtrable / Terminal.
- [ ] **Nivel de detalle del scraper X:** solo top 10 / todos + volumen / trends + link directo a búsqueda.
- [ ] **Subreddits exactos** a monitorear (hoy aparecieron: r/chile, r/peliculas, r/popculturechat).
- [ ] **Frecuencia:** ejecución manual on-demand vs. cron diario.

---

## 8. Stack técnico del usuario (contexto para quien implemente)

- SO: **CachyOS** (Arch-based Linux) en HP Victus.
- Navegador: Brave Origin Nightly.
- Lenguaje preferido: **Python** (en roadmap de aprendizaje "Operación BLACKOUT": pandas, SQL, en progreso OOP).
- Herramientas de gestión: TickTick, Obsidian (segundo cerebro), Monday.com.
- Filosofía: prioriza **open-source y privacy-focused**; evita dependencias de Big Tech / terceros cuando hay alternativa.
- Aprende mejor con **ejemplos prácticos y scripts aplicados**.

---

## 9. Aprendizajes editoriales del status (criterios a preservar)

Estos son los criterios que el analista aplicó hoy y que **NO debe perder** la automatización. Sirven como "reglas de negocio" del reporte.

### Formato del status
- Título: `¿De qué se está hablando hoy? | DD/MM`
- Estructura fija de secciones: **Lectura general → X → TikTok → Reddit → Otros temas → Marcas & Marketing**.
- Cada item: `**Tema**` en negrita + contexto 1-2 líneas + enlace directo al final.
- **Enlace directo, SIN el prefijo "Link:".** (Preferencia confirmada por el usuario.)
- "Lectura general" se redacta AL FINAL, una vez cargado todo.
- Orden de sentimiento, cuando aplica: positivo → neutro → negativo.

### Criterios de clasificación
- **Temas políticos sensibles → solo monitoreo, nunca oportunidad de contenido.** Ej: "Boric" (juicio político a exministro) se marcó "mantener solo en monitoreo".
- **Temas con roce político contingente → revisar antes de considerar como oportunidad.** Ej: "Neme" (conductor TV) por su cruce con CAE / secreto bancario.
- **Descartar temas difusos / sin contenido representativo.** Ej: "Nakamura" se sacó por no tener un tweet o ángulo claro.
- **Cluster de hashtags relacionados:** agrupar mentalmente aunque se reporten por separado. Ej: #Justice_For_SevEN + #sevEN_Means_Fate + #ENGENEs_Always_For_Enhypen = misma campaña del fandom ENGENE (ENHYPEN, salida de Heeseung).

### PATRÓN DETECTADO HOY — "Humor de ausencia mundialista"
- **Qué es:** memes que convierten la NO clasificación de Chile al Mundial 2026 en contenido de autoescarnio (Chile emparejado con objetos cotidianos: "Grupo S" = Televisor, Netflix, Sillón).
- **Por qué importa:** alta viralidad + identificación local + tono liviano = oportunidad de contenido cercano para marcas chilenas durante todo el Mundial.
- **Señal de monitoreo:** formatos tipo "Grupo de Chile", "la selección de [X]", parodias de fixture. Recurrente mientras dure el torneo.
- **Cautela:** es humor amable, no funa. Sin riesgo reputacional, pero medir el tono para que la marca no se vea oportunista.

---

## 10. Snapshot del status de hoy (09/06) — fuentes usadas

Referencia de qué plataformas y cuántos temas se cubrieron, para dimensionar el alcance del tablero:

| Sección | Nº temas | Fuente de descubrimiento |
|---------|----------|--------------------------|
| X | 9 | Trends de X Chile (manual) |
| TikTok | 3 | TikTok / Creative Center (manual) |
| Reddit | 2 | r/chile, r/peliculas (manual) |
| Otros temas | 2-3 | Mixto (X, LinkedIn, observación) |
| Marcas & Marketing | 1 | Medios de marketing / observación |

Las 3 fuentes con mayor ROI para automatizar primero: **X Chile, Reddit, Google Trends.** (TikTok Creative Center y LinkedIn quedan para una fase posterior por mayor fricción de scraping/API.)

---

## 11. Próximo paso concreto

Enmanuel avisará cuándo retomar. Cuando lo haga:
1. Resolver los 4 pendientes de la sección 7.
2. Implementar `sources/x_chile.py` (scraper getdaytrends) como primer entregable.
3. Validar que devuelve el contrato de datos de la sección 4.
4. Recién entonces sumar Reddit y Google Trends.

---

## 12. Estado de implementación (actualizado 11/06/2026)

**Fase 1.1 — X Chile: HECHA.** Código en `trends_board/` (ver `trends_board/README.md`).

Decisiones de la sección 7 ya resueltas en la implementación:
- **Formato:** JSON como capa de datos + HTML como vista (no CSV). El JSON deja
  histórico para comparar día a día.
- **Detalle scraper X:** top 20 + posición + link a búsqueda en X. Volumen queda
  pendiente (no está en la página de listado de getdaytrends).
- **Subreddits / frecuencia:** en `config.py`; ejecución manual on-demand por ahora.

Cambios incorporados sobre el plan original (auditoría):
- **Aislamiento de fallos por fuente:** una fuente caída devuelve `ok=False` con un
  item de error visible, sin tumbar el tablero. Probado.
- **Guardado de HTML crudo** en `output/raw/` para depurar cuando el scraper se rompa.
- **Marcado de keywords sensibles** (🔶): resalta, no clasifica ni descarta.

**Fase 1.3 — Google Trends: HECHA.** `sources/google_trends.py`, vía feed RSS
oficial (`trends.google.com/trending/rss?geo=CL`) en vez de pytrends. Sin API key,
trae volumen aproximado (`approx_traffic`) y se parsea con `xml.etree` (stdlib, sin
dependencia extra).

**Fase 1.2 — Reddit: HECHA (con cambio de enfoque).** Se descartó la API OAuth:
el endpoint `.json` sin auth devuelve 403 y la creación de apps en reddit.com/prefs/apps
fallaba (recargaba sin crear). Solución: feed RSS `r/<sub>/hot.rss`, **sin credenciales**.
No trae score (volumen=None); el orden de `hot` es el ranking. Cada subreddit falla
aislado y hay reintento con backoff ante 429.

**FASE 1 COMPLETA.** El tablero combina X + Google + Reddit (~55 items) en una sola
vista HTML, con JSON de respaldo. Ver `trends_board/README.md`.

---

## 13. Mejoras de UX y operación (actualizado 15/06/2026)

**Diseño Material 3.** La vista HTML se rediseñó siguiendo Material Design 3:
tokens de color como CSS vars, modo oscuro por defecto con toggle claro/oscuro
(persistido en localStorage), tipografía Roboto Flex/Roboto, layout responsive
mobile-first (breakpoint 768px). Header fijo con badge por fuente.

**Reddit agrupado por comunidad.** `config.SUBREDDITS` es un dict
`{etiqueta de grupo: query}`. La columna de Reddit se muestra en dos niveles:
grupo (Chile, Marketing, Viral…) → subreddit (`r/chile`…) → posts renumerados.
El RSS limita a ~1 req/12s: el código respeta `x-ratelimit-*` y agrupa subs en
multireddits (`a+b+c`) para que ~5 requests tomen ~1 min.

**Columna lateral "Cuentas a revisar" (estilo Threads).** Marcadores manuales
(perfiles/newsletters de LinkedIn, Instagram…) que NO se scrapean. 4ª columna
sticky en desktop. Dos formas de gestionarlas:
- **Archivo `trends_board/cuentas.txt`** — texto plano, una URL por línea bajo su
  categoría. Editable en cualquier editor/Obsidian. Es la fuente permanente.
- **Botón "+" en el panel** — guarda en localStorage del navegador (file:// no
  puede escribir en disco). Persiste entre recargas, vive solo en ese navegador.

**Data siempre fresca (anti-data-vieja).** Riesgo de trabajo identificado por el
usuario: ver data de otro día. Dos protecciones:
- `board.py` escribe un archivo fijo **`output/trends_latest.html`** (siempre la
  última corrida) y lo abre. Es el que se marca en el navegador.
- **Banner rojo de "data desactualizada"**: JS compara la fecha de los datos con
  la fecha de hoy del navegador; si difieren, avisa arriba de todo.

**Navegador.** Abre en **Vivaldi** (`config.NAVEGADOR`), con fallback al navegador
por defecto si no se encuentra.

**Automatización diaria (systemd user timer).** `~/.config/systemd/user/
trends-board.{service,timer}` corren `board.py --no-open` cada día 08:30.
`Persistent=true`: si el laptop estaba apagado/suspendido, corre al encender.
Comandos útiles:
- Ver estado / próxima corrida: `systemctl --user list-timers trends-board.timer`
- Correr ahora: `systemctl --user start trends-board.service`
- Logs: `journalctl --user -u trends-board.service`
- Cambiar la hora: editar `OnCalendar` en el `.timer` y `systemctl --user daemon-reload`

Posibles siguientes pasos: Fase 2 (enriquecedor de contexto con Claude API),
comparación día-a-día sobre el histórico JSON, exportar las cuentas del botón a
`cuentas.txt`, o sumar más subreddits/fuentes.
