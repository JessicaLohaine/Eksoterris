/**
 * Global constants and technical platform parameters
 * NASA Space Apps Challenge 2026
 */
export const APP_CONFIG = Object.freeze({
  appName: 'Eksoterris',
  appSubtitle: 'Planetary Analog Research & Geospatial Platform',
  challengeEdition: 'NASA Space Apps Challenge 2026',
  version: '1.0.0-research-demo',
  isPlaceholderMode: false,
  maxPixelRatio: 2,
  defaultCoordinates: Object.freeze({
    latitude: -23.8634,
    longitude: -69.1328,
    altitudeKm: 12500,
    regionLabel: 'Atacama Desert, Chile (Reference Analog Site)'
  })
});
