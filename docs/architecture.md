# Arquitetura da Plataforma — TERRA-ANALOG (NASA Space Apps Challenge 2026)

## 1. Visão Geral da Arquitetura Híbrida de Alta Resolução (CesiumJS + Three.js)

A plataforma utiliza uma arquitetura modular ES6+ com separação clara entre **motores gráficos 3D**, **proxy/cache de tiles científicos**, **barramento de eventos** e **interface científica**:

### 1.1. Globo Terrestre Central (`src/globe/globe.js` — CesiumJS)
Implementa uma pirâmide multirresolução de camadas geoespaciais reais com carregamento progressivo e cache em disco local (`.tile-cache/`):
- **Camada Base 0 (Offline Instantânea):** *NASA Blue Marble Next Generation 2K* (`/textures/earth/earth_bluemarble_2k.jpg`).
- **Camada Orbital Global:** *EOX Sentinel-2 Cloudless (ESA Copernicus 10m-15m)* (`/api-tiles/sentinel2/{z}/{y}/{x}`), proporcionando oceanos em tons reais de azul profundo e turquesa costeira, florestas, desertos e calotas polares sem nuvens.
- **Camada de Aproximação HD:** *Esri / Maxar / Earthstar Geographics World Imagery* (`/api-tiles/arcgis/{z}/{y}/{x}`, até nível de zoom 18), mesclada dinamicamente conforme a altitude da câmera diminui (`updateHybridLODBlend`), garantindo nitidez fotográfica em aproximações regionais e locais.
- **Camada de Relevo Topográfico:** *World Elevation Hillshade* (`/api-tiles/hillshade/{z}/{y}/{x}`) com transparência de luminância via GPU (`colorToAlpha`), evidenciando cordilheiras, vales e crateras.
- **Camadas Adicionais Selecionáveis:** *NASA GIBS Blue Marble WMTS* e *NASA GIBS Suomi NPP VIIRS True Color*.
- **Camada Global de Nuvens (Opcional):** Mosaico de nefanálise de satélite (`/textures/earth/earth_clouds_1k.png`) processado em GPU (`colorToAlpha`) e alternável em tempo real no HUD.
- **Iluminação Solar Direcional Coerente:** `Cesium.DirectionalLight` sincronizada com o ângulo orbital de observação em `scene.preRender`, criando uma transição natural entre o hemisfério iluminado e a penumbra noturna com dispersão atmosférica (*SkyAtmosphere* + *GroundAtmosphere*).

### 1.2. Corpos Planetários Secundários (`src/planets/` — Three.js)
- **Lua (`src/planets/moon.js`):** Malha esférica de `96×96` segmentos com mosaico real 2K (`2048×1024`) derivado da sonda **NASA LRO (Lunar Reconnaissance Orbiter)** e mapeamento de relevo pixel-a-pixel das crateras e mares lunares.
- **Marte (`src/planets/mars.js`):** Malha esférica de `96×96` segmentos com mosaico real 2K (`2048×1024`) derivado das missões **NASA Viking e MGS MOLA**, destacando *Valles Marineris*, *Tharsis*, *Syrtis Major*, calotas polares e halo atmosférico sutil.
- **Iluminação Coerente com a Câmera:** O sistema de iluminação direcional solar está acoplado ao referencial orbital da câmera (`this.camera.add(sunLight)`), garantindo sombreamento tridimensional consistente em qualquer rotação de 360°.

## 2. Segurança e Desempenho

1. **Prevenção de XSS:** Toda criação dinâmica de elementos e ícones SVG utiliza `createSafeElement`, `createElementNS` e `textContent` (`src/utils/sanitizer.js`).
2. **Proxy e Cache de Tiles Seguro (`vite.config.js`):** Validação estrita de parâmetros numéricos (`z`, `y`, `x`) e lista fechada (*allowlist*) de provedores institucionais, com armazenamento em `.tile-cache/` para evitar downloads repetidos.
3. **Economia de GPU:** Uso de `IntersectionObserver`, `ResizeObserver` e `visibilitychange` para pausar loops WebGL quando fora de foco.
