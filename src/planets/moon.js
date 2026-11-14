/**
 * Módulo 3D da Lua (src/planets/moon.js)
 * Etapa 5: Instancia e configura o modelo tridimensional da Lua utilizando Three.js.
 *
 * Nota: Conforme a Regra 13, nenhum marcador ou ponto de interesse foi adicionado.
 */
import { PlanetRenderer } from './planet-renderer.js';

export const MOON_METADATA = Object.freeze({
  id: 'moon',
  name: 'Lua (Luna)',
  meanRadiusKm: 1737.4,
  surfaceGravityMs2: 1.62,
  axialTiltDeg: 6.68
});

/**
 * Inicializa o modelo 3D interativo da Lua no container especificado.
 * @param {HTMLElement} container
 * @returns {PlanetRenderer}
 */
export function initMoonModel(container) {
  const renderer = new PlanetRenderer(container, {
    id: MOON_METADATA.id,
    name: MOON_METADATA.name,
    albedoUrl: '/textures/moon/moon_albedo.jpg',
    bumpUrl: '/textures/moon/moon_bump.png',
    bumpScale: 0.028,
    roughness: 0.92,
    metalness: 0.02,
    axialTiltDeg: MOON_METADATA.axialTiltDeg,
    rotationSpeed: 0.0018,
    fallbackColorHex: '#94a3b8',
    hasAtmosphereGlow: false // A Lua possui apenas exosfera tênue (sem halo óptico)
  });

  return renderer.init();
}
