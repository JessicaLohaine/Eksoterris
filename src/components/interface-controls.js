/**
 * Módulo de Controles da Interface e HUD Central (src/components/interface-controls.js)
 * Responsável pelo cabeçalho superior do palco central e pela barra inferior de
 * telemetria de coordenadas/status, mantendo o Globo Terrestre 3D como protagonista.
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
    label: 'América do Sul — Atacama (1.800 km)',
    latitude: -23.8634,
    longitude: -69.1328,
    altitudeKm: 1800
  },
  {
    id: 'hawaii',
    label: 'Pacífico — Havaí / Mauna Loa (1.400 km)',
    latitude: 19.4756,
    longitude: -155.5828,
    altitudeKm: 1400
  },
  {
    id: 'antarctica',
    label: 'Antártida — Vales Secos (2.200 km)',
    latitude: -77.55,
    longitude: 161.8,
    altitudeKm: 2200
  }
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

  // Bloco direito: Controles de navegação e iluminação do Globo Terrestre
  const controlsGroup = createSafeElement('nav', {
    className: 'hud-controls-group',
    attributes: { 'aria-label': 'Controles de Navegação do Globo' }
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

  const btnResetCamera = createSafeElement('button', {
    className: 'hud-control-btn',
    text: 'Resetar Órbita',
    attributes: {
      type: 'button',
      id: 'btn-reset-camera',
      title: 'Retornar a câmera do globo para a posição orbital padrão'
    }
  });

  const btnToggleLighting = createSafeElement('button', {
    className: 'hud-control-btn',
    text: 'Luz Solar',
    attributes: {
      type: 'button',
      id: 'btn-toggle-lighting',
      'aria-pressed': 'false',
      title: 'Alternar iluminação dia/noite no globo terrestre'
    }
  });

  btnAutoRotate.addEventListener('click', () => {
    const isPressed = btnAutoRotate.getAttribute('aria-pressed') === 'true';
    const nextState = !isPressed;
    eventBus.emit('globe:toggle-autorotate', { enabled: nextState });
  });

  // Sincroniza estado visual do botão quando o usuário pausa a rotação arrastando o globo
  eventBus.on('globe:autorotate-changed', (payload) => {
    if (!payload) return;
    const active = Boolean(payload.enabled);
    btnAutoRotate.setAttribute('aria-pressed', String(active));
    btnAutoRotate.classList.toggle('is-active', active);
    btnAutoRotate.textContent = active ? 'Rotação: ON' : 'Rotação: OFF';
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

  btnToggleLighting.addEventListener('click', () => {
    const isPressed = btnToggleLighting.getAttribute('aria-pressed') === 'true';
    const nextState = !isPressed;
    btnToggleLighting.setAttribute('aria-pressed', String(nextState));
    btnToggleLighting.classList.toggle('is-active', nextState);
    eventBus.emit('globe:toggle-lighting', { enabled: nextState });
  });

  controlsGroup.append(regionSelect, btnAutoRotate, btnResetCamera, btnToggleLighting);
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
  const datumCell = createTelemetryCell('MOTOR / DATUM', 'CESIUM 3D // WGS84', 'hud-telemetry-datum');

  footer.append(latCell.cell, lonCell.cell, altCell.cell, datumCell.cell);

  // Escuta atualizações de coordenadas emitidas pelo Globo Terrestre (Etapa 4)
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

  return footer;
}
