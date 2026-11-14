/**
 * Ponto de Entrada Principal (src/main.js)
 * Inicialização imediata da interface de 3 regiões seguida da montagem
 * dos motores 3D (Three.js para Lua/Marte e CesiumJS para o Globo Terrestre).
 */
import { createLeftSidebar } from './components/sidebar.js';
import { createTopHudBar, createBottomTelemetryBar } from './components/interface-controls.js';
import { createRightInformationPanel } from './components/information-panel.js';
import { EarthGlobeController } from './globe/globe.js';
import { initMoonModel } from './planets/moon.js';
import { initMarsModel } from './planets/mars.js';
import { createSafeElement } from './utils/sanitizer.js';

/**
 * Constrói a Região Central (Protagonista: Palco do Globo Terrestre 3D).
 * @returns {{ main: HTMLElement, globeViewport: HTMLElement }}
 */
function createCenterGlobeRegion() {
  const main = createSafeElement('main', {
    className: 'region-center-stage',
    attributes: {
      id: 'center-globe-stage',
      'aria-label': 'Visualização Tridimensional do Planeta Terra'
    }
  });

  const topHud = createTopHudBar();

  // Container principal do Globo Terrestre 3D (CesiumJS)
  const globeViewport = createSafeElement('div', {
    className: 'cesium-globe-viewport',
    attributes: {
      id: 'cesium-globe-container',
      role: 'region',
      'aria-label': 'Globo Terrestre 3D Interativo'
    }
  });

  const bottomHud = createBottomTelemetryBar();

  main.append(topHud, globeViewport, bottomHud);
  return { main, globeViewport };
}

/**
 * Inicializa os modelos tridimensionais da Lua e de Marte na barra lateral esquerda.
 */
function mountSidebarPlanets() {
  const moonContainer = document.getElementById('moon-three-viewport');
  const marsContainer = document.getElementById('mars-three-viewport');

  if (moonContainer) {
    try {
      initMoonModel(moonContainer);
    } catch (error) {
      console.error('[App] Falha ao inicializar o modelo 3D da Lua:', error);
    }
  }

  if (marsContainer) {
    try {
      initMarsModel(marsContainer);
    } catch (error) {
      console.error('[App] Falha ao inicializar o modelo 3D de Marte:', error);
    }
  }
}

/**
 * Inicializa a interface e monta os três ambientes 3D (Terra, Lua e Marte).
 */
async function bootstrapApplication() {
  const appRoot = document.getElementById('app');
  if (!appRoot) return;

  const workspaceGrid = createSafeElement('div', {
    className: 'scientific-workspace-grid'
  });

  const leftRegion = createLeftSidebar();
  const { main: centerRegion, globeViewport } = createCenterGlobeRegion();
  const rightRegion = createRightInformationPanel();

  workspaceGrid.append(leftRegion, centerRegion, rightRegion);
  appRoot.replaceChildren(workspaceGrid);

  // 1. Inicializa os modelos 3D da Lua e de Marte (Three.js) na lateral esquerda
  mountSidebarPlanets();

  // 2. Inicializa o Globo Terrestre 3D (CesiumJS) no palco central
  try {
    const earthGlobe = new EarthGlobeController(globeViewport);
    await earthGlobe.init();
  } catch (error) {
    console.error('[App] Falha ao inicializar o Globo Terrestre 3D:', error);
    const fallbackBox = createSafeElement('div', {
      className: 'stage-label-box',
      text: 'Aviso: Não foi possível inicializar o contexto WebGL do Globo Terrestre neste dispositivo.'
    });
    globeViewport.appendChild(fallbackBox);
  }
}

// Em módulos ES6 com dependências grandes (CesiumJS), o evento DOMContentLoaded
// pode já ter disparado quando o script termina de carregar. Esta verificação
// garante que a interface seja montada em 100% dos casos.
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => {
    bootstrapApplication();
  });
} else {
  bootstrapApplication();
}
