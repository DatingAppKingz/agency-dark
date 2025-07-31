import { useRouteError } from 'react-router-dom';
import { ErrorFallback } from '@/components/error/ErrorFallback';

export const ErrorBoundary = () => { 
  const error = useRouteError() as Error;

  // Use the improved error fallback component
  return (
    <ErrorFallback
      error={error }
      resetError={() => window.location.reload()}
      showDetails={process.env.NODE_ENV === 'development'}
    />
  );
};
