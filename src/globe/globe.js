/**
 * Módulo Central do Globo Terrestre 3D (src/globe/globe.js)
 * Arquitetura Geoespacial NASA-First:
 * - Camada Base 0 (Offline Instantânea): NASA Visible Earth — Blue Marble Next Generation 2K.
 * - Camada Orbital Principal: NASA GIBS (Global Imagery Browse Services) Blue Marble Next Generation WMTS.
 * - Camada de Aproximação HD: Fotografia de Satélite Multirresolução (Landsat / Maxar / World Imagery até nível 18),
 *   integrada progressivamente conforme o usuário aproxima a câmera.
 * - Camada Adicional NASA: NASA GIBS Suomi NPP VIIRS True Color.
 * - Relevo Topográfico (Hillshade): Ativado dinamicamente apenas em aproximações regionais (< 3.500 km)
 *   para manter nitidez e contraste puros na visão orbital.
 * - Sem névoa superficial esbranquiçada (showGroundAtmosphere: false), preservando oceanos em azul profundo
 *   e apenas o halo atmosférico externo (skyAtmosphere) no horizonte espacial.
 */
import * as Cesium from 'cesium';
import { APP_CONFIG } from '../config/constants.js';
import { eventBus } from '../utils/event-bus.js';
import { isValidCoordinate } from '../utils/coordinates.js';

if (typeof window !== 'undefined') {
  window.CESIUM_BASE_URL = '/cesium/';
}

export function getCesiumEngineInfo() {
  return {
    engine: 'CesiumJS',
    version: Cesium.VERSION,
    ready: Boolean(Cesium && Cesium.Viewer)
  };
}

export class EarthGlobeController {
  /**
   * @param {HTMLElement} containerElement Container DOM onde o globo será montado
   */
  constructor(containerElement) {
    this.container = containerElement;
    this.viewer = null;
    this.eventHandler = null;
    this.resizeObserver = null;
    this.isAutoRotating = true;
    this.isUserInteracting = false;
    this.activeImageryMode = 'nasa_hybrid';
    this.layers = {
      baseBlueMarble: null,
      nasaGibsBlueMarble: null,
      arcticSeaIce: null,
      worldImagery: null,
      nasaGibsViirs: null,
      hillshade: null
    };
    this.lastPointerEmitTime = 0;
    this.lastClockTickTime = performance.now();
    this.boundOnTick = this.handleSceneTick.bind(this);
    this.boundPreRender = this.handlePreRender.bind(this);
    this.discoveredCandidates = new Map();
    this.discoveryEntities = [];
    this.scienceEntities = [];
    this.investigationEntities = [];
    this.pendingDiscoveryPayload = null;
    this.pendingSciencePayload = null;
    this.registerEarlyDataListeners();
  }

  /**
   * Captures candidate payloads emitted before the Cesium Viewer finishes initializing.
   */
  registerEarlyDataListeners() {
    eventBus.on('discovery:results', (payload) => {
      this.pendingDiscoveryPayload = payload;
      if (this.viewer && !this.viewer.isDestroyed()) {
        this.renderDiscoveryCandidates(payload);
      }
    });

    eventBus.on('science:results', (run) => {
      this.pendingSciencePayload = run;
      if (this.viewer && !this.viewer.isDestroyed()) {
        this.renderScienceCandidates(run);
      }
    });
  }

  /**
   * Initializes the CesiumJS engine prioritizing official NASA data sources.
   */
  async init() {
    if (!this.container) {
      throw new Error('Terrestrial Globe container (#cesium-globe-container) not found.');
    }

    Cesium.Ion.defaultAccessToken = '';

    // 1. Camada Base 0 + Gelo Marinho Ártico (AMSRU2 / NSIDC 2024-06-15):
    // Decodificados localmente (~25ms) antes da criação do Viewer para que o quadro 1
    // já exiba Blue Marble Next Generation e gelo marinho ártico sem pop-in ou halo artificial.
    const [baseBlueMarbleProvider, arcticSeaIceProvider] = await Promise.all([
      Cesium.SingleTileImageryProvider.fromUrl('/textures/earth/earth_bluemarble_2k.jpg', {
        rectangle: Cesium.Rectangle.MAX_VALUE
      }),
      Cesium.SingleTileImageryProvider.fromUrl('/textures/earth/arctic_sea_ice_amsr2_20240615.png', {
        rectangle: Cesium.Rectangle.fromDegrees(-180, 45, 180, 90),
        credit: 'NASA GIBS / NSIDC GCOM-W1 AMSR2 Sea Ice Concentration 12km (2024-06-15)'
      })
    ]);
    const baseBlueMarbleLayer = new Cesium.ImageryLayer(baseBlueMarbleProvider, {
      brightness: 1.0,
      contrast: 1.0,
      saturation: 1.0,
      gamma: 1.0
    });
    this.preloadedArcticSeaIceProvider = arcticSeaIceProvider;

    // 2. Instancia o Viewer em modo 3D de alta precisão
    this.viewer = new Cesium.Viewer(this.container, {
      baseLayer: baseBlueMarbleLayer,
      terrainProvider: new Cesium.EllipsoidTerrainProvider(),
      animation: false,
      baseLayerPicker: false,
      fullscreenButton: false,
      vrButton: false,
      geocoder: false,
      homeButton: false,
      infoBox: false,
      sceneModePicker: false,
      selectionIndicator: false,
      timeline: false,
      navigationHelpButton: false,
      navigationInstructionsInitiallyVisible: false,
      scene3DOnly: true,
      shouldAnimate: true,
      requestRenderMode: false,
      contextOptions: {
        webgl: {
          alpha: false,
          antialias: true,
          powerPreference: 'high-performance',
          failIfMajorPerformanceCaveat: false
        }
      }
    });

    this.layers.baseBlueMarble = baseBlueMarbleLayer;

    this.configureVisualQuality();
    this.configureCameraControls();

    // Posiciona a câmera imediatamente de forma síncrona antes do primeiro quadro renderizado
    this.flyToRegion({
      latitude: APP_CONFIG.defaultCoordinates.latitude,
      longitude: APP_CONFIG.defaultCoordinates.longitude,
      altitudeKm: APP_CONFIG.defaultCoordinates.altitudeKm,
      duration: 0
    });

    this.setupScientificImageryLayers();
    this.setupPointerTelemetry();
    this.setupEventBusSubscriptions();
    this.setupWebGLContextGuard();

    this.viewer.entities.show = true;
    if (this.pendingDiscoveryPayload) {
      this.renderDiscoveryCandidates(this.pendingDiscoveryPayload);
    }
    if (this.pendingSciencePayload) {
      this.renderScienceCandidates(this.pendingSciencePayload);
    }

    this.viewer.clock.onTick.addEventListener(this.boundOnTick);
    this.viewer.scene.preRender.addEventListener(this.boundPreRender);

    return this.viewer;
  }

  /**
   * Configura qualidade visual sem névoa esbranquiçada (showGroundAtmosphere = false),
   * preservando contraste profundo desde a distância orbital inicial.
   */
  configureVisualQuality() {
    const { scene } = this.viewer;

    const targetPixelRatio = Math.min(window.devicePixelRatio || 1, APP_CONFIG.maxPixelRatio);
    this.viewer.resolutionScale = targetPixelRatio;

    scene.postProcessStages.fxaa.enabled = true;
    if (scene.msaaSamples !== undefined) {
      scene.msaaSamples = 4;
    }

    scene.backgroundColor = Cesium.Color.fromCssColorString('#05070c');
    scene.highDynamicRange = false;

    // Halo atmosférico externo sutil apenas na borda espacial do planeta
    if (scene.skyAtmosphere) {
      scene.skyAtmosphere.show = true;
      scene.skyAtmosphere.atmosphereLightIntensity = 20.0;
      scene.skyAtmosphere.hueShift = -0.02;
      scene.skyAtmosphere.saturationShift = 0.1;
      scene.skyAtmosphere.brightnessShift = 0.02;
    }

    // IMPORTANTE: Desativa showGroundAtmosphere e sombreamento direcional para manter
    // fidelidade radiométrica uniforme nas imagens de satélite em todo o globo.
    scene.globe.showGroundAtmosphere = false;
    scene.globe.enableLighting = false;

    scene.globe.baseColor = Cesium.Color.fromCssColorString('#041026');
    scene.globe.maximumScreenSpaceError = 1.3;
    scene.globe.tileCacheSize = 400;
    scene.globe.preloadAncestors = true;

    if (this.viewer.cesiumWidget && this.viewer.cesiumWidget.creditContainer) {
      this.viewer.cesiumWidget.creditContainer.style.display = 'none';
    }
  }

  /**
   * Cria um provedor de tiles resiliente com suporte ao cache local e esquemas de projeção customizados.
   */
  createTileProvider(urlTemplate, maxLevel, creditText, options = {}) {
    const provider = new Cesium.UrlTemplateImageryProvider({
      url: urlTemplate,
      maximumLevel: maxLevel,
      credit: creditText,
      ...options
    });
    provider.errorEvent.addEventListener((err) => {
      err.retry = false;
    });
    return provider;
  }

  /**
   * Configura as camadas científicas priorizando NASA GIBS Blue Marble (EPSG:4326) + Satélite HD.
   */
  setupScientificImageryLayers() {
    const imageryLayers = this.viewer.imageryLayers;

    // Esquema Geográfico Oficial NASA GIBS EPSG:4326 (TileMatrix 3 = 10x5 tiles de 512x512, cobrindo -90° a +90° sem corte polar)
    const nasaGeographicTilingScheme = new Cesium.GeographicTilingScheme({
      numberOfLevelZeroTilesX: 10,
      numberOfLevelZeroTilesY: 5
    });

    // Parâmetros radiométricos neutros (1.0) sem distorção cromática artificial
    if (this.layers.baseBlueMarble) {
      this.layers.baseBlueMarble.brightness = 1.0;
      this.layers.baseBlueMarble.contrast = 1.0;
      this.layers.baseBlueMarble.saturation = 1.0;
      this.layers.baseBlueMarble.gamma = 1.0;
    }

    // 1. Camada Principal Orbital: NASA GIBS Blue Marble Next Generation (MODIS Cloud-Free Composite EPSG:4326)
    const gibsBlueMarbleProvider = this.createTileProvider(
      '/api-tiles/nasa-bluemarble/{z}/{y}/{x}',
      4,
      'NASA GIBS / Earthdata Blue Marble Next Generation (MODIS EPSG:4326)',
      {
        tilingScheme: nasaGeographicTilingScheme,
        tileWidth: 512,
        tileHeight: 512,
        minimumLevel: 0
      }
    );
    this.layers.nasaGibsBlueMarble = imageryLayers.addImageryProvider(gibsBlueMarbleProvider);
    this.layers.nasaGibsBlueMarble.alpha = 1.0;
    this.layers.nasaGibsBlueMarble.brightness = 1.0;
    this.layers.nasaGibsBlueMarble.contrast = 1.0;
    this.layers.nasaGibsBlueMarble.saturation = 1.0;
    this.layers.nasaGibsBlueMarble.gamma = 1.0;

    // 2. Camada de Satélite de Alta Resolução (Landsat / Maxar / World Imagery até nível 18)
    const worldImageryProvider = this.createTileProvider(
      '/api-tiles/arcgis/{z}/{y}/{x}',
      18,
      'NASA Landsat / Maxar / Earthstar Geographics / Esri'
    );
    this.layers.worldImagery = imageryLayers.addImageryProvider(worldImageryProvider);
    this.layers.worldImagery.alpha = 0.0;
    this.layers.worldImagery.show = false;
    this.layers.worldImagery.brightness = 1.0;
    this.layers.worldImagery.contrast = 1.0;
    this.layers.worldImagery.saturation = 1.0;
    this.layers.worldImagery.gamma = 1.0;

    // 2.5 Camada Científica de Gelo Marinho Ártico (NASA GIBS / NSIDC GCOM-W1 AMSR2 12km, 2024-06-15)
    if (this.preloadedArcticSeaIceProvider) {
      this.layers.arcticSeaIce = imageryLayers.addImageryProvider(this.preloadedArcticSeaIceProvider);
      this.layers.arcticSeaIce.alpha = 1.0;
      this.layers.arcticSeaIce.show = true;
      this.layers.arcticSeaIce.brightness = 1.0;
      this.layers.arcticSeaIce.contrast = 1.0;
      this.layers.arcticSeaIce.saturation = 1.0;
      this.layers.arcticSeaIce.gamma = 1.0;
    }

    // 3. Camada NASA GIBS / Worldview VIIRS True Color (Satélite NASA/NOAA Suomi NPP em EPSG:4326)
    const gibsViirsProvider = this.createTileProvider(
      '/api-tiles/nasa-viirs/{z}/{y}/{x}',
      5,
      'NASA GIBS / Suomi NPP VIIRS True Color (EPSG:4326)',
      {
        tilingScheme: nasaGeographicTilingScheme,
        tileWidth: 512,
        tileHeight: 512,
        minimumLevel: 0
      }
    );
    this.layers.nasaGibsViirs = imageryLayers.addImageryProvider(gibsViirsProvider);
    this.layers.nasaGibsViirs.show = false;
    this.layers.nasaGibsViirs.brightness = 1.0;
    this.layers.nasaGibsViirs.contrast = 1.0;
    this.layers.nasaGibsViirs.saturation = 1.0;
    this.layers.nasaGibsViirs.gamma = 1.0;

    // 4. Camada de Relevo Topográfico (Ativada apenas quando a câmera se aproxima < 3.500 km)
    const hillshadeProvider = this.createTileProvider(
      '/api-tiles/hillshade/{z}/{y}/{x}',
      15,
      'World Elevation Hillshade',
      {
        minimumLevel: 3
      }
    );
    this.layers.hillshade = imageryLayers.addImageryProvider(hillshadeProvider);
    this.layers.hillshade.colorToAlpha = Cesium.Color.WHITE;
    this.layers.hillshade.colorToAlphaThreshold = 0.35;
    this.layers.hillshade.alpha = 0.0;
    this.layers.hillshade.show = false;
    this.layers.hillshade.contrast = 1.35;

    this.applyImageryMode(this.activeImageryMode);
  }

  /**
   * Alterna entre os modos científicos de imagem da Terra.
   * @param {'nasa_hybrid' | 'nasa_bluemarble' | 'world_imagery' | 'nasa_viirs'} mode
   */
  applyImageryMode(mode) {
    this.activeImageryMode = mode;
    const { nasaGibsBlueMarble, arcticSeaIce, worldImagery, nasaGibsViirs, hillshade } = this.layers;

    if (!nasaGibsBlueMarble || !worldImagery) return;

    nasaGibsBlueMarble.show = false;
    if (arcticSeaIce) arcticSeaIce.show = false;
    worldImagery.show = false;
    if (nasaGibsViirs) nasaGibsViirs.show = false;
    if (hillshade) hillshade.show = false;

    switch (mode) {
      case 'nasa_bluemarble':
        // Visualização pura do compósito NASA GIBS Blue Marble Next Generation + Gelo Marinho AMSR2 (EPSG:4326)
        nasaGibsBlueMarble.show = true;
        nasaGibsBlueMarble.alpha = 1.0;
        if (arcticSeaIce) {
          arcticSeaIce.show = true;
          arcticSeaIce.alpha = 1.0;
        }
        break;
      case 'world_imagery':
        // Mantém a base polar EPSG:4326 e o gelo marinho ártico sob a camada Web Mercator para cobertura contínua até 90°N/S
        nasaGibsBlueMarble.show = true;
        nasaGibsBlueMarble.alpha = 1.0;
        if (arcticSeaIce) {
          arcticSeaIce.show = true;
          arcticSeaIce.alpha = 1.0;
        }
        worldImagery.show = true;
        worldImagery.alpha = 1.0;
        if (hillshade) hillshade.show = true;
        this.updateHybridLODBlend();
        break;
      case 'nasa_viirs':
        // VIIRS Suomi NPP (2024-06-15) já captura cobertura de nuvens e gelo marinho ótico em tempo real
        if (nasaGibsViirs) {
          nasaGibsViirs.show = true;
          nasaGibsViirs.alpha = 1.0;
        }
        break;
      case 'nasa_hybrid':
      default:
        // Em órbita (>= 6.000 km): Blue Marble Next Generation + Gelo Marinho Ártico AMSR2 puros.
        // Abaixo de 6.000 km: transição gradual para Satélite HD (Landsat / Maxar).
        nasaGibsBlueMarble.show = true;
        nasaGibsBlueMarble.alpha = 1.0;
        if (arcticSeaIce) {
          arcticSeaIce.show = true;
          arcticSeaIce.alpha = 1.0;
        }
        worldImagery.show = false;
        this.updateHybridLODBlend();
        break;
    }
  }

  /**
   * Ajusta dinamicamente a fusão entre o NASA GIBS Blue Marble Next Generation e os tiles
   * de satélite de alta resolução + relevo topográfico conforme a câmera se aproxima.
   */
  updateHybridLODBlend() {
    if (!this.viewer) return;

    const carto = this.viewer.camera.positionCartographic;
    const altitudeKm = carto ? carto.height / 1000 : 12500;
    const absLatDeg = carto ? Math.abs(Cesium.Math.toDegrees(carto.latitude)) : 0;

    // Estima a latitude máxima no campo de visão para que o limite Web Mercator (±85.0511°)
    // da camada de aproximação se atenue totalmente antes de entrar no disco visível.
    const viewMarginDeg = Math.min(28.0, (altitudeKm * 0.75) / 111.0);
    const effectiveMaxLat = Math.min(90.0, absLatDeg + viewMarginDeg);
    const polarFade = Math.max(0, Math.min(1, (80.0 - effectiveMaxLat) / (80.0 - 70.0)));

    if (this.activeImageryMode === 'nasa_hybrid' && this.layers.worldImagery) {
      // Em órbita (>= 6.000 km): 0% World Imagery (sem batimetria Esri nos oceanos/Ártico).
      // Abaixo de 6.000 km até 1.600 km: transição progressiva até 98% World Imagery (Zoom 18).
      const zoomBlend = Math.max(0, Math.min(1, (6000 - altitudeKm) / (6000 - 1600)));
      const targetAlpha = zoomBlend * 0.98 * polarFade;
      this.layers.worldImagery.alpha = targetAlpha;
      this.layers.worldImagery.show = targetAlpha > 0.01;
    } else if (this.activeImageryMode === 'world_imagery' && this.layers.worldImagery) {
      this.layers.worldImagery.alpha = polarFade;
      this.layers.worldImagery.show = polarFade > 0.01;
    }

    // Relevo topográfico (Hillshade) só entra quando a câmera está abaixo de 3.500 km
    if (this.layers.hillshade) {
      const hillshadeAllowed =
        this.activeImageryMode === 'nasa_hybrid' || this.activeImageryMode === 'world_imagery';
      if (!hillshadeAllowed || altitudeKm >= 3500) {
        this.layers.hillshade.alpha = 0.0;
        this.layers.hillshade.show = false;
      } else {
        const reliefFactor = Math.max(0, Math.min(1, (3500 - altitudeKm) / 2500));
        const targetReliefAlpha = reliefFactor * 0.22 * polarFade;
        this.layers.hillshade.alpha = targetReliefAlpha;
        this.layers.hillshade.show = targetReliefAlpha > 0.01;
      }
    }
  }

  /**
   * Atualiza o balanceamento dinâmico de resolução (LOD) antes de cada quadro.
   */
  handlePreRender() {
    if (!this.viewer) return;

    this.updateHybridLODBlend();
  }

  /**
   * Configura rotação interativa, zoom, inclinação (tilt) e amortecimento inercial.
   */
  configureCameraControls() {
    const controller = this.viewer.scene.screenSpaceCameraController;

    controller.enableRotate = true;
    controller.enableZoom = true;
    controller.enableTilt = true;
    controller.enableLook = true;

    controller.minimumZoomDistance = 800;
    controller.maximumZoomDistance = 38000000;

    controller.inertiaSpin = 0.91;
    controller.inertiaTranslate = 0.9;
    controller.inertiaZoom = 0.84;
  }

  /**
   * Configura captura de eventos de mouse para telemetria de coordenadas e seleção de regiões.
   */
  setupPointerTelemetry() {
    const { scene, camera } = this.viewer;
    this.eventHandler = new Cesium.ScreenSpaceEventHandler(scene.canvas);

    this.eventHandler.setInputAction(() => {
      this.isUserInteracting = true;
      this.setAutoRotation(false);
    }, Cesium.ScreenSpaceEventType.LEFT_DOWN);

    this.eventHandler.setInputAction(() => {
      this.isUserInteracting = false;
    }, Cesium.ScreenSpaceEventType.LEFT_UP);

    this.eventHandler.setInputAction(() => {
      this.setAutoRotation(false);
    }, Cesium.ScreenSpaceEventType.WHEEL);

    this.eventHandler.setInputAction((movement) => {
      const now = performance.now();
      if (now - this.lastPointerEmitTime < 45) {
        return;
      }
      this.lastPointerEmitTime = now;

      const coords = this.pickCoordinatesFromScreenPosition(movement.endPosition);
      const cameraCartographic = camera.positionCartographic;
      const altitudeKm = cameraCartographic ? cameraCartographic.height / 1000 : 12500;

      if (coords) {
        eventBus.emit('globe:pointer-move', {
          latitude: coords.latitude,
          longitude: coords.longitude,
          altitudeKm
        });
      } else {
        eventBus.emit('globe:pointer-move', { altitudeKm });
      }
    }, Cesium.ScreenSpaceEventType.MOUSE_MOVE);

    this.eventHandler.setInputAction((click) => {
      const picked = this.viewer.scene.pick(click.position);
      const entityId = picked?.id?.id;
      if (typeof entityId === 'string' && entityId.startsWith('investigation-')) {
        eventBus.emit('discovery:select-evidence', {
          id: entityId.slice('investigation-'.length).replace(/-center$/, '')
        });
      } else if (typeof entityId === 'string' && entityId.startsWith('discovered-')) {
        const candidate = this.discoveredCandidates?.get(entityId.slice('discovered-'.length));
        if (candidate) {
          eventBus.emit('discovery:focus-candidate', candidate);
        }
      } else if (typeof entityId === 'string' && entityId.startsWith('candidate-')) {
        eventBus.emit('science:select-candidate', { id: entityId.slice('candidate-'.length) });
      }

      const coords = this.pickCoordinatesFromScreenPosition(click.position);
      if (!coords) return;

      const cameraCartographic = camera.positionCartographic;
      const altitudeKm = cameraCartographic ? cameraCartographic.height / 1000 : 12500;

      eventBus.emit('globe:location-selected', {
        latitude: coords.latitude,
        longitude: coords.longitude,
        altitudeKm
      });
    }, Cesium.ScreenSpaceEventType.LEFT_CLICK);
  }

  /**
   * Converte uma posição 2D da tela (pixels) em coordenadas geográficas (Lat/Lon WGS84).
   */
  pickCoordinatesFromScreenPosition(windowPosition) {
    if (!this.viewer || !windowPosition) return null;
    const ellipsoid = this.viewer.scene.globe.ellipsoid;
    const cartesian = this.viewer.camera.pickEllipsoid(windowPosition, ellipsoid);
    if (!cartesian) return null;

    const cartographic = ellipsoid.cartesianToCartographic(cartesian);
    if (!cartographic) return null;

    const latitude = Cesium.Math.toDegrees(cartographic.latitude);
    const longitude = Cesium.Math.toDegrees(cartographic.longitude);

    if (!isValidCoordinate(latitude, longitude)) {
      return null;
    }
    return { latitude, longitude };
  }

  /**
   * Executa transição suave de câmera (flyTo) ou posicionamento síncrono imediato (duration <= 0).
   */
  flyToRegion({ latitude, longitude, altitudeKm = 12500, duration = 2.0 }) {
    if (!this.viewer || !isValidCoordinate(latitude, longitude)) return;

    const heightMeters = Math.max(0.8, altitudeKm) * 1000;
    const destination = Cesium.Cartesian3.fromDegrees(longitude, latitude, heightMeters);
    const orientation = {
      heading: Cesium.Math.toRadians(0.0),
      pitch: Cesium.Math.toRadians(-90.0),
      roll: 0.0
    };

    if (duration <= 0) {
      this.viewer.camera.setView({
        destination,
        orientation
      });
    } else {
      this.viewer.camera.flyTo({
        destination,
        orientation,
        duration,
        easingFunction: Cesium.EasingFunction.QUADRATIC_IN_OUT
      });
    }

    eventBus.emit('globe:pointer-move', {
      latitude,
      longitude,
      altitudeKm
    });
  }

  /**
   * Rotação axial suave do globo quando a auto-rotação está ativa e a aba está visível.
   */
  handleSceneTick() {
    const now = performance.now();
    const deltaSeconds = Math.min((now - this.lastClockTickTime) / 1000, 0.1);
    this.lastClockTickTime = now;

    if (!this.isAutoRotating || this.isUserInteracting || document.hidden || !this.viewer) {
      return;
    }

    const angularSpeedRadPerSec = 0.032;
    this.viewer.scene.camera.rotate(Cesium.Cartesian3.UNIT_Z, -angularSpeedRadPerSec * deltaSeconds);
  }

  /**
   * Ativa ou desativa a auto-rotação e notifica a interface.
   */
  setAutoRotation(enabled) {
    this.isAutoRotating = Boolean(enabled);
    eventBus.emit('globe:autorotate-changed', { enabled: this.isAutoRotating });
  }

  /**
   * Removes previously rendered entities belonging to a single visual layer group.
   * @param {Cesium.Entity[]} entityList
   */
  clearEntityGroup(entityList) {
    if (!this.viewer || this.viewer.isDestroyed() || !Array.isArray(entityList)) return;
    if (entityList.length === 0) return;

    this.viewer.entities.suspendEvents();
    try {
      for (const entity of entityList) {
        this.viewer.entities.remove(entity);
      }
      entityList.length = 0;
    } finally {
      this.viewer.entities.resumeEvents();
    }
  }

  /**
   * Renders the active discovery experiment candidates onto viewer.entities.
   * @param {{ candidates?: Array<Object>, experimentId?: string }} payload
   */
  renderDiscoveryCandidates(payload) {
    if (!this.viewer || this.viewer.isDestroyed() || !payload || !Array.isArray(payload.candidates)) {
      return;
    }

    const { candidates, experimentId } = payload;
    this.clearEntityGroup(this.discoveryEntities);
    this.discoveredCandidates = new Map();
    this.viewer.entities.show = true;

    this.viewer.entities.suspendEvents();
    try {
      for (const candidate of candidates) {
        if (!candidate || !isValidCoordinate(candidate.latitude, candidate.longitude)) {
          continue;
        }
        this.discoveredCandidates.set(candidate.id, candidate);

        const isTopRank = candidate.rank === 1;
        const isTopTen = typeof candidate.rank === 'number' && candidate.rank <= 10;
        const pointColor = isTopRank
          ? Cesium.Color.fromCssColorString('#ff7a18')
          : isTopTen
            ? Cesium.Color.fromCssColorString('#22e58a')
            : Cesium.Color.fromCssColorString('#84ff4d');

        const entity = this.viewer.entities.add({
          id: `discovered-${candidate.id}`,
          name: `${experimentId || 'discovery'} #${candidate.rank ?? ''}`,
          show: true,
          position: Cesium.Cartesian3.fromDegrees(candidate.longitude, candidate.latitude, 5000),
          point: {
            show: true,
            pixelSize: isTopRank ? 15 : isTopTen ? 11 : 8,
            color: pointColor,
            outlineColor: isTopRank ? Cesium.Color.WHITE : Cesium.Color.BLACK,
            outlineWidth: 2
          },
          label: {
            text: `#${candidate.rank} · generated`,
            font: '600 11px Inter, sans-serif',
            fillColor: Cesium.Color.WHITE,
            backgroundColor: Cesium.Color.fromCssColorString('rgba(5, 10, 20, 0.82)'),
            showBackground: true,
            pixelOffset: new Cesium.Cartesian2(0, -18),
            distanceDisplayCondition: new Cesium.DistanceDisplayCondition(0, isTopRank ? 2400000 : 800000),
            show: typeof candidate.rank === 'number' && candidate.rank <= 3
          }
        });
        this.discoveryEntities.push(entity);
      }
    } finally {
      this.viewer.entities.resumeEvents();
    }
  }

  /**
   * Renders the seven-site baseline candidates onto viewer.entities separately from discovery catalogs.
   * @param {{ candidates?: Array<Object> }} run
   */
  renderScienceCandidates(run) {
    if (!this.viewer || this.viewer.isDestroyed() || !run || !Array.isArray(run.candidates)) {
      return;
    }

    this.clearEntityGroup(this.scienceEntities);
    this.viewer.entities.show = true;

    this.viewer.entities.suspendEvents();
    try {
      for (const candidate of run.candidates) {
        if (!candidate || !isValidCoordinate(candidate.latitude, candidate.longitude)) {
          continue;
        }
        const isTopRank = candidate.rank === 1;
        const entity = this.viewer.entities.add({
          id: `candidate-${candidate.id}`,
          name: candidate.name || candidate.id,
          show: true,
          position: Cesium.Cartesian3.fromDegrees(candidate.longitude, candidate.latitude, 3500),
          point: {
            show: true,
            pixelSize: isTopRank ? 16 : 11,
            color: isTopRank ? Cesium.Color.GOLD : Cesium.Color.CYAN,
            outlineColor: Cesium.Color.BLACK,
            outlineWidth: 2
          },
          label: {
            text: `${candidate.rank}. ${candidate.name}`,
            font: '600 12px Inter, sans-serif',
            fillColor: Cesium.Color.WHITE,
            backgroundColor: Cesium.Color.fromCssColorString('rgba(5, 10, 20, 0.82)'),
            showBackground: true,
            pixelOffset: new Cesium.Cartesian2(0, -22),
            distanceDisplayCondition: new Cesium.DistanceDisplayCondition(0, 12000000),
            show: true
          }
        });
        this.scienceEntities.push(entity);
      }
    } finally {
      this.viewer.entities.resumeEvents();
    }
  }

  /**
   * Renders an analyzed Earth investigation window polygon and center marker onto viewer.entities.
   * @param {Object} record
   */
  renderInvestigationWindow(record) {
    if (!this.viewer || this.viewer.isDestroyed() || !record) return;

    this.clearEntityGroup(this.investigationEntities);
    const ring = record.footprint_geojson?.coordinates?.[0];
    if (!Array.isArray(ring) || ring.length === 0) return;

    const positions = ring.map(([longitude, latitude]) =>
      Cesium.Cartesian3.fromDegrees(longitude, latitude)
    );

    this.viewer.entities.suspendEvents();
    try {
      const footprintEntity = this.viewer.entities.add({
        id: `investigation-${record.id}`,
        show: true,
        polygon: {
          show: true,
          hierarchy: new Cesium.PolygonHierarchy(positions),
          material: Cesium.Color.ORANGE.withAlpha(0.22),
          outline: true,
          outlineColor: Cesium.Color.ORANGE,
          outlineWidth: 2,
          height: 1000
        }
      });
      this.investigationEntities.push(footprintEntity);

      if (isValidCoordinate(record.latitude, record.longitude)) {
        const centerEntity = this.viewer.entities.add({
          id: `investigation-${record.id}-center`,
          show: true,
          position: Cesium.Cartesian3.fromDegrees(record.longitude, record.latitude, 4500),
          point: {
            show: true,
            pixelSize: 13,
            color: Cesium.Color.ORANGE,
            outlineColor: Cesium.Color.WHITE,
            outlineWidth: 2
          }
        });
        this.investigationEntities.push(centerEntity);
      }
    } finally {
      this.viewer.entities.resumeEvents();
    }

    if (isValidCoordinate(record.latitude, record.longitude)) {
      this.setAutoRotation(false);
      this.flyToRegion({ latitude: record.latitude, longitude: record.longitude, altitudeKm: 500 });
    }
  }

  /**
   * Inscreve o controlador do globo nos eventos emitidos pelos botões da interface.
   */
  setupEventBusSubscriptions() {
    eventBus.on('discovery:focus-candidate', (candidate) => {
      if (!candidate || !isValidCoordinate(candidate.latitude, candidate.longitude)) return;
      this.setAutoRotation(false);
      this.flyToRegion({ latitude: candidate.latitude, longitude: candidate.longitude, altitudeKm: 650 });
    });

    eventBus.on('discovery:focus-evidence', (record) => {
      this.renderInvestigationWindow(record);
    });

    eventBus.on('science:focus-candidate', (candidate) => {
      if (!candidate || !isValidCoordinate(candidate.latitude, candidate.longitude)) return;
      this.setAutoRotation(false);
      this.flyToRegion({ latitude: candidate.latitude, longitude: candidate.longitude, altitudeKm: 1200 });
    });

    eventBus.on('globe:reset-camera', (coords) => {
      const target = coords || APP_CONFIG.defaultCoordinates;
      this.flyToRegion({
        latitude: target.latitude,
        longitude: target.longitude,
        altitudeKm: target.altitudeKm || 12500,
        duration: 2.0
      });
    });

    eventBus.on('globe:fly-to-preset', (preset) => {
      if (!preset) return;
      this.setAutoRotation(false);
      this.flyToRegion({
        latitude: preset.latitude,
        longitude: preset.longitude,
        altitudeKm: preset.altitudeKm || 2800,
        duration: 2.2
      });
    });

    eventBus.on('globe:change-imagery-mode', (payload) => {
      if (!payload || !payload.mode) return;
      this.applyImageryMode(payload.mode);
    });

    eventBus.on('globe:toggle-autorotate', (payload) => {
      if (!payload) return;
      this.setAutoRotation(Boolean(payload.enabled));
    });
  }

  /**
   * Monitors WebGL context loss, responsive resizing, and tab visibility.
   */
  setupWebGLContextGuard() {
    const canvas = this.viewer?.scene?.canvas;
    if (canvas) {
      canvas.addEventListener('webglcontextlost', (event) => {
        event.preventDefault();
        console.warn('[Globe] WebGL context temporarily lost.');
      });
    }

    if (typeof ResizeObserver !== 'undefined' && this.container) {
      this.resizeObserver = new ResizeObserver(() => {
        if (this.viewer && !this.viewer.isDestroyed()) {
          this.viewer.resize();
        }
      });
      this.resizeObserver.observe(this.container);
    }

    if (typeof document !== 'undefined' && typeof document.addEventListener === 'function') {
      document.addEventListener('visibilitychange', () => {
        if (!this.viewer || this.viewer.isDestroyed()) return;
        this.viewer.useDefaultRenderLoop = !document.hidden;
        this.lastClockTickTime = performance.now();
      });
    }
  }
}
