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
  if (!Number.isFinite(decimalDegrees)) {
    return '00° 00\' 00"';
  }
  const absolute = Math.abs(decimalDegrees);
  const degrees = Math.floor(absolute);
  const minutesFloat = (absolute - degrees) * 60;
  const minutes = Math.floor(minutesFloat);
  const seconds = Math.round((minutesFloat - minutes) * 60);

  const hemisphere =
    type === 'lat'
      ? decimalDegrees >= 0
        ? 'N'
        : 'S'
      : decimalDegrees >= 0
        ? 'E'
        : 'W';

  const degStr = String(degrees).padStart(2, '0');
  const minStr = String(minutes).padStart(2, '0');
  const secStr = String(seconds).padStart(2, '0');

  return `${degStr}° ${minStr}' ${secStr}" ${hemisphere}`;
}
