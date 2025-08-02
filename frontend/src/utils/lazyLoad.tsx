import { lazy, Suspense, ComponentType } from 'react';
import { Box, CircularProgress } from '@mui/material';

// Loading component for lazy loaded pages
const PageLoader = () => (
  <Box
    sx={{
      display: 'flex',
      justifyContent: 'center',
      alignItems: 'center',
      minHeight: '60vh' }}
  >
    <CircularProgress />
  </Box>
);

// Wrapper function for lazy loading with Suspense
export function lazyLoad<T extends ComponentType<any>>(
  importFunc: () => Promise<{ default: T }>
) {
  const LazyComponent = lazy(importFunc);

  return (props: any) => (
    <Suspense fallback={<PageLoader />}>
      <LazyComponent {...props} />
    </Suspense>
  );
}

// Named exports helper
export function lazyLoadNamed(
  importFunc: () => Promise<Record<string, ComponentType<any>>>,
  componentName: string
) {
  const LazyComponent = lazy(async () => {
    const module = await importFunc();
    return { default: module[componentName] };
  });

  return (props: any) => (
    <Suspense fallback={<PageLoader />}>
      <LazyComponent {...props} />
    </Suspense>
  );
}

// Preload component helper
export function preloadComponent(
  importFunc: () => Promise<any>
) {
  return importFunc();
}

// Retry mechanism for failed lazy loads
export function lazyLoadWithRetry<T extends ComponentType<any>>(
  importFunc: () => Promise<{ default: T }>,
  retries = 3,
  delay = 1000
) {
  return lazyLoad(() =>
    new Promise<{ default: T }>((resolve, reject) => {
      const attemptImport = (attemptsLeft: number) => {
        importFunc()
          .then(resolve)
          .catch((error) => {
            if (attemptsLeft <= 0) {
              reject(error);
            } else {
              setTimeout(() => attemptImport(attemptsLeft - 1), delay);
            }
          });
      };
      attemptImport(retries);
    })
  );
}
