/**
 * Utilitários de Segurança e Sanitização de DOM (Prevenção contra XSS).
 * Todas as inserções de dados externos ou dinâmicos devem utilizar estas funções
 * em vez de concatenação de strings com innerHTML.
 */

const SVG_NS = 'http://www.w3.org/2000/svg';

/**
 * Mapa de caminhos vetoriais (paths) para ícones científicos minimalistas (viewBox 0 0 24 24).
 */
const SCIENTIFIC_ICON_PATHS = Object.freeze({
  target: [
    'M12 2a10 10 0 1 0 10 10A10 10 0 0 0 12 2zm0 18a8 8 0 1 1 8-8 8 8 0 0 1-8 8z',
    'M12 8a4 4 0 1 0 4 4 4 4 0 0 0-4-4zm0 6a2 2 0 1 1 2-2 2 2 0 0 1-2 2z'
  ],
  coordinates: [
    'M12 2L4.5 20.29l.71.71L12 18l6.79 3 .71-.71L12 2z'
  ],
  environment: [
    'M12 7a5 5 0 1 0 5 5 5 5 0 0 0-5-5zm0 8a3 3 0 1 1 3-3 3 3 0 0 1-3 3z',
    'M11 1h2v3h-2zm0 19h2v3h-2zM3.51 4.92l1.42-1.42 2.12 2.12-1.42 1.42zM16.95 18.36l1.42-1.42 2.12 2.12-1.42 1.42zM1 11h3v2H1zm19 0h3v2h-3zM4.92 20.49l-1.42-1.42 2.12-2.12 1.42 1.42zM18.36 7.05l-1.42-1.42 2.12-2.12 1.42 1.42z'
  ],
  topography: [
    'M14 6l-3.75 5 2.85 3.8-1.6 1.2C9.81 13.75 7 10 7 10l-6 8h22L14 6z'
  ],
  geology: [
    'M11.99 18.54l-7.37-5.73L3 14.07l9 7 9-7-1.63-1.27-7.38 5.74zM12 16l7.36-5.73L21 9l-9-7-9 7 1.63 1.27L12 16z'
  ],
  temperature: [
    'M15 13V5c0-1.66-1.34-3-3-3S9 3.34 9 5v8c-1.21.91-2 2.37-2 4 0 2.76 2.24 5 5 5s5-2.24 5-5c0-1.63-.79-3.09-2-4zm-4-8c0-.55.45-1 1-1s1 .45 1 1h-1v1h1v2h-1v1h1v2h-2V5z'
  ],
  water: [
    'M12 2c-5.33 4.55-8 8.48-8 11.8 0 4.98 3.8 8.2 8 8.2s8-3.22 8-8.2c0-3.32-2.67-7.25-8-11.8zm0 18c-3.35 0-6-2.57-6-6.2 0-2.34 1.95-5.44 6-9.14 4.05 3.7 6 6.79 6 9.14 0 3.63-2.65 6.2-6 6.2z'
  ],
  comparison: [
    'M10 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h5v2h2V1h-2v2zm0 15H5l5-6v6zm9-15h-5v2h5v13l-5-6v9h5c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2z'
  ]
});

/**
 * Garante que um valor seja tratado como string segura e limitada em tamanho.
 * @param {unknown} value
 * @param {string} fallback
 * @param {number} maxLength
 * @returns {string}
 */
export function sanitizeText(value, fallback = 'N/A', maxLength = 500) {
  if (value === null || value === undefined) {
    return fallback;
  }
  const str = String(value).trim();
  if (str.length === 0) {
    return fallback;
  }
  return str.slice(0, maxLength);
}

/**
 * Safely creates an HTML element using textContent and validated attributes.
 * @param {string} tagName
 * @param {Object} options
 * @param {string} [options.className]
 * @param {string} [options.text]
 * @param {Record<string, string>} [options.attributes]
 * @returns {HTMLElement}
 */
export function createSafeElement(tagName, { className = '', text = '', attributes = {} } = {}) {
  const element = document.createElement(tagName);
  if (className) {
    element.className = className;
  }
  if (text !== '') {
    element.textContent = sanitizeText(text, '');
  }
  for (const [key, val] of Object.entries(attributes)) {
    // Blocks inline event attributes (e.g. onclick, onerror) for XSS prevention
    if (key.toLowerCase().startsWith('on')) {
      console.warn(`[Security] Blocked attempt to set inline event attribute: ${key}`);
      continue;
    }
    element.setAttribute(key, String(val));
  }
  return element;
}

/**
 * Cria um ícone vetorial SVG científico de forma segura via createElementNS (sem innerHTML).
 * @param {keyof typeof SCIENTIFIC_ICON_PATHS} iconKey
 * @returns {SVGElement | HTMLElement}
 */
export function createScientificIcon(iconKey) {
  const paths = SCIENTIFIC_ICON_PATHS[iconKey] || SCIENTIFIC_ICON_PATHS.target;
  if (typeof document.createElementNS !== 'function') {
    return createSafeElement('span', { className: 'info-section-icon' });
  }

  const svg = document.createElementNS(SVG_NS, 'svg');
  svg.setAttribute('viewBox', '0 0 24 24');
  svg.setAttribute('width', '14');
  svg.setAttribute('height', '14');
  svg.setAttribute('fill', 'currentColor');
  svg.setAttribute('aria-hidden', 'true');
  svg.setAttribute('class', 'info-section-icon');

  for (const d of paths) {
    const pathEl = document.createElementNS(SVG_NS, 'path');
    pathEl.setAttribute('d', d);
    svg.appendChild(pathEl);
  }

  return svg;
}
