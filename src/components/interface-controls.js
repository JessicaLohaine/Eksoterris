/**
 * Módulo de Controles da Interface e HUD Central (src/components/interface-controls.js)
 * Responsável pelo cabeçalho superior do palco central (seletores de região, camada
 * científica de satélite, rotação, iluminação solar e camada de nuvens) e pela barra
 * inferior de telemetria geoespacial em tempo real.
 */
import { APP_CONFIG } from '../config/constants.js';
import { createSafeElement } from '../utils/sanitizer.js';
import { eventBus } from '../utils/event-bus.js';
import { formatDMS } from '../utils/coordinates.js';

const PRESET_REGIONS = Object.freeze([
  {
    id: 'global',
    label: 'Órbita Global (12.500 km)',
    latitude: -23.8634,
    longitude: -69.1328,
    altitudeKm: 12500
  },
  {
    id: 'atacama',
    label: 'América do Sul — Atacama (850 km)',
    latitude: -23.8634,
    longitude: -69.1328,
    altitudeKm: 850
  },
  {
    id: 'hawaii',
    label: 'Pacífico — Havaí / Mauna Loa (380 km)',
    latitude: 19.4756,
    longitude: -155.5828,
    altitudeKm: 380
  },
  {
    id: 'sahara',
    label: 'África — Saara / Tibesti (1.400 km)',
    latitude: 20.78,
    longitude: 18.05,
    altitudeKm: 1400
  },
  {
    id: 'antarctica',
    label: 'Antártida — Vales Secos (950 km)',
    latitude: -77.55,
    longitude: 161.8,
    altitudeKm: 950
  }
]);

const IMAGERY_MODES = Object.freeze([
  { id: 'hybrid', label: 'Camada: Híbrido Sentinel-2 + Satélite HD' },
  { id: 'sentinel2', label: 'Camada: Sentinel-2 Cloudless (ESA)' },
  { id: 'world_imagery', label: 'Camada: Satélite Maxar/Esri (Zoom 18)' },
  { id: 'nasa_bluemarble', label: 'Camada: NASA GIBS Blue Marble' },
  { id: 'nasa_viirs', label: 'Camada: NASA GIBS VIIRS True Color' }
]);

/**
 * Constrói a barra superior flutuante sobre a região central do globo.
 * @returns {HTMLElement}
 */
export function createTopHudBar() {
  const header = createSafeElement('header', {
    className: 'central-top-hud',
    attributes: { role: 'banner', 'aria-label': 'Identificação da Missão e Controles de Câmera' }
  });

  // Bloco esquerdo: Identidade da missão
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

  // Bloco direito: Controles de navegação, camadas científicas e atmosfera
  const controlsGroup = createSafeElement('nav', {
    className: 'hud-controls-group',
    attributes: { 'aria-label': 'Controles de Navegação e Camadas do Globo' }
  });

  // Seletor de transição suave (flyTo) para explorar diferentes regiões do planeta
  const regionSelect = createSafeElement('select', {
    className: 'hud-region-select',
    attributes: {
      id: 'hud-region-select',
      'aria-label': 'Navegar suavemente para região do planeta'
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
      eventBus.emit('globe:fly-to-preset', selected);
      eventBus.emit('profile:select', { profileId: 'earth_default', source: 'region-select' });
    }
  });

  // Seletor de fonte científica de satélite (Sentinel-2, Maxar/Esri, NASA GIBS)
  const imagerySelect = createSafeElement('select', {
    className: 'hud-region-select',
    attributes: {
      id: 'hud-imagery-select',
      'aria-label': 'Selecionar fonte científica de imagem de satélite'
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
    text: 'Rotação: ON',
    attributes: {
      type: 'button',
      id: 'btn-toggle-autorotate',
      'aria-pressed': 'true',
      title: 'Ativar ou pausar a rotação axial contínua do Globo Terrestre'
    }
  });

  const btnToggleLighting = createSafeElement('button', {
    className: 'hud-control-btn is-active',
    text: 'Luz Solar',
    attributes: {
      type: 'button',
      id: 'btn-toggle-lighting',
      'aria-pressed': 'true',
      title: 'Alternar iluminação direcional solar e transição dia/noite'
    }
  });

  const btnToggleClouds = createSafeElement('button', {
    className: 'hud-control-btn is-active',
    text: 'Nuvens',
    attributes: {
      type: 'button',
      id: 'btn-toggle-clouds',
      'aria-pressed': 'true',
      title: 'Mostrar ou ocultar a camada global de nuvens'
    }
  });

  const btnResetCamera = createSafeElement('button', {
    className: 'hud-control-btn',
    text: 'Resetar Órbita',
    attributes: {
      type: 'button',
      id: 'btn-reset-camera',
      title: 'Retornar a câmera do globo para a posição orbital padrão'
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
    btnAutoRotate.textContent = active ? 'Rotação: ON' : 'Rotação: OFF';
  });

  btnToggleLighting.addEventListener('click', () => {
    const isPressed = btnToggleLighting.getAttribute('aria-pressed') === 'true';
    const nextState = !isPressed;
    btnToggleLighting.setAttribute('aria-pressed', String(nextState));
    btnToggleLighting.classList.toggle('is-active', nextState);
    eventBus.emit('globe:toggle-lighting', { enabled: nextState });
  });

  btnToggleClouds.addEventListener('click', () => {
    const isPressed = btnToggleClouds.getAttribute('aria-pressed') === 'true';
    const nextState = !isPressed;
    btnToggleClouds.setAttribute('aria-pressed', String(nextState));
    btnToggleClouds.classList.toggle('is-active', nextState);
    eventBus.emit('globe:toggle-clouds', { enabled: nextState });
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
    btnToggleLighting,
    btnToggleClouds,
    btnResetCamera
  );
  header.append(brandGroup, controlsGroup);

  return header;
}

/**
 * Constrói a barra inferior de telemetria da região central (coordenadas do cursor, altitude e datum).
 * @returns {HTMLElement}
 */
export function createBottomTelemetryBar() {
  const footer = createSafeElement('footer', {
    className: 'central-bottom-hud',
    attributes: { 'aria-label': 'Telemetria Geoespacial em Tempo Real' }
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

  const latCell = createTelemetryCell('LATITUDE CURSOR', defaultLat, 'hud-telemetry-lat');
  const lonCell = createTelemetryCell('LONGITUDE CURSOR', defaultLon, 'hud-telemetry-lon');
  const altCell = createTelemetryCell(
    'ALTITUDE CÂMERA',
    `${APP_CONFIG.defaultCoordinates.altitudeKm.toLocaleString('pt-BR')} km`,
    'hud-telemetry-alt'
  );
  const datumCell = createTelemetryCell('SATÉLITE / DATUM', 'SENTINEL-2 + MAXAR // WGS84', 'hud-telemetry-datum');

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
      altCell.val.textContent = `${Math.round(coords.altitudeKm).toLocaleString('pt-BR')} km`;
    }
  });

  eventBus.on('globe:change-imagery-mode', (payload) => {
    if (!payload) return;
    const labels = {
      hybrid: 'SENTINEL-2 + MAXAR // WGS84',
      sentinel2: 'ESA SENTINEL-2 // WGS84',
      world_imagery: 'ESRI MAXAR HD // WGS84',
      nasa_bluemarble: 'NASA GIBS BLUE MARBLE // WGS84',
      nasa_viirs: 'NASA GIBS VIIRS // WGS84'
    };
    datumCell.val.textContent = labels[payload.mode] || 'CESIUM 3D // WGS84';
  });

  return footer;
}
