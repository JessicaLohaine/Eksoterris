/**
 * Módulo 3D da Lua (src/planets/moon.js)
 * Reestruturação Visual: Utilização do mosaico global 2K (2048x1024) baseado em dados
 * da missão Lunar Reconnaissance Orbiter (NASA LRO) com relevo de crateras e mares lunares.
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
    // Usa o próprio mosaico 2K LRO para micro-relevo pixel-perfeito das crateras reais (Tycho, Copernicus, etc.)
    bumpUrl: '/textures/moon/moon_albedo.jpg',
    bumpScale: 0.018,
    roughness: 0.94,
    metalness: 0.02,
    axialTiltDeg: MOON_METADATA.axialTiltDeg,
    rotationSpeed: 0.0014,
    fallbackColorHex: '#94a3b8',
    hasAtmosphereGlow: false
  });

  return renderer.init();
}
