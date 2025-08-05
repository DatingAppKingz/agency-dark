import { ThemeProvider } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { RouterProvider } from 'react-router-dom';
import { HelmetProvider } from 'react-helmet-async';
import { router } from './router/index';
import theme from './theme';
import { Toaster } from './components/common/Toaster';
import { PushNotificationProvider } from './providers/PushNotificationProvider';
import { LanguageProvider } from './i18n/LanguageProvider';
import { PerformanceProvider } from './providers/PerformanceProvider';
import { RealtimeProvider } from './providers/RealtimeProvider';
import { ErrorNotificationProvider } from './providers/ErrorNotificationProvider';
import { ErrorBoundary, AsyncErrorBoundary } from './components/ErrorBoundary';
import './i18n';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 3,
      staleTime: 5 * 60 * 1000, // 5 minutes
    },
  },
});

function App() {
  console.log('App component rendering...')
  
  try {
    return (
      <HelmetProvider>
        <ThemeProvider theme={theme}>
          <CssBaseline />
          <QueryClientProvider client={queryClient}>
            <RouterProvider router={router} />
            <Toaster />
          </QueryClientProvider>
        </ThemeProvider>
      </HelmetProvider>
    );
  } catch (error) {
    console.error('Error in App render:', error);
    return <div>Error in App: {String(error)}</div>;
  }
}

export default App;
