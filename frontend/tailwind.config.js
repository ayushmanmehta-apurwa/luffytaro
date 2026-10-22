/** Palette: dark navy shell, white work surfaces, electric blue accent, three verdict colours. */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        ink: '#060C1E',
        navy: { 950: '#070D20', 900: '#0B1530', 800: '#101D42', 700: '#1A2A5C', 600: '#2A3D78' },
        paper: '#F4F7FF',
        electric: { DEFAULT: '#2F6BFF', soft: '#6C9BFF', deep: '#1B4FD6' },
        verdict: { ok: '#13A67A', okbg: '#E3F7F0', warn: '#B7791F', warnbg: '#FFF4DB', bad: '#D63A4D', badbg: '#FDE8EB' },
      },
      fontFamily: {
        display: ['"Bricolage Grotesque Variable"', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        sans: ['"Hanken Grotesk Variable"', 'ui-sans-serif', 'system-ui', 'sans-serif'],
      },
      opacity: { 6: '0.06', 8: '0.08', 12: '0.12' },
      boxShadow: { lift: '0 1px 2px rgba(7,13,32,.06), 0 8px 24px -12px rgba(7,13,32,.25)' },
    },
  },
  plugins: [],
}
