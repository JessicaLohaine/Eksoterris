/**
 * Constantes globais e parâmetros técnicos da plataforma
 * NASA Space Apps Challenge 2026
 */
export const APP_CONFIG = Object.freeze({
  appName: 'TERRA-ANALOG',
  appSubtitle: 'Planetary Analog Research & Geospatial Platform',
  challengeEdition: 'NASA Space Apps Challenge 2026',
  version: '0.2.0-stage2',
  isPlaceholderMode: true,
  maxPixelRatio: 2,
  defaultCoordinates: Object.freeze({
    latitude: -23.8634,
    longitude: -69.1328,
    altitudeKm: 12500,
    regionLabel: 'Deserto do Atacama, Chile (Referência Demonstrativa)'
  })
});
