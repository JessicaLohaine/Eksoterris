/**
 * Módulo da Região Esquerda — Lua e Marte (src/components/sidebar.js)
 * Etapa 6: Refinamento visual, dicas discretas de interação 3D e botão de reset orbital.
 */
import { MOON_METADATA } from '../planets/moon.js';
import { MARS_METADATA } from '../planets/mars.js';
import { createSafeElement } from '../utils/sanitizer.js';
import { eventBus } from '../utils/event-bus.js';

/**
 * Cria um cartão de corpo celeste para a barra lateral esquerda.
 * @param {Object} config
 * @returns {HTMLElement}
 */
function createCelestialCard(config) {
  const article = createSafeElement('article', {
    className: `celestial-card ${config.accentClass}`,
    attributes: {
      id: `card-${config.id}`,
      'data-profile-id': config.profileId,
      'aria-label': `Visualizador 3D — ${config.title}`
    }
  });

  // Cabeçalho do Card
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
      title: `Reposicionar câmera 3D de ${config.title}`,
      'aria-label': `Reposicionar câmera 3D de ${config.title}`
    }
  });

  resetViewBtn.addEventListener('click', () => {
    eventBus.emit('planet:reset-view', { id: config.id });
  });

  const inspectBtn = createSafeElement('button', {
    className: 'celestial-inspect-btn',
    text: 'Ver Dados',
    attributes: {
      type: 'button',
      title: `Exibir parâmetros demonstrativos de ${config.title} no painel direito`,
      'aria-label': `Exibir dados demonstrativos de ${config.title} no painel direito`
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

  // Viewport 3D (Recebe o canvas do Three.js)
  const viewportContainer = createSafeElement('div', {
    className: 'celestial-viewport',
    attributes: {
      id: config.viewportId,
      role: 'img',
      'aria-label': `Modelo 3D interativo de ${config.title}`
    }
  });

  // Placeholder inicial (removido automaticamente pelo PlanetRenderer.init)
  const stagePlaceholder = createSafeElement('div', {
    className: `celestial-stage-placeholder placeholder-${config.id}`,
    attributes: { 'data-stage-placeholder': 'true' }
  });
  const spherePreview = createSafeElement('div', {
    className: `celestial-sphere-preview sphere-${config.id}`
  });
  stagePlaceholder.appendChild(spherePreview);

  // Legenda sutil de interatividade sobre o viewport 3D
  const interactionHint = createSafeElement('span', {
    className: 'celestial-interaction-hint',
    text: 'Arraste 360° • Scroll Zoom',
    attributes: { 'aria-hidden': 'true' }
  });

  viewportContainer.append(stagePlaceholder, interactionHint);

  // Rodapé compacto com parâmetros físicos de referência
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
 * Inicializa e retorna a região esquerda (Lua e Marte empilhados).
 * @returns {HTMLElement}
 */
export function createLeftSidebar() {
  const aside = createSafeElement('aside', {
    className: 'region-left-sidebar',
    attributes: {
      id: 'left-sidebar',
      'aria-label': 'Corpos Celestes de Comparação: Lua e Marte'
    }
  });

  const sectionHeader = createSafeElement('div', { className: 'sidebar-section-header' });
  const sectionTag = createSafeElement('span', {
    className: 'sidebar-section-tag',
    text: 'ASTROS DE REFERÊNCIA // 3D'
  });
  const sectionDesc = createSafeElement('p', {
    className: 'sidebar-section-desc',
    text: 'Modelos tridimensionais interativos para comparação com ambientes terrestres.'
  });
  sectionHeader.append(sectionTag, sectionDesc);

  const stackContainer = createSafeElement('div', { className: 'celestial-stack' });

  const moonCard = createCelestialCard({
    id: 'moon',
    code: 'SATÉLITE // TERRA-I',
    title: MOON_METADATA.name,
    subtitle: 'Referência Selenológica',
    viewportId: 'moon-three-viewport',
    profileId: 'moon_reference',
    accentClass: 'accent-moon',
    metrics: [
      ['RAIO MÉDIO', `${MOON_METADATA.meanRadiusKm.toLocaleString('pt-BR')} km`],
      ['GRAVIDADE', `${MOON_METADATA.surfaceGravityMs2.toLocaleString('pt-BR')} m/s²`]
    ]
  });

  const marsCard = createCelestialCard({
    id: 'mars',
    code: 'PLANETA // SOL-IV',
    title: MARS_METADATA.name,
    subtitle: 'Referência Areológica',
    viewportId: 'mars-three-viewport',
    profileId: 'mars_reference',
    accentClass: 'accent-mars',
    metrics: [
      ['RAIO MÉDIO', `${MARS_METADATA.meanRadiusKm.toLocaleString('pt-BR')} km`],
      ['GRAVIDADE', `${MARS_METADATA.surfaceGravityMs2.toLocaleString('pt-BR')} m/s²`]
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
