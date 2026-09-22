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
      { id: 'cafe-labels', type: 'symbol', source: 'cafes', minzoom: 13, layout: { 'text-field': ['get', 'name'], 'text-font': ['Noto Sans Regular'], 'text-size': 12, 'text-variable-anchor': ['bottom', 'top', 'right', 'left'], 'text-radial-offset': 1, 'symbol-sort-key': ['get', 'priority'] }, paint: text },
      { id: 'highlight-glow', type: 'circle', source: 'highlight', paint: { 'circle-color': '#DCAF59', 'circle-radius': ['interpolate', ['linear'], ['zoom'], 7, 15, 15, 24], 'circle-blur': 0.7, 'circle-opacity': 0.4 } },
      { id: 'highlight-point', type: 'circle', source: 'highlight', paint: { 'circle-color': ['get', 'color'], 'circle-radius': ['interpolate', ['linear'], ['zoom'], 7, 5.5, 15, 10], 'circle-stroke-color': '#DCAF59', 'circle-stroke-width': 2.5 } }
    ]
  };
}

export function fallbackToLeaflet({ reason }) {
  const mapDiv = document.getElementById('map');
  if (mapDiv) {
    mapDiv.replaceChildren();
    mapDiv.setAttribute('data-vector-failed', reason || 'unknown');
  }
  window.dispatchEvent(new CustomEvent('vector-fallback', { detail: { reason } }));
}

export async function loadVectorRenderer() {
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
  const base = 'https://unpkg.com/maplibre-gl@5.24.0/dist/';
  for (const [rel, href] of [['preconnect', 'https://tiles.openfreemap.org'], ['stylesheet', base + 'maplibre-gl.css']]) {
    const link = document.createElement('link');
    link.rel = rel;
    link.href = href;
    document.head.append(link);
  }
  await new Promise((resolve, reject) => {
    const script = document.createElement('script');
    const timeout = setTimeout(() => reject(new Error('Map renderer download timed out')), 8000);
    script.src = base + 'maplibre-gl.js';
    script.onload = () => { clearTimeout(timeout); resolve(); };
    script.onerror = () => { clearTimeout(timeout); reject(new Error('Map renderer unavailable')); };
    document.head.append(script);
  });
  if (typeof maplibregl === 'undefined') {
    throw new Error('MapLibre failed to initialize');
  }
  return createVectorRenderer;
}

function createVectorRenderer({ theme, onSelect, categories }) {
  const map = new maplibregl.Map({
    container: 'map', style: styleFor(theme), center: [-84.142, 33.972], zoom: 10,
    minZoom: 6, maxZoom: 19, maxPitch: 0, dragRotate: false, pitchWithRotate: false,
    renderWorldCopies: false, attributionControl: { compact: true }
  });
  map.touchZoomRotate.disableRotation();
  map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-left');
  const canvas = map.getCanvas();
  canvas.setAttribute('role', 'img');
  canvas.setAttribute('aria-label', 'Interactive coffee shop map. Use the list below for keyboard and screen-reader navigation.');
  let contextTimeout = null;
  canvas.addEventListener('webglcontextlost', (e) => {
    e.preventDefault(); // Allow recovery attempt
    contextTimeout = setTimeout(() => {
      console.warn('WebGL context loss timeout. Falling back to Leaflet.');
      try { map.remove(); } catch {}
      fallbackToLeaflet({ reason: 'context_loss_timeout' });
    }, 1500);
  });
  canvas.addEventListener('webglcontextrestored', () => {
    clearTimeout(contextTimeout);
    if (ready) setShops(shops);
  });
  let shops = [], byId = new Map(), selectedId = null, hoveredId = null, highlightedId;
  let ready = false, pointer = null, frame = null;
  const feature = shop => ({ type: 'Feature', id: shop.id, geometry: { type: 'Point', coordinates: [shop.lng, shop.lat] }, properties: { id: shop.id, name: shop.name, color: categories[shop.category]?.hex || '#7b6cb8', priority: -(shop.weightedRating || 0) } });
  function updateHighlight() {
    if (!ready) return;
    const id = hoveredId || selectedId;
    if (id === highlightedId) return;
    highlightedId = id;
    const shop = byId.get(id);
    map.getSource('highlight').setData({ type: 'FeatureCollection', features: shop ? [feature(shop)] : [] });
    map.setPaintProperty('cafes', 'circle-opacity', shop ? 0.48 : 0.92);
    map.setPaintProperty('cafes', 'circle-stroke-opacity', shop ? 0.48 : 1);
  }
  function setShops(next) {
    shops = next;
    byId = new Map(shops.map(shop => [shop.id, shop]));
    if (!byId.has(hoveredId)) hoveredId = null;
    if (ready) {
      map.getSource('cafes').setData({ type: 'FeatureCollection', features: shops.map(feature) });
      highlightedId = undefined;
      updateHighlight();
    }
  }
  const whenReady = new Promise(resolve => map.once('style.load', () => {
    ready = true;
    setShops(shops);
    resolve();
  }));
  function pick(point) {
    if (!ready || !map.isSourceLoaded('cafes')) return null;
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
    updateHighlight();
  }
  map.on('mousemove', event => {
    pointer = event.point;
    if (frame || map.isMoving()) return;
    frame = requestAnimationFrame(() => {
      frame = null;
      hoveredId = pointer ? pick(pointer)?.id || null : null;
      map.getCanvas().style.cursor = hoveredId ? 'pointer' : '';
      updateHighlight();
    });
  });
  map.on('mouseout', clearHover);
  map.on('movestart', clearHover);
  map.on('click', event => { const shop = pick(event.point); if (shop) onSelect(shop); });
  map.on('error', () => {
    if (document.getElementById('mapLoadStatus')) return;
    const status = document.createElement('div');
    status.id = 'mapLoadStatus';
    status.className = 'map-load-status';
    status.setAttribute('role', 'status');
    status.textContent = 'Some map detail could not load. Shop search and the list are still available.';
    document.getElementById('map').append(status);
  });
  map.on('idle', () => {
    if (map.areTilesLoaded()) document.getElementById('mapLoadStatus')?.remove();
  });
  return {
    map, whenReady, setShops,
    select(shop) { selectedId = shop?.id || null; hoveredId = null; updateHighlight(); },
    setTheme(next) {
      theme = next;
      const apply = () => {
        for (const layer of styleFor(theme).layers) {
          for (const [property, value] of Object.entries(layer.paint || {})) map.setPaintProperty(layer.id, property, value);
        }
        highlightedId = undefined;
        updateHighlight();
      };
      if (ready) apply(); else whenReady.then(apply);
    }
  };
}
