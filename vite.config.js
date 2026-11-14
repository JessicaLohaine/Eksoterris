import { defineConfig } from 'vite';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

/**
 * Plugin nativo para sincronizar os ativos estáticos obrigatórios do CesiumJS
 * (Workers, ThirdParty, Assets e Widgets) para public/cesium sem depender
 * de pacotes externos de terceiros.
 */
function cesiumStaticAssetsPlugin() {
  const cesiumSource = path.resolve(__dirname, 'node_modules/cesium/Build/Cesium');
  const cesiumDest = path.resolve(__dirname, 'public/cesium');
  const directories = ['Workers', 'ThirdParty', 'Assets', 'Widgets'];

  return {
    name: 'vite-plugin-cesium-static-assets',
    buildStart() {
      if (!fs.existsSync(cesiumSource)) {
        return;
      }
      fs.mkdirSync(cesiumDest, { recursive: true });
      for (const dir of directories) {
        const srcDir = path.join(cesiumSource, dir);
        const destDir = path.join(cesiumDest, dir);
        if (fs.existsSync(srcDir) && !fs.existsSync(destDir)) {
          fs.cpSync(srcDir, destDir, { recursive: true });
        }
      }
    }
  };
}

/**
 * Mapa de provedores científicos e institucionais de imagens de satélite por tiles.
 * - sentinel2: EOX Sentinel-2 Cloudless (ESA Copernicus 10m-15m Global Mosaic)
 * - arcgis: Esri / Maxar / Earthstar Geographics World Imagery (Nível orbital a sub-métrico)
 * - nasa-bluemarble: NASA GIBS Blue Marble Next Generation (WMTS Oficial da NASA)
 * - nasa-viirs: NASA GIBS / Worldview VIIRS True Color
 * - hillshade: Esri World Elevation Hillshade (Sombreado de Relevo Topográfico)
 */
const TILE_PROVIDERS = Object.freeze({
  sentinel2: (z, y, x) =>
    `https://tiles.maps.eox.at/wmts/1.0.0/s2cloudless-2020_3857/default/GoogleMapsCompatible/${z}/${y}/${x}.jpg`,
  arcgis: (z, y, x) =>
    `https://services.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/${z}/${y}/${x}`,
  'nasa-bluemarble': (z, y, x) =>
    `https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/BlueMarble_NextGeneration/default/GoogleMapsCompatible_Level8/${z}/${y}/${x}.jpeg`,
  'nasa-viirs': (z, y, x) =>
    `https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/VIIRS_SNPP_CorrectedReflectance_TrueColor/default/2024-06-15/GoogleMapsCompatible_Level9/${z}/${y}/${x}.jpg`,
  hillshade: (z, y, x) =>
    `https://services.arcgisonline.com/ArcGIS/rest/services/Elevation/World_Hillshade/MapServer/tile/${z}/${y}/${x}`
});

/**
 * Middleware de Proxy e Cache Local de Tiles Geoespaciais.
 * Evita downloads repetitivos, elimina bloqueios de CORS/CSP e acelera o carregamento progressivo.
 */
function geospatialTileProxyPlugin() {
  const cacheRoot = path.resolve(__dirname, '.tile-cache');

  return {
    name: 'vite-plugin-geospatial-tile-proxy',
    configureServer(server) {
      server.middlewares.use('/api-tiles', async (req, res, next) => {
        if (req.method !== 'GET') {
          next();
          return;
        }

        // Formato esperado: /<provider>/<z>/<y>/<x>
        const parts = (req.url || '').split('?')[0].split('/').filter(Boolean);
        if (parts.length !== 4) {
          res.statusCode = 400;
          res.end('Invalid tile path');
          return;
        }

        const [provider, zStr, yStr, xStr] = parts;
        const buildUrl = TILE_PROVIDERS[provider];
        if (!buildUrl || !/^\d+$/.test(zStr) || !/^\d+$/.test(yStr) || !/^\d+$/.test(xStr)) {
          res.statusCode = 400;
          res.end('Invalid tile parameters');
          return;
        }

        const z = Number(zStr);
        const y = Number(yStr);
        const x = Number(xStr);
        if (z < 0 || z > 20) {
          res.statusCode = 400;
          res.end('Zoom out of bounds');
          return;
        }

        const providerCacheDir = path.join(cacheRoot, provider, String(z));
        const cacheFile = path.join(providerCacheDir, `${y}_${x}.jpg`);

        try {
          // 1. Verifica cache em disco local
          if (fs.existsSync(cacheFile)) {
            const cachedBuffer = fs.readFileSync(cacheFile);
            res.setHeader('Content-Type', 'image/jpeg');
            res.setHeader('Cache-Control', 'public, max-age=604800, immutable');
            res.setHeader('X-Tile-Cache', 'HIT');
            res.statusCode = 200;
            res.end(cachedBuffer);
            return;
          }

          // 2. Busca tile na fonte institucional com timeout seguro
          const targetUrl = buildUrl(z, y, x);
          const controller = new AbortController();
          const timeoutId = setTimeout(() => controller.abort(), 8000);

          const upstreamRes = await fetch(targetUrl, {
            headers: {
              'User-Agent': 'Eksoterris-NASA-SpaceApps-2026/1.0',
              Accept: 'image/jpeg,image/png,image/*,*/*'
            },
            signal: controller.signal
          });
          clearTimeout(timeoutId);

          if (!upstreamRes.ok) {
            res.statusCode = upstreamRes.status;
            res.end();
            return;
          }

          const arrayBuffer = await upstreamRes.arrayBuffer();
          const buffer = Buffer.from(arrayBuffer);

          // Salva no cache local para acesso instantâneo futuro
          fs.mkdirSync(providerCacheDir, { recursive: true });
          fs.writeFileSync(cacheFile, buffer);

          res.setHeader('Content-Type', upstreamRes.headers.get('content-type') || 'image/jpeg');
          res.setHeader('Cache-Control', 'public, max-age=604800, immutable');
          res.setHeader('X-Tile-Cache', 'MISS');
          res.statusCode = 200;
          res.end(buffer);
        } catch {
          res.statusCode = 502;
          res.end();
        }
      });
    }
  };
}

export default defineConfig({
  define: {
    CESIUM_BASE_URL: JSON.stringify('/cesium/')
  },
  plugins: [cesiumStaticAssetsPlugin(), geospatialTileProxyPlugin()],
  server: {
    host: '127.0.0.1',
    port: 5173,
    strictPort: false,
    open: false
  },
  build: {
    target: 'es2022',
    sourcemap: false,
    chunkSizeWarningLimit: 5500,
    rollupOptions: {
      output: {
        manualChunks: {
          'vendor-cesium': ['cesium'],
          'vendor-three': ['three']
        }
      }
    }
  }
});
