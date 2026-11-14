/**
 * Módulo da Região Direita — Painel de Informações Científicas e Geográficas
 * (src/components/information-panel.js)
 *
 * Etapa 6: Adição de ícones vetoriais científicos seguros (SVG), transições suaves
 * ao alternar perfis e destaque visual ao capturar coordenadas no Globo Terrestre.
 */
import { APP_CONFIG } from '../config/constants.js';
import { PLACEHOLDER_SCIENTIFIC_DATA } from '../config/mock-data.js';
import { createSafeElement, createScientificIcon, sanitizeText } from '../utils/sanitizer.js';
import { eventBus } from '../utils/event-bus.js';
import { formatDMS } from '../utils/coordinates.js';

/**
 * Cria um bloco modular (seção científica) dentro do painel direito.
 * @param {string} code Código técnico da seção (ex: "SEC-01")
 * @param {string} iconKey Chave do ícone vetorial científico
 * @param {string} title Título legível da seção
 * @param {Array<{ label: string, key: string }>} rows Definição das linhas de dados
 * @param {Map<string, HTMLElement>} valueRefs Mapa onde as referências de DOM serão salvas
 * @returns {HTMLElement}
 */
function createScientificSection(code, iconKey, title, rows, valueRefs) {
  const section = createSafeElement('section', { className: 'info-section-card' });

  const header = createSafeElement('header', { className: 'info-section-header' });
  const iconEl = createScientificIcon(iconKey);
  const codeBadge = createSafeElement('span', { className: 'info-section-code', text: code });
  const heading = createSafeElement('h3', { className: 'info-section-title', text: title });
  const placeholderTag = createSafeElement('span', {
    className: 'info-placeholder-pill',
    text: 'PLACEHOLDER'
  });

  header.append(iconEl, codeBadge, heading, placeholderTag);

  const dl = createSafeElement('dl', { className: 'info-data-grid' });
  for (const row of rows) {
    const itemWrap = createSafeElement('div', { className: 'info-data-row' });
    const dt = createSafeElement('dt', { className: 'info-data-label', text: row.label });
    const dd = createSafeElement('dd', {
      className: 'info-data-value',
      text: '—'
    });
    valueRefs.set(row.key, dd);
    itemWrap.append(dt, dd);
    dl.appendChild(itemWrap);
  }

  section.append(header, dl);
  return section;
}

/**
 * Constrói e inicializa a Região Direita (Painel de Informações).
 * @returns {HTMLElement}
 */
export function createRightInformationPanel() {
  const valueRefs = new Map();

  const aside = createSafeElement('aside', {
    className: 'region-right-panel',
    attributes: {
      id: 'right-information-panel',
      'aria-label': 'Painel de Informações Científicas e Geográficas'
    }
  });

  // 1. Cabeçalho Fixo do Painel: Título da Plataforma + Aviso Obrigatório de Dados Demonstrativos
  const panelHeader = createSafeElement('header', { className: 'info-panel-header' });

  const platformType = createSafeElement('span', {
    className: 'info-platform-tag',
    text: 'SISTEMA DE TELEMETRIA E ANÁLISE PLANETÁRIA'
  });

  const platformTitle = createSafeElement('h1', {
    className: 'info-platform-title',
    text: APP_CONFIG.appName
  });

  const platformSubtitle = createSafeElement('p', {
    className: 'info-platform-subtitle',
    text: APP_CONFIG.appSubtitle
  });

  const warningBanner = createSafeElement('div', {
    className: 'info-placeholder-banner',
    attributes: { role: 'status', 'aria-live': 'polite' }
  });

  const warningDot = createSafeElement('span', {
    className: 'warning-banner-dot',
    attributes: { 'aria-hidden': 'true' }
  });

  const warningText = createSafeElement('span', {
    text: PLACEHOLDER_SCIENTIFIC_DATA.noticeBanner
  });

  warningBanner.append(warningDot, warningText);

  // Seletor rápido de perfil demonstrativo no topo do painel
  const profileSwitcher = createSafeElement('div', {
    className: 'info-profile-switcher',
    attributes: { role: 'group', 'aria-label': 'Alternar conjunto de dados demonstrativos' }
  });

  const profileButtons = [
    { id: 'earth_default', label: 'Terra (Demo)' },
    { id: 'moon_reference', label: 'Lua (Ref)' },
    { id: 'mars_reference', label: 'Marte (Ref)' }
  ];

  const btnElements = new Map();
  for (const item of profileButtons) {
    const btn = createSafeElement('button', {
      className: `profile-switch-btn ${item.id === 'earth_default' ? 'is-active' : ''}`,
      text: item.label,
      attributes: { type: 'button', 'data-profile': item.id }
    });
    btn.addEventListener('click', () => {
      eventBus.emit('profile:select', { profileId: item.id, source: 'info-panel' });
    });
    btnElements.set(item.id, btn);
    profileSwitcher.appendChild(btn);
  }

  panelHeader.append(
    platformType,
    platformTitle,
    platformSubtitle,
    warningBanner,
    profileSwitcher
  );

  // Container rolável com todas as seções científicas
  const scrollBody = createSafeElement('div', { className: 'info-panel-scroll-body' });

  // 2. Região / Planeta Selecionado
  const targetSection = createScientificSection(
    'SEC-01',
    'target',
    'Planeta ou Região Selecionada',
    [
      { label: 'Alvo / Sítio', key: 'target.name' },
      { label: 'Classificação', key: 'target.classification' },
      { label: 'Contexto Ambiental', key: 'target.biomeContext' }
    ],
    valueRefs
  );

  // 3. Coordenadas Geográficas
  const coordsSection = createScientificSection(
    'SEC-02',
    'coordinates',
    'Coordenadas Geográficas',
    [
      { label: 'Latitude', key: 'coords.latitude' },
      { label: 'Longitude', key: 'coords.longitude' },
      { label: 'Elevação Estimada', key: 'coords.elevation' },
      { label: 'Referencial / Datum', key: 'coords.datum' }
    ],
    valueRefs
  );

  // 4. Indicadores Ambientais
  const envSection = createScientificSection(
    'SEC-03',
    'environment',
    'Indicadores Ambientais',
    [
      { label: 'Irradiância Solar', key: 'env.solarIrradiance' },
      { label: 'Pressão Atmosférica', key: 'env.atmosphericPressure' },
      { label: 'Radiação / Índice UV', key: 'env.uvIndex' },
      { label: 'Umidade Relativa', key: 'env.relativeHumidity' }
    ],
    valueRefs
  );

  // 5. Informações Topográficas
  const topoSection = createScientificSection(
    'SEC-04',
    'topography',
    'Informações Topográficas',
    [
      { label: 'Morfologia do Relevo', key: 'topo.reliefType' },
      { label: 'Declividade Média', key: 'topo.averageSlope' },
      { label: 'Índice de Rugosidade', key: 'topo.roughnessIndex' }
    ],
    valueRefs
  );

  // 6. Informações Geológicas
  const geoSection = createScientificSection(
    'SEC-05',
    'geology',
    'Informações Geológicas',
    [
      { label: 'Litologia Dominante', key: 'geo.lithology' },
      { label: 'Solo / Regolito', key: 'geo.soilComposition' },
      { label: 'Contexto Estratigráfico', key: 'geo.stratigraphy' }
    ],
    valueRefs
  );

  // 7. Dados de Temperatura
  const tempSection = createScientificSection(
    'SEC-06',
    'temperature',
    'Dados de Temperatura',
    [
      { label: 'Temperatura Média Anual', key: 'temp.meanAnnual' },
      { label: 'Amplitude Térmica Diurna', key: 'temp.diurnalRange' },
      { label: 'Inércia Térmica Superficial', key: 'temp.surfaceThermalInertia' }
    ],
    valueRefs
  );

  // 8. Informações sobre Água e Gelo
  const waterSection = createScientificSection(
    'SEC-07',
    'water',
    'Água e Gelo',
    [
      { label: 'Água Superficial', key: 'water.surfaceWater' },
      { label: 'Gelo Subsuperficial', key: 'water.subsurfaceIce' },
      { label: 'Regime Hidrológico', key: 'water.hydrologicalRegime' }
    ],
    valueRefs
  );

  // 9. Comparação com Ambientes Lunares e Marcianos
  const compSection = createSafeElement('section', {
    className: 'info-section-card comparison-card'
  });

  const compHeader = createSafeElement('header', { className: 'info-section-header' });
  const compIcon = createScientificIcon('comparison');
  const compCode = createSafeElement('span', { className: 'info-section-code', text: 'SEC-08' });
  const compTitle = createSafeElement('h3', {
    className: 'info-section-title',
    text: 'Comparação Lunar & Marciana'
  });
  const compPill = createSafeElement('span', {
    className: 'info-placeholder-pill',
    text: 'PLACEHOLDER'
  });
  compHeader.append(compIcon, compCode, compTitle, compPill);

  const compBody = createSafeElement('div', { className: 'comparison-blocks-wrap' });

  // Bloco Lunar
  const lunarBox = createSafeElement('div', { className: 'comparison-subcard lunar-subcard' });
  const lunarHead = createSafeElement('div', { className: 'comparison-subcard-head' });
  const lunarLabel = createSafeElement('span', {
    className: 'comparison-planet-label',
    text: 'ANALOGIA LUNAR (LUNA)'
  });
  const lunarScore = createSafeElement('span', {
    className: 'comparison-score-badge',
    text: '—'
  });
  valueRefs.set('comp.lunarScore', lunarScore);
  lunarHead.append(lunarLabel, lunarScore);

  const lunarDesc = createSafeElement('p', {
    className: 'comparison-desc-text',
    text: '—'
  });
  valueRefs.set('comp.lunarRelevance', lunarDesc);
  lunarBox.append(lunarHead, lunarDesc);

  // Bloco Marciano
  const marsBox = createSafeElement('div', { className: 'comparison-subcard mars-subcard' });
  const marsHead = createSafeElement('div', { className: 'comparison-subcard-head' });
  const marsLabel = createSafeElement('span', {
    className: 'comparison-planet-label',
    text: 'ANALOGIA MARCIANA (MARS)'
  });
  const marsScore = createSafeElement('span', {
    className: 'comparison-score-badge',
    text: '—'
  });
  valueRefs.set('comp.martianScore', marsScore);
  marsHead.append(marsLabel, marsScore);

  const marsDesc = createSafeElement('p', {
    className: 'comparison-desc-text',
    text: '—'
  });
  valueRefs.set('comp.martianRelevance', marsDesc);
  marsBox.append(marsHead, marsDesc);

  compBody.append(lunarBox, marsBox);
  compSection.append(compHeader, compBody);

  scrollBody.append(
    targetSection,
    coordsSection,
    envSection,
    topoSection,
    geoSection,
    tempSection,
    waterSection,
    compSection
  );

  aside.append(panelHeader, scrollBody);

  /**
   * Aciona animação visual sutil ao atualizar o conteúdo do painel.
   */
  function triggerPanelTransition() {
    scrollBody.classList.remove('is-updating');
    // Força reflow leve para reiniciar a transição CSS se aplicável
    void scrollBody.offsetWidth;
    scrollBody.classList.add('is-updating');
  }

  /**
   * Atualiza todos os campos do painel direito de forma segura usando textContent.
   * @param {string} profileKey
   */
  function applyProfileData(profileKey) {
    const profile =
      PLACEHOLDER_SCIENTIFIC_DATA.profiles[profileKey] ||
      PLACEHOLDER_SCIENTIFIC_DATA.profiles.earth_default;

    const setField = (key, val) => {
      const el = valueRefs.get(key);
      if (el) {
        el.textContent = sanitizeText(val);
      }
    };

    setField('target.name', profile.selectedTarget.name);
    setField('target.classification', profile.selectedTarget.classification);
    setField('target.biomeContext', profile.selectedTarget.biomeContext);

    setField('coords.latitude', profile.coordinates.latitude);
    setField('coords.longitude', profile.coordinates.longitude);
    setField('coords.elevation', profile.coordinates.elevation);
    setField('coords.datum', profile.coordinates.datum);

    setField('env.solarIrradiance', profile.environmentalIndicators.solarIrradiance);
    setField('env.atmosphericPressure', profile.environmentalIndicators.atmosphericPressure);
    setField('env.uvIndex', profile.environmentalIndicators.uvIndex);
    setField('env.relativeHumidity', profile.environmentalIndicators.relativeHumidity);

    setField('topo.reliefType', profile.topography.reliefType);
    setField('topo.averageSlope', profile.topography.averageSlope);
    setField('topo.roughnessIndex', profile.topography.roughnessIndex);

    setField('geo.lithology', profile.geology.lithology);
    setField('geo.soilComposition', profile.geology.soilComposition);
    setField('geo.stratigraphy', profile.geology.stratigraphy);

    setField('temp.meanAnnual', profile.temperature.meanAnnual);
    setField('temp.diurnalRange', profile.temperature.diurnalRange);
    setField('temp.surfaceThermalInertia', profile.temperature.surfaceThermalInertia);

    setField('water.surfaceWater', profile.waterAndIce.surfaceWater);
    setField('water.subsurfaceIce', profile.waterAndIce.subsurfaceIce);
    setField('water.hydrologicalRegime', profile.waterAndIce.hydrologicalRegime);

    setField('comp.lunarScore', profile.planetaryComparison.lunarAnalogScore);
    setField('comp.lunarRelevance', profile.planetaryComparison.lunarRelevance);
    setField('comp.martianScore', profile.planetaryComparison.martianAnalogScore);
    setField('comp.martianRelevance', profile.planetaryComparison.martianRelevance);

    for (const [id, btn] of btnElements.entries()) {
      btn.classList.toggle('is-active', id === profile.id);
    }

    triggerPanelTransition();
  }

  // Inicializa com o perfil demonstrativo terrestre
  applyProfileData('earth_default');

  // Escuta mudanças de perfil vindas da barra lateral ou do HUD superior
  eventBus.on('profile:select', (payload) => {
    if (payload && payload.profileId) {
      applyProfileData(payload.profileId);
    }
  });

  // Escuta cliques em coordenadas do Globo Terrestre
  eventBus.on('globe:location-selected', (coords) => {
    if (!coords) return;
    applyProfileData('earth_default');
    const latEl = valueRefs.get('coords.latitude');
    const lonEl = valueRefs.get('coords.longitude');
    const nameEl = valueRefs.get('target.name');
    if (latEl && typeof coords.latitude === 'number') {
      latEl.textContent = `${formatDMS(coords.latitude, 'lat')} (${coords.latitude.toFixed(4)}°)`;
    }
    if (lonEl && typeof coords.longitude === 'number') {
      lonEl.textContent = `${formatDMS(coords.longitude, 'lon')} (${coords.longitude.toFixed(4)}°)`;
    }
    if (nameEl) {
      nameEl.textContent = 'Ponto Terrestre Selecionado no Globo [Placeholder]';
    }

    // Destaca suavemente o cartão de coordenadas
    coordsSection.classList.remove('is-highlighted');
    void coordsSection.offsetWidth;
    coordsSection.classList.add('is-highlighted');
  });

  return aside;
}
