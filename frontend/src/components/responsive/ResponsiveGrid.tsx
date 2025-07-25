import { Grid, GridProps } from '@mui/material';
import { useResponsive } from '@/hooks/useResponsive';

interface ResponsiveGridProps extends GridProps {
  mobileColumns?: number;
  tabletColumns?: number;
  desktopColumns?: number;
}

export const ResponsiveGrid = ({
  mobileColumns = 12,
  tabletColumns = 6,
  desktopColumns = 4,
  children,
  ...props
}: ResponsiveGridProps) => {
  const { isMobile, isTablet } = useResponsive();
  
  const columns = isMobile ? mobileColumns : isTablet ? tabletColumns : desktopColumns;
  
  return (
    <Grid
      {...props}
      xs={mobileColumns}
      sm={tabletColumns}
      md={desktopColumns}
    >
      {children}
    </Grid>
  );
};

// Responsive card grid container
interface ResponsiveCardGridProps {
  children: React.ReactNode;
  minCardWidth?: number;
  spacing?: number;
}

export const ResponsiveCardGrid = ({
  children,
  minCardWidth = 300,
  spacing = 3,
}: ResponsiveCardGridProps) => {
  return (
    <Grid
      container
      spacing={spacing}
      sx={{
        display: 'grid',
        gridTemplateColumns: `repeat(auto-fill, minmax(${minCardWidth}px, 1fr))`,
        gap: spacing,
      }}
    >
      {children}
    </Grid>
  );
};