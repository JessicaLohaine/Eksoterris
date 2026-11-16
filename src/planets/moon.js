/**
 * 3D Moon Module (src/planets/moon.js)
 * Visual Architecture: Global 2K mosaic (2048x1024) based on NASA Lunar
 * Reconnaissance Orbiter (LRO) mission data with crater and mare relief.
 */
import { PlanetRenderer } from './planet-renderer.js';

export const MOON_METADATA = Object.freeze({
  id: 'moon',
  name: 'Moon (Luna)',
  meanRadiusKm: 1737.4,
  surfaceGravityMs2: 1.62,
  axialTiltDeg: 6.68
});

/**
 * Initializes the interactive 3D Moon model in the specified container.
 * @param {HTMLElement} container
 * @returns {PlanetRenderer}
 */
export function initMoonModel(container) {
  const renderer = new PlanetRenderer(container, {
    id: MOON_METADATA.id,
    name: MOON_METADATA.name,
    albedoUrl: '/textures/moon/moon_albedo.jpg',
    // Uses the 2K LRO mosaic for pixel-aligned micro-relief of real lunar craters (Tycho, Copernicus, etc.)
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
