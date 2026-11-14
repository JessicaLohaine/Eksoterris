/**
 * Renderizador Base de Corpos Planetários Secundários (src/planets/planet-renderer.js)
 * Reestruturação Visual 3D:
 * - Geometria de alta densidade (96x96 segmentos) para silhueta perfeitamente esférica.
 * - Texturas reais 2K (2048x1024) baseadas em missões da NASA (LRO para Lua, Viking/MOLA para Marte).
 * - Mapeamento de relevo (Bump Map) em registro pixel-a-pixel com as feições reais (crateras, mares e cânions).
 * - Iluminação solar coerente com a posição da câmera (acoplada ao referencial orbital da câmera),
 *   garantindo transição dia/noite (terminador) natural e visibilidade em qualquer ângulo de rotação.
 */
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { APP_CONFIG } from '../config/constants.js';
import { eventBus } from '../utils/event-bus.js';

export function getThreeEngineInfo() {
  return {
    engine: 'Three.js',
    revision: THREE.REVISION,
    ready: Boolean(THREE && THREE.WebGLRenderer)
  };
}

export class PlanetRenderer {
  /**
   * @param {HTMLElement} container Container DOM do cartão lateral
   * @param {Object} options Configurações visuais e físicas do corpo celeste
   */
  constructor(container, options) {
    this.container = container;
    this.options = {
      id: 'planet',
      name: 'Corpo Celeste',
      albedoUrl: '',
      bumpUrl: '',
      bumpScale: 0.02,
      roughness: 0.88,
      metalness: 0.03,
      axialTiltDeg: 0,
      rotationSpeed: 0.0016,
      fallbackColorHex: '#94a3b8',
      hasAtmosphereGlow: false,
      atmosphereColorHex: '#f97316',
      ...options
    };

    this.scene = null;
    this.camera = null;
    this.renderer = null;
    this.controls = null;
    this.planetMesh = null;
    this.planetGroup = null;
    this.resizeObserver = null;
    this.intersectionObserver = null;
    this.animationFrameId = null;
    this.isUserDragging = false;
    this.isVisibleInViewport = true;
    this.isDisposed = false;
    this.defaultCameraPos = new THREE.Vector3(0, 0.12, 2.48);
  }

  /**
   * Inicializa a cena Three.js, carrega texturas 2K e inicia o loop de renderização.
   */
  init() {
    if (!this.container) {
      throw new Error(`Container para ${this.options.name} não encontrado.`);
    }

    const placeholder = this.container.querySelector('[data-stage-placeholder="true"]');
    if (placeholder) {
      placeholder.remove();
    }

    const width = Math.max(this.container.clientWidth, 180);
    const height = Math.max(this.container.clientHeight, 130);

    // 1. Cena e Câmera Perspectiva (FOV 34° para proporção teleobjetiva espacial)
    this.scene = new THREE.Scene();
    this.camera = new THREE.PerspectiveCamera(34, width / height, 0.1, 50);
    this.camera.position.copy(this.defaultCameraPos);
    this.scene.add(this.camera);

    // 2. Renderizador WebGL de alta precisão cromática
    this.renderer = new THREE.WebGLRenderer({
      antialias: true,
      alpha: true,
      powerPreference: 'high-performance'
    });
    this.renderer.setSize(width, height);
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, APP_CONFIG.maxPixelRatio));
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
    this.renderer.toneMappingExposure = 1.12;

    this.container.insertBefore(this.renderer.domElement, this.container.firstChild);

    // 3. Iluminação Solar Coerente com a Câmera
    this.setupLighting();

    // 4. Malha Esférica 3D + Texturas Reais 2K + Relevo
    this.setupPlanetMesh();

    // 5. Controles de Interação com o Mouse (OrbitControls)
    this.setupControls();

    // 6. Observadores de Redimensionamento, Visibilidade e Eventos
    this.setupObservers();

    // 7. Inicia Loop de Animação
    this.animate();

    return this;
  }

  /**
   * Configura iluminação acoplada à câmera para que a luz solar seja sempre coerente
   * com o ponto de vista do observador, preservando um terminador suave no limbo.
   */
  setupLighting() {
    const ambientLight = new THREE.AmbientLight(0xdbeafe, 0.22);
    this.scene.add(ambientLight);

    // Luz Solar Direcional principal acoplada ao referencial da câmera
    const sunLight = new THREE.DirectionalLight(0xfffaf0, 2.65);
    sunLight.position.set(3.8, 1.6, 3.2);
    this.camera.add(sunLight);

    // Luz secundária de penumbra / contra-luz suave no limbo oposto
    const rimLight = new THREE.DirectionalLight(0x64748b, 0.42);
    rimLight.position.set(-3.5, -1.4, -2.0);
    this.camera.add(rimLight);
  }

  /**
   * Cria a geometria esférica do planeta e aplica texturas reais 2K com relevo alinhado.
   */
  setupPlanetMesh() {
    this.planetGroup = new THREE.Group();
    this.planetGroup.rotation.z = THREE.MathUtils.degToRad(this.options.axialTiltDeg);
    this.scene.add(this.planetGroup);

    const geometry = new THREE.SphereGeometry(0.85, 96, 96);
    const fallbackTexture = this.createProceduralFallbackTexture(this.options.fallbackColorHex);

    const material = new THREE.MeshStandardMaterial({
      map: fallbackTexture,
      roughness: this.options.roughness,
      metalness: this.options.metalness,
      bumpScale: this.options.bumpScale
    });

    this.planetMesh = new THREE.Mesh(geometry, material);
    this.planetGroup.add(this.planetMesh);

    // Halo atmosférico sutil para Marte (dispersão de poeira e CO2 no horizonte)
    if (this.options.hasAtmosphereGlow) {
      const glowGeometry = new THREE.SphereGeometry(0.88, 64, 64);
      const glowMaterial = new THREE.MeshBasicMaterial({
        color: new THREE.Color(this.options.atmosphereColorHex),
        transparent: true,
        opacity: 0.09,
        side: THREE.BackSide,
        blending: THREE.AdditiveBlending,
        depthWrite: false
      });
      const glowMesh = new THREE.Mesh(glowGeometry, glowMaterial);
      this.planetGroup.add(glowMesh);
    }

    const loader = new THREE.TextureLoader();
    const maxAnisotropy = this.renderer.capabilities.getMaxAnisotropy();

    if (this.options.albedoUrl) {
      loader.load(
        this.options.albedoUrl,
        (texture) => {
          texture.colorSpace = THREE.SRGBColorSpace;
          texture.anisotropy = maxAnisotropy;
          texture.minFilter = THREE.LinearMipmapLinearFilter;
          texture.magFilter = THREE.LinearFilter;
          material.map = texture;

          // Usa o próprio mosaico fotográfico de alta resolução como micro-relevo base
          // garantindo alinhamento 100% exato de cada cratera, cânion e monte vulcânico
          if (!material.bumpMap) {
            material.bumpMap = texture;
          }
          material.needsUpdate = true;
          fallbackTexture.dispose();
        },
        undefined,
        (err) => {
          console.warn(`[PlanetRenderer] Usando textura de contingência para ${this.options.name}:`, err);
        }
      );
    }

    if (this.options.bumpUrl) {
      loader.load(
        this.options.bumpUrl,
        (bumpTexture) => {
          bumpTexture.anisotropy = maxAnisotropy;
          material.bumpMap = bumpTexture;
          material.needsUpdate = true;
        },
        undefined,
        () => {}
      );
    }
  }

  /**
   * Gera uma textura procedural leve em Canvas 2D caso a imagem principal ainda esteja carregando.
   * @param {string} baseColorHex
   * @returns {THREE.CanvasTexture}
   */
  createProceduralFallbackTexture(baseColorHex) {
    const canvas = document.createElement('canvas');
    canvas.width = 256;
    canvas.height = 128;
    const ctx = canvas.getContext('2d');

    if (ctx) {
      ctx.fillStyle = baseColorHex;
      ctx.fillRect(0, 0, canvas.width, canvas.height);
    }

    const texture = new THREE.CanvasTexture(canvas);
    texture.colorSpace = THREE.SRGBColorSpace;
    return texture;
  }

  /**
   * Configura controles de rotação e zoom com o mouse mantendo o astro centralizado.
   */
  setupControls() {
    this.controls = new OrbitControls(this.camera, this.renderer.domElement);
    this.controls.enableDamping = true;
    this.controls.dampingFactor = 0.06;
    this.controls.enablePan = false;
    this.controls.enableRotate = true;
    this.controls.enableZoom = true;
    this.controls.rotateSpeed = 0.75;
    this.controls.zoomSpeed = 0.8;
    this.controls.minDistance = 1.55;
    this.controls.maxDistance = 3.5;

    this.controls.addEventListener('start', () => {
      this.isUserDragging = true;
    });

    this.controls.addEventListener('end', () => {
      this.isUserDragging = false;
    });
  }

  /**
   * Reposiciona a câmera orbital do astro para a distância e ângulo iniciais.
   */
  resetCameraView() {
    if (!this.camera || !this.controls) return;
    this.camera.position.copy(this.defaultCameraPos);
    this.controls.target.set(0, 0, 0);
    this.controls.update();
  }

  /**
   * Configura redimensionamento responsivo, IntersectionObserver e eventos.
   */
  setupObservers() {
    if (typeof ResizeObserver !== 'undefined') {
      this.resizeObserver = new ResizeObserver((entries) => {
        for (const entry of entries) {
          const { width, height } = entry.contentRect;
          if (width > 10 && height > 10 && this.camera && this.renderer) {
            this.camera.aspect = width / height;
            this.camera.updateProjectionMatrix();
            this.renderer.setSize(width, height, false);
          }
        }
      });
      this.resizeObserver.observe(this.container);
    }

    if (typeof IntersectionObserver !== 'undefined') {
      this.intersectionObserver = new IntersectionObserver(
        (entries) => {
          for (const entry of entries) {
            this.isVisibleInViewport = entry.isIntersecting;
          }
        },
        { threshold: 0.05 }
      );
      this.intersectionObserver.observe(this.container);
    }

    eventBus.on('planet:reset-view', (payload) => {
      if (payload && payload.id === this.options.id) {
        this.resetCameraView();
      }
    });

    const canvas = this.renderer.domElement;
    canvas.addEventListener('webglcontextlost', (e) => {
      e.preventDefault();
      console.warn(`[PlanetRenderer] Contexto WebGL perdido em ${this.options.name}.`);
    });
  }

  /**
   * Loop de renderização com economia inteligente de GPU.
   */
  animate() {
    if (this.isDisposed) return;

    this.animationFrameId = requestAnimationFrame(() => this.animate());

    if (document.hidden || !this.isVisibleInViewport) {
      return;
    }

    if (this.planetMesh && !this.isUserDragging) {
      this.planetMesh.rotation.y += this.options.rotationSpeed;
    }

    if (this.controls) {
      this.controls.update();
    }

    if (this.renderer && this.scene && this.camera) {
      this.renderer.render(this.scene, this.camera);
    }
  }

  /**
   * Libera memória de vídeo (VRAM) e encerra observadores.
   */
  dispose() {
    this.isDisposed = true;
    if (this.animationFrameId) {
      cancelAnimationFrame(this.animationFrameId);
    }
    if (this.resizeObserver) {
      this.resizeObserver.disconnect();
    }
    if (this.intersectionObserver) {
      this.intersectionObserver.disconnect();
    }
    if (this.controls) {
      this.controls.dispose();
    }
    if (this.planetMesh) {
      this.planetMesh.geometry.dispose();
      if (this.planetMesh.material.map) this.planetMesh.material.map.dispose();
      if (this.planetMesh.material.bumpMap) this.planetMesh.material.bumpMap.dispose();
      this.planetMesh.material.dispose();
    }
    if (this.renderer) {
      this.renderer.dispose();
    }
  }
}
