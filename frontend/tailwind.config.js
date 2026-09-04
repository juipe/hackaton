/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    container: {
      center: true,
      padding: "1.5rem",
      screens: { "2xl": "1400px" },
    },
    extend: {
      fontFamily: {
        sans: [
          "Golos Text",
          "ui-sans-serif",
          "system-ui",
          "-apple-system",
          "Segoe UI",
          "Roboto",
          "sans-serif",
        ],
      },
      colors: {
        app: "hsl(var(--app))",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        border: "hsl(var(--border))",
        input: "hsl(var(--input))",
        ring: "hsl(var(--ring))",
        card: {
          DEFAULT: "hsl(var(--card))",
          foreground: "hsl(var(--card-foreground))",
        },
        popover: {
          DEFAULT: "hsl(var(--popover))",
          foreground: "hsl(var(--popover-foreground))",
        },
        primary: {
          DEFAULT: "hsl(var(--primary))",
          hover: "hsl(var(--primary-hover))",
          foreground: "hsl(var(--primary-foreground))",
        },
        secondary: {
          DEFAULT: "hsl(var(--secondary))",
          foreground: "hsl(var(--secondary-foreground))",
        },
        muted: {
          DEFAULT: "hsl(var(--muted))",
          foreground: "hsl(var(--muted-foreground))",
        },
        accent: {
          DEFAULT: "hsl(var(--accent))",
          hover: "hsl(var(--accent-hover))",
          foreground: "hsl(var(--accent-foreground))",
        },
        dim: "hsl(var(--dim))",
        faint: "hsl(var(--faint))",
        subtle: "hsl(var(--subtle))",
        "subtle-hover": "hsl(var(--subtle-hover))",
        destructive: {
          DEFAULT: "hsl(var(--destructive))",
          foreground: "hsl(var(--destructive-foreground))",
        },
        success: {
          DEFAULT: "hsl(var(--success))",
          foreground: "hsl(var(--success-foreground))",
        },
        positive: "hsl(var(--positive))",
        negative: "hsl(var(--negative))",
        "negative-surface": {
          DEFAULT: "hsl(var(--negative-surface))",
          hover: "hsl(var(--negative-surface-hover))",
        },
        "chart-muted": "hsl(var(--chart-muted))",
      },
      borderRadius: {
        card: "28px",
        panel: "24px",
        row: "20px",
        tile: "18px",
        field: "16px",
        badge: "15px",
        chip: "13px",
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
      },
      boxShadow: {
        flat: "0 1px 2px rgba(12,31,20,.04)",
        card: "0 1px 2px rgba(12,31,20,.04), 0 14px 36px -20px rgba(12,31,20,.22)",
        panel: "0 1px 2px rgba(12,31,20,.04), 0 12px 30px -20px rgba(12,31,20,.2)",
        panelHover: "0 1px 2px rgba(12,31,20,.04), 0 18px 40px -18px rgba(12,31,20,.28)",
        nav: "0 1px 2px rgba(12,31,20,.04), 0 8px 20px -14px rgba(12,31,20,.18)",
        modal: "0 1px 2px rgba(12,31,20,.04), 0 24px 60px -24px rgba(12,31,20,.32)",
        green: "0 8px 20px -8px rgba(33,160,56,.6)",
        greenSm: "0 8px 20px -10px rgba(33,160,56,.7)",
      },
      keyframes: {
        "accordion-down": {
          from: { height: "0" },
          to: { height: "var(--radix-accordion-content-height)" },
        },
        "accordion-up": {
          from: { height: "var(--radix-accordion-content-height)" },
          to: { height: "0" },
        },
        "fade-in": {
          from: { opacity: "0", transform: "translateY(4px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
      },
      animation: {
        "accordion-down": "accordion-down 0.2s ease-out",
        "accordion-up": "accordion-up 0.2s ease-out",
        "fade-in": "fade-in 0.2s ease-out",
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
};
