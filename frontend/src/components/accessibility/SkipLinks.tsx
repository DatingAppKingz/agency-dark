import { Box, Link } from '@mui/material';
import { srOnly } from '@/utils/accessibility';

export const SkipLinks = () => {
  return (
    <Box
      component="nav"
      aria-label="Skip links"
      sx={{
        '& a': {
          ...srOnly,
          '&:focus': {
            position: 'absolute',
            top: 0,
            left: 0,
            width: 'auto',
            height: 'auto',
            padding: 2,
            margin: 0,
            overflow: 'visible',
            clip: 'auto',
            whiteSpace: 'normal',
            backgroundColor: 'primary.main',
            color: 'primary.contrastText',
            textDecoration: 'none',
            zIndex: 9999,
          },
        },
      }}
    >
      <Link href="#main-content">Skip to main content</Link>
      <Link href="#navigation">Skip to navigation</Link>
      <Link href="#search">Skip to search</Link>
    </Box>
  );
};