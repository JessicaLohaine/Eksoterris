/**
 * Módulo 3D de Marte (src/planets/mars.js)
 * Etapa 5: Instancia e configura o modelo tridimensional de Marte utilizando Three.js.
 *
 * Nota: Conforme a Regra 13, nenhum marcador ou ponto de interesse foi adicionado.
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
    albedoUrl: '/textures/mars/mars_albedo.png',
    bumpUrl: '/textures/mars/mars_bump.png',
    bumpScale: 0.032,
    roughness: 0.85,
    metalness: 0.05,
    axialTiltDeg: MARS_METADATA.axialTiltDeg,
    rotationSpeed: 0.0024,
    fallbackColorHex: '#c2410c',
    hasAtmosphereGlow: true,
    atmosphereColorHex: '#fb923c' // Halo sutil de poeira e CO2 marciano no horizonte
  });

  return renderer.init();
}
