/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        sar: '#ff9100',
        'sar-dark': '#cc7400',
        'slate-950': '#020617',
      },
      animation: {
        'radar-sweep': 'radarSweep 3s linear infinite',
        'pulse-ring': 'pulseRing 2s ease-out infinite',
        'topo-drift': 'topoDrift 20s linear infinite',
      },
      keyframes: {
        radarSweep: {
          '0%': { transform: 'rotate(0deg)' },
          '100%': { transform: 'rotate(360deg)' },
        },
        pulseRing: {
          '0%': { transform: 'scale(0.8)', opacity: '1' },
          '100%': { transform: 'scale(2)', opacity: '0' },
        },
        topoDrift: {
          '0%': { transform: 'translateY(0px)' },
          '100%': { transform: 'translateY(-100px)' },
        },
      },
    },
  },
  plugins: [],
}

