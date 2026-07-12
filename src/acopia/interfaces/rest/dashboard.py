"""Dashboard demo (`GET /demo`): el día chileno sembrado como reporte HTML autocontenido.

Dos historias: el **plan del día** (duck curve — CMg, PV, acciones de la batería y
SoC, con el motivo del `ExplicadorDespacho` en el tooltip) y el **pipeline de datos**
(del XLSX crudo del Coordinador al backtest de forecasters). Cero dependencias
nuevas: HTML/CSS/SVG/JS vanilla en un solo documento; KPIs y tabla se renderizan
server-side (el reporte es legible sin JavaScript). Read-only: reusa el día demo
compartido (`interfaces.demo_dia`) y no persiste nada.
"""

from __future__ import annotations

import html
import json
from functools import lru_cache

from acopia.domain.services.explicador_despacho import ExplicadorDespacho
from acopia.interfaces.demo_dia import sembrar_dia_demo


@lru_cache(maxsize=1)
def render_dashboard() -> str:
    """Optimiza el día demo (una vez: es determinista) y arma el HTML del reporte."""
    demo = sembrar_dia_demo()
    explicaciones = ExplicadorDespacho().explicar(
        demo.planta.bateria, demo.plan, demo.rastro, demo.politica.resolucion
    )
    puntos = demo.escenario.puntos
    capacidad_wh = demo.planta.bateria.capacidad.wh

    cmg_mills = [p.cmg.mills_por_mwh for p in puntos]
    pv_w = [p.generacion.w for p in puntos]
    bateria_w = [
        e.potencia_w if e.accion == "DESCARGAR" else -e.potencia_w if e.accion == "CARGAR" else 0
        for e in explicaciones
    ]
    soc_pct = [round(e.energia_despues_wh * 100 / capacidad_wh, 1) for e in explicaciones]
    soc_inicial_pct = round(demo.rastro.estado_inicial.energia_almacenada.wh * 100 / capacidad_wh, 1)

    datos = {
        "cmg_mills": cmg_mills,
        "pv_w": pv_w,
        "bateria_w": bateria_w,
        "accion": [e.accion for e in explicaciones],
        "soc_pct": soc_pct,
        "soc_inicial_pct": soc_inicial_pct,
        "vertido_wh": [e.energia_vertida_wh for e in explicaciones],
        "motivo": [e.motivo for e in explicaciones],
    }

    ingreso_usd = demo.plan.ingreso_esperado_mills / 1_000
    descarga_kwh = sum(w for w in bateria_w if w > 0) / 1_000
    horas_cmg_cero = sum(1 for c in cmg_mills if c == 0)
    dif_cmg = (max(cmg_mills) - min(cmg_mills)) / 1_000

    filas = []
    for e in explicaciones:
        signo = "+" if e.accion == "DESCARGAR" else "−" if e.accion == "CARGAR" else ""
        potencia = f"{signo}{e.potencia_w / 1_000:.0f}" if e.potencia_w else "0"
        filas.append(
            "<tr>"
            f"<td>{e.intervalo:02d}:00</td>"
            f"<td>{e.cmg_mills_por_mwh / 1_000:.0f}</td>"
            f"<td>{pv_w[e.intervalo] / 1_000:.0f}</td>"
            f"<td>{html.escape(e.accion.capitalize())}</td>"
            f"<td>{potencia}</td>"
            f"<td>{soc_pct[e.intervalo]:.0f}%</td>"
            f"<td>{e.energia_vertida_wh / 1_000:.1f}</td>"
            f"<td class=\"motivo\">{html.escape(e.motivo)}</td>"
            "</tr>"
        )

    return (
        _PLANTILLA.replace("__DATOS__", json.dumps(datos, ensure_ascii=False))
        .replace("__PLAN_ID__", html.escape(demo.plan_id))
        .replace("__KPI_INGRESO__", f"US$ {ingreso_usd:,.0f}")
        .replace("__KPI_DIF_CMG__", f"{dif_cmg:.0f}")
        .replace("__KPI_HORAS_CERO__", str(horas_cmg_cero))
        .replace("__KPI_DESCARGA__", f"{descarga_kwh:,.0f}")
        .replace("__FILAS_TABLA__", "\n".join(filas))
    )


_PLANTILLA = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Acopia — plan de despacho del día</title>
<style>
  :root {
    --page: #f9f9f7; --surface: #fcfcfb;
    --text: #0b0b0b; --text-2: #52514e; --muted: #898781;
    --grid: #e1e0d9; --baseline: #c3c2b7; --border: rgba(11,11,11,0.10);
    --cmg: #2a78d6; --carga: #1baf7a; --descarga: #e34948;
    --soc: #4a3aa7; --pv: #898781;
  }
  @media (prefers-color-scheme: dark) {
    :root {
      --page: #0d0d0d; --surface: #1a1a19;
      --text: #ffffff; --text-2: #c3c2b7; --muted: #898781;
      --grid: #2c2c2a; --baseline: #383835; --border: rgba(255,255,255,0.10);
      --cmg: #3987e5; --carga: #199e70; --descarga: #e66767;
      --soc: #9085e9; --pv: #898781;
    }
  }
  * { box-sizing: border-box; margin: 0; }
  body {
    background: var(--page); color: var(--text);
    font: 15px/1.5 system-ui, -apple-system, "Segoe UI", sans-serif;
    padding: 24px 16px 48px;
  }
  .wrap { max-width: 1040px; margin: 0 auto; }
  header h1 { font-size: 26px; font-weight: 650; letter-spacing: -0.01em; }
  header p { color: var(--text-2); max-width: 70ch; margin-top: 4px; }
  header .plan-id { color: var(--muted); font-size: 12.5px; margin-top: 6px; }
  section { margin-top: 28px; }
  h2 { font-size: 17px; font-weight: 650; margin-bottom: 4px; }
  .sub { color: var(--text-2); font-size: 13.5px; margin-bottom: 14px; max-width: 80ch; }

  .kpis { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; }
  .tile {
    background: var(--surface); border: 1px solid var(--border); border-radius: 10px;
    padding: 14px 16px;
  }
  .tile .label { color: var(--text-2); font-size: 13px; }
  .tile .value { font-size: 28px; font-weight: 600; margin-top: 2px; }
  .tile .hint { color: var(--muted); font-size: 12px; margin-top: 2px; }

  .card {
    background: var(--surface); border: 1px solid var(--border); border-radius: 10px;
    padding: 18px; position: relative;
  }
  .chart-title { font-size: 13.5px; color: var(--text-2); margin: 10px 0 2px; }
  .chart-title:first-child { margin-top: 0; }
  svg { display: block; width: 100%; height: auto; }
  .legend { display: flex; gap: 18px; flex-wrap: wrap; margin-top: 10px; font-size: 13px; color: var(--text-2); }
  .legend .item { display: flex; align-items: center; gap: 6px; }
  .swatch { width: 12px; height: 12px; border-radius: 3px; }
  .linekey { width: 14px; height: 0; border-top: 2.5px solid; border-radius: 2px; }

  #tooltip {
    position: absolute; pointer-events: none; display: none; z-index: 3;
    background: var(--surface); border: 1px solid var(--border); border-radius: 8px;
    box-shadow: 0 4px 16px rgba(0,0,0,0.14); padding: 10px 12px; min-width: 230px; max-width: 320px;
    font-size: 13px;
  }
  #tooltip .hora { font-weight: 650; margin-bottom: 6px; }
  #tooltip .fila { display: flex; align-items: baseline; gap: 8px; margin-top: 2px; }
  #tooltip .fila .k { flex: 0 0 14px; border-top: 2.5px solid; border-radius: 2px; align-self: center; }
  #tooltip .fila .v { font-weight: 600; }
  #tooltip .fila .l { color: var(--text-2); }
  #tooltip .motivo { color: var(--text-2); margin-top: 8px; border-top: 1px solid var(--grid); padding-top: 6px; }

  details { margin-top: 14px; }
  summary { cursor: pointer; color: var(--text-2); font-size: 13.5px; }
  table { border-collapse: collapse; width: 100%; margin-top: 10px; font-size: 13px; }
  th, td { text-align: right; padding: 6px 10px; border-bottom: 1px solid var(--grid); font-variant-numeric: tabular-nums; }
  th { color: var(--text-2); font-weight: 600; }
  th:first-child, td:first-child, td:nth-child(4), th:nth-child(4) { text-align: left; }
  td.motivo { text-align: left; color: var(--text-2); font-variant-numeric: normal; min-width: 260px; }
  .tabla-scroll { overflow-x: auto; }

  .pasos { display: flex; flex-wrap: wrap; gap: 10px; counter-reset: paso; }
  .paso {
    flex: 1 1 180px; background: var(--surface); border: 1px solid var(--border);
    border-radius: 10px; padding: 12px 14px; counter-increment: paso;
  }
  .paso h3 { font-size: 13.5px; font-weight: 650; }
  .paso h3::before { content: counter(paso) " · "; color: var(--muted); }
  .paso p { color: var(--text-2); font-size: 12.5px; margin-top: 4px; }
  .paso code { font-size: 11.5px; background: var(--page); border: 1px solid var(--grid); border-radius: 4px; padding: 0 4px; }
  .destacado { font-weight: 650; color: var(--text); }
  .nota { color: var(--muted); font-size: 12.5px; margin-top: 10px; max-width: 90ch; }
  footer { margin-top: 36px; color: var(--muted); font-size: 12.5px; border-top: 1px solid var(--grid); padding-top: 14px; }
  footer a { color: var(--text-2); }
</style>
</head>
<body>
<div class="wrap">
  <header>
    <h1>Acopia — plan de despacho del día</h1>
    <p>Motor determinista <em>predict-then-optimize</em> para una planta solar con batería
    (PV-BESS) en el mercado eléctrico chileno: pronostica el costo marginal (CMg) nodal y
    decide cuándo cargar y descargar para arbitrar el diferencial y rescatar energía que se
    vertería. Día típico del SEN: sobreoferta solar a mediodía, punta vespertina.</p>
    <p class="plan-id">Plan <code>__PLAN_ID__</code> · política arbitraje-demo v1 · semilla 42 ·
    misma entrada &rarr; mismo plan (determinista, auditable)</p>
  </header>

  <section>
    <div class="kpis">
      <div class="tile"><div class="label">Ingreso esperado del día</div>
        <div class="value">__KPI_INGRESO__</div><div class="hint">plan optimizado vía LP (HiGHS)</div></div>
      <div class="tile"><div class="label">Diferencial CMg punta/valle</div>
        <div class="value">__KPI_DIF_CMG__ <span style="font-size:15px">US$/MWh</span></div>
        <div class="hint">el spread que la batería arbitra</div></div>
      <div class="tile"><div class="label">Horas a CMg = 0</div>
        <div class="value">__KPI_HORAS_CERO__ h</div><div class="hint">sobreoferta solar a mediodía</div></div>
      <div class="tile"><div class="label">Energía descargada</div>
        <div class="value">__KPI_DESCARGA__ <span style="font-size:15px">kWh</span></div>
        <div class="hint">vendida en la punta vespertina</div></div>
    </div>
  </section>

  <section>
    <h2>El plan del día</h2>
    <p class="sub">La batería carga cuando el CMg colapsa (absorbe el excedente solar) y
    descarga en la punta de la tarde. Pasa el cursor —o usa las flechas del teclado— para ver
    cada hora con el <strong>motivo</strong> que reconstruye el explicador del dominio.</p>
    <div class="card" id="graficos" tabindex="0" aria-label="Gráficos del plan; use flechas izquierda y derecha para recorrer las horas">
      <div class="chart-title">Costo marginal (US$/MWh)</div>
      <svg id="ch-cmg" viewBox="0 0 960 190" role="img" aria-label="Línea de costo marginal por hora"></svg>
      <div class="chart-title">Potencia (kW) — PV disponible y acciones de la batería</div>
      <svg id="ch-pot" viewBox="0 0 960 230" role="img" aria-label="PV disponible y carga/descarga de la batería por hora"></svg>
      <div class="legend">
        <span class="item"><span class="linekey" style="border-color:var(--pv)"></span>PV disponible</span>
        <span class="item"><span class="swatch" style="background:var(--carga)"></span>Carga (absorbe)</span>
        <span class="item"><span class="swatch" style="background:var(--descarga)"></span>Descarga (inyecta)</span>
      </div>
      <div class="chart-title">Estado de carga de la batería (%)</div>
      <svg id="ch-soc" viewBox="0 0 960 140" role="img" aria-label="Estado de carga por hora"></svg>
      <div id="tooltip" role="status"></div>
    </div>

    <details>
      <summary>Ver como tabla (24 horas, valores exactos)</summary>
      <div class="tabla-scroll">
      <table>
        <thead><tr><th>Hora</th><th>CMg (US$/MWh)</th><th>PV (kW)</th><th>Acción</th>
        <th>Batería (kW)</th><th>SoC</th><th>Vertido (kWh)</th><th>Motivo</th></tr></thead>
        <tbody>
__FILAS_TABLA__
        </tbody>
      </table>
      </div>
    </details>
  </section>

  <section>
    <h2>El pipeline de datos que alimenta al motor</h2>
    <p class="sub">De descargas crudas del mercado real a un plan auditable — ingesta,
    limpieza, alineación y validación out-of-sample, reproducibles por CLI.</p>
    <div class="pasos">
      <div class="paso"><h3>XLSX del Coordinador</h3>
        <p>CMg horario real por barra (S.GREGORIO, 2025). Formato hostil: coma decimal
        chilena, fecha en celdas combinadas, columna titulada por el mnemónico de la barra.</p></div>
      <div class="paso"><h3>Explorador Solar (TMY)</h3>
        <p>Generación PV de año típico (Antofagasta), ~54 filas de metadatos sobre la tabla
        y sin calendario común con el CMg.</p></div>
      <div class="paso"><h3><code>acopia-datos alinear</code></h3>
        <p>Parseo tolerante + alineación por posición + escala a unidades enteras del dominio
        (mills/MWh, W) &rarr; <code>planta_2025.csv</code>, 8.754 h alineadas.</p></div>
      <div class="paso"><h3>Backtest rodante</h3>
        <p>7 folds × 24 h out-of-sample, entrenamiento régimen-local (ventana de 720 h):
        el forecast se valida contra lo que no vio.</p></div>
      <div class="paso"><h3>Plan de despacho</h3>
        <p><em>Predict-then-optimize</em>: LP (cvxpy + HiGHS) cuantizado a enteros y validado
        contra el modelo físico de la batería — siempre factible.</p></div>
    </div>

    <h2 style="margin-top:22px">Backtest anual de forecasters (CMg real 2025, 7 folds)</h2>
    <p class="sub">El target difícil es el CMg — es el que decide el arbitraje. El Seq2Seq-LSTM
    entrenado régimen-local recorta el RMSE de CMg <span class="destacado">−23% frente al
    baseline</span>; en generación el naive sigue ganando (y así se reporta).</p>
    <div class="tabla-scroll">
    <table>
      <thead><tr><th>Modelo</th><th>Gen RMSE (W)</th><th>CMg RMSE (mills/MWh)</th><th>CMg MAPE</th></tr></thead>
      <tbody>
        <tr><td>Estacional-naive (baseline)</td><td>36.2</td><td>26,220</td><td>39.1%</td></tr>
        <tr><td>SARIMAX</td><td>41.3</td><td>28,200</td><td>~40%</td></tr>
        <tr><td class="destacado">Seq2Seq-LSTM (ventana 720 h)</td><td>46.5</td>
          <td class="destacado">20,300 (−23%)</td><td>~39%</td></tr>
      </tbody>
    </table>
    </div>
    <p class="nota">Cifras direccionales: planta modelo de 1 kW (generación TMY) + CMg real de
    una barra; no es telemetría de una planta en operación. La honestidad del reporte es parte
    del método: cada cifra sale de un comando reproducible (<code>acopia-datos backtest</code>).</p>
  </section>

  <footer>
    Acopia · Python 3.12+ · FastAPI · cvxpy/HiGHS · PyTorch (Seq2Seq-LSTM) · FastMCP ·
    Clean Architecture con frontera verificada (<code>import-linter</code>) ·
    <a href="https://github.com/faborubio/acopia">github.com/faborubio/acopia</a> ·
    Demo read-only: nada se ejecuta ni persiste.
  </footer>
</div>

<script>
"use strict";
const D = __DATOS__;
const N = 24;
const css = (v) => getComputedStyle(document.documentElement).getPropertyValue(v).trim();
const NS = "http://www.w3.org/2000/svg";
const ML = 64, MR = 16;
const W = 960;

function el(tag, attrs, parent) {
  const e = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
  if (parent) parent.appendChild(e);
  return e;
}
const bandW = (W - ML - MR) / N;
const xCentro = (i) => ML + bandW * (i + 0.5);

function ejeY(svg, esc, ticks, fmt, x0, x1) {
  for (const t of ticks) {
    const y = esc(t);
    el("line", { x1: x0, y1: y, x2: x1, y2: y, stroke: css("--grid"), "stroke-width": 1 }, svg);
    const txt = el("text", { x: x0 - 8, y: y + 4, "text-anchor": "end", fill: css("--muted"),
      "font-size": 11, "font-family": "system-ui, sans-serif" }, svg);
    txt.textContent = fmt(t);
  }
}
function ejeX(svg, y) {
  for (let h = 0; h < N; h += 4) {
    const txt = el("text", { x: xCentro(h), y: y, "text-anchor": "middle", fill: css("--muted"),
      "font-size": 11, "font-family": "system-ui, sans-serif" }, svg);
    txt.textContent = h + "h";
  }
}
function linea(svg, valores, esc, color) {
  const d = valores.map((v, i) => (i ? "L" : "M") + xCentro(i).toFixed(1) + " " + esc(v).toFixed(1)).join(" ");
  el("path", { d, fill: "none", stroke: color, "stroke-width": 2,
    "stroke-linejoin": "round", "stroke-linecap": "round" }, svg);
}
function area(svg, valores, esc, y0, color) {
  const d = valores.map((v, i) => (i ? "L" : "M") + xCentro(i).toFixed(1) + " " + esc(v).toFixed(1)).join(" ")
    + " L" + xCentro(N - 1).toFixed(1) + " " + y0 + " L" + xCentro(0).toFixed(1) + " " + y0 + " Z";
  el("path", { d, fill: color, opacity: 0.1 }, svg);
}
// Barra con extremo de datos redondeado (4px) y base cuadrada en el eje cero.
function barra(svg, i, v, esc, color) {
  const w = Math.min(24, bandW - 6), x = xCentro(i) - w / 2, r = 4;
  const y0 = esc(0), y1 = esc(v);
  let d;
  if (v >= 0) {
    d = `M${x} ${y0} L${x} ${y1 + r} Q${x} ${y1} ${x + r} ${y1} L${x + w - r} ${y1} ` +
        `Q${x + w} ${y1} ${x + w} ${y1 + r} L${x + w} ${y0} Z`;
  } else {
    d = `M${x} ${y0} L${x} ${y1 - r} Q${x} ${y1} ${x + r} ${y1} L${x + w - r} ${y1} ` +
        `Q${x + w} ${y1} ${x + w} ${y1 - r} L${x + w} ${y0} Z`;
  }
  return el("path", { d, fill: color }, svg);
}

// ---- Gráfico 1: CMg (US$/MWh) ----
const cmgUsd = D.cmg_mills.map((m) => m / 1000);
const svgCmg = document.getElementById("ch-cmg");
const escCmg = (v) => 150 - (v / 120) * 130; // dominio 0..120 -> y 150..20
ejeY(svgCmg, escCmg, [0, 40, 80, 120], (t) => t, ML, W - MR);
area(svgCmg, cmgUsd, escCmg, escCmg(0), css("--cmg"));
linea(svgCmg, cmgUsd, escCmg, css("--cmg"));
ejeX(svgCmg, 175);
// Etiqueta selectiva: solo la punta (el extremo que cuenta la historia).
const iMax = cmgUsd.indexOf(Math.max(...cmgUsd));
el("circle", { cx: xCentro(iMax), cy: escCmg(cmgUsd[iMax]), r: 4.5, fill: css("--cmg"),
  stroke: css("--surface"), "stroke-width": 2 }, svgCmg);
const lblMax = el("text", { x: xCentro(iMax), y: escCmg(cmgUsd[iMax]) - 10, "text-anchor": "middle",
  fill: css("--text-2"), "font-size": 12, "font-weight": 600,
  "font-family": "system-ui, sans-serif" }, svgCmg);
lblMax.textContent = cmgUsd[iMax] + " US$/MWh · punta";
const ceros = cmgUsd.map((v, i) => [v, i]).filter(([v]) => v === 0).map(([, i]) => i);
if (ceros.length) {
  const lbl0 = el("text", { x: xCentro((ceros[0] + ceros[ceros.length - 1]) / 2), y: escCmg(0) - 8,
    "text-anchor": "middle", fill: css("--muted"), "font-size": 11.5,
    "font-family": "system-ui, sans-serif" }, svgCmg);
  lbl0.textContent = "CMg = 0 — sobreoferta solar";
}

// ---- Gráfico 2: potencia (kW): PV contexto + carga/descarga divergente ----
const pvKw = D.pv_w.map((w) => w / 1000);
const batKw = D.bateria_w.map((w) => w / 1000);
const svgPot = document.getElementById("ch-pot");
const escPot = (v) => 170 - ((v + 60) / 160) * 150; // dominio -60..100 -> y 170..20
ejeY(svgPot, escPot, [-50, 0, 50, 100], (t) => t, ML, W - MR);
el("line", { x1: ML, y1: escPot(0), x2: W - MR, y2: escPot(0), stroke: css("--baseline"), "stroke-width": 1 }, svgPot);
area(svgPot, pvKw, escPot, escPot(0), css("--pv"));
linea(svgPot, pvKw, escPot, css("--pv"));
const barras = batKw.map((v, i) =>
  v ? barra(svgPot, i, v, escPot, v > 0 ? css("--descarga") : css("--carga")) : null);
ejeX(svgPot, 215);

// ---- Gráfico 3: SoC (%) ----
const svgSoc = document.getElementById("ch-soc");
const escSoc = (v) => 100 - (v / 100) * 80; // dominio 0..100 -> y 100..20
ejeY(svgSoc, escSoc, [0, 50, 100], (t) => t + "%", ML, W - MR);
area(svgSoc, D.soc_pct, escSoc, escSoc(0), css("--soc"));
linea(svgSoc, D.soc_pct, escSoc, css("--soc"));
ejeX(svgSoc, 125);

// ---- Crosshair sincronizado + tooltip (hover y teclado) ----
const cruces = [[svgCmg, 20, 150], [svgPot, 20, 170], [svgSoc, 20, 100]].map(([svg, y1, y2]) =>
  el("line", { x1: -10, y1, x2: -10, y2, stroke: css("--baseline"), "stroke-width": 1,
    "pointer-events": "none" }, svg));
const tooltip = document.getElementById("tooltip");
const card = document.getElementById("graficos");
let horaActiva = -1;

function filaTooltip(color, valor, etiqueta) {
  const f = document.createElement("div"); f.className = "fila";
  const k = document.createElement("span"); k.className = "k"; k.style.borderColor = color;
  const v = document.createElement("span"); v.className = "v"; v.textContent = valor;
  const l = document.createElement("span"); l.className = "l"; l.textContent = etiqueta;
  f.append(k, v, l); return f;
}
function mostrarHora(i, px, py) {
  horaActiva = i;
  for (const c of cruces) { c.setAttribute("x1", xCentro(i)); c.setAttribute("x2", xCentro(i)); }
  barras.forEach((b, j) => { if (b) b.setAttribute("opacity", j === i ? "0.75" : "1"); });
  tooltip.replaceChildren();
  const h = document.createElement("div"); h.className = "hora";
  h.textContent = String(i).padStart(2, "0") + ":00"; tooltip.appendChild(h);
  tooltip.appendChild(filaTooltip(css("--cmg"), cmgUsd[i] + " US$/MWh", "CMg"));
  tooltip.appendChild(filaTooltip(css("--pv"), pvKw[i] + " kW", "PV disponible"));
  const acc = D.accion[i], bat = batKw[i];
  const colorBat = bat > 0 ? css("--descarga") : bat < 0 ? css("--carga") : css("--baseline");
  tooltip.appendChild(filaTooltip(colorBat, (bat > 0 ? "+" : "") + bat + " kW",
    "batería · " + acc.toLowerCase()));
  tooltip.appendChild(filaTooltip(css("--soc"), D.soc_pct[i] + " %", "SoC al cierre"));
  if (D.vertido_wh[i] > 0)
    tooltip.appendChild(filaTooltip(css("--baseline"), (D.vertido_wh[i] / 1000).toFixed(1) + " kWh", "vertido"));
  const m = document.createElement("div"); m.className = "motivo";
  m.textContent = D.motivo[i]; tooltip.appendChild(m);
  tooltip.style.display = "block";
  const cw = card.clientWidth, tw = tooltip.offsetWidth;
  tooltip.style.left = Math.min(Math.max(8, px + 16), cw - tw - 8) + "px";
  tooltip.style.top = Math.max(8, py - 20) + "px";
}
function ocultar() {
  horaActiva = -1;
  tooltip.style.display = "none";
  for (const c of cruces) { c.setAttribute("x1", -10); c.setAttribute("x2", -10); }
  barras.forEach((b) => { if (b) b.setAttribute("opacity", "1"); });
}
card.addEventListener("pointermove", (ev) => {
  const r = card.getBoundingClientRect();
  const sx = svgCmg.getBoundingClientRect();
  const xRel = ((ev.clientX - sx.left) / sx.width) * W;
  if (xRel < ML || xRel > W - MR) { ocultar(); return; }
  const i = Math.min(N - 1, Math.max(0, Math.floor((xRel - ML) / bandW)));
  mostrarHora(i, ev.clientX - r.left, ev.clientY - r.top);
});
card.addEventListener("pointerleave", ocultar);
card.addEventListener("keydown", (ev) => {
  if (ev.key === "Escape") { ocultar(); return; }
  if (ev.key !== "ArrowLeft" && ev.key !== "ArrowRight") return;
  ev.preventDefault();
  const i = horaActiva < 0 ? 0 : Math.min(N - 1, Math.max(0, horaActiva + (ev.key === "ArrowRight" ? 1 : -1)));
  mostrarHora(i, (xCentro(i) / W) * card.clientWidth, 40);
});
card.addEventListener("blur", ocultar);
</script>
</body>
</html>
"""
