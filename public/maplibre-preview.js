// Opt-in renderer: /?renderer=vector. The application owns filtering,
// ranking, hydration, and details; this module owns only map presentation.
const empty = () => ({ type: 'FeatureCollection', features: [] });
const radius = ['interpolate', ['linear'], ['zoom'], 7, 2, 11, 4, 15, 7, 19, 9];

function styleFor(theme) {
  const dark = theme === 'dark';
  const c = dark
    ? { land: '#181e19', water: '#101d19', park: '#223b2c', building: '#303b31', road: '#536052', casing: '#252f27', ink: '#d6dbc9', muted: '#9aa993', halo: '#181e19' }
    : { land: '#F4F3ED', water: '#293F34', park: '#e0e7d8', building: '#e4e1d5', road: '#e3e0d6', casing: '#d1cbb9', ink: '#222721', muted: '#60645F', halo: '#F4F3ED' };
  const vector = (id, type, layer, paint, extra = {}) => ({ id, type, source: 'openmaptiles', 'source-layer': layer, paint, ...extra });
  const text = { 'text-color': c.ink, 'text-halo-color': c.halo, 'text-halo-width': 1.5 };
  const name = ['coalesce', ['get', 'name:latin'], ['get', 'name:en'], ['get', 'name']];
  return {
    version: 8,
    glyphs: 'https://tiles.openfreemap.org/fonts/{fontstack}/{range}.pbf',
    sources: {
      openmaptiles: { type: 'vector', url: 'https://tiles.openfreemap.org/planet', attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> · <a href="https://openfreemap.org">OpenFreeMap</a> · <a href="https://openmaptiles.org">OpenMapTiles</a>' },
      cafes: { type: 'geojson', data: empty() },
      highlight: { type: 'geojson', data: empty() }
    },
    layers: [
      { id: 'land', type: 'background', paint: { 'background-color': c.land } },
      vector('parks', 'fill', 'park', { 'fill-color': c.park, 'fill-opacity': 0.8 }),
      vector('woods', 'fill', 'landcover', { 'fill-color': c.park, 'fill-opacity': 0.5 }, { filter: ['==', ['get', 'class'], 'wood'] }),
      vector('water', 'fill', 'water', { 'fill-color': c.water }),
      vector('waterways', 'line', 'waterway', { 'line-color': c.water, 'line-width': 1 }, { minzoom: 12 }),
      vector('buildings', 'fill', 'building', { 'fill-color': c.building }, { minzoom: 13 }),
      vector('road-casing', 'line', 'transportation', { 'line-color': c.casing, 'line-width': ['interpolate', ['linear'], ['zoom'], 8, 0.5, 14, 4, 18, 14] }, { filter: ['in', ['get', 'class'], ['literal', ['motorway', 'trunk', 'primary', 'secondary', 'tertiary']]] }),
      vector('roads', 'line', 'transportation', { 'line-color': c.road, 'line-width': ['interpolate', ['linear'], ['zoom'], 8, 0.3, 14, 2.5, 18, 11] }, { filter: ['!=', ['get', 'class'], 'rail'] }),
      vector('boundaries', 'line', 'boundary', { 'line-color': c.muted, 'line-width': 0.7, 'line-opacity': 0.35, 'line-dasharray': [3, 3] }),
      vector('street-names', 'symbol', 'transportation_name', { ...text, 'text-color': c.muted }, { minzoom: 13, layout: { 'symbol-placement': 'line', 'text-field': name, 'text-font': ['Noto Sans Regular'], 'text-size': 11 } }),
      vector('place-names', 'symbol', 'place', text, { layout: { 'text-field': name, 'text-font': ['Noto Sans Regular'], 'text-size': ['interpolate', ['linear'], ['zoom'], 7, 11, 14, 15], 'text-transform': 'uppercase', 'text-letter-spacing': 0.06 } }),
      { id: 'cafes', type: 'circle', source: 'cafes', paint: { 'circle-radius': radius, 'circle-color': ['get', 'color'], 'circle-stroke-color': dark ? '#e5e0c9' : '#fffdf5', 'circle-stroke-width': 0.8, 'circle-opacity': 0.92 } },
      { id: 'cafe-labels', type: 'symbol', source: 'cafes', minzoom: 12, layout: { 'text-field': ['get', 'name'], 'text-font': ['Noto Sans Regular'], 'text-size': 12, 'text-variable-anchor': ['bottom', 'top', 'right', 'left'], 'text-radial-offset': 1, 'symbol-sort-key': ['get', 'priority'] }, paint: text },
      { id: 'highlight-glow', type: 'circle', source: 'highlight', paint: { 'circle-color': '#DCAF59', 'circle-radius': ['interpolate', ['linear'], ['zoom'], 7, 15, 15, 24], 'circle-blur': 0.7, 'circle-opacity': 0.4 } },
      { id: 'highlight-point', type: 'circle', source: 'highlight', paint: { 'circle-color': ['get', 'color'], 'circle-radius': ['interpolate', ['linear'], ['zoom'], 7, 5.5, 15, 10], 'circle-stroke-color': '#DCAF59', 'circle-stroke-width': 2.5 } }
    ]
  };
}

// Vector-only styles live here so the default page doesn't carry them. Appended after the
// app's styles (maplibre-gl.css is inserted before them), so these overrides win.
const overrides = document.createElement('style');
overrides.textContent = `
  .map-load-status { position: absolute; z-index: 5; bottom: 28px; left: 12px; right: 12px; padding: 8px 12px; background: var(--surface); color: var(--text); border: 1px solid var(--border); border-radius: 8px; font-size: 12px; }
  .maplibregl-ctrl-group { background: var(--surface); border: 1px solid var(--border); border-radius: 8px; overflow: hidden; }
  .maplibregl-ctrl-group button + button { border-top-color: var(--border); }
  [data-theme="dark"] .maplibregl-ctrl-icon { filter: invert(1); }
  @media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) .maplibregl-ctrl-icon { filter: invert(1); } }
  .maplibregl-ctrl-attrib { color: #222721; }
  .renderer-note { font-size: 11px; padding: 6px 12px; background: var(--accent-soft); color: var(--text); }
  .renderer-note a { color: inherit; }`;
document.head.append(overrides);

// One line above the map saying which renderer is showing, with a link to the standard map.
function showNote(vector) {
  let note = document.querySelector('.renderer-note');
  if (!note) {
    note = Object.assign(document.createElement('div'), { className: 'renderer-note' });
    document.querySelector('.layout').before(note);
  }
  note.replaceChildren(vector ? 'Vector map preview · ' : 'Vector preview unavailable. Showing the standard map · ',
    Object.assign(document.createElement('a'), { href: location.pathname, textContent: 'Standard map' }));
}

let fellBack = false;
export function fallbackToLeaflet({ reason }) {
  if (fellBack) return;
  fellBack = true;
  showNote(false);
  const mapDiv = document.getElementById('map');
  if (mapDiv) {
    mapDiv.setAttribute('data-vector-failed', reason || 'unknown');
  }
  window.dispatchEvent(new CustomEvent('vector-fallback', { detail: { reason } }));
}

// Pinned with SRI so a CDN compromise cannot run arbitrary code on preview users.
const BASE = 'https://unpkg.com/maplibre-gl@5.24.0/dist/';
const SRI = {
  js: 'sha384-5+cfbwT0iiub6VsQAdn6yz16nr6sDiQoHx6tm4O8OVYXHYOxcffFmCJBL0dgdvGp',
  css: 'sha384-uTttxo/aOKbdE5RlD/SPzSDoDmNvGlUYPjONi2MN/b7c9HPSvW07OIuyP7uL6jxK'
};
// ATL_BOUNDS from index.html padded by 2° longitude and 1° latitude. MapLibre's maxBounds
// must contain the whole viewport (Leaflet's only clamps the centre), so the exact region
// box would block zooming out far enough to fit every spot on wide or short maps.
const MAX_BOUNDS = [[-87.05, 32.15], [-81.30, 35.75]];
// The list waits for the renderer, so a slow or hanging CDN falls back quickly.
const DOWNLOAD_TIMEOUT_MS = 3000;
// Give MapLibre time to restore its own context before downgrading to Leaflet.
const CONTEXT_RESTORE_MS = 3000;

export async function loadVectorRenderer() {
  try {
    await load();
  } catch (error) {
    showNote(false);
    throw error;
  }
  // The note goes in before the map exists so MapLibre starts at its final size.
  return options => {
    showNote(true);
    try {
      return createVectorRenderer(options);
    } catch (error) {
      showNote(false);
      throw error;
    }
  };
}

async function load() {
  const isSupported = (() => {
    try {
      const canvas = document.createElement('canvas');
      return !!(window.WebGLRenderingContext && (canvas.getContext('webgl2') || canvas.getContext('webgl') || canvas.getContext('experimental-webgl')));
    } catch {
      return false;
    }
  })();
  if (!isSupported) {
    throw new Error('WebGL unsupported');
  }
  const preconnect = Object.assign(document.createElement('link'), { rel: 'preconnect', href: 'https://tiles.openfreemap.org', crossOrigin: 'anonymous' });
  document.head.append(preconnect);
  // Insert before the app's styles so its .maplibregl-* overrides win at equal specificity.
  const css = Object.assign(document.createElement('link'), { rel: 'stylesheet', href: BASE + 'maplibre-gl.css', integrity: SRI.css, crossOrigin: 'anonymous' });
  const loaded = (el, what) => new Promise((resolve, reject) => {
    el.onload = resolve;
    el.onerror = () => reject(new Error(`Map renderer ${what} unavailable`));
  });
  // Without its stylesheet MapLibre renders a broken layout, so a CSS failure also falls back.
  const cssReady = loaded(css, 'styles');
  document.head.insertBefore(css, document.head.querySelector('style'));
  const script = Object.assign(document.createElement('script'), { src: BASE + 'maplibre-gl.js', integrity: SRI.js, crossOrigin: 'anonymous' });
  const scriptReady = loaded(script, 'script');
  document.head.append(script);
  let timer;
  await Promise.race([
    Promise.all([cssReady, scriptReady]),
    new Promise((_, reject) => { timer = setTimeout(() => reject(new Error('Map renderer download timed out')), DOWNLOAD_TIMEOUT_MS); })
  ]).finally(() => clearTimeout(timer));
  if (typeof maplibregl === 'undefined') {
    throw new Error('MapLibre failed to initialize');
  }
}

function createVectorRenderer({ theme, onSelect, categories }) {
  const map = new maplibregl.Map({
    // Regional shell camera: Leaflet's [33.95, -84.17] at zoom 9 is MapLibre zoom 8.
    container: 'map', style: styleFor(theme), center: [-84.17, 33.95], zoom: 8,
    minZoom: 6, maxZoom: 19, maxBounds: MAX_BOUNDS, maxPitch: 0, dragRotate: false, pitchWithRotate: false,
    renderWorldCopies: false, attributionControl: { compact: true }
  });
  map.touchZoomRotate.disableRotation();
  map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-left');
  const canvas = map.getCanvas();
  let shops = [], byId = new Map(), selectedId = null, hoveredId = null, highlightedId;
  let ready = false, contextLost = false, pointer = null, frame = null;
  // MapLibre keeps role="region"; the label names the filtered set and the selection.
  function updateLabel() {
    const selected = byId.get(selectedId);
    canvas.setAttribute('aria-label', `Coffee shop map with ${shops.length} matching spot${shops.length === 1 ? '' : 's'}${selected ? `, ${selected.name} selected` : ''}. Use the list for keyboard and screen-reader navigation.`);
  }
  // While the WebGL context is lost MapLibre has no style; buffer state and apply it on restore.
  const live = () => ready && !contextLost && !!map.style && !!map.getSource('cafes');
  function safely(update) {
    try { update(); } catch (error) { console.warn('Vector map update deferred:', error); }
  }
  let contextTimeout = null;
  function armWatchdog() {
    clearTimeout(contextTimeout);
    // Hidden tabs often restore only when shown again, so only count visible time.
    if (!contextLost || fellBack || document.hidden) return;
    contextTimeout = setTimeout(() => {
      if (!contextLost || fellBack) return;
      console.warn('WebGL context was not restored. Falling back to Leaflet.');
      canvas.removeEventListener('webglcontextlost', onContextLost);
      document.removeEventListener('visibilitychange', armWatchdog);
      fallbackToLeaflet({ reason: 'context_loss_timeout' });
    }, CONTEXT_RESTORE_MS);
  }
  function onContextLost(e) {
    e.preventDefault(); // Allow recovery attempt
    contextLost = true;
    armWatchdog();
  }
  canvas.addEventListener('webglcontextlost', onContextLost);
  document.addEventListener('visibilitychange', armWatchdog);
  canvas.addEventListener('webglcontextrestored', () => {
    contextLost = false;
    clearTimeout(contextTimeout);
    // MapLibre re-creates its style asynchronously; re-apply buffered data, theme and selection after it loads.
    map.once('style.load', applyAll);
  });
  const feature = shop => ({ type: 'Feature', id: shop.id, geometry: { type: 'Point', coordinates: [shop.lng, shop.lat] }, properties: { id: shop.id, name: shop.name, color: categories[shop.category]?.hex || '#7b6cb8', priority: -(shop.weightedRating || 0) } });
  function updateHighlight() {
    if (!live()) return;
    const id = hoveredId || selectedId;
    if (id === highlightedId) return;
    highlightedId = id;
    const shop = byId.get(id);
    map.getSource('highlight').setData({ type: 'FeatureCollection', features: shop ? [feature(shop)] : [] });
    map.setPaintProperty('cafes', 'circle-opacity', shop ? 0.48 : 0.92);
    map.setPaintProperty('cafes', 'circle-stroke-opacity', shop ? 0.48 : 1);
  }
  function applyAll() {
    if (!live()) return;
    safely(() => {
      for (const layer of styleFor(theme).layers) {
        for (const [property, value] of Object.entries(layer.paint || {})) map.setPaintProperty(layer.id, property, value);
      }
      map.getSource('cafes').setData({ type: 'FeatureCollection', features: shops.map(feature) });
      highlightedId = undefined;
      updateHighlight();
    });
  }
  function setShops(next) {
    shops = next;
    byId = new Map(shops.map(shop => [shop.id, shop]));
    if (!byId.has(hoveredId)) hoveredId = null;
    updateLabel();
    if (live()) safely(() => {
      map.getSource('cafes').setData({ type: 'FeatureCollection', features: shops.map(feature) });
      highlightedId = undefined;
      updateHighlight();
    });
  }
  updateLabel();
  const whenReady = new Promise(resolve => map.once('style.load', () => {
    ready = true;
    setShops(shops);
    resolve();
  }));
  function pick(point) {
    if (!live() || !map.isSourceLoaded('cafes')) return null;
    const pad = matchMedia('(pointer: coarse)').matches ? 12 : 5;
    const hits = map.queryRenderedFeatures([[point.x - pad, point.y - pad], [point.x + pad, point.y + pad]], { layers: ['cafes'] });
    hits.sort((a, b) => {
      const pa = map.project(a.geometry.coordinates), pb = map.project(b.geometry.coordinates);
      return Math.hypot(pa.x - point.x, pa.y - point.y) - Math.hypot(pb.x - point.x, pb.y - point.y);
    });
    return hits.length ? byId.get(hits[0].properties.id) : null;
  }
  function clearHover() {
    cancelAnimationFrame(frame);
    frame = null;
    pointer = null;
    hoveredId = null;
    map.getCanvas().style.cursor = '';
    safely(updateHighlight);
  }
  map.on('mousemove', event => {
    pointer = event.point;
    if (frame || map.isMoving()) return;
    frame = requestAnimationFrame(() => {
      frame = null;
      hoveredId = pointer ? pick(pointer)?.id || null : null;
      map.getCanvas().style.cursor = hoveredId ? 'pointer' : '';
      safely(updateHighlight);
    });
  });
  map.on('mouseout', clearHover);
  map.on('movestart', clearHover);
  map.on('click', event => { const shop = pick(event.point); if (shop) onSelect(shop); });
  // A failed tile keeps the notice up until a later basemap tile actually loads.
  map.on('error', () => {
    if (document.getElementById('mapLoadStatus')) return;
    const status = document.createElement('div');
    status.id = 'mapLoadStatus';
    status.className = 'map-load-status';
    status.setAttribute('role', 'status');
    status.textContent = 'Some map detail could not load. Shop search and the list are still available.';
    document.getElementById('map').append(status);
  });
  map.on('sourcedata', e => {
    if (e.sourceId === 'openmaptiles' && e.tile && e.tile.state === 'loaded') document.getElementById('mapLoadStatus')?.remove();
  });
  return {
    map, whenReady, setShops,
    select(shop) { selectedId = shop?.id || null; hoveredId = null; updateLabel(); safely(updateHighlight); },
    setTheme(next) {
      theme = next;
      if (ready) applyAll(); else whenReady.then(applyAll);
    }
  };
}
