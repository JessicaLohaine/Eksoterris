/**
 * Renderizador Base de Corpos Planetários Secundários (src/planets/planet-renderer.js)
 * Etapa 6: Refinamento de desempenho (IntersectionObserver + Visibility API),
 * transição suave de reset de câmera e gerenciamento de recursos GPU.
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
      bumpScale: 0.025,
      roughness: 0.88,
      metalness: 0.04,
      axialTiltDeg: 0,
      rotationSpeed: 0.002,
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
    this.defaultCameraPos = new THREE.Vector3(0, 0.15, 2.55);
  }

  /**
   * Inicializa a cena Three.js, carrega texturas e inicia o loop de renderização.
   */
  init() {
    if (!this.container) {
      throw new Error(`Container para ${this.options.name} não encontrado.`);
    }

    // Remove apenas o placeholder estático da Etapa 3 preservando dicas de UI se houver
    const placeholder = this.container.querySelector('[data-stage-placeholder="true"]');
    if (placeholder) {
      placeholder.remove();
    }

    const width = Math.max(this.container.clientWidth, 180);
    const height = Math.max(this.container.clientHeight, 130);

    // 1. Cena e Câmera Perspectiva (FOV 35° evita distorção esférica nas bordas)
    this.scene = new THREE.Scene();
    this.camera = new THREE.PerspectiveCamera(35, width / height, 0.1, 50);
    this.camera.position.copy(this.defaultCameraPos);

    // 2. Renderizador WebGL otimizado
    this.renderer = new THREE.WebGLRenderer({
      antialias: true,
      alpha: true,
      powerPreference: 'high-performance'
    });
    this.renderer.setSize(width, height);
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, APP_CONFIG.maxPixelRatio));
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
    this.renderer.toneMappingExposure = 1.08;

    this.container.insertBefore(this.renderer.domElement, this.container.firstChild);

    // 3. Iluminação Coerente (Sol Principal + Luz Espacial de Preenchimento + Rim Light)
    this.setupLighting();

    // 4. Malha Esférica 3D + Texturas + Inclinação Axial
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
   * Configura iluminação tridimensional com padrão orbital realista.
   */
  setupLighting() {
    const ambientLight = new THREE.AmbientLight(0xdbeafe, 0.34);
    this.scene.add(ambientLight);

    const sunLight = new THREE.DirectionalLight(0xfffbeb, 2.4);
    sunLight.position.set(4.5, 2.0, 3.8);
    this.scene.add(sunLight);

    const rimLight = new THREE.DirectionalLight(0x64748b, 0.58);
    rimLight.position.set(-4.0, -1.8, -3.2);
    this.scene.add(rimLight);
  }

  /**
   * Cria a geometria esférica do planeta e aplica texturas com fallback automático.
   */
  setupPlanetMesh() {
    this.planetGroup = new THREE.Group();
    this.planetGroup.rotation.z = THREE.MathUtils.degToRad(this.options.axialTiltDeg);
    this.scene.add(this.planetGroup);

    const geometry = new THREE.SphereGeometry(0.84, 64, 64);
    const fallbackTexture = this.createProceduralFallbackTexture(this.options.fallbackColorHex);

    const material = new THREE.MeshStandardMaterial({
      map: fallbackTexture,
      roughness: this.options.roughness,
      metalness: this.options.metalness,
      bumpScale: this.options.bumpScale
    });

    this.planetMesh = new THREE.Mesh(geometry, material);
    this.planetGroup.add(this.planetMesh);

    if (this.options.hasAtmosphereGlow) {
      const glowGeometry = new THREE.SphereGeometry(0.874, 48, 48);
      const glowMaterial = new THREE.MeshBasicMaterial({
        color: new THREE.Color(this.options.atmosphereColorHex),
        transparent: true,
        opacity: 0.12,
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
          material.map = texture;
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
   * Gera uma textura procedural leve em Canvas 2D caso a imagem principal ainda esteja carregando ou falhe.
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

      for (let i = 0; i < 180; i++) {
        const x = (Math.sin(i * 12.9898) * 0.5 + 0.5) * canvas.width;
        const y = (Math.cos(i * 78.233) * 0.5 + 0.5) * canvas.height;
        const r = 2 + (i % 10);
        ctx.fillStyle = i % 2 === 0 ? 'rgba(0, 0, 0, 0.12)' : 'rgba(255, 255, 255, 0.08)';
        ctx.beginPath();
        ctx.arc(x, y, r, 0, Math.PI * 2);
        ctx.fill();
      }
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
    this.controls.minDistance = 1.65;
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

    // Pausa renderização caso o card saia da área visível em telas menores/mobile
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
   * Loop de renderização com economia inteligente de GPU (aba oculta ou elemento fora da tela).
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
