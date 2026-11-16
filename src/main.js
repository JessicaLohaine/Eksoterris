/**
 * Main Entry Point (src/main.js)
 * Immediate initialization of the 3-region interface followed by mounting
 * the 3D engines (Three.js for Moon/Mars and CesiumJS for the Terrestrial Globe).
 */
import { createLeftSidebar } from './components/sidebar.js';
import { createTopHudBar, createBottomTelemetryBar } from './components/interface-controls.js';
import { createRightInformationPanel } from './components/information-panel.js';
import { EarthGlobeController } from './globe/globe.js';
import { initMoonModel } from './planets/moon.js';
import { initMarsModel } from './planets/mars.js';
import { createSafeElement } from './utils/sanitizer.js';
import { eventBus } from './utils/event-bus.js';
import './science.css';

/**
 * Builds the Central Region (Protagonist: 3D Terrestrial Globe Stage).
 * @returns {{ main: HTMLElement, globeViewport: HTMLElement }}
 */
function createCenterGlobeRegion() {
  const main = createSafeElement('main', {
    className: 'region-center-stage',
    attributes: {
      id: 'center-globe-stage',
      'aria-label': 'Three-Dimensional Planet Earth Visualization'
    }
  });

  const topHud = createTopHudBar();

  // Main container for the 3D Terrestrial Globe (CesiumJS)
  const globeViewport = createSafeElement('div', {
    className: 'cesium-globe-viewport',
    attributes: {
      id: 'cesium-globe-container',
      role: 'region',
      'aria-label': 'Interactive 3D Terrestrial Globe'
    }
  });

  const bottomHud = createBottomTelemetryBar();

  main.append(topHud, globeViewport, bottomHud);
  return { main, globeViewport };
}

/**
 * Initializes the three-dimensional Moon and Mars models in the left sidebar.
 */
function mountSidebarPlanets() {
  const moonContainer = document.getElementById('moon-three-viewport');
  const marsContainer = document.getElementById('mars-three-viewport');

  if (moonContainer) {
    try {
      initMoonModel(moonContainer);
    } catch (error) {
      console.error('[App] Failed to initialize 3D Moon model:', error);
    }
  }

  if (marsContainer) {
    try {
      initMarsModel(marsContainer);
    } catch (error) {
      console.error('[App] Failed to initialize 3D Mars model:', error);
    }
  }
}

/**
 * Initializes the interface and mounts the three 3D environments (Earth, Moon, and Mars).
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

  // 1. Initialize 3D Moon and Mars models (Three.js) in the left sidebar
  mountSidebarPlanets();

  // 2. Initialize 3D Terrestrial Globe (CesiumJS) on the central stage
  try {
    const earthGlobe = new EarthGlobeController(globeViewport);
    await earthGlobe.init();
    eventBus.emit('globe:ready', {});
  } catch (error) {
    console.error('[App] Failed to initialize 3D Terrestrial Globe:', error);
    const fallbackBox = createSafeElement('div', {
      className: 'stage-label-box',
      text: 'Notice: Unable to initialize the WebGL context for the Terrestrial Globe on this device.'
    });
    globeViewport.appendChild(fallbackBox);
  }
}

// In ES6 modules with large dependencies (CesiumJS), the DOMContentLoaded event
// may have already fired by the time the script finishes loading. This check
// guarantees the interface mounts in 100% of cases.
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => {
    bootstrapApplication();
  });
} else {
  bootstrapApplication();
}
