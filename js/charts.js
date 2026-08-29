// Charts for one session, drawn as inline SVG.
//
// Two plots stacked on a shared time axis rather than one plot with two vertical scales.
// Glucose in mmol/L and heart rate in beats per minute have no common scale, and putting them
// on twin axes lets the author choose where the lines appear to cross, which is a decision the
// data has not made. Stacking them keeps every temporal comparison available and invents nothing.
//
// The palette is the three leading categorical slots, validated for all-pairs separation in
// both light and dark modes. Aqua sits below 3:1 against the light surface, so carbohydrate
// markers always carry a visible label, and marker shape differs from insulin's so that hue is
// never the only channel.

const PAD = { top: 16, right: 16, bottom: 26, left: 44 };
const GLUCOSE_H = 190;
const HR_H = 90;
const GAP = 10;

const HYPO = 3.9;
const HYPO_L2 = 3.0;
const HYPER = 10.0;
const MGDL = 18.0182;

const esc = (s) => String(s).replace(/[&<>"']/g, (c) =>
  ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

const clockOf = (ms) => new Date(ms).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

/**
 * Render the glucose and heart rate plots for one session.
 *
 * @param {object} opts
 * @param {Array<{t:number,mmol:number}>} opts.entries CGM over the window
 * @param {Array<{t:number,bpm:number}>} opts.hr heart rate during the session
 * @param {Array<object>} opts.treatments doses in the window
 * @param {number} opts.sessionStart
 * @param {number} opts.sessionEnd
 * @param {number} opts.windowStart
 * @param {number} opts.windowEnd
 * @param {'mmol'|'mgdl'} opts.units
 * @returns {string} SVG markup
 */
export function sessionChart({
  entries, hr = [], treatments = [], sessionStart, sessionEnd,
  windowStart, windowEnd, units = 'mmol', width = 720,
}) {
  const hasHr = hr.length > 2;
  const totalH = PAD.top + GLUCOSE_H + (hasHr ? GAP + HR_H : 0) + PAD.bottom;
  const plotW = width - PAD.left - PAD.right;

  if (!entries.length) {
    return `<div class="chart-empty">No sensor readings in this window, so there is nothing to
      plot. The session is still evaluated on whatever else is available.</div>`;
  }

  const x = (t) => PAD.left + ((t - windowStart) / (windowEnd - windowStart)) * plotW;

  // The glucose scale always spans the target band, so that two sessions can be compared by eye
  // without checking the axis, and extends to hold the data where it goes outside it.
  const values = entries.map((e) => e.mmol);
  const lo = Math.min(2.5, Math.floor(Math.min(...values) - 0.5));
  const hi = Math.max(12.0, Math.ceil(Math.max(...values) + 0.5));
  const yG = (v) => PAD.top + GLUCOSE_H - ((v - lo) / (hi - lo)) * GLUCOSE_H;

  const hrTop = PAD.top + GLUCOSE_H + GAP;
  const hrValues = hr.map((p) => p.bpm);
  const hrLo = hasHr ? Math.floor(Math.min(...hrValues) / 10) * 10 - 5 : 0;
  const hrHi = hasHr ? Math.ceil(Math.max(...hrValues) / 10) * 10 + 5 : 1;
  const yH = (v) => hrTop + HR_H - ((v - hrLo) / (hrHi - hrLo)) * HR_H;

  const parts = [];

  // Threshold bands. The hypoglycaemic region uses the reserved critical colour because it is
  // a state rather than a series, and it is the only thing on the plot that is a state.
  parts.push(`<rect class="band-hypo" x="${PAD.left}" y="${yG(HYPO)}"
    width="${plotW}" height="${Math.max(0, PAD.top + GLUCOSE_H - yG(HYPO))}"/>`);
  parts.push(`<rect class="band-target" x="${PAD.left}" y="${yG(HYPER)}"
    width="${plotW}" height="${Math.max(0, yG(HYPO) - yG(HYPER))}"/>`);

  // The session itself.
  const sx = x(Math.max(sessionStart, windowStart));
  const sw = Math.max(1, x(Math.min(sessionEnd, windowEnd)) - sx);
  parts.push(`<rect class="session-span" x="${sx}" y="${PAD.top}" width="${sw}"
    height="${(hasHr ? hrTop + HR_H : PAD.top + GLUCOSE_H) - PAD.top}"/>`);
  parts.push(`<text class="session-label" x="${sx + sw / 2}" y="${PAD.top - 4}"
    text-anchor="middle">exercise</text>`);

  // Gridlines and the glucose axis.
  const step = hi - lo > 14 ? 4 : 2;
  for (let v = Math.ceil(lo / step) * step; v <= hi; v += step) {
    parts.push(`<line class="grid" x1="${PAD.left}" y1="${yG(v)}" x2="${width - PAD.right}" y2="${yG(v)}"/>`);
    const label = units === 'mgdl' ? Math.round(v * MGDL) : v;
    parts.push(`<text class="axis" x="${PAD.left - 6}" y="${yG(v) + 4}" text-anchor="end">${label}</text>`);
  }
  // The hypoglycaemia threshold is drawn as a labelled rule, because it is the number every
  // reading on the plot is being judged against.
  parts.push(`<line class="threshold" x1="${PAD.left}" y1="${yG(HYPO)}" x2="${width - PAD.right}" y2="${yG(HYPO)}"/>`);
  parts.push(`<text class="threshold-label" x="${width - PAD.right}" y="${yG(HYPO) - 4}"
    text-anchor="end">${units === 'mgdl' ? '70 mg/dL' : '3.9 mmol/L'}</text>`);

  // Time axis, at a spacing that keeps the labels apart.
  const spanHours = (windowEnd - windowStart) / 3_600_000;
  const tickHours = spanHours > 14 ? 4 : spanHours > 7 ? 2 : 1;
  const first = new Date(windowStart);
  first.setMinutes(0, 0, 0);
  for (let t = first.getTime(); t <= windowEnd; t += tickHours * 3_600_000) {
    if (t < windowStart) continue;
    const px = x(t);
    parts.push(`<line class="grid-v" x1="${px}" y1="${PAD.top}" x2="${px}"
      y2="${hasHr ? hrTop + HR_H : PAD.top + GLUCOSE_H}"/>`);
    parts.push(`<text class="axis" x="${px}" y="${totalH - PAD.bottom + 16}"
      text-anchor="middle">${clockOf(t)}</text>`);
  }

  // The glucose trace. Segments separated by more than 20 minutes are left as gaps rather than
  // joined, because a line drawn across an outage asserts readings that were never taken.
  let d = '';
  let prev = null;
  for (const e of entries) {
    const cmd = prev === null || e.t - prev > 20 * 60_000 ? 'M' : 'L';
    d += `${cmd}${x(e.t).toFixed(1)},${yG(e.mmol).toFixed(1)}`;
    prev = e.t;
  }
  parts.push(`<path class="series-glucose" d="${d}"/>`);

  // Doses. Carbohydrate is a triangle with a visible label, insulin a circle, so that the two
  // differ in shape as well as in hue.
  const laneY = PAD.top + 12;
  for (const tr of treatments) {
    if (tr.t < windowStart || tr.t > windowEnd) continue;
    const px = x(tr.t);
    if (tr.carbsG) {
      parts.push(`<path class="marker-carb" d="M${px},${laneY - 5} L${px + 5},${laneY + 4} L${px - 5},${laneY + 4} Z"/>`);
      parts.push(`<text class="marker-label" x="${px}" y="${laneY + 15}" text-anchor="middle">${Math.round(tr.carbsG)} g</text>`);
    }
    if (tr.insulinU) {
      const iy = laneY + (tr.carbsG ? 26 : 0);
      parts.push(`<circle class="marker-insulin${tr.automatic ? ' auto' : ''}" cx="${px}" cy="${iy}" r="4"/>`);
      if (!tr.automatic) {
        parts.push(`<text class="marker-label" x="${px}" y="${iy + 15}" text-anchor="middle">${tr.insulinU.toFixed(1)} U</text>`);
      }
    }
  }

  // Heart rate, on its own scale below.
  if (hasHr) {
    parts.push(`<line class="baseline" x1="${PAD.left}" y1="${hrTop + HR_H}" x2="${width - PAD.right}" y2="${hrTop + HR_H}"/>`);
    for (const v of [hrLo + 5, hrHi - 5]) {
      parts.push(`<text class="axis" x="${PAD.left - 6}" y="${yH(v) + 4}" text-anchor="end">${Math.round(v)}</text>`);
    }
    let hd = '';
    hr.forEach((p, i) => { hd += `${i ? 'L' : 'M'}${x(p.t).toFixed(1)},${yH(p.bpm).toFixed(1)}`; });
    parts.push(`<path class="series-hr" d="${hd}"/>`);
    parts.push(`<text class="plot-title" x="${PAD.left}" y="${hrTop - 2}">heart rate, bpm</text>`);
  }

  parts.push(`<text class="plot-title" x="${PAD.left}" y="${PAD.top - 4}"
    text-anchor="start">glucose, ${units === 'mgdl' ? 'mg/dL' : 'mmol/L'}</text>`);

  // Hover layer: one transparent rectangle carrying the data, so the crosshair can be driven
  // without a listener per point.
  const points = entries.map((e) => `${Math.round(e.t)},${e.mmol.toFixed(2)}`).join(';');
  parts.push(`<g class="crosshair" hidden>
    <line class="crosshair-line" y1="${PAD.top}" y2="${hasHr ? hrTop + HR_H : PAD.top + GLUCOSE_H}"/>
    <circle class="crosshair-dot" r="4"/>
  </g>`);
  parts.push(`<rect class="hover-target" x="${PAD.left}" y="${PAD.top}" width="${plotW}"
    height="${(hasHr ? hrTop + HR_H : PAD.top + GLUCOSE_H) - PAD.top}"
    data-points="${points}" data-x0="${PAD.left}" data-x1="${width - PAD.right}"
    data-t0="${windowStart}" data-t1="${windowEnd}"
    data-lo="${lo}" data-hi="${hi}" data-top="${PAD.top}" data-h="${GLUCOSE_H}"
    data-units="${units}"/>`);

  return `<figure class="chart">
    <svg viewBox="0 0 ${width} ${totalH}" width="100%" height="${totalH}"
         role="img" preserveAspectRatio="xMidYMid meet"
         aria-label="Glucose and heart rate around a ${Math.round((sessionEnd - sessionStart) / 60000)} minute session">
      ${parts.join('\n')}
    </svg>
    <div class="tooltip" hidden></div>
  </figure>`;
}

/** Attach the crosshair and tooltip. Called once after charts are inserted into the page. */
export function attachHover(root) {
  for (const target of root.querySelectorAll('.hover-target')) {
    if (target.dataset.wired) continue;
    target.dataset.wired = '1';

    const svg = target.ownerSVGElement;
    const figure = svg.closest('.chart');
    const tip = figure.querySelector('.tooltip');
    const group = svg.querySelector('.crosshair');
    const line = group.querySelector('.crosshair-line');
    const dot = group.querySelector('.crosshair-dot');

    const points = (target.dataset.points || '').split(';').filter(Boolean)
      .map((p) => { const [t, v] = p.split(','); return { t: +t, v: +v }; });
    if (!points.length) continue;

    const d = target.dataset;
    const x0 = +d.x0, x1 = +d.x1, t0 = +d.t0, t1 = +d.t1;
    const lo = +d.lo, hi = +d.hi, top = +d.top, h = +d.h;
    const units = d.units;

    const move = (ev) => {
      const box = svg.getBoundingClientRect();
      const vb = svg.viewBox.baseVal;
      const sx = ((ev.clientX - box.left) / box.width) * vb.width;
      const t = t0 + ((sx - x0) / (x1 - x0)) * (t1 - t0);

      let best = points[0];
      for (const p of points) {
        if (Math.abs(p.t - t) < Math.abs(best.t - t)) best = p;
      }
      const px = x0 + ((best.t - t0) / (t1 - t0)) * (x1 - x0);
      const py = top + h - ((best.v - lo) / (hi - lo)) * h;

      group.removeAttribute('hidden');
      line.setAttribute('x1', px);
      line.setAttribute('x2', px);
      dot.setAttribute('cx', px);
      dot.setAttribute('cy', py);

      const shown = units === 'mgdl'
        ? `${Math.round(best.v * MGDL)} mg/dL` : `${best.v.toFixed(1)} mmol/L`;
      tip.hidden = false;
      tip.textContent = `${clockOf(best.t)}  ${shown}`;
      tip.style.left = `${(px / vb.width) * 100}%`;
    };

    const leave = () => { group.setAttribute('hidden', ''); tip.hidden = true; };
    target.addEventListener('pointermove', move);
    target.addEventListener('pointerleave', leave);
  }
}

/**
 * The same data as a table.
 *
 * Present for every chart, not as a fallback but because several of the figures the report
 * quotes are read off these series, and a reader checking one should not have to hover a line
 * to do it.
 */
export function summaryTable(windows, units) {
  const fmt = (v) => v === null || v === undefined ? '—'
    : units === 'mgdl' ? `${Math.round(v * MGDL)}` : v.toFixed(1);
  const pct = (v) => v === null || v === undefined ? '—' : `${(v * 100).toFixed(0)}%`;

  const rows = windows.filter(Boolean).map((w) => `<tr>
      <th scope="row">${esc(w.label)}</th>
      <td>${w.n || '—'}</td><td>${pct(w.coverage)}</td>
      <td>${fmt(w.first_mmol)}</td><td>${fmt(w.nadir_mmol)}</td>
      <td>${fmt(w.peak_mmol)}</td><td>${fmt(w.mean_mmol)}</td>
      <td>${pct(w.time_below_l1)}</td><td>${pct(w.time_in_range)}</td>
      <td>${w.hypo_events ?? '—'}</td>
    </tr>`).join('');

  return `<table class="data-table">
    <caption>Glucose by window, in ${units === 'mgdl' ? 'mg/dL' : 'mmol/L'}. Coverage is the
      fraction of the window with sensor readings; figures from a poorly covered window are
      indicative rather than measured.</caption>
    <thead><tr>
      <th scope="col">Window</th><th scope="col">Readings</th><th scope="col">Coverage</th>
      <th scope="col">Start</th><th scope="col">Nadir</th><th scope="col">Peak</th>
      <th scope="col">Mean</th><th scope="col">Below 3.9</th><th scope="col">In range</th>
      <th scope="col">Events</th>
    </tr></thead>
    <tbody>${rows}</tbody>
  </table>`;
}
