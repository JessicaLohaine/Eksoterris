/**
 * Barramento de Eventos (Event Bus) desacoplado.
 * Permite que o globo CesiumJS, os modelos Three.js (Lua/Marte) e os painéis da UI
 * se comuniquem sem dependência direta entre módulos.
 */
class EventBus {
  constructor() {
    this.listeners = new Map();
  }

  /**
   * Registra um ouvinte para um evento específico.
   * @param {string} eventName
   * @param {Function} callback
   * @returns {Function} Função para cancelar a inscrição (unsubscribe)
   */
  on(eventName, callback) {
    if (typeof eventName !== 'string' || typeof callback !== 'function') {
      throw new TypeError('EventBus.on requer um nome de evento (string) e um callback (function).');
    }
    if (!this.listeners.has(eventName)) {
      this.listeners.set(eventName, new Set());
    }
    this.listeners.get(eventName).add(callback);

    return () => this.off(eventName, callback);
  }

  /**
   * Remove um ouvinte específico.
   * @param {string} eventName
   * @param {Function} callback
   */
  off(eventName, callback) {
    const callbacks = this.listeners.get(eventName);
    if (callbacks) {
      callbacks.delete(callback);
    }
  }

  /**
   * Emite um evento com dados opcionais (payload).
   * @param {string} eventName
   * @param {any} payload
   */
  emit(eventName, payload) {
    const callbacks = this.listeners.get(eventName);
    if (!callbacks) return;
    for (const callback of callbacks) {
      try {
        callback(payload);
      } catch (error) {
        console.error(`[EventBus] Erro ao processar evento "${eventName}":`, error);
      }
    }
  }
}

export const eventBus = new EventBus();
