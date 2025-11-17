/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        primary: '#1B5E20',
        secondary: '#A8E6CF',
        dark: '#121212',
        darkCard: '#1E1E1E'
      }
    },
  },
  plugins: [],
}
