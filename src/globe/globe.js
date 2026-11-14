/**
 * Módulo Central do Globo Terrestre 3D (src/globe/globe.js)
 * Reestruturação Visual e Técnica:
 * - Pirâmide multirresolução de tiles científicos com cache local:
 *   1. Base 0 (Instantânea Offline): NASA Blue Marble Next Generation 2K.
 *   2. Camada Orbital Global: EOX Sentinel-2 Cloudless (10m-15m, oceanos profundos/turquesa e biomas naturais).
 *   3. Camada de Aproximação HD: Esri/Maxar World Imagery (até nível 18) com transição contínua por altitude.
 *   4. Camada de Relevo Topográfico: World Elevation Hillshade (destaque tridimensional de cordilheiras e vales).
 *   5. Camadas Adicionais Selecionáveis: NASA GIBS Blue Marble WMTS e NASA GIBS VIIRS True Color.
 *   6. Camada Opcional de Nuvens Globais: Nefanálise de satélite com transparência dinâmica via shader (colorToAlpha).
 * - Iluminação Solar Direcional Coerente com a Câmera: Terminador dia/noite suave e dispersão atmosférica realista.
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
    this.activeImageryMode = 'hybrid';
    this.cloudsEnabled = true;
    this.solarLightingEnabled = true;
    this.layers = {
      baseBlueMarble: null,
      sentinel2: null,
      worldImagery: null,
      nasaGibsBlueMarble: null,
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
   * Inicializa o motor CesiumJS e configura as camadas de satélite, atmosfera, luz solar e controles.
   */
  async init() {
    if (!this.container) {
      throw new Error('Container do Globo Terrestre (#cesium-globe-container) não encontrado.');
    }

    Cesium.Ion.defaultAccessToken = '';

    // 1. Camada Base 0: NASA Blue Marble Next Generation 2K local (carregamento imediato e fallback offline)
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

    // Posiciona a câmera inicialmente sobre a América do Sul / Oceano Atlântico e Pacífico
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
   * Configura atmosfera Rayleigh/Mie, iluminação solar direcional e nitidez de renderização.
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

    // Luz Solar Direcional controlada para garantir iluminação natural e terminador suave
    scene.light = new Cesium.DirectionalLight({
      direction: new Cesium.Cartesian3(1.0, 0.0, 0.0),
      color: Cesium.Color.fromCssColorString('#fffcf5'),
      intensity: 2.15
    });

    // Atmosfera Orbital Realista
    if (scene.skyAtmosphere) {
      scene.skyAtmosphere.show = true;
      scene.skyAtmosphere.atmosphereLightIntensity = 22.0;
      scene.skyAtmosphere.hueShift = -0.02;
      scene.skyAtmosphere.saturationShift = 0.08;
      scene.skyAtmosphere.brightnessShift = 0.04;
    }

    // Dispersão atmosférica sobre a superfície e transição dia/noite suave
    scene.globe.showGroundAtmosphere = true;
    scene.globe.dynamicAtmosphereLighting = true;
    scene.globe.dynamicAtmosphereLightingFromSun = false;
    scene.globe.enableLighting = this.solarLightingEnabled;
    scene.globe.lightingFadeOutDistance = 12000000.0;
    scene.globe.lightingFadeInDistance = 30000000.0;
    scene.globe.nightFadeOutDistance = 10000000.0;
    scene.globe.nightFadeInDistance = 28000000.0;
    scene.globe.atmosphereLightIntensity = 16.0;
    scene.globe.atmosphereHueShift = -0.01;
    scene.globe.atmosphereBrightnessShift = 0.05;

    // Nitidez elevada de carregamento de tiles (menor erro em espaço de tela = maior detalhe)
    scene.globe.baseColor = Cesium.Color.fromCssColorString('#071733');
    scene.globe.maximumScreenSpaceError = 1.35;
    scene.globe.tileCacheSize = 400;
    scene.globe.preloadAncestors = true;

    if (this.viewer.cesiumWidget && this.viewer.cesiumWidget.creditContainer) {
      this.viewer.cesiumWidget.creditContainer.style.display = 'none';
    }
  }

  /**
   * Cria um provedor de tiles resiliente que utiliza o proxy/cache local (/api-tiles/...)
   * e silencia eventuais falhas de rede individuais sem interromper a renderização.
   * @param {string} urlTemplate
   * @param {number} maxLevel
   * @param {string} creditText
   * @returns {Cesium.UrlTemplateImageryProvider}
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
   * Configura todas as camadas científicas de imagens de satélite, relevo e nuvens.
   */
  async setupScientificImageryLayers() {
    const imageryLayers = this.viewer.imageryLayers;

    // Ajuste cromático na camada base 0 (NASA Blue Marble 2K local)
    if (this.layers.baseBlueMarble) {
      this.layers.baseBlueMarble.brightness = 1.02;
      this.layers.baseBlueMarble.contrast = 1.08;
      this.layers.baseBlueMarble.saturation = 1.06;
    }

    // 1. Camada Sentinel-2 Cloudless (ESA / EOX — Oceanos azul-profundo/turquesa e biomas naturais)
    const sentinelProvider = this.createTileProvider(
      '/api-tiles/sentinel2/{z}/{y}/{x}',
      14,
      'EOX Sentinel-2 Cloudless / Copernicus ESA'
    );
    this.layers.sentinel2 = imageryLayers.addImageryProvider(sentinelProvider);
    this.layers.sentinel2.alpha = 0.92;
    this.layers.sentinel2.brightness = 1.03;
    this.layers.sentinel2.contrast = 1.08;
    this.layers.sentinel2.saturation = 1.08;

    // 2. Camada de Alta Resolução para Zoom Próximo (Esri / Maxar World Imagery até nível 18)
    const worldImageryProvider = this.createTileProvider(
      '/api-tiles/arcgis/{z}/{y}/{x}',
      18,
      'Esri, Maxar, Earthstar Geographics, NASA'
    );
    this.layers.worldImagery = imageryLayers.addImageryProvider(worldImageryProvider);
    this.layers.worldImagery.alpha = 0.35; // Aumenta progressivamente ao aproximar a câmera
    this.layers.worldImagery.brightness = 1.04;
    this.layers.worldImagery.contrast = 1.1;
    this.layers.worldImagery.saturation = 1.12;

    // 3. Camada NASA GIBS Blue Marble Next Generation (WMTS Oficial da NASA)
    const gibsBlueMarbleProvider = this.createTileProvider(
      '/api-tiles/nasa-bluemarble/{z}/{y}/{x}',
      8,
      'NASA GIBS / Earthdata Blue Marble Next Generation'
    );
    this.layers.nasaGibsBlueMarble = imageryLayers.addImageryProvider(gibsBlueMarbleProvider);
    this.layers.nasaGibsBlueMarble.show = false;
    this.layers.nasaGibsBlueMarble.brightness = 1.05;
    this.layers.nasaGibsBlueMarble.contrast = 1.1;

    // 4. Camada NASA GIBS / Worldview VIIRS True Color
    const gibsViirsProvider = this.createTileProvider(
      '/api-tiles/nasa-viirs/{z}/{y}/{x}',
      9,
      'NASA GIBS / Suomi NPP VIIRS True Color'
    );
    this.layers.nasaGibsViirs = imageryLayers.addImageryProvider(gibsViirsProvider);
    this.layers.nasaGibsViirs.show = false;

    // 5. Camada de Relevo Topográfico (World Elevation Hillshade)
    // Utiliza colorToAlpha no branco para projetar apenas o sombreado de montanhas e escarpas
    const hillshadeProvider = this.createTileProvider(
      '/api-tiles/hillshade/{z}/{y}/{x}',
      15,
      'World Elevation Hillshade'
    );
    this.layers.hillshade = imageryLayers.addImageryProvider(hillshadeProvider);
    this.layers.hillshade.colorToAlpha = Cesium.Color.WHITE;
    this.layers.hillshade.colorToAlphaThreshold = 0.26;
    this.layers.hillshade.alpha = 0.28;
    this.layers.hillshade.contrast = 1.35;

    // 6. Camada Global de Nuvens (Opcional, com fundo preto convertido em transparência na GPU)
    try {
      const cloudsProvider = await Cesium.SingleTileImageryProvider.fromUrl(
        '/textures/earth/earth_clouds_1k.png',
        { rectangle: Cesium.Rectangle.MAX_VALUE }
      );
      this.layers.clouds = imageryLayers.addImageryProvider(cloudsProvider);
      this.layers.clouds.colorToAlpha = Cesium.Color.BLACK;
      this.layers.clouds.colorToAlphaThreshold = 0.42;
      this.layers.clouds.alpha = 0.34;
      this.layers.clouds.brightness = 1.18;
      this.layers.clouds.show = this.cloudsEnabled;
    } catch (err) {
      console.warn('[Globe] Camada de nuvens opcional indisponível:', err);
    }

    this.applyImageryMode(this.activeImageryMode);
  }

  /**
   * Alterna entre os modos científicos de imagem de satélite.
   * @param {'hybrid' | 'sentinel2' | 'world_imagery' | 'nasa_bluemarble' | 'nasa_viirs'} mode
   */
  applyImageryMode(mode) {
    this.activeImageryMode = mode;
    const { sentinel2, worldImagery, nasaGibsBlueMarble, nasaGibsViirs, hillshade } = this.layers;

    if (!sentinel2 || !worldImagery) return;

    sentinel2.show = false;
    worldImagery.show = false;
    if (nasaGibsBlueMarble) nasaGibsBlueMarble.show = false;
    if (nasaGibsViirs) nasaGibsViirs.show = false;
    if (hillshade) hillshade.show = true;

    switch (mode) {
      case 'sentinel2':
        sentinel2.show = true;
        sentinel2.alpha = 0.96;
        break;
      case 'world_imagery':
        worldImagery.show = true;
        worldImagery.alpha = 1.0;
        break;
      case 'nasa_bluemarble':
        if (nasaGibsBlueMarble) {
          nasaGibsBlueMarble.show = true;
          nasaGibsBlueMarble.alpha = 1.0;
        }
        break;
      case 'nasa_viirs':
        if (nasaGibsViirs) {
          nasaGibsViirs.show = true;
          nasaGibsViirs.alpha = 1.0;
        }
        if (hillshade) hillshade.show = false;
        break;
      case 'hybrid':
      default:
        // No modo híbrido, Sentinel-2 fornece os oceanos azul-turquesa e biomas naturais em órbita
        // enquanto World Imagery aumenta progressivamente de opacidade conforme o usuário dá zoom!
        sentinel2.show = true;
        sentinel2.alpha = 0.9;
        worldImagery.show = true;
        this.updateHybridLODBlend();
        break;
    }
  }

  /**
   * Ajusta dinamicamente a fusão entre a visão orbital (Sentinel-2 + Blue Marble)
   * e a fotografia aérea/satélite de alta resolução (World Imagery) conforme a altitude da câmera.
   */
  updateHybridLODBlend() {
    if (this.activeImageryMode !== 'hybrid' || !this.viewer || !this.layers.worldImagery) {
      return;
    }

    const carto = this.viewer.camera.positionCartographic;
    const altitudeKm = carto ? carto.height / 1000 : 12500;

    // Acima de 7.000 km: 35% World Imagery + 90% Sentinel-2 (oceanos vibrantes e cores naturais)
    // Abaixo de 1.800 km: 92% World Imagery (máximo detalhe de terreno, crateras e escarpas)
    const t = Math.max(0, Math.min(1, (7000 - altitudeKm) / (7000 - 1500)));
    this.layers.worldImagery.alpha = 0.35 + t * 0.58;

    // Atenua as nuvens automaticamente quando muito próximo do solo (< 1.200 km) para leitura geológica limpa
    if (this.layers.clouds && this.cloudsEnabled) {
      const cloudFade = Math.max(0.05, Math.min(0.34, ((altitudeKm - 600) / 3500) * 0.34));
      this.layers.clouds.alpha = cloudFade;
    }
  }

  /**
   * Atualiza a direção da luz solar antes de cada quadro para manter um ângulo
   * de iluminação espacial natural e um terminador suave no horizonte direito/inferior.
   */
  handlePreRender() {
    if (!this.viewer) return;

    this.updateHybridLODBlend();

    const { camera, light } = this.viewer.scene;
    if (light && camera) {
      // Calcula direção solar deslocada 32° à esquerda e 18° acima do eixo de visão da câmera
      const dir = camera.directionWC;
      const up = camera.upWC;
      const right = camera.rightWC;

      const sunDir = new Cesium.Cartesian3(
        dir.x - right.x * 0.55 - up.x * 0.32,
        dir.y - right.y * 0.55 - up.y * 0.32,
        dir.z - right.z * 0.55 - up.z * 0.32
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

    controller.minimumZoomDistance = 800; // Permite aproximação até 800 metros da superfície
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
   * @param {Cesium.Cartesian2} windowPosition
   * @returns {{ latitude: number, longitude: number } | null}
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
   * @param {boolean} enabled
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
