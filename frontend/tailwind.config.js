/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        mono: ["JetBrains Mono", "ui-monospace", "monospace"],
      },
      colors: {
        forge: {
          bg: "#0b0d12",
          panel: "#11151c",
          border: "#1f2530",
          accent: "#7cf6c2",
          warn: "#f6d27c",
          err: "#f67c8c",
        },
      },
    },
  },
  plugins: [],
};
