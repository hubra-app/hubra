import { createTheme, DEFAULT_THEME, rem } from "@mantine/core";
import { accColors, pinkColors } from "./colors";

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
    pink: pinkColors,
    bg: [
      "#eef3f0",
      "#eef3f0",
      "#eef3f0",
      "#eef3f0",
      "#eef3f0",
      "#eef3f0",
      "#eef3f0",
      "#eef3f0",
      "#eef3f0",
      "#eef3f0",
    ],
    surface: [
      "#ffffff",
      "#f4f8f5",
      "#e7eeea",
      "#dbe4df",
      "#c4d0c8",
      "#b3c1ba",
      "#9aaba3",
      "#7e918a",
      "#5f746c",
      "#3a4048",
    ],
    line: [
      "#e3eae6",
      "#e3eae6",
      "#e3eae6",
      "#d3ddd7",
      "#d3ddd7",
      "#b3c1ba",
      "#b3c1ba",
      "#b3c1ba",
      "#b3c1ba",
      "#b3c1ba",
    ],
    ink: [
      "#f4f8f5",
      "#e7eeea",
      "#dbe4df",
      "#99a2ac",
      "#6b7480",
      "#6b7480",
      "#3a4048",
      "#3a4048",
      "#181818",
      "#181818",
    ],
  },

  fontFamily: '"Hanken Grotesk", system-ui, sans-serif',
  fontFamilyMonospace: '"JetBrains Mono", ui-monospace, monospace',

  headings: {
    fontFamily: `"Hanken Grotesk", ${DEFAULT_THEME.fontFamily}`,
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
    xs: "0 1px 2px rgba(24,32,28,.07)",
    sm: "0 1px 2px rgba(24,32,28,.05), 0 10px 26px -14px rgba(24,32,28,.16)",
    md: "0 1px 2px rgba(24,32,28,.05), 0 10px 26px -14px rgba(24,32,28,.16)",
    lg: "0 26px 64px -22px rgba(24,32,28,.28), 0 4px 14px -6px rgba(24,32,28,.15)",
    xl: "0 26px 64px -22px rgba(24,32,28,.28), 0 4px 14px -6px rgba(24,32,28,.15)",
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
