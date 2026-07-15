"""La página de vertimiento del Observatorio (ADR-012): HTML estático autocontenido.

Misma filosofía que el dashboard demo (ADR-011): HTML/CSS/SVG vanilla en un solo
documento, gráficos renderizados **server-side** (testeables sin navegador), un
tooltip JS mínimo que enriquece pero nunca es la única vía al dato (la tabla
mensual es la vista de respaldo), modo claro/oscuro por `prefers-color-scheme`.
Paleta categórica validada con el método dataviz en ambos modos (orden de apilado
= orden de slots; el amarillo/magenta sub-3:1 en claro se releva con etiquetas
directas + tabla).
"""

from __future__ import annotations

import html
import json
from collections.abc import Iterable, Mapping, Sequence

from acopia.infrastructure.ingesta.reducciones_erv import ReduccionDiaria
from acopia.interfaces.observatorio.agregados import (
    perfil_horario_mwh,
    top_centrales,
    total_mensual_gwh,
)

# Orden fijo de apilado (abajo → arriba) = orden de slots validado por el validador
# del skill dataviz (claro y oscuro, pares adyacentes): PASS en todas las puertas.
TECNOLOGIAS: tuple[str, ...] = ("solar", "eolica", "hidro_pasada", "hidro_embalse")
_ETIQUETAS = {
    "solar": "Solar",
    "eolica": "Eólica",
    "hidro_pasada": "Hidro pasada",
    "hidro_embalse": "Hidro embalse",
}
_MESES_ES = (
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
)

_ANCHO = 960


def render_vertimiento(
    registros: Iterable[ReduccionDiaria], generado_el: str, enlace_demo: bool = False
) -> str:
    """Arma la página completa desde los registros de `leer_reducciones_erv`.

    ``enlace_demo`` agrega el enlace al snapshot del dashboard (`demo.html`) cuando
    el sitio se genera completo (ADR-012 absorbe la publicación de ADR-011).
    """
    registros = tuple(registros)
    if not registros:
        raise ValueError("Sin registros de vertimiento: no hay página que generar")

    mensual = total_mensual_gwh(registros)
    meses = sorted({mes for mes, _ in mensual})
    perfil = perfil_horario_mwh(registros)
    top = top_centrales(registros, n=10)

    total_gwh = sum(mensual.values())
    total_solar_gwh = sum(v for (_, tec), v in mensual.items() if tec == "solar")
    horas_perfil = [sum(p[i] for p in perfil.values()) for i in range(24)]
    hora_pico = horas_perfil.index(max(horas_perfil)) + 1
    n_centrales = len({r.central for r in registros})

    return (
        _PLANTILLA.replace("__PERIODO__", html.escape(_periodo(meses)))
        .replace("__GENERADO__", html.escape(generado_el))
        .replace("__KPI_TOTAL__", f"{total_gwh:,.0f}")
        .replace("__KPI_SOLAR_PCT__", f"{total_solar_gwh * 100 / total_gwh:.0f}%")
        .replace("__KPI_HORA_PICO__", f"{hora_pico}:00")
        .replace("__KPI_CENTRALES__", str(n_centrales))
        .replace("__LEYENDA__", _leyenda())
        .replace("__SVG_MENSUAL__", _svg_mensual(meses, mensual))
        .replace("__SVG_PERFIL__", _svg_perfil(perfil))
        .replace("__SVG_TOP__", _svg_top(top))
        .replace("__FILAS_TABLA__", _filas_tabla(meses, mensual))
        .replace(
            "__ENLACE_DEMO__",
            ' · <a href="demo.html">ver la demo del motor</a>' if enlace_demo else "",
        )
    )


def _periodo(meses: Sequence[str]) -> str:
    """``["2026-01", "2026-05"]`` -> ``"enero - mayo 2026"`` (con guión largo en la página)."""
    def nombre(mes: str) -> str:
        return _MESES_ES[int(mes[5:7]) - 1]

    primero, ultimo = meses[0], meses[-1]
    if primero == ultimo:
        return f"{nombre(primero)} {primero[:4]}"
    if primero[:4] == ultimo[:4]:
        return f"{nombre(primero)} – {nombre(ultimo)} {primero[:4]}"
    return f"{nombre(primero)} {primero[:4]} – {nombre(ultimo)} {ultimo[:4]}"


def _leyenda() -> str:
    piezas = [
        f'<span class="clave"><i class="sw {tec}"></i>{html.escape(_ETIQUETAS[tec])}</span>'
        for tec in TECNOLOGIAS
    ]
    return f'<div class="leyenda">{"".join(piezas)}</div>'


def _tick_limpio(maximo: float) -> float:
    """Techo 'redondo' para el eje Y (1/2/2.5/5 x 10^n por sobre el máximo)."""
    if maximo <= 0:
        return 1.0
    magnitud = 10.0 ** len(str(int(maximo)))
    for factor in (0.1, 0.2, 0.25, 0.5, 1.0):
        if maximo <= magnitud * factor:
            return magnitud * factor
    return magnitud


def _fmt(valor: float) -> str:
    return f"{valor:,.1f}" if valor < 100 else f"{valor:,.0f}"


def _barra_apilada(
    x: float, ancho: float, valores: Sequence[float], techo: float,
    alto_plot: float, y0: float,
) -> str:
    """Segmentos de una columna apilada: gap de 2px de superficie, tope redondeado 4px."""
    partes: list[str] = []
    y = y0 + alto_plot
    visibles = [(tec, v) for tec, v in zip(TECNOLOGIAS, valores, strict=True) if v > 0]
    for orden, (tec, valor) in enumerate(visibles):
        alto = valor / techo * alto_plot
        y -= alto
        es_tope = orden == len(visibles) - 1
        alto_px = max(alto - 2.0, 0.75)  # el gap de 2px lo pone la superficie, no un borde
        if es_tope and alto_px >= 4:
            r = 4.0
            partes.append(
                f'<path class="serie {tec}" d="M{x:.1f},{y + alto_px:.1f} v{-(alto_px - r):.1f} '
                f"q0,-{r} {r},-{r} h{ancho - 2 * r:.1f} q{r},0 {r},{r} "
                f'v{alto_px - r:.1f} z"/>'
            )
        else:
            partes.append(
                f'<rect class="serie {tec}" x="{x:.1f}" y="{y:.1f}" '
                f'width="{ancho:.1f}" height="{alto_px:.1f}"/>'
            )
    return "".join(partes)


def _eje_y(techo: float, alto_plot: float, y0: float, unidad: str) -> str:
    partes = []
    for i in range(5):
        frac = i / 4
        y = y0 + alto_plot * (1 - frac)
        valor = techo * frac
        etiqueta = f"{valor:,.0f}" if techo >= 10 else f"{valor:.1f}"
        clase = "baseline" if i == 0 else "grid"
        partes.append(f'<line class="{clase}" x1="46" y1="{y:.1f}" x2="{_ANCHO}" y2="{y:.1f}"/>')
        partes.append(f'<text class="tick" x="40" y="{y + 4:.1f}" text-anchor="end">{etiqueta}</text>')
    partes.append(f'<text class="tick unidad" x="40" y="{y0 - 6:.1f}" text-anchor="end">{unidad}</text>')
    return "".join(partes)


def _tooltip_payload(titulo: str, valores: Sequence[float], unidad: str) -> str:
    filas = [
        {"tec": _ETIQUETAS[tec], "clase": tec, "valor": f"{_fmt(v)} {unidad}"}
        for tec, v in zip(TECNOLOGIAS, valores, strict=True)
    ]
    total = {"tec": "Total", "clase": "", "valor": f"{_fmt(sum(valores))} {unidad}"}
    return html.escape(json.dumps({"titulo": titulo, "filas": [*filas, total]}, ensure_ascii=False))


def _columnas_apiladas(
    categorias: Sequence[str],
    etiquetas_x: Sequence[str],
    series: Mapping[str, Sequence[float]],
    unidad: str,
    etiquetar: Sequence[int],
    alto: int = 280,
) -> str:
    """Chart de columnas apiladas server-side (mensual y perfil horario lo reusan)."""
    y0, alto_plot, x0 = 18, alto - 18 - 26, 46.0
    n = len(categorias)
    banda = (_ANCHO - x0) / n
    ancho_barra = min(24.0, banda * 0.6)
    totales = [sum(series[tec][i] for tec in TECNOLOGIAS) for i in range(n)]
    techo = _tick_limpio(max(totales))

    partes = [_eje_y(techo, alto_plot, y0, unidad)]
    for i, categoria in enumerate(categorias):
        x = x0 + banda * i + (banda - ancho_barra) / 2
        valores = [series[tec][i] for tec in TECNOLOGIAS]
        partes.append(_barra_apilada(x, ancho_barra, valores, techo, alto_plot, y0))
        if i in etiquetar and totales[i] > 0:
            y_tope = y0 + alto_plot * (1 - totales[i] / techo) - 6
            partes.append(
                f'<text class="valor" x="{x + ancho_barra / 2:.1f}" y="{y_tope:.1f}" '
                f'text-anchor="middle">{_fmt(totales[i])}</text>'
            )
        if etiquetas_x[i]:
            partes.append(
                f'<text class="tick" x="{x + ancho_barra / 2:.1f}" y="{alto - 8}" '
                f'text-anchor="middle">{html.escape(etiquetas_x[i])}</text>'
            )
        # hit target: la banda completa, no solo los píxeles pintados
        partes.append(
            f'<rect class="hit" tabindex="0" x="{x0 + banda * i:.1f}" y="{y0}" '
            f'width="{banda:.1f}" height="{alto_plot}" '
            f'data-tooltip="{_tooltip_payload(categoria, valores, unidad)}"/>'
        )
    return (
        f'<svg viewBox="0 0 {_ANCHO} {alto}" role="img" '
        f'preserveAspectRatio="xMidYMid meet">{"".join(partes)}</svg>'
    )


def _svg_mensual(meses: Sequence[str], mensual: dict[tuple[str, str], float]) -> str:
    series = {tec: [mensual.get((mes, tec), 0.0) for mes in meses] for tec in TECNOLOGIAS}
    etiquetas = [f"{_MESES_ES[int(mes[5:7]) - 1][:3]} {mes[2:4]}" for mes in meses]
    titulos = [f"{_MESES_ES[int(mes[5:7]) - 1]} {mes[:4]}" for mes in meses]
    svg = _columnas_apiladas(titulos, etiquetas, series, "GWh", etiquetar=range(len(meses)))
    return svg


def _svg_perfil(perfil: dict[str, tuple[float, ...]]) -> str:
    series = {tec: perfil.get(tec, (0.0,) * 24) for tec in TECNOLOGIAS}
    totales = [sum(series[tec][i] for tec in TECNOLOGIAS) for i in range(24)]
    pico = totales.index(max(totales))
    etiquetas = [str(h) if h in (1, 6, 12, 18, 24) else "" for h in range(1, 25)]
    return _columnas_apiladas(
        [f"{h}:00" for h in range(1, 25)], etiquetas, series, "MWh", etiquetar=[pico]
    )


def _svg_top(top: Sequence[tuple[str, str, float]]) -> str:
    alto_fila, alto = 30, 30 * len(top) + 8
    x0 = 236.0
    maximo = max(total for _, _, total in top)
    partes: list[str] = []
    for i, (central, tec, total) in enumerate(top):
        y = 4 + i * alto_fila
        largo = max((total / maximo) * (_ANCHO - x0 - 76), 1.0)
        r = 4.0
        partes.append(
            f'<text class="tick central" x="{x0 - 10}" y="{y + 18}" text-anchor="end">{html.escape(central)}</text>'
        )
        partes.append(
            f'<path class="serie {tec}" d="M{x0},{y + 4} h{largo - r:.1f} '
            f'q{r},0 {r},{r} v{alto_fila - 10 - 2 * r} q0,{r} -{r},{r} h-{largo - r:.1f} z"/>'
        )
        partes.append(f'<text class="valor" x="{x0 + largo + 8:.1f}" y="{y + 18}">{_fmt(total)}</text>')
        payload = html.escape(
            json.dumps(
                {"titulo": central, "filas": [{"tec": _ETIQUETAS[tec], "clase": tec, "valor": f"{_fmt(total)} MWh"}]},
                ensure_ascii=False,
            )
        )
        partes.append(
            f'<rect class="hit" tabindex="0" x="0" y="{y}" width="{_ANCHO}" '
            f'height="{alto_fila}" data-tooltip="{payload}"/>'
        )
    return (
        f'<svg viewBox="0 0 {_ANCHO} {alto}" role="img" '
        f'preserveAspectRatio="xMidYMid meet">{"".join(partes)}</svg>'
    )


def _filas_tabla(meses: Sequence[str], mensual: dict[tuple[str, str], float]) -> str:
    filas = []
    for mes in meses:
        valores = [mensual.get((mes, tec), 0.0) for tec in TECNOLOGIAS]
        celdas = "".join(f"<td>{v:,.1f}</td>" for v in valores)
        filas.append(
            f"<tr><td>{_MESES_ES[int(mes[5:7]) - 1].capitalize()} {mes[:4]}</td>"
            f"{celdas}<td><strong>{sum(valores):,.1f}</strong></td></tr>"
        )
    total_por_tec = [
        sum(mensual.get((mes, tec), 0.0) for mes in meses) for tec in TECNOLOGIAS
    ]
    celdas = "".join(f"<td><strong>{v:,.1f}</strong></td>" for v in total_por_tec)
    filas.append(
        f"<tr class=\"total\"><td><strong>Total</strong></td>{celdas}"
        f"<td><strong>{sum(total_por_tec):,.1f}</strong></td></tr>"
    )
    return "\n".join(filas)


_PLANTILLA = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Observatorio Acopia — vertimiento renovable en Chile</title>
<style>
  :root {
    color-scheme: light dark;
    --page: #f9f9f7; --surface: #fcfcfb;
    --text: #0b0b0b; --text-2: #52514e; --muted: #898781;
    --grid: #e1e0d9; --baseline: #c3c2b7; --border: rgba(11,11,11,0.10);
    --solar: #eda100; --eolica: #2a78d6; --hidro_pasada: #008300; --hidro_embalse: #e87ba4;
  }
  @media (prefers-color-scheme: dark) {
    :root {
      --page: #0d0d0d; --surface: #1a1a19;
      --text: #ffffff; --text-2: #c3c2b7; --muted: #898781;
      --grid: #2c2c2a; --baseline: #383835; --border: rgba(255,255,255,0.10);
      --solar: #c98500; --eolica: #3987e5; --hidro_pasada: #008300; --hidro_embalse: #d55181;
    }
  }
  * { box-sizing: border-box; margin: 0; }
  body { background: var(--page); color: var(--text); font: 15px/1.5 system-ui, -apple-system, "Segoe UI", sans-serif; padding: 24px 16px 48px; }
  .wrap { max-width: 1040px; margin: 0 auto; }
  header h1 { font-size: 26px; font-weight: 650; letter-spacing: -0.01em; }
  header p { color: var(--text-2); max-width: 72ch; margin-top: 4px; }
  header .meta { color: var(--muted); font-size: 12.5px; margin-top: 6px; }
  section { margin-top: 28px; }
  h2 { font-size: 17px; font-weight: 650; margin-bottom: 4px; }
  .sub { color: var(--text-2); font-size: 13.5px; margin-bottom: 14px; max-width: 80ch; }
  .kpis { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; margin-top: 18px; }
  .kpi { background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 14px 16px; }
  .kpi .etiqueta { color: var(--text-2); font-size: 13px; }
  .kpi .cifra { font-size: 30px; font-weight: 650; margin-top: 2px; }
  .kpi .nota { color: var(--muted); font-size: 12px; margin-top: 2px; }
  .card { background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 16px; }
  .leyenda { display: flex; gap: 16px; flex-wrap: wrap; margin-bottom: 10px; color: var(--text-2); font-size: 13px; }
  .clave { display: inline-flex; align-items: center; gap: 6px; }
  .sw { width: 12px; height: 12px; border-radius: 3px; display: inline-block; }
  .sw.solar { background: var(--solar); } .sw.eolica { background: var(--eolica); }
  .sw.hidro_pasada { background: var(--hidro_pasada); } .sw.hidro_embalse { background: var(--hidro_embalse); }
  svg { width: 100%; height: auto; display: block; }
  svg .serie.solar { fill: var(--solar); } svg .serie.eolica { fill: var(--eolica); }
  svg .serie.hidro_pasada { fill: var(--hidro_pasada); } svg .serie.hidro_embalse { fill: var(--hidro_embalse); }
  svg .grid { stroke: var(--grid); stroke-width: 1; } svg .baseline { stroke: var(--baseline); stroke-width: 1; }
  svg .tick { fill: var(--muted); font-size: 11.5px; } svg .tick.unidad { font-size: 10.5px; }
  svg .tick.central { font-size: 12px; fill: var(--text-2); }
  svg .valor { fill: var(--text-2); font-size: 11.5px; font-variant-numeric: tabular-nums; }
  svg .hit { fill: transparent; outline: none; }
  svg .hit:hover, svg .hit:focus-visible { fill: rgba(137,135,129,0.12); }
  table { border-collapse: collapse; width: 100%; font-size: 13.5px; }
  th, td { text-align: right; padding: 7px 10px; border-bottom: 1px solid var(--grid); font-variant-numeric: tabular-nums; }
  th:first-child, td:first-child { text-align: left; }
  th { color: var(--text-2); font-weight: 600; }
  tr.total td { border-bottom: none; }
  #tooltip { position: fixed; pointer-events: none; background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 9px 11px; font-size: 12.5px; box-shadow: 0 4px 14px rgba(0,0,0,0.18); display: none; z-index: 10; min-width: 168px; }
  #tooltip .titulo { color: var(--text-2); margin-bottom: 5px; }
  #tooltip .fila { display: flex; align-items: center; gap: 7px; margin-top: 2px; }
  #tooltip .fila .stroke { width: 10px; height: 3px; border-radius: 2px; background: var(--baseline); }
  #tooltip .fila .stroke.solar { background: var(--solar); } #tooltip .fila .stroke.eolica { background: var(--eolica); }
  #tooltip .fila .stroke.hidro_pasada { background: var(--hidro_pasada); } #tooltip .fila .stroke.hidro_embalse { background: var(--hidro_embalse); }
  #tooltip .fila .v { font-weight: 650; margin-left: auto; font-variant-numeric: tabular-nums; }
  #tooltip .fila .n { color: var(--text-2); }
  footer { margin-top: 34px; color: var(--muted); font-size: 12.5px; max-width: 82ch; }
  footer a { color: var(--text-2); }
</style>
</head>
<body>
<div class="wrap">
  <header>
    <h1>Vertimiento renovable en Chile — __PERIODO__</h1>
    <p>Energía eólica, solar e hidro que el sistema eléctrico no pudo aprovechar, por congestión
    de transmisión o sobreoferta. Datos oficiales del Coordinador Eléctrico Nacional
    ("Reducciones ERV"), agregados desde el detalle central × hora.</p>
    <p class="meta">Generado el __GENERADO__ · fuente con ~2 meses de rezago · un proyecto del motor de despacho <a href="https://github.com/faborubio/acopia">Acopia</a>__ENLACE_DEMO__</p>
  </header>

  <div class="kpis">
    <div class="kpi"><div class="etiqueta">Energía vertida en el período</div><div class="cifra">__KPI_TOTAL__ GWh</div><div class="nota">no se pudo inyectar a la red</div></div>
    <div class="kpi"><div class="etiqueta">Del total, es solar</div><div class="cifra">__KPI_SOLAR_PCT__</div><div class="nota">se pierde justo a mediodía</div></div>
    <div class="kpi"><div class="etiqueta">Hora que más vierte</div><div class="cifra">__KPI_HORA_PICO__</div><div class="nota">suma del período, hora oficial</div></div>
    <div class="kpi"><div class="etiqueta">Centrales afectadas</div><div class="cifra">__KPI_CENTRALES__</div><div class="nota">con al menos una reducción</div></div>
  </div>

  <section>
    <h2>Vertimiento por mes</h2>
    <p class="sub">GWh reducidos por tecnología. El verano concentra el problema: más sol,
    misma transmisión.</p>
    <div class="card">__LEYENDA__ __SVG_MENSUAL__</div>
  </section>

  <section>
    <h2>El perfil horario cuenta la historia</h2>
    <p class="sub">Suma del período por hora del día. El vertimiento se concentra en las horas
    de sol — exactamente cuando el costo marginal colapsa. Almacenar esa energía y desplazarla
    a la punta de la tarde es el problema que optimiza Acopia.</p>
    <div class="card">__LEYENDA__ __SVG_PERFIL__</div>
  </section>

  <section>
    <h2>Las 10 centrales que más vierten</h2>
    <p class="sub">MWh reducidos en el período, por central (nombre según el Coordinador).</p>
    <div class="card">__SVG_TOP__</div>
  </section>

  <section>
    <h2>Tabla del período</h2>
    <p class="sub">GWh por mes y tecnología — los mismos datos de los gráficos, en número.</p>
    <div class="card"><table>
      <thead><tr><th>Mes</th><th>Solar</th><th>Eólica</th><th>Hidro pasada</th><th>Hidro embalse</th><th>Total</th></tr></thead>
      <tbody>__FILAS_TABLA__</tbody>
    </table></div>
  </section>

  <footer>
    <p><strong>Nota metodológica.</strong> Fuente: XLSX mensual "Reducciones de Generación Renovable"
    (Coordinador Eléctrico Nacional), detalle por central × hora; los totales se recalculan desde ese
    detalle, no se copian del resumen del archivo. La fuente se publica con ~2 meses de rezago.
    Valorizar esta energía "a precio spot" sería engañoso — se vierte justo cuando el precio colapsa
    a ~0 —; la valorización honesta (¿cuánto valdría desplazada a la punta?) es una página futura de
    este observatorio.</p>
  </footer>
</div>
<div id="tooltip" role="status"></div>
<script>
(function () {
  var tip = document.getElementById("tooltip");
  function mostrar(el, x, y) {
    var datos;
    try { datos = JSON.parse(el.getAttribute("data-tooltip")); } catch (e) { return; }
    tip.textContent = "";
    var t = document.createElement("div"); t.className = "titulo";
    t.textContent = datos.titulo; tip.appendChild(t);
    datos.filas.forEach(function (f) {
      var fila = document.createElement("div"); fila.className = "fila";
      var sw = document.createElement("span"); sw.className = "stroke " + (f.clase || "");
      var n = document.createElement("span"); n.className = "n"; n.textContent = f.tec;
      var v = document.createElement("span"); v.className = "v"; v.textContent = f.valor;
      fila.appendChild(sw); fila.appendChild(n); fila.appendChild(v); tip.appendChild(fila);
    });
    tip.style.display = "block";
    var w = tip.offsetWidth, h = tip.offsetHeight;
    var px = Math.min(x + 14, window.innerWidth - w - 8);
    var py = y - h - 12 < 8 ? y + 18 : y - h - 12;
    tip.style.left = px + "px"; tip.style.top = py + "px";
  }
  function ocultar() { tip.style.display = "none"; }
  document.querySelectorAll(".hit").forEach(function (el) {
    el.addEventListener("pointermove", function (ev) { mostrar(el, ev.clientX, ev.clientY); });
    el.addEventListener("pointerleave", ocultar);
    el.addEventListener("focus", function () {
      var r = el.getBoundingClientRect(); mostrar(el, r.left + r.width / 2, r.top);
    });
    el.addEventListener("blur", ocultar);
  });
})();
</script>
</body>
</html>
"""
