/**
 * Módulo 3D de Marte (src/planets/mars.js)
 * Reestruturação Visual: Utilização do mosaico global 2K (2048x1024) baseado em dados
 * das missões Viking e MGS MOLA da NASA, destacando Valles Marineris, Tharsis, Syrtis Major e crateras.
 */
import { PlanetRenderer } from './planet-renderer.js';

export const MARS_METADATA = Object.freeze({
  id: 'mars',
  name: 'Marte',
  meanRadiusKm: 3389.5,
  surfaceGravityMs2: 3.72,
  axialTiltDeg: 25.19
});

/**
 * Inicializa o modelo 3D interativo de Marte no container especificado.
 * @param {HTMLElement} container
 * @returns {PlanetRenderer}
 */
export function initMarsModel(container) {
  const renderer = new PlanetRenderer(container, {
    id: MARS_METADATA.id,
    name: MARS_METADATA.name,
    albedoUrl: '/textures/mars/mars_albedo.jpg',
    // Usa o mosaico 2K real para alinhamento topográfico exato das feições geológicas marcianas
    bumpUrl: '/textures/mars/mars_albedo.jpg',
    bumpScale: 0.022,
    roughness: 0.86,
    metalness: 0.04,
    axialTiltDeg: MARS_METADATA.axialTiltDeg,
    rotationSpeed: 0.0018,
    fallbackColorHex: '#c2410c',
    hasAtmosphereGlow: true,
    atmosphereColorHex: '#fb923c'
  });

  return renderer.init();
}
