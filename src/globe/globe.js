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
    this.cloudsEnabled = false;
    this.solarLightingEnabled = false; // Inicia com iluminação global plena para cores vivas e naturais em todo o globo
    this.layers = {
      baseBlueMarble: null,
      nasaGibsBlueMarble: null,
      worldImagery: null,
      nasaGibsViirs: null,
      hillshade: null,
      clouds: null
    };
    this.lastPointerEmitTime = 0;
    this.lastClockTickTime = performance.now();
    this.boundOnTick = this.handleSceneTick.bind(this);
    this.boundPreRender = this.handlePreRender.bind(this);
  }

  /**
   * Inicializa o motor CesiumJS priorizando fontes oficiais da NASA.
   */
  async init() {
    if (!this.container) {
      throw new Error('Container do Globo Terrestre (#cesium-globe-container) não encontrado.');
    }

    Cesium.Ion.defaultAccessToken = '';

    // 1. Camada Base 0: NASA Blue Marble Next Generation 2K local
    const baseBlueMarbleLayer = Cesium.ImageryLayer.fromProviderAsync(
      Cesium.SingleTileImageryProvider.fromUrl('/textures/earth/earth_bluemarble_2k.jpg', {
        rectangle: Cesium.Rectangle.MAX_VALUE
      })
    );

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
    await this.setupScientificImageryLayers();
    this.setupPointerTelemetry();
    this.setupEventBusSubscriptions();
    this.setupWebGLContextGuard();

    // Posiciona a câmera inicialmente em órbita global
    this.flyToRegion({
      latitude: APP_CONFIG.defaultCoordinates.latitude,
      longitude: APP_CONFIG.defaultCoordinates.longitude,
      altitudeKm: APP_CONFIG.defaultCoordinates.altitudeKm,
      duration: 0
    });

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

    // Luz Solar Direcional controlada para iluminação natural quando ativada pelo usuário
    scene.light = new Cesium.DirectionalLight({
      direction: new Cesium.Cartesian3(1.0, 0.0, 0.0),
      color: Cesium.Color.fromCssColorString('#ffffff'),
      intensity: 2.85
    });

    // Halo atmosférico externo sutil apenas na borda espacial do planeta
    if (scene.skyAtmosphere) {
      scene.skyAtmosphere.show = true;
      scene.skyAtmosphere.atmosphereLightIntensity = 20.0;
      scene.skyAtmosphere.hueShift = -0.02;
      scene.skyAtmosphere.saturationShift = 0.1;
      scene.skyAtmosphere.brightnessShift = 0.02;
    }

    // IMPORTANTE: Desativa showGroundAtmosphere para eliminar o véu esbranquiçado/leitoso
    // sobre os oceanos e continentes quando o globo é visto em distância orbital (12.500 km).
    scene.globe.showGroundAtmosphere = false;
    scene.globe.enableLighting = this.solarLightingEnabled;
    scene.globe.lightingFadeOutDistance = 14000000.0;
    scene.globe.lightingFadeInDistance = 32000000.0;
    scene.globe.nightFadeOutDistance = 12000000.0;
    scene.globe.nightFadeInDistance = 30000000.0;

    scene.globe.baseColor = Cesium.Color.fromCssColorString('#041026');
    scene.globe.maximumScreenSpaceError = 1.3;
    scene.globe.tileCacheSize = 400;
    scene.globe.preloadAncestors = true;

    if (this.viewer.cesiumWidget && this.viewer.cesiumWidget.creditContainer) {
      this.viewer.cesiumWidget.creditContainer.style.display = 'none';
    }
  }

  /**
   * Cria um provedor de tiles resiliente com suporte ao cache local.
   */
  createTileProvider(urlTemplate, maxLevel, creditText) {
    const provider = new Cesium.UrlTemplateImageryProvider({
      url: urlTemplate,
      maximumLevel: maxLevel,
      credit: creditText
    });
    provider.errorEvent.addEventListener((err) => {
      err.retry = false;
    });
    return provider;
  }

  /**
   * Configura as camadas científicas priorizando NASA GIBS Blue Marble + Satélite HD.
   */
  async setupScientificImageryLayers() {
    const imageryLayers = this.viewer.imageryLayers;

    // Calibração cromática natural na camada base 0 (NASA Blue Marble 2K local)
    if (this.layers.baseBlueMarble) {
      this.layers.baseBlueMarble.brightness = 1.12;
      this.layers.baseBlueMarble.contrast = 1.06;
      this.layers.baseBlueMarble.saturation = 1.14;
      this.layers.baseBlueMarble.gamma = 1.08;
    }

    // 1. Camada Principal Orbital: NASA GIBS Blue Marble Next Generation (WMTS Oficial da NASA)
    const gibsBlueMarbleProvider = this.createTileProvider(
      '/api-tiles/nasa-bluemarble/{z}/{y}/{x}',
      8,
      'NASA GIBS / Earthdata Blue Marble Next Generation'
    );
    this.layers.nasaGibsBlueMarble = imageryLayers.addImageryProvider(gibsBlueMarbleProvider);
    this.layers.nasaGibsBlueMarble.alpha = 1.0;
    this.layers.nasaGibsBlueMarble.brightness = 1.18;
    this.layers.nasaGibsBlueMarble.contrast = 1.06;
    this.layers.nasaGibsBlueMarble.saturation = 1.16;
    this.layers.nasaGibsBlueMarble.gamma = 1.12;

    // 2. Camada de Satélite de Alta Resolução (Landsat / Maxar / World Imagery até nível 18)
    const worldImageryProvider = this.createTileProvider(
      '/api-tiles/arcgis/{z}/{y}/{x}',
      18,
      'NASA Landsat / Maxar / Earthstar Geographics / Esri'
    );
    this.layers.worldImagery = imageryLayers.addImageryProvider(worldImageryProvider);
    this.layers.worldImagery.alpha = 0.55;
    this.layers.worldImagery.brightness = 1.08;
    this.layers.worldImagery.contrast = 1.08;
    this.layers.worldImagery.saturation = 1.14;
    this.layers.worldImagery.gamma = 1.04;

    // 3. Camada NASA GIBS / Worldview VIIRS True Color (Satélite NASA/NOAA Suomi NPP)
    const gibsViirsProvider = this.createTileProvider(
      '/api-tiles/nasa-viirs/{z}/{y}/{x}',
      9,
      'NASA GIBS / Suomi NPP VIIRS True Color'
    );
    this.layers.nasaGibsViirs = imageryLayers.addImageryProvider(gibsViirsProvider);
    this.layers.nasaGibsViirs.show = false;
    this.layers.nasaGibsViirs.brightness = 0.96;
    this.layers.nasaGibsViirs.contrast = 1.12;

    // 4. Camada de Relevo Topográfico (Ativada apenas quando a câmera se aproxima < 3.500 km)
    const hillshadeProvider = this.createTileProvider(
      '/api-tiles/hillshade/{z}/{y}/{x}',
      15,
      'World Elevation Hillshade'
    );
    this.layers.hillshade = imageryLayers.addImageryProvider(hillshadeProvider);
    this.layers.hillshade.colorToAlpha = Cesium.Color.WHITE;
    this.layers.hillshade.colorToAlphaThreshold = 0.35;
    this.layers.hillshade.alpha = 0.0; // Em órbita global fica 0.0 para não esbranquiçar o globo!
    this.layers.hillshade.contrast = 1.4;

    // 5. Camada Global de Nuvens da NASA (Opcional, desligada por padrão na abertura)
    try {
      const cloudsProvider = await Cesium.SingleTileImageryProvider.fromUrl(
        '/textures/earth/earth_clouds_1k.png',
        { rectangle: Cesium.Rectangle.MAX_VALUE }
      );
      this.layers.clouds = imageryLayers.addImageryProvider(cloudsProvider);
      this.layers.clouds.colorToAlpha = Cesium.Color.BLACK;
      this.layers.clouds.colorToAlphaThreshold = 0.48;
      this.layers.clouds.alpha = 0.32;
      this.layers.clouds.brightness = 1.1;
      this.layers.clouds.show = this.cloudsEnabled;
    } catch (err) {
      console.warn('[Globe] Camada de nuvens opcional indisponível:', err);
    }

    this.applyImageryMode(this.activeImageryMode);
  }

  /**
   * Alterna entre os modos científicos de imagem da Terra.
   * @param {'nasa_hybrid' | 'nasa_bluemarble' | 'world_imagery' | 'nasa_viirs'} mode
   */
  applyImageryMode(mode) {
    this.activeImageryMode = mode;
    const { nasaGibsBlueMarble, worldImagery, nasaGibsViirs, hillshade } = this.layers;

    if (!nasaGibsBlueMarble || !worldImagery) return;

    nasaGibsBlueMarble.show = false;
    worldImagery.show = false;
    if (nasaGibsViirs) nasaGibsViirs.show = false;
    if (hillshade) hillshade.show = false;

    switch (mode) {
      case 'nasa_bluemarble':
        nasaGibsBlueMarble.show = true;
        nasaGibsBlueMarble.alpha = 1.0;
        break;
      case 'world_imagery':
        worldImagery.show = true;
        worldImagery.alpha = 1.0;
        if (hillshade) hillshade.show = true;
        break;
      case 'nasa_viirs':
        if (nasaGibsViirs) {
          nasaGibsViirs.show = true;
          nasaGibsViirs.alpha = 1.0;
        }
        break;
      case 'nasa_hybrid':
      default:
        // Combina NASA GIBS Blue Marble Next Generation com Satélite HD multirresolução
        nasaGibsBlueMarble.show = true;
        nasaGibsBlueMarble.alpha = 1.0;
        worldImagery.show = true;
        if (hillshade) hillshade.show = true;
        this.updateHybridLODBlend();
        break;
    }
  }

  /**
   * Ajusta dinamicamente a fusão entre o NASA GIBS Blue Marble (órbita global) e os tiles
   * de satélite de alta resolução + relevo topográfico conforme a câmera se aproxima.
   */
  updateHybridLODBlend() {
    if (!this.viewer) return;

    const carto = this.viewer.camera.positionCartographic;
    const altitudeKm = carto ? carto.height / 1000 : 12500;

    if (this.activeImageryMode === 'nasa_hybrid' && this.layers.worldImagery) {
      // Em órbita global (12.500 km): 55% Satélite HD + 100% NASA Blue Marble (cores oceânicas profundas e naturais)
      // Abaixo de 2.500 km: 100% Satélite HD para nitidez máxima de crateras, montanhas e desertos
      const t = Math.max(0, Math.min(1, (8500 - altitudeKm) / (8500 - 2000)));
      this.layers.worldImagery.alpha = 0.55 + t * 0.45;
    }

    // Relevo topográfico (Hillshade) só entra quando a câmera está abaixo de 3.500 km
    // evitando qualquer aspecto esbranquiçado na visão orbital global!
    if (this.layers.hillshade && this.layers.hillshade.show) {
      if (altitudeKm > 3500) {
        this.layers.hillshade.alpha = 0.0;
      } else {
        const reliefFactor = Math.max(0, Math.min(1, (3500 - altitudeKm) / 2500));
        this.layers.hillshade.alpha = reliefFactor * 0.24;
      }
    }
  }

  /**
   * Atualiza a direção da luz solar antes de cada quadro.
   */
  handlePreRender() {
    if (!this.viewer) return;

    this.updateHybridLODBlend();

    const { camera, light } = this.viewer.scene;
    if (light && camera) {
      const dir = camera.directionWC;
      const up = camera.upWC;
      const right = camera.rightWC;

      const sunDir = new Cesium.Cartesian3(
        dir.x - right.x * 0.5 - up.x * 0.28,
        dir.y - right.y * 0.5 - up.y * 0.28,
        dir.z - right.z * 0.5 - up.z * 0.28
      );
      Cesium.Cartesian3.normalize(sunDir, light.direction);
    }
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
   * Executa transição suave de câmera (flyTo) para uma região do planeta.
   */
  flyToRegion({ latitude, longitude, altitudeKm = 12500, duration = 2.0 }) {
    if (!this.viewer || !isValidCoordinate(latitude, longitude)) return;

    const heightMeters = Math.max(0.8, altitudeKm) * 1000;

    this.viewer.camera.flyTo({
      destination: Cesium.Cartesian3.fromDegrees(longitude, latitude, heightMeters),
      orientation: {
        heading: Cesium.Math.toRadians(0.0),
        pitch: Cesium.Math.toRadians(-90.0),
        roll: 0.0
      },
      duration,
      easingFunction: Cesium.EasingFunction.QUADRATIC_IN_OUT
    });

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
   * Inscreve o controlador do globo nos eventos emitidos pelos botões da interface.
   */
  setupEventBusSubscriptions() {
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

    eventBus.on('globe:toggle-lighting', (payload) => {
      if (!this.viewer || !payload) return;
      this.solarLightingEnabled = Boolean(payload.enabled);
      this.viewer.scene.globe.enableLighting = this.solarLightingEnabled;
    });

    eventBus.on('globe:toggle-clouds', (payload) => {
      if (!payload) return;
      this.cloudsEnabled = Boolean(payload.enabled);
      if (this.layers.clouds) {
        this.layers.clouds.show = this.cloudsEnabled;
      }
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
   * Monitora perda de contexto WebGL, redimensionamento responsivo e visibilidade da aba.
   */
  setupWebGLContextGuard() {
    const canvas = this.viewer?.scene?.canvas;
    if (canvas) {
      canvas.addEventListener('webglcontextlost', (event) => {
        event.preventDefault();
        console.warn('[Globe] Contexto WebGL perdido temporariamente.');
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
