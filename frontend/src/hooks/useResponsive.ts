import { useTheme } from '@mui/material/styles';
import useMediaQuery from '@mui/material/useMediaQuery';

type Breakpoint = 'xs' | 'sm' | 'md' | 'lg' | 'xl';

export const useResponsive = () => {
  const theme = useTheme();
  
  const isMobile = useMediaQuery(theme.breakpoints.down('sm'));
  const isTablet = useMediaQuery(theme.breakpoints.between('sm', 'md'));
  const isDesktop = useMediaQuery(theme.breakpoints.up('md'));
  const isLargeDesktop = useMediaQuery(theme.breakpoints.up('lg'));
  
  const up = (breakpoint: Breakpoint) => useMediaQuery(theme.breakpoints.up(breakpoint));
  const down = (breakpoint: Breakpoint) => useMediaQuery(theme.breakpoints.down(breakpoint));
  const between = (start: Breakpoint, end: Breakpoint) => 
    useMediaQuery(theme.breakpoints.between(start, end));
  const only = (breakpoint: Breakpoint) => useMediaQuery(theme.breakpoints.only(breakpoint));
  
  return {
    isMobile,
    isTablet,
    isDesktop,
    isLargeDesktop,
    up,
    down,
    between,
    only,
  };
};

// Hook for handling mobile-specific behaviors
export const useMobileOptimizations = () => {
  const { isMobile } = useResponsive();
  
  return {
    // Reduce animation duration on mobile
    animationDuration: isMobile ? 200 : 300,
    
    // Simplify shadows on mobile for performance
    boxShadow: isMobile ? 1 : 2,
    
    // Adjust spacing for mobile
    spacing: isMobile ? 1 : 2,
    
    // Use simpler transitions on mobile
    transition: isMobile ? 'none' : 'all 0.3s ease',
    
    // Disable hover effects on touch devices
    disableHover: isMobile,
  };
};

// Hook for responsive font sizes
export const useResponsiveFontSize = () => {
  const { isMobile, isTablet } = useResponsive();
  
  const scale = (desktop: number, tablet?: number, mobile?: number) => {
    if (isMobile && mobile !== undefined) return mobile;
    if (isTablet && tablet !== undefined) return tablet;
    return desktop;
  };
  
  return {
    h1: scale(48, 40, 32),
    h2: scale(40, 36, 28),
    h3: scale(32, 28, 24),
    h4: scale(28, 24, 20),
    h5: scale(24, 20, 18),
    h6: scale(20, 18, 16),
    body1: scale(16, 16, 14),
    body2: scale(14, 14, 12),
    caption: scale(12, 12, 11),
  };
};