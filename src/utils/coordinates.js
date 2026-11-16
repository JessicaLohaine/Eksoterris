/**
 * Utilitários matemáticos para manipulação e formatação de coordenadas geográficas (WGS84).
 */

/**
 * Valida se um par de coordenadas está dentro dos limites geográficos terrestres.
 * @param {number} latitude
 * @param {number} longitude
 * @returns {boolean}
 */
export function isValidCoordinate(latitude, longitude) {
  return (
    typeof latitude === 'number' &&
    typeof longitude === 'number' &&
    Number.isFinite(latitude) &&
    Number.isFinite(longitude) &&
    latitude >= -90 &&
    latitude <= 90 &&
    longitude >= -180 &&
    longitude <= 180
  );
}

/**
 * Formata graus decimais para notação científica Graus, Minutos e Segundos (DMS).
 * @param {number} decimalDegrees
 * @param {'lat' | 'lon'} type
 * @returns {string}
 */
export function formatDMS(decimalDegrees, type = 'lat') {
  if (typeof decimalDegrees !== 'number' || !Number.isFinite(decimalDegrees)) {
    return '00° 00\' 00"';
  }
  const maxDeg = type === 'lat' ? 90 : 180;
  const clamped = Math.max(-maxDeg, Math.min(maxDeg, decimalDegrees));
  const absolute = Math.abs(clamped);

  let degrees = Math.floor(absolute);
  const minutesFloat = (absolute - degrees) * 60;
  let minutes = Math.floor(minutesFloat);
  let seconds = Math.round((minutesFloat - minutes) * 60);

  if (seconds === 60) {
    seconds = 0;
    minutes += 1;
  }
  if (minutes === 60) {
    minutes = 0;
    degrees += 1;
  }

  const hemisphere =
    type === 'lat'
      ? clamped >= 0
        ? 'N'
        : 'S'
      : clamped >= 0
        ? 'E'
        : 'W';

  const degStr = String(degrees).padStart(2, '0');
  const minStr = String(minutes).padStart(2, '0');
  const secStr = String(seconds).padStart(2, '0');

  return `${degStr}° ${minStr}' ${secStr}" ${hemisphere}`;
}
