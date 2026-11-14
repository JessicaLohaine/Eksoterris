/**
 * Módulo Central do Globo Terrestre 3D (src/globe/globe.js)
 * Etapa 4: Implementação completa do Globo Terrestre tridimensional com CesiumJS.
 *
 * Funcionalidades:
 * - Renderização 3D real em projeção geodésica WGS84.
 * - Dupla camada de textura sem necessidade de chaves privadas (Token-Free):
 *   1. Camada base offline garantida (NaturalEarthII local).
 *   2. Camada orbital de satélite multirresolução (ArcGIS World Imagery) com fallback silencioso.
 * - Rotação orbital com inércia suave, zoom progressivo com limites de segurança e inclinação 3D.
 * - Auto-rotação sutil opcional que pausa automaticamente quando o usuário interage com o globo.
 * - Iluminação atmosférica (SkyAtmosphere + GroundAtmosphere) e alternância de iluminação solar.
 * - Telemetria em tempo real (Latitude, Longitude e Altitude) via Raycasting no elipsoide.
 * - Transições de câmera suaves (flyTo) para explorar diferentes regiões do planeta.
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
    this.isAutoRotating = true;
    this.isUserInteracting = false;
    this.lastPointerEmitTime = 0;
    this.lastClockTickTime = performance.now();
    this.boundOnTick = this.handleSceneTick.bind(this);
  }

  /**
   * Inicializa o motor CesiumJS e configura texturas, câmera e eventos.
   */
  async init() {
    if (!this.container) {
      throw new Error('Container do Globo Terrestre (#cesium-globe-container) não encontrado.');
    }

    // Garante que nenhuma chamada ao Cesium Ion seja tentada
    Cesium.Ion.defaultAccessToken = '';

    // 1. Camada base local (Offline-first: NaturalEarthII incluso nos ativos do Cesium)
    const localBaseLayer = Cesium.ImageryLayer.fromProviderAsync(
      Cesium.TileMapServiceImageryProvider.fromUrl(
        Cesium.buildModuleUrl('Assets/Textures/NaturalEarthII')
      )
    );

    // 2. Instancia o Viewer sem widgets genéricos para preservar nossa interface científica
    this.viewer = new Cesium.Viewer(this.container, {
      baseLayer: localBaseLayer,
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

    this.configureVisualQuality();
    this.configureCameraControls();
    await this.attachHighResSatelliteLayer();
    this.setupPointerTelemetry();
    this.setupEventBusSubscriptions();
    this.setupWebGLContextGuard();

    // Posiciona a câmera inicialmente e emite telemetria inicial
    this.flyToRegion({
      latitude: APP_CONFIG.defaultCoordinates.latitude,
      longitude: APP_CONFIG.defaultCoordinates.longitude,
      altitudeKm: APP_CONFIG.defaultCoordinates.altitudeKm,
      duration: 0
    });

    // Inicia loop sutil de rotação orbital quando ocioso
    this.viewer.clock.onTick.addEventListener(this.boundOnTick);

    return this.viewer;
  }

  /**
   * Ajusta qualidade gráfica, atmosfera, estrelas e escala de resolução (DPI).
   */
  configureVisualQuality() {
    const { scene } = this.viewer;

    // Limita o pixel ratio para manter alto desempenho em monitores 4K/Retina
    const targetPixelRatio = Math.min(window.devicePixelRatio || 1, APP_CONFIG.maxPixelRatio);
    this.viewer.resolutionScale = targetPixelRatio;

    // Anti-aliasing pós-processamento
    scene.postProcessStages.fxaa.enabled = true;
    if (scene.msaaSamples !== undefined) {
      scene.msaaSamples = 4;
    }

    // Cor de fundo espacial coerente com nossa paleta CSS
    scene.backgroundColor = Cesium.Color.fromCssColorString('#05070c');

    // Atmosfera e iluminação terrestre
    if (scene.skyAtmosphere) {
      scene.skyAtmosphere.show = true;
      scene.skyAtmosphere.atmosphereLightIntensity = 18.0;
    }

    scene.globe.showGroundAtmosphere = true;
    scene.globe.enableLighting = false; // Inicia com iluminação uniforme para visibilidade global
    scene.globe.baseColor = Cesium.Color.fromCssColorString('#0b1528');
    scene.globe.maximumScreenSpaceError = 1.75; // Equilíbrio entre nitidez de tiles e uso de VRAM
    scene.globe.tileCacheSize = 250;

    // Oculta créditos padrão redundantes mantendo atribuição limpa no rodapé se necessário
    if (this.viewer.cesiumWidget && this.viewer.cesiumWidget.creditContainer) {
      this.viewer.cesiumWidget.creditContainer.style.display = 'none';
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

    // Limites seguros de altitude: de 1,2 km acima do solo até 38.000 km no espaço orbital
    controller.minimumZoomDistance = 1200;
    controller.maximumZoomDistance = 38000000;

    // Amortecimento inercial para navegação fluida
    controller.inertiaSpin = 0.91;
    controller.inertiaTranslate = 0.9;
    controller.inertiaZoom = 0.84;
  }

  /**
   * Adiciona camada pública de imagens de satélite de alta resolução (Token-Free).
   * Caso o usuário esteja offline, falha silenciosamente mantendo a textura NaturalEarthII local.
   */
  async attachHighResSatelliteLayer() {
    try {
      const satelliteProvider = new Cesium.UrlTemplateImageryProvider({
        url: 'https://services.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
        maximumLevel: 18,
        credit: 'Esri, Maxar, Earthstar Geographics, NASA'
      });

      // Silencia erros de rede individuais (ex: modo offline) para não poluir o console
      satelliteProvider.errorEvent.addEventListener((err) => {
        err.retry = false;
      });

      const satelliteLayer = new Cesium.ImageryLayer(satelliteProvider, {
        alpha: 0.92,
        brightness: 1.04,
        contrast: 1.06,
        saturation: 1.02
      });

      this.viewer.imageryLayers.add(satelliteLayer);
    } catch (error) {
      console.warn('[Globe] Usando apenas textura base offline NaturalEarthII:', error);
    }
  }

  /**
   * Configura captura de eventos de mouse para telemetria de coordenadas e seleção de regiões.
   */
  setupPointerTelemetry() {
    const { scene, camera } = this.viewer;
    this.eventHandler = new Cesium.ScreenSpaceEventHandler(scene.canvas);

    // Pausa auto-rotação imediatamente quando o usuário pressiona o mouse ou rola o scroll
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

    // Movimento do cursor: atualiza Latitude, Longitude e Altitude da Câmera no HUD inferior
    this.eventHandler.setInputAction((movement) => {
      const now = performance.now();
      if (now - this.lastPointerEmitTime < 45) {
        return; // Throttle de ~22 Hz para eficiência de CPU
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

    // Clique simples na superfície terrestre: seleciona a coordenada e atualiza o painel direito
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
   * @param {Object} params
   * @param {number} params.latitude
   * @param {number} params.longitude
   * @param {number} [params.altitudeKm=12500]
   * @param {number} [params.duration=2.0]
   */
  flyToRegion({ latitude, longitude, altitudeKm = 12500, duration = 2.0 }) {
    if (!this.viewer || !isValidCoordinate(latitude, longitude)) return;

    const heightMeters = Math.max(1.5, altitudeKm) * 1000;

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

    // Rotação orbital sutil ao redor do eixo Z terrestre
    const angularSpeedRadPerSec = 0.035;
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
      this.viewer.scene.globe.enableLighting = Boolean(payload.enabled);
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
