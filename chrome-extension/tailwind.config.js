/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./src/**/*.{js,ts,jsx,tsx,html}",
  ],
  theme: {
    extend: {
      colors: {
        // Dual accent system
        capture: {
          DEFAULT: '#ef4444',
          hover: '#dc2626',
          light: '#fef2f2',
        },
        codegen: {
          DEFAULT: '#22c55e',
          hover: '#16a34a',
          light: '#f0fdf4',
        },
        // Core colors
        primary: {
          DEFAULT: '#ef4444', // Default to capture color
          foreground: '#ffffff',
        },
        background: {
          DEFAULT: '#000000',
          secondary: '#0a0a0a',
          elevated: '#050505',
        },
        border: {
          DEFAULT: '#111111',
          active: '#1a1a1a',
        },
        text: {
          primary: '#e5e5e5',
          secondary: '#737373',
          muted: '#525252',
          disabled: '#404040',
        },
        card: {
          DEFAULT: '#050505',
          foreground: '#e5e5e5',
        },
        muted: {
          DEFAULT: '#0a0a0a',
          foreground: '#525252',
        },
        accent: {
          DEFAULT: '#0a0a0a',
          foreground: '#e5e5e5',
        },
        ring: '#ef4444',
        input: '#111111',
        foreground: '#e5e5e5',
        // Semantic colors
        destructive: {
          DEFAULT: '#ef4444',
          foreground: '#ffffff',
        },
        success: {
          DEFAULT: '#22c55e',
          foreground: '#ffffff',
        },
        warning: {
          DEFAULT: '#f59e0b',
          foreground: '#ffffff',
        },
        info: {
          DEFAULT: '#3b82f6',
          foreground: '#ffffff',
        },
      },
      fontFamily: {
        sans: [
          '-apple-system',
          'BlinkMacSystemFont',
          '"Segoe UI"',
          'Roboto',
          '"Helvetica Neue"',
          'Arial',
          'sans-serif',
          '"Apple Color Emoji"',
          '"Segoe UI Emoji"'
        ],
        heading: [
          'ui-monospace',
          'SFMono-Regular',
          '"SF Mono"',
          'Menlo',
          'Monaco',
          'Consolas',
          '"Liberation Mono"',
          '"Courier New"',
          'monospace'
        ],
        mono: [
          'ui-monospace',
          'SFMono-Regular',
          '"SF Mono"',
          'Menlo',
          'Monaco',
          'Consolas',
          '"Liberation Mono"',
          '"Courier New"',
          'monospace'
        ],
      },
      fontSize: {
        'tiny': ['11px', { lineHeight: '1.3', letterSpacing: '0.03em', fontWeight: '600' }],
        'caption': ['11px', { lineHeight: '1.5', letterSpacing: '0.02em', fontWeight: '500' }],
        'small': ['12px', { lineHeight: '1.5', fontWeight: '500' }],
        'base': ['14px', { lineHeight: '1.5', fontWeight: '400' }],
        'code': ['13px', { lineHeight: '1.5', fontWeight: '400' }],
      },
      animation: {
        'pulse-slow': 'pulse 1.5s ease-in-out infinite',
        'slide-in-from-bottom': 'slide-in-from-bottom 200ms ease-out',
      },
      keyframes: {
        'slide-in-from-bottom': {
          'from': { transform: 'translateY(8px)', opacity: '0' },
          'to': { transform: 'translateY(0)', opacity: '1' },
        },
      },
    },
  },
  plugins: [],
}
