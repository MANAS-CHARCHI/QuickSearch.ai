import type { Config } from 'tailwindcss';

export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        val: {
          bg: '#FAFAFA',
          card: '#FFFFFF',
          border: '#E5E7EB',
          darkBg: '#0A0A0C',
          darkCard: '#121216',
          darkBorder: '#23232A',
        },
      },
      fontFamily: {
        sans: ['Geist', 'Inter', '-apple-system', 'sans-serif'],
        mono: ['"Geist Mono"', 'JetBrains Mono', 'monospace'],
      },
      boxShadow: {
        'val': '0 1px 2px 0 rgba(0, 0, 0, 0.05), 0 1px 3px 0 rgba(0, 0, 0, 0.03)',
        'val-hover': '0 4px 12px 0 rgba(0, 0, 0, 0.08)',
        'val-dark': '0 0 0 1px rgba(255, 255, 255, 0.08), 0 4px 12px 0 rgba(0, 0, 0, 0.4)',
      },
    },
  },
  plugins: [],
} satisfies Config;
