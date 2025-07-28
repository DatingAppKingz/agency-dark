/**
 * AgencyDark Mobile Application
 * 
 * Main entry point for the React Native app
 */
import React, { useEffect } from 'react';
import { StatusBar, useColorScheme } from 'react-native';
import { NavigationContainer } from '@react-navigation/native';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Provider as PaperProvider } from 'react-native-paper';
import { GestureHandlerRootView } from 'react-native-gesture-handler';
import NetInfo from '@react-native-community/netinfo';
import { NetworkProvider } from 'react-native-offline';

import { AuthProvider } from '@/contexts/AuthContext';
import { ThemeProvider } from '@/contexts/ThemeContext';
import { NotificationProvider } from '@/contexts/NotificationContext';
import { SyncProvider } from '@/contexts/SyncContext';
import RootNavigator from '@/navigation/RootNavigator';
import { setupNotifications } from '@/services/notifications';
import { initializeBackgroundSync } from '@/services/backgroundSync';
import { darkTheme, lightTheme } from '@/constants/theme';
import ErrorBoundary from '@/components/ErrorBoundary';
import SplashScreen from '@/screens/SplashScreen';
import { useAppState } from '@/hooks/useAppState';
import { useAuth } from '@/hooks/useAuth';

// Create a client
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 2,
      staleTime: 5 * 60 * 1000, // 5 minutes
      gcTime: 10 * 60 * 1000, // 10 minutes
    },
  },
});

function App(): React.JSX.Element {
  const isDarkMode = useColorScheme() === 'dark';
  const { isInitialized, initialize } = useAppState();

  useEffect(() => {
    // Initialize app services
    const initializeApp = async () => {
      try {
        // Setup push notifications
        await setupNotifications();

        // Initialize background sync
        await initializeBackgroundSync();

        // Setup network monitoring
        const unsubscribe = NetInfo.addEventListener(state => {
          console.log('Network state changed:', state);
        });

        // Initialize app state
        await initialize();

        return () => {
          unsubscribe();
        };
      } catch (error) {
        console.error('Failed to initialize app:', error);
      }
    };

    initializeApp();
  }, [initialize]);

  if (!isInitialized) {
    return <SplashScreen />;
  }

  return (
    <ErrorBoundary>
      <GestureHandlerRootView style={{ flex: 1 }}>
        <QueryClientProvider client={queryClient}>
          <NetworkProvider>
            <SafeAreaProvider>
              <ThemeProvider>
                <PaperProvider theme={isDarkMode ? darkTheme : lightTheme}>
                  <AuthProvider>
                    <NotificationProvider>
                      <SyncProvider>
                        <NavigationContainer>
                          <StatusBar
                            barStyle={isDarkMode ? 'light-content' : 'dark-content'}
                            backgroundColor={isDarkMode ? '#000000' : '#FFFFFF'}
                          />
                          <RootNavigator />
                        </NavigationContainer>
                      </SyncProvider>
                    </NotificationProvider>
                  </AuthProvider>
                </PaperProvider>
              </ThemeProvider>
            </SafeAreaProvider>
          </NetworkProvider>
        </QueryClientProvider>
      </GestureHandlerRootView>
    </ErrorBoundary>
  );
}

export default App;