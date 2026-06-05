/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        // Midnight Green — cor primária do projeto Raiky (SDI.Micro.Produto — PUC-GO)
        // #075056 — HSL(185, 85%, 18%)
        brand: {
          50:  "#effbfc",
          100: "#d6f5f7",
          200: "#a8e9ee",
          300: "#5dd4dd",
          400: "#1ab5c0",
          500: "#0c93a0",
          600: "#097a87",
          700: "#075056", // Midnight Green — cor âncora do Raiky
          800: "#064047",
          900: "#042c30",
        },
        // Orange CTA — cor de destaque do projeto Raiky — #FF5B04 HSL(21, 100%, 51%)
        orange: {
          50:  "#fff4ee",
          100: "#ffe3ce",
          200: "#ffc39a",
          300: "#ff9a5c",
          400: "#ff7424",
          500: "#ff5b04", // CTA Orange — #FF5B04
          600: "#e04500",
          700: "#ba3500",
          800: "#962800",
          900: "#7a1d00",
        },
      },
      fontFamily: {
        sans: ['"Inter"', "system-ui", "sans-serif"],
      },
      animation: {
        "bounce-truck": "bounceTruck 1.5s ease-in-out infinite",
        "pulse-slow": "pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite",
        "fade-in": "fadeIn 0.5s ease-out",
        "slide-up": "slideUp 0.4s ease-out",
      },
      keyframes: {
        bounceTruck: {
          "0%, 100%": { transform: "translateX(0)" },
          "50%": { transform: "translateX(8px)" },
        },
        fadeIn: {
          "0%": { opacity: "0" },
          "100%": { opacity: "1" },
        },
        slideUp: {
          "0%": { opacity: "0", transform: "translateY(12px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
      },
    },
  },
  plugins: [],
};
