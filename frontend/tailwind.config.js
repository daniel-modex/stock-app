/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./src/**/*.{html,ts}",
  ],
  theme: {
    extend: {
      colors: {
        obsidian: '#0D0E12',
        slatecard: '#151922',
        mintaccent: '#00E699',
        crimsondanger: '#FF4D4D',
        quartzgray: '#8E95A5',
        alabaster: '#F5F6F8',
      },
      fontFamily: {
        display: ['Outfit', 'sans-serif'],
        body: ['Inter', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'monospace'],
      }
    },
  },
  plugins: [],
}
