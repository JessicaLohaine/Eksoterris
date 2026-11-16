/**
 * 3D Mars Module (src/planets/mars.js)
 * Visual Architecture: Global 2K mosaic (2048x1024) based on NASA Viking and
 * MGS MOLA mission data, highlighting Valles Marineris, Tharsis, Syrtis Major, and craters.
 */
import { PlanetRenderer } from './planet-renderer.js';

export const MARS_METADATA = Object.freeze({
  id: 'mars',
  name: 'Mars',
  meanRadiusKm: 3389.5,
  surfaceGravityMs2: 3.72,
  axialTiltDeg: 25.19
});

/**
 * Initializes the interactive 3D Mars model in the specified container.
 * @param {HTMLElement} container
 * @returns {PlanetRenderer}
 */
export function initMarsModel(container) {
  const renderer = new PlanetRenderer(container, {
    id: MARS_METADATA.id,
    name: MARS_METADATA.name,
    albedoUrl: '/textures/mars/mars_albedo.jpg',
    // Uses the 2K mosaic for exact topographic alignment of Martian geological features
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
