import { createTheme, ThemeOptions } from '@mui/material/styles';
import { grey, blue, green, red, orange } from '@mui/material/colors';

// Optimized theme configuration with minimal imports
const themeOptions: ThemeOptions = {
  palette: {
    mode: 'dark',
    primary: {
      main: blue[500],
      light: blue[300],
      dark: blue[700],
    },
    secondary: {
      main: '#f50057',
    },
    background: {
      default: '#0a0a0a',
      paper: '#1a1a1a',
    },
    success: {
      main: green[500],
    },
    error: {
      main: red[500],
    },
    warning: {
      main: orange[500],
    },
    grey: grey,
  },
  typography: {
    fontFamily: '"Inter", "Roboto", "Helvetica", "Arial", sans-serif',
    h1: {
      fontSize: '2.5rem',
      fontWeight: 600,
    },
    h2: {
      fontSize: '2rem',
      fontWeight: 600,
    },
    h3: {
      fontSize: '1.75rem',
      fontWeight: 600,
    },
    h4: {
      fontSize: '1.5rem',
      fontWeight: 600,
    },
    h5: {
      fontSize: '1.25rem',
      fontWeight: 600,
    },
    h6: {
      fontSize: '1rem',
      fontWeight: 600,
    },
  },
  shape: {
    borderRadius: 8,
  },
  components: {
    // Optimize Material-UI components
    MuiCssBaseline: {
      styleOverrides: {
        body: {
          scrollbarColor: '#6b6b6b #2b2b2b',
          '&::-webkit-scrollbar, & *::-webkit-scrollbar': {
            backgroundColor: '#2b2b2b',
            width: 8,
            height: 8,
          },
          '&::-webkit-scrollbar-thumb, & *::-webkit-scrollbar-thumb': {
            borderRadius: 8,
            backgroundColor: '#6b6b6b',
            minHeight: 24,
          },
        },
      },
    },
    MuiButton: {
      styleOverrides: {
        root: {
          textTransform: 'none',
          fontWeight: 500,
        },
      },
      defaultProps: {
        disableElevation: true,
      },
    },
    MuiPaper: {
      styleOverrides: {
        root: {
          backgroundImage: 'none',
        },
      },
    },
    // Disable ripple globally for better performance on mobile
    MuiButtonBase: {
      defaultProps: {
        disableRipple: true,
      },
    },
  },
};

// Create theme instance
export const theme = createTheme(themeOptions);

// Light theme variant
export const lightTheme = createTheme({
  ...themeOptions,
  palette: {
    ...themeOptions.palette,
    mode: 'light',
    background: {
      default: '#fafafa',
      paper: '#ffffff',
    },
  },
});

// Performance optimizations for Material-UI
export const muiOptimizations = {
  // Use CSS variables for dynamic theming
  cssVariables: true,
  
  // Disable transitions on mobile for better performance
  disableTransitionsOnMobile: () => {
    if (window.matchMedia('(max-width: 600px)').matches) {
      return {
        MuiButtonBase: {
          defaultProps: {
            disableTouchRipple: true,
          },
        },
        transitions: {
          create: () => 'none',
        },
      };
    }
    return {};
  },
};