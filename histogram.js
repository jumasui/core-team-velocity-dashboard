function validTimes(values) {
  return values.filter(v => Number.isFinite(v) && v >= 0);
}
function timeBins(values) {
  const samples = validTimes(values);
  if (!samples.length) return [];
  const maximum = samples.reduce((a, b) => Math.max(a, b), 0);
  const edges = [0, 1, 2, 4, 8, 16];
  while (edges.at(-1) < maximum) edges.push(edges.at(-1) + 16);
  return edges;
}
function relativeCounts(counts) {
  if (counts.some(n => !Number.isInteger(n) || n < 0)) throw Error('Invalid frequency counts');
  const n = counts.reduce((a, b) => a + b, 0);
  return counts.map(count => n ? 100 * count / n : null);
}
const percent = value => value == null ? 'unavailable' : value > 0 && value < .1 ? '<0.1%' : `${value.toFixed(1)}%`;
function binDurations(values, edges = timeBins(values)) {
  const samples = validTimes(values), omitted = values.length - samples.length;
  if (!samples.length && !edges.length) return {edges: [], counts: [], omitted};
  if (edges.length < 2 || edges.some((v, i) => !Number.isFinite(v) || (i && v <= edges[i - 1]))) throw Error('Invalid histogram edges');
  const counts = Array(edges.length - 1).fill(0);
  samples.forEach(value => {
    if (value < edges[0] || value > edges.at(-1)) throw Error('Duration outside histogram range');
    const upper = edges.findIndex((edge, i) => i > 0 && (value < edge || (i === edges.length - 1 && value <= edge)));
    counts[upper - 1] += 1;
  });
  return {edges, counts, omitted};
}
function svgNode(tag, attributes = {}, text) {
  const n = document.createElementNS('http://www.w3.org/2000/svg', tag);
  Object.entries(attributes).forEach(([key, value]) => n.setAttribute(key, String(value)));
  if (text !== undefined) n.textContent = String(text);
  return n;
}
function histogram(title, values, unit, countLabel, edges, scaleMaximum, reference = []) {
  edges = edges || timeBins([...values, ...reference]);
  const bins = binDurations(values, edges), ref = binDurations(reference, edges);
  const n = bins.counts.reduce((a, b) => a + b, 0), rn = ref.counts.reduce((a, b) => a + b, 0);
  const percentages = relativeCounts(bins.counts), rp = relativeCounts(ref.counts);
  const figure = el('figure', null, 'histogram'); figure.append(el('h3', title));
  Object.assign(figure.dataset, {sampleCount: n, omitted: bins.omitted, counts: JSON.stringify(bins.counts), edges: JSON.stringify(bins.edges),
    percentages: JSON.stringify(percentages), referenceCount: rn, referenceCounts: JSON.stringify(ref.counts), referencePercentages: JSON.stringify(rp)});
  const peak = Math.max(0, ...percentages.filter(Number.isFinite), ...rp.filter(Number.isFinite));
  figure.dataset.scaleMaximum = scaleMaximum ?? (Math.ceil(peak / 10) * 10 || 10);
  if (!n && !rn) { figure.append(el('p', 'No measured durations for these filters.', 'muted')); return figure; }
  const left = 68, top = 40, width = Math.max(510,bins.counts.length * 42), height = 158, base = top + height;
  const svg = svgNode('svg', {viewBox: `0 0 ${width + 90} 260`, role: 'img', 'aria-label': `${title}: Core Team Owned ${countLabel} n=${n}; rest of AISTUDIO n=${rn}; early ${unit} bands then linear 16-unit intervals versus percentage`});
  svg.style.minWidth = `${width + 90}px`;
  const maximum = Number(figure.dataset.scaleMaximum), barWidth = width / bins.counts.length;
  const ticks = [...new Set([0, maximum / 2, maximum])];
  ticks.forEach(tick => {
    const y = base - height * tick / maximum;
    svg.append(svgNode('line', {x1: left, x2: left + width, y1: y, y2: y, stroke: '#d6e1ea'}));
    svg.append(svgNode('text', {x: left - 8, y: y + 4, 'text-anchor': 'end'}, `${tick}%`));
  });
  const number = value => Number(value.toPrecision(4)).toLocaleString('en-US');
  const annotations = [];
  bins.counts.forEach((count, i) => {
    const h = height * (percentages[i] || 0) / maximum;
    const bar = svgNode('rect', {x: left + i * barWidth + 1, y: base - h, width: Math.max(1, barWidth - 2), height: h, fill: '#146a96', 'data-bin': i});
    const range = `${number(bins.edges[i])}–${number(bins.edges[i + 1])} ${unit}`;
    bar.append(svgNode('title', {}, `${range}: ${count}/${n} ${countLabel} (${percent(percentages[i])})`)); svg.append(bar);
    if (n) {
      annotations.push(svgNode('text', {x: left + (i + .5) * barWidth, y: base - h - 18, 'text-anchor': 'middle', 'data-count-label': i}, count));
      annotations.push(svgNode('text', {x: left + (i + .5) * barWidth, y: base - h - 5, 'text-anchor': 'middle', 'data-percent-label': i}, percent(percentages[i])));
    }
  });
  if (rn) {
    svg.append(svgNode('polyline', {points: rp.map((v, i) => `${left + (i + .5) * barWidth},${base - height * v / maximum}`).join(' '), fill: 'none', stroke: '#a56618', 'stroke-width': 2}));
    rp.forEach((v, i) => {
      const dot = svgNode('circle', {cx: left + (i + .5) * barWidth, cy: base - height * v / maximum, r: 3, fill: '#a56618'});
      dot.append(svgNode('title', {}, `Rest of AISTUDIO ${number(edges[i])}–${number(edges[i + 1])} ${unit}: ${ref.counts[i]}/${rn} (${percent(v)})`)); svg.append(dot);
    });
  }
  bins.edges.forEach((edge, i) => {
    svg.append(svgNode('text', {x: left + i * barWidth, y: base + 20, 'text-anchor': 'middle'}, edge === 1 ? `1 ${unit === 'days' ? 'day' : 'hour'}` : number(edge)));
  });
  svg.append(...annotations);
  svg.append(svgNode('text', {x: left + Math.min(width,510) / 2, y: 249, 'text-anchor': 'middle'}, `Calendar ${unit}: time bands; +16 after 16`));
  svg.append(svgNode('text', {transform: 'translate(16 112) rotate(-90)', 'text-anchor': 'middle'}, 'Frequency (% within cohort)'));
  const scroll = el('div', null, 'hist-scroll'); scroll.append(svg); figure.append(scroll);
  figure.append(el('figcaption', `Blue bars: Core Team Owned ${countLabel} n=${n.toLocaleString()} · amber line: rest of AISTUDIO n=${rn.toLocaleString()}`));
  figure.append(el('small', `${bins.omitted} Core Team Owned ${countLabel} and ${ref.omitted} org durations unmeasured/excluded. Percentages use each cohort's measured n. Bands end at 1, 2, 4, 8, 16, then 32, 48, 64… ${unit}; final upper edge included. Scroll horizontally for later bands.`));
  figure.append(el('small', `Source: ${countLabel === 'Jiras' ? 'Jira' : 'GitHub'} · study ${D.start.slice(0, 10)}–${D.snapshot.slice(0, 10)} · current filters.`));
  return figure;
}
function histogramGroup(id, specs, unit, countLabel, shared = false) {
  const edges = shared ? timeBins(specs.flatMap(s => [...s.values, ...(s.reference || [])])) : undefined;
  const percentages = shared ? specs.flatMap(s => [s.values, s.reference || []]).flatMap(v => relativeCounts(binDurations(v, edges).counts)).filter(Number.isFinite) : [];
  const peak = shared ? (Math.ceil(Math.max(0, ...percentages) / 10) * 10 || 10) : undefined;
  $(id).replaceChildren(...specs.map(s => histogram(s.title, s.values, unit, countLabel, edges, peak, s.reference || [])));
}
if (typeof module !== 'undefined') module.exports = {timeBins, binDurations, relativeCounts};
