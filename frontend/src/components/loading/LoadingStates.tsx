import { Box, CircularProgress, Skeleton, Typography, LinearProgress } from '@mui/material';

// Full page loader
export const FullPageLoader = ({ message }: { message?: string }) => {
  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        minHeight: '100vh',
        gap: 2 }}
    >
      <CircularProgress size={60} />
      {message && (
        <Typography variant="body2" color="text.secondary">
          {message}
        </Typography>
      )}
    </Box>
  );
};

// Inline loader
export const InlineLoader = ({ size = 20 }: { size?: number }) => {
  return <CircularProgress size={size} sx={{ ml: 1 }} />;
};

// Content loader with skeleton
export const ContentLoader = ({ lines = 3, showAvatar = false }: { lines?: number; showAvatar?: boolean }) => {
  return (
    <Box sx={{ p: 2 }}>
      {showAvatar && (
        <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
          <Skeleton variant="circular" width={40} height={40} />
          <Box sx={{ ml: 2, flex: 1 }}>
            <Skeleton variant="text" width="60%" />
            <Skeleton variant="text" width="40%" />
          </Box>
        </Box>
      )}
      {Array.from({ length: lines }).map((_, index) => (
        <Skeleton
          key={index}
          variant="text"
          width={index === lines - 1 ? '80%' : '100%'}
          sx={{ mb: 1 }}
        />
      ))}
    </Box>
  );
};

// Card skeleton loader
export const CardSkeleton = () => {
  return (
    <Box
      sx={{
        p: 2,
        border: '1px solid',
        borderColor: 'divider',
        borderRadius: 1 }}
    >
      <Skeleton variant="rectangular" height={200} sx={{ mb: 2 }} />
      <Skeleton variant="text" width="80%" sx={{ mb: 1 }} />
      <Skeleton variant="text" width="60%" sx={{ mb: 2 }} />
      <Box sx={{ display: 'flex', gap: 1 }}>
        <Skeleton variant="rectangular" width={80} height={36} />
        <Skeleton variant="rectangular" width={80} height={36} />
      </Box>
    </Box>
  );
};

// Table skeleton loader
export const TableSkeleton = ({ rows = 5, columns = 4 }: { rows?: number; columns?: number }) => {
  return (
    <Box>
      {/* Header */}
      <Box
        sx={{
          display: 'flex',
          p: 2,
          borderBottom: '1px solid',
          borderColor: 'divider',
          backgroundColor: 'grey.50' }}
      >
        {Array.from({ length: columns }).map((_, index) => (
          <Skeleton key={index} variant="text" width="20%" sx={{ mx: 1 }} />
        ))}
      </Box>
      
      {/* Rows */}
      {Array.from({ length: rows }).map((_, rowIndex) => (
        <Box
          key={rowIndex}
          sx={{
            display: 'flex',
            p: 2,
            borderBottom: '1px solid',
            borderColor: 'divider' }}
        >
          {Array.from({ length: columns }).map((_, colIndex) => (
            <Skeleton
              key={colIndex}
              variant="text"
              width={colIndex === 0 ? '25%' : '20%'}
              sx={{ mx: 1 }}
            />
          ))}
        </Box>
      ))}
    </Box>
  );
};

// Progress loader with message
export const ProgressLoader = ({
  value,
  message,
  showPercentage = true }: {
  value: number;
  message?: string;
  showPercentage?: boolean;
}) => {
  return (
    <Box sx={{ width: '100%' }}>
      {message && (
        <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
          <Typography variant="body2" color="text.secondary">
            {message}
          </Typography>
          {showPercentage && (
            <Typography variant="body2" color="text.secondary">
              {Math.round(value)}%
            </Typography>
          )}
        </Box>
      )}
      <LinearProgress variant="determinate" value={value} />
    </Box>
  );
};

// Shimmer effect loader
export const ShimmerLoader = ({ width = '100%', height = 20 }: { width?: string | number; height?: number }) => {
  return (
    <Box
      sx={{
        width,
        height,
        backgroundColor: 'grey.300',
        borderRadius: 1,
        position: 'relative',
        overflow: 'hidden',
        '&::after': {
          content: '""',
          position: 'absolute',
          top: 0,
          right: 0,
          bottom: 0,
          left: 0,
          transform: 'translateX(-100%)',
          background: 'linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.4), transparent)',
          animation: `shimmer 2s infinite` },
        '@keyframes shimmer': {
          '100%': {
            transform: 'translateX(100%)' } } }}
    />
  );
};
