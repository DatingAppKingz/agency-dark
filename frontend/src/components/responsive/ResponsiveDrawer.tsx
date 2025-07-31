import { Drawer, DrawerProps, SwipeableDrawer } from '@mui/material';
import { useResponsive } from '@/hooks/useResponsive';

interface ResponsiveDrawerProps extends Omit<DrawerProps, 'variant'> {
  mobileVariant?: 'temporary' | 'persistent' | 'permanent';
  desktopVariant?: 'temporary' | 'persistent' | 'permanent';
  swipeable?: boolean;
  onSwipeOpen?: () => void;
  onSwipeClose?: () => void;
}

export const ResponsiveDrawer = ({
  mobileVariant = 'temporary',
  desktopVariant = 'permanent',
  swipeable = true,
  onSwipeOpen,
  onSwipeClose,
  children,
  ...props
}: ResponsiveDrawerProps) => {
  const { isMobile } = useResponsive();
  const variant = isMobile ? mobileVariant : desktopVariant;
  
  if (swipeable && isMobile && onSwipeOpen && onSwipeClose) {
    return (
      <SwipeableDrawer
        {...props}
        variant={variant}
        onOpen={onSwipeOpen}
        onClose={onSwipeClose}
        ModalProps={{
          keepMounted: true, // Better open performance on mobile
        }}
      >
        {children}
      </SwipeableDrawer>
    );
  }
  
  return (
    <Drawer
      {...props}
      variant={variant}
      ModalProps={{
        keepMounted: isMobile, // Better open performance on mobile
      }}
    >
      {children}
    </Drawer>
  );
};
