import { defineConfig } from 'vite';
import buildPlugin from '@hono/vite-cloudflare-pages';

export default defineConfig(({ command }) => {
  return {
    plugins: [
      buildPlugin({
        entry: 'src/index.jsx',
      }),
    ],
    build: {
      outDir: 'dist',
      emitAssets: true, // Ensure assets are created
      manifest: true, // Generate the manifest
      // Rollup options might only need the worker entry now
      rollupOptions: {
        input: { app: 'src/index.jsx' }, // Or let plugin handle input? Test this.
        output: {
          entryFileNames: '_worker.js',
          assetFileNames: `public/[name].[ext]`
        }
      },
    },
  };
});