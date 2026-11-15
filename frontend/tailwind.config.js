/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx,ts,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Rubik', 'system-ui', 'sans-serif'],
      },
      animation: {
        'fade-in': 'fadeIn 0.15s ease-out',
        'progress-indeterminate': 'progressIndeterminate 1.4s ease-in-out infinite',
      },
      keyframes: {
        // RTL: the bar starts at the right edge and sweeps left
        progressIndeterminate: {
          from: { transform: 'translateX(100%)' },
          to: { transform: 'translateX(-300%)' },
        },
        fadeIn: {
          from: { opacity: '0', transform: 'translateY(-4px)' },
          to: { opacity: '1', transform: 'translateY(0)' },
        },
      },
    },
  },
  plugins: [],
};
