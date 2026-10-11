import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes('node_modules')) return;
          const d3Package = id.match(/node_modules\/(d3-[^/]+)/);
          if (d3Package) return d3Package[1];
          if (id.includes('/recharts/')) return 'charts';
          if (id.includes('/lucide-react/')) return 'icons';
          if (id.includes('/react/')) return 'react-vendor';
        },
      },
    },
  },
});
