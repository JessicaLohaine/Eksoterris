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

export default defineConfig({
  define: {
    // Define o caminho base onde o CesiumJS buscará seus Web Workers e Assets em tempo de execução
    CESIUM_BASE_URL: JSON.stringify('/cesium/')
  },
  plugins: [cesiumStaticAssetsPlugin()],
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
