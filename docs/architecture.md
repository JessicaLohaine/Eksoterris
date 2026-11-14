# Arquitetura da Plataforma — TERRA-ANALOG (NASA Space Apps Challenge 2026)

## 1. Visão Geral da Arquitetura Híbrida (Opção B)

A plataforma utiliza uma arquitetura modular ES6+ com separação clara entre **motores gráficos 3D**, **estado/eventos** e **interface científica**:

- **Globo Terrestre Central (`src/globe/globe.js`):** Utiliza **CesiumJS** para projeção geodésica real (WGS84), precisão cartográfica e streaming multirresolução de imagens orbitais sem necessidade de chave privada (utilizando provedores abertos e fallback local).
- **Corpos Planetários Secundários (`src/planets/`):** Utiliza **Three.js** para renderizar modelos 3D interativos da **Lua** e de **Marte** na barra lateral esquerda com baixo consumo de memória de vídeo (VRAM).
- **Comunicação Desacoplada (`src/utils/event-bus.js`):** O ambiente 3D não manipula o HTML do painel direito diretamente; ele emite eventos através do `eventBus`, mantendo o código limpo e preparado para receber a API de Inteligência Artificial no futuro.

## 2. Segurança desde a Concepção (Security by Design)

1. **Prevenção de XSS:** Toda criação dinâmica de elementos utiliza `createSafeElement` e `textContent` (`src/utils/sanitizer.js`).
2. **Proteção de Segredos:** Nenhuma chave de API privada é armazenada no código cliente ou em variáveis `VITE_*`. Quando a integração com IA e APIs autenticadas ocorrer na Fase 2, ela será intermediada por um servidor Backend Proxy.
3. **Content Security Policy (CSP):** Configurada no `index.html` para restringir origens de scripts, conexões e Web Workers.
