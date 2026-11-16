/**
 * Left Region Module — Moon and Mars (src/components/sidebar.js)
 * Stage 6: Visual refinement, subtle 3D interaction hints, and orbital reset button.
 */
import { MOON_METADATA } from '../planets/moon.js';
import { MARS_METADATA } from '../planets/mars.js';
import { createSafeElement } from '../utils/sanitizer.js';
import { eventBus } from '../utils/event-bus.js';

/**
 * Creates a celestial body card for the left sidebar.
 * @param {Object} config
 * @returns {HTMLElement}
 */
function createCelestialCard(config) {
  const article = createSafeElement('article', {
    className: `celestial-card ${config.accentClass}`,
    attributes: {
      id: `card-${config.id}`,
      'data-profile-id': config.profileId,
      'aria-label': `3D Viewer — ${config.title}`
    }
  });

  // Card Header
  const cardHeader = createSafeElement('header', { className: 'celestial-card-header' });
  const titleGroup = createSafeElement('div', { className: 'celestial-title-group' });
  const codeSpan = createSafeElement('span', { className: 'celestial-code', text: config.code });
  const nameHeading = createSafeElement('h2', { className: 'celestial-name', text: config.title });
  titleGroup.append(codeSpan, nameHeading);

  const actionsGroup = createSafeElement('div', { className: 'celestial-actions-group' });

  const resetViewBtn = createSafeElement('button', {
    className: 'celestial-micro-btn',
    text: 'Reset 3D',
    attributes: {
      type: 'button',
      title: `Reset 3D camera for ${config.title}`,
      'aria-label': `Reset 3D camera for ${config.title}`
    }
  });

  resetViewBtn.addEventListener('click', () => {
    eventBus.emit('planet:reset-view', { id: config.id });
  });

  const inspectBtn = createSafeElement('button', {
    className: 'celestial-inspect-btn',
    text: 'View Data',
    attributes: {
      type: 'button',
      title: `Display reference parameters for ${config.title} in the right panel`,
      'aria-label': `Display reference data for ${config.title} in the right panel`
    }
  });

  inspectBtn.addEventListener('click', () => {
    eventBus.emit('profile:select', {
      profileId: config.profileId,
      source: `sidebar-${config.id}`
    });
  });

  actionsGroup.append(resetViewBtn, inspectBtn);
  cardHeader.append(titleGroup, actionsGroup);

  // 3D Viewport (Receives the Three.js canvas)
  const viewportContainer = createSafeElement('div', {
    className: 'celestial-viewport',
    attributes: {
      id: config.viewportId,
      role: 'img',
      'aria-label': `Interactive 3D model of ${config.title}`
    }
  });

  // Initial placeholder (automatically removed by PlanetRenderer.init)
  const stagePlaceholder = createSafeElement('div', {
    className: `celestial-stage-placeholder placeholder-${config.id}`,
    attributes: { 'data-stage-placeholder': 'true' }
  });
  const spherePreview = createSafeElement('div', {
    className: `celestial-sphere-preview sphere-${config.id}`
  });
  stagePlaceholder.appendChild(spherePreview);

  // Subtle interactivity hint over the 3D viewport
  const interactionHint = createSafeElement('span', {
    className: 'celestial-interaction-hint',
    text: 'Drag 360° • Scroll Zoom',
    attributes: { 'aria-hidden': 'true' }
  });

  viewportContainer.append(stagePlaceholder, interactionHint);

  // Compact footer with physical reference parameters
  const metricsFooter = createSafeElement('footer', { className: 'celestial-metrics' });
  for (const [label, value] of config.metrics) {
    const metricItem = createSafeElement('div', { className: 'celestial-metric-item' });
    const metricLabel = createSafeElement('span', { className: 'celestial-metric-label', text: label });
    const metricVal = createSafeElement('span', { className: 'celestial-metric-val', text: value });
    metricItem.append(metricLabel, metricVal);
    metricsFooter.appendChild(metricItem);
  }

  article.append(cardHeader, viewportContainer, metricsFooter);
  return article;
}

/**
 * Initializes and returns the left region (stacked Moon and Mars cards).
 * @returns {HTMLElement}
 */
export function createLeftSidebar() {
  const aside = createSafeElement('aside', {
    className: 'region-left-sidebar',
    attributes: {
      id: 'left-sidebar',
      'aria-label': 'Reference Celestial Bodies: Moon and Mars'
    }
  });

  const sectionHeader = createSafeElement('div', { className: 'sidebar-section-header' });
  const sectionTag = createSafeElement('span', {
    className: 'sidebar-section-tag',
    text: 'REFERENCE BODIES // 3D'
  });
  const sectionDesc = createSafeElement('p', {
    className: 'sidebar-section-desc',
    text: 'Interactive three-dimensional models for comparison with terrestrial analog environments.'
  });
  sectionHeader.append(sectionTag, sectionDesc);

  const stackContainer = createSafeElement('div', { className: 'celestial-stack' });

  const moonCard = createCelestialCard({
    id: 'moon',
    code: 'SATELLITE // EARTH-I',
    title: MOON_METADATA.name,
    subtitle: 'Selenological Reference',
    viewportId: 'moon-three-viewport',
    profileId: 'moon_reference',
    accentClass: 'accent-moon',
    metrics: [
      ['MEAN RADIUS', `${MOON_METADATA.meanRadiusKm.toLocaleString('en-US')} km`],
      ['GRAVITY', `${MOON_METADATA.surfaceGravityMs2.toLocaleString('en-US')} m/s²`]
    ]
  });

  const marsCard = createCelestialCard({
    id: 'mars',
    code: 'PLANET // SOL-IV',
    title: MARS_METADATA.name,
    subtitle: 'Areological Reference',
    viewportId: 'mars-three-viewport',
    profileId: 'mars_reference',
    accentClass: 'accent-mars',
    metrics: [
      ['MEAN RADIUS', `${MARS_METADATA.meanRadiusKm.toLocaleString('en-US')} km`],
      ['GRAVITY', `${MARS_METADATA.surfaceGravityMs2.toLocaleString('en-US')} m/s²`]
    ]
  });

  stackContainer.append(moonCard, marsCard);
  aside.append(sectionHeader, stackContainer);

  eventBus.on('profile:select', (payload) => {
    if (!payload) return;
    moonCard.classList.toggle('is-selected', payload.profileId === 'moon_reference');
    marsCard.classList.toggle('is-selected', payload.profileId === 'mars_reference');
  });

  return aside;
}
