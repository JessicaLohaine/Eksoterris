/**
 * Camada de Serviços de API (Preparada para Fase 2).
 *
 * IMPORTANTE:
 * Nesta primeira fase do projeto, NÃO há integração ativa com APIs externas ou IA.
 * Quando implementada no futuro, toda requisição que exigir chave privada (IA / NASA)
 * deverá passar por um Backend Proxy próprio, nunca expondo segredos no Frontend.
 */

export class ApiClient {
  constructor() {
    this.baseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:3000/api';
  }

  /**
   * Método demonstrativo de verificação de status da camada de serviço.
   * @returns {{ status: string, mode: string }}
   */
  getServiceStatus() {
    return {
      status: 'STANDBY',
      mode: 'LOCAL_PLACEHOLDER_ONLY'
    };
  }
}

export const apiClient = new ApiClient();
