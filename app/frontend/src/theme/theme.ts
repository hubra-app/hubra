import { createTheme, DEFAULT_THEME, rem } from "@mantine/core";
import { accColors, goldColors, pinkColors } from "./colors";

export const theme = createTheme({
  primaryColor: "acc",
  primaryShade: { light: 6, dark: 4 },
  autoContrast: true,
  luminanceThreshold: 0.3,

  breakpoints: {
    xs: "36em",
    sm: "48em",
    md: "62em",
    lg: "75em",
    xl: "90em",
    tab: "54.375em",
    nav: "68.75em",
  },

  colors: {
    acc: accColors,
    gold: goldColors,
    pink: pinkColors,
    bg: [
      "#f7f6fb",
      "#f7f6fb",
      "#f7f6fb",
      "#f7f6fb",
      "#f7f6fb",
      "#f7f6fb",
      "#f7f6fb",
      "#f7f6fb",
      "#f7f6fb",
      "#f7f6fb",
    ],
    surface: [
      "#ffffff",
      "#f4f2f9",
      "#ebe8f2",
      "#dfdbe9",
      "#c8c1d8",
      "#b7b0c9",
      "#9d95b3",
      "#827a99",
      "#625a7a",
      "#2e2940",
    ],
    line: [
      "#e6e3ef",
      "#e6e3ef",
      "#e6e3ef",
      "#d6d2e3",
      "#d6d2e3",
      "#b7b0c9",
      "#b7b0c9",
      "#b7b0c9",
      "#b7b0c9",
      "#b7b0c9",
    ],
    ink: [
      "#f4f2f9",
      "#ebe8f2",
      "#dfdbe9",
      "#8c86a0",
      "#5e5873",
      "#5e5873",
      "#2e2940",
      "#2e2940",
      "#1a1625",
      "#1a1625",
    ],
  },

  fontFamily: '"Hanken Grotesk", system-ui, sans-serif',
  fontFamilyMonospace: '"JetBrains Mono", ui-monospace, monospace',

  headings: {
    fontFamily: `"Bricolage Grotesque", "Hanken Grotesk", ${DEFAULT_THEME.fontFamily}`,
    fontWeight: "700",
    sizes: {
      h1: { fontSize: rem(25), lineHeight: "1.2" },
      h2: { fontSize: rem(22), lineHeight: "1.25" },
      h3: { fontSize: rem(18), lineHeight: "1.3" },
    },
  },

  radius: {
    xs: "6px",
    sm: "8px",
    md: "11px",
    lg: "15px",
    xl: "20px",
  },

  shadows: {
    xs: "0 1px 2px rgba(26,22,37,.07)",
    sm: "0 1px 2px rgba(26,22,37,.05), 0 10px 26px -14px rgba(26,22,37,.16)",
    md: "0 1px 2px rgba(26,22,37,.05), 0 10px 26px -14px rgba(26,22,37,.16)",
    lg: "0 26px 64px -22px rgba(26,22,37,.28), 0 4px 14px -6px rgba(26,22,37,.15)",
    xl: "0 26px 64px -22px rgba(26,22,37,.28), 0 4px 14px -6px rgba(26,22,37,.15)",
  },

  defaultRadius: "md",

  components: {
    Button: {
      defaultProps: {
        radius: "sm",
        size: "sm",
        fw: 600,
      },
    },
    TextInput: {
      defaultProps: {
        radius: "md",
        size: "md",
      },
    },
    PasswordInput: {
      defaultProps: {
        radius: "md",
        size: "md",
      },
    },
    Textarea: {
      defaultProps: {
        radius: "md",
        size: "md",
      },
    },
    Select: {
      defaultProps: {
        radius: "md",
        size: "md",
      },
    },
    Modal: {
      defaultProps: {
        radius: "lg",
        centered: true,
        overlayProps: { backgroundOpacity: 0.42, blur: 2 },
      },
    },
    Paper: {
      defaultProps: {
        radius: "lg",
        shadow: "sm",
      },
    },
    Badge: {
      defaultProps: {
        radius: "sm",
        size: "md",
        fw: 600,
      },
    },
    Table: {
      defaultProps: {
        verticalSpacing: "sm",
        horizontalSpacing: "md",
        fontSize: "md",
      },
    },
    Notification: {
      defaultProps: {
        radius: "md",
      },
    },
  },
});
