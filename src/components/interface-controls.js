/**
 * Interface Controls and Central HUD Module (src/components/interface-controls.js)
 * NASA Institutional Focus: NASA GIBS Blue Marble Next Generation, NASA VIIRS,
 * and Multi-resolution HD Satellite Imagery layers.
 */
import { APP_CONFIG } from '../config/constants.js';
import { createSafeElement } from '../utils/sanitizer.js';
import { eventBus } from '../utils/event-bus.js';
import { formatDMS } from '../utils/coordinates.js';

const PRESET_REGIONS = Object.freeze([
  {
    id: 'global',
    label: 'Global Orbit (12,500 km)',
    latitude: -23.8634,
    longitude: -69.1328,
    altitudeKm: 12500
  },
  {
    id: 'atacama',
    label: 'South America — Atacama (850 km)',
    latitude: -23.8634,
    longitude: -69.1328,
    altitudeKm: 850
  },
  {
    id: 'hawaii',
    label: 'Pacific — Hawaii / Mauna Loa (380 km)',
    latitude: 19.4756,
    longitude: -155.5828,
    altitudeKm: 380
  },
  {
    id: 'sahara',
    label: 'Africa — Sahara / Tibesti (1,400 km)',
    latitude: 20.78,
    longitude: 18.05,
    altitudeKm: 1400
  },
  {
    id: 'antarctica',
    label: 'Antarctica — McMurdo Dry Valleys (950 km)',
    latitude: -77.55,
    longitude: 161.8,
    altitudeKm: 950
  }
]);

const IMAGERY_MODES = Object.freeze([
  { id: 'nasa_hybrid', label: 'Layer: NASA Blue Marble + HD Satellite' },
  { id: 'nasa_bluemarble', label: 'Layer: NASA GIBS Blue Marble (Official)' },
  { id: 'nasa_viirs', label: 'Layer: NASA GIBS VIIRS (Suomi NPP)' },
  { id: 'world_imagery', label: 'Layer: Landsat/Maxar Satellite (Zoom 18)' }
]);

/**
 * Builds the floating top HUD bar over the central globe stage.
 * @returns {HTMLElement}
 */
export function createTopHudBar() {
  const header = createSafeElement('header', {
    className: 'central-top-hud',
    attributes: { role: 'banner', 'aria-label': 'Mission Identification and Camera Controls' }
  });

  // Left block: Mission identity
  const brandGroup = createSafeElement('div', { className: 'hud-brand-group' });

  const statusDot = createSafeElement('span', {
    className: 'hud-status-indicator',
    attributes: { 'aria-hidden': 'true' }
  });

  const titleWrap = createSafeElement('div', { className: 'hud-title-wrap' });
  const appTitle = createSafeElement('span', {
    className: 'hud-app-name',
    text: APP_CONFIG.appName
  });
  const editionBadge = createSafeElement('span', {
    className: 'hud-edition-tag',
    text: APP_CONFIG.challengeEdition
  });

  titleWrap.append(appTitle, editionBadge);
  brandGroup.append(statusDot, titleWrap);

  // Right block: Navigation controls, NASA scientific layers, and atmosphere
  const controlsGroup = createSafeElement('nav', {
    className: 'hud-controls-group',
    attributes: { 'aria-label': 'Globe Navigation and Layer Controls' }
  });

  const regionSelect = createSafeElement('select', {
    className: 'hud-region-select',
    attributes: {
      id: 'hud-region-select',
      'aria-label': 'Fly smoothly to planetary analog region'
    }
  });

  for (const region of PRESET_REGIONS) {
    const option = createSafeElement('option', {
      text: region.label,
      attributes: { value: region.id }
    });
    regionSelect.appendChild(option);
  }

  regionSelect.addEventListener('change', () => {
    const selected = PRESET_REGIONS.find((r) => r.id === regionSelect.value);
    if (selected) {
      eventBus.emit('profile:select', { profileId: 'earth_default', source: 'region-select' });
      eventBus.emit('globe:fly-to-preset', selected);
    }
  });

  const imagerySelect = createSafeElement('select', {
    className: 'hud-region-select',
    attributes: {
      id: 'hud-imagery-select',
      'aria-label': 'Select NASA scientific satellite imagery data source'
    }
  });

  for (const mode of IMAGERY_MODES) {
    const option = createSafeElement('option', {
      text: mode.label,
      attributes: { value: mode.id }
    });
    imagerySelect.appendChild(option);
  }

  imagerySelect.addEventListener('change', () => {
    eventBus.emit('globe:change-imagery-mode', { mode: imagerySelect.value });
  });

  const btnAutoRotate = createSafeElement('button', {
    className: 'hud-control-btn is-active',
    text: 'Rotation: ON',
    attributes: {
      type: 'button',
      id: 'btn-toggle-autorotate',
      'aria-pressed': 'true',
      title: 'Enable or pause continuous axial rotation of the Earth globe'
    }
  });

  const btnResetCamera = createSafeElement('button', {
    className: 'hud-control-btn',
    text: 'Reset Orbit',
    attributes: {
      type: 'button',
      id: 'btn-reset-camera',
      title: 'Return the globe camera to the default orbital position'
    }
  });

  btnAutoRotate.addEventListener('click', () => {
    const isPressed = btnAutoRotate.getAttribute('aria-pressed') === 'true';
    const nextState = !isPressed;
    eventBus.emit('globe:toggle-autorotate', { enabled: nextState });
  });

  eventBus.on('globe:autorotate-changed', (payload) => {
    if (!payload) return;
    const active = Boolean(payload.enabled);
    btnAutoRotate.setAttribute('aria-pressed', String(active));
    btnAutoRotate.classList.toggle('is-active', active);
    btnAutoRotate.textContent = active ? 'Rotation: ON' : 'Rotation: OFF';
  });

  btnResetCamera.addEventListener('click', () => {
    regionSelect.value = 'global';
    eventBus.emit('globe:reset-camera', {
      latitude: APP_CONFIG.defaultCoordinates.latitude,
      longitude: APP_CONFIG.defaultCoordinates.longitude,
      altitudeKm: APP_CONFIG.defaultCoordinates.altitudeKm
    });
    eventBus.emit('profile:select', { profileId: 'earth_default', source: 'reset-camera' });
  });

  controlsGroup.append(
    regionSelect,
    imagerySelect,
    btnAutoRotate,
    btnResetCamera
  );
  header.append(brandGroup, controlsGroup);

  return header;
}

/**
 * Builds the bottom geospatial telemetry bar in the central region.
 * @returns {HTMLElement}
 */
export function createBottomTelemetryBar() {
  const footer = createSafeElement('footer', {
    className: 'central-bottom-hud',
    attributes: { 'aria-label': 'Real-Time Geospatial Telemetry' }
  });

  const createTelemetryCell = (label, initialValue, valueId) => {
    const cell = createSafeElement('div', { className: 'telemetry-cell' });
    const lbl = createSafeElement('span', { className: 'telemetry-label', text: label });
    const val = createSafeElement('span', {
      className: 'telemetry-value',
      text: initialValue,
      attributes: { id: valueId }
    });
    cell.append(lbl, val);
    return { cell, val };
  };

  const defaultLat = formatDMS(APP_CONFIG.defaultCoordinates.latitude, 'lat');
  const defaultLon = formatDMS(APP_CONFIG.defaultCoordinates.longitude, 'lon');

  const latCell = createTelemetryCell('CURSOR LATITUDE', defaultLat, 'hud-telemetry-lat');
  const lonCell = createTelemetryCell('CURSOR LONGITUDE', defaultLon, 'hud-telemetry-lon');
  const altCell = createTelemetryCell(
    'CAMERA ALTITUDE',
    `${APP_CONFIG.defaultCoordinates.altitudeKm.toLocaleString('en-US')} km`,
    'hud-telemetry-alt'
  );
  const datumCell = createTelemetryCell(
    'DATA SOURCE / DATUM',
    'NASA GIBS + LANDSAT HD // WGS84',
    'hud-telemetry-datum'
  );

  footer.append(latCell.cell, lonCell.cell, altCell.cell, datumCell.cell);

  eventBus.on('globe:pointer-move', (coords) => {
    if (!coords) return;
    if (typeof coords.latitude === 'number') {
      latCell.val.textContent = formatDMS(coords.latitude, 'lat');
    }
    if (typeof coords.longitude === 'number') {
      lonCell.val.textContent = formatDMS(coords.longitude, 'lon');
    }
    if (typeof coords.altitudeKm === 'number') {
      altCell.val.textContent = `${Math.round(coords.altitudeKm).toLocaleString('en-US')} km`;
    }
  });

  eventBus.on('globe:change-imagery-mode', (payload) => {
    if (!payload) return;
    const labels = {
      nasa_hybrid: 'NASA GIBS + LANDSAT HD // WGS84',
      nasa_bluemarble: 'NASA GIBS BLUE MARBLE // WGS84',
      nasa_viirs: 'NASA GIBS VIIRS // WGS84',
      world_imagery: 'LANDSAT / MAXAR HD // WGS84'
    };
    datumCell.val.textContent = labels[payload.mode] || 'NASA GIBS // WGS84';
  });

  return footer;
}
