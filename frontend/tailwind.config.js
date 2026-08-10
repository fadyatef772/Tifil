/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        display: ["Baloo 2", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
};
