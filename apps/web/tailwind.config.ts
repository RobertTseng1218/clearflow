import type { Config } from 'tailwindcss';

const config: Config = {
  content: [
    './app/**/*.{ts,tsx}',
    './components/**/*.{ts,tsx}',
    './lib/**/*.{ts,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          50: '#eefaf6',
          100: '#d8f2e7',
          500: '#23a26d',
          600: '#18855a',
          900: '#0f3d2c'
        }
      }
    }
  },
  plugins: [],
};

export default config;
