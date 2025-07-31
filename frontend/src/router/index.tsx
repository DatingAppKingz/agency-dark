import { createBrowserRouter, Navigate } from 'react-router-dom';
import { lazy, Suspense } from 'react';
import { RootLayout } from '@/layouts/RootLayout';
import { AuthLayout } from '@/layouts/AuthLayout';
import { DashboardLayout } from '@/layouts/DashboardLayout';
import { ProtectedRoute } from '@/components/auth/ProtectedRoute';
import { PageLoader } from '@/components/common/PageLoader';
import { ErrorBoundary } from '@/components/common/ErrorBoundary';

// Lazy load pages for code splitting
const LoginPage = lazy(() => import('@/pages/auth/LoginPage'));
const RegisterPage = lazy(() => import('@/pages/auth/RegisterPage'));
const ForgotPasswordPage = lazy(() => import('@/pages/auth/ForgotPasswordPage'));
const DashboardPage = lazy(() => import('@/pages/dashboard/DashboardPage'));
const UsersPage = lazy(() => import('@/pages/users/UsersPage'));
const ModelsPage = lazy(() => import('@/pages/models/ModelsPage'));
const ModelDetailPage = lazy(() => import('@/pages/models/ModelDetailPage'));
const ChatPage = lazy(() => import('@/pages/chat/ChatPage'));
const AnalyticsPage = lazy(() => import('@/pages/analytics/AnalyticsPage'));
const FinancialPage = lazy(() => import('@/pages/financial/FinancialPage'));
const SettingsPage = lazy(() => import('@/pages/settings/SettingsPage'));
const ApiKeysPage = lazy(() => import('@/pages/settings/ApiKeysPage'));
const WebhooksPage = lazy(() => import('@/pages/settings/WebhooksPage'));
const BulkOperationsPage = lazy(() => import('@/pages/bulk/BulkOperationsPage'));
const SyncDashboardPage = lazy(() => import('@/pages/sync/SyncDashboardPage'));
const UserProfilePage = lazy(() => import('@/pages/profile/UserProfilePage'));
const ReportsPage = lazy(() => import('@/pages/reports/ReportsPage'));
const ReportBuilderPage = lazy(() => import('@/pages/reports/ReportBuilderPage'));
const ReportViewerPage = lazy(() => import('@/pages/reports/ReportViewerPage'));
const AgencySettingsPage = lazy(() => import('@/pages/agency/AgencySettingsPage'));
const NotFoundPage = lazy(() => import('@/pages/NotFoundPage'));
const ApiTestPage = lazy(() => import('@/pages/ApiTestPage'));
const DebugAnalytics = lazy(() => import('@/pages/DebugAnalytics'));
const DashboardDebug = lazy(() => import('@/pages/dashboard/DashboardDebug'));

// Wrapper for lazy loaded components
const LazyPage = ({ children }: { children: React.ReactNode }) => (
  <Suspense fallback={<PageLoader />}>{children}</Suspense>
);

export const router = createBrowserRouter([
  {
    path: '/',
    element: <RootLayout />,
    errorElement: <ErrorBoundary />,
    children: [
      {
        index: true,
        element: <Navigate to="/dashboard" replace />,
      },
      {
        path: 'auth',
        element: <AuthLayout />,
        children: [
          {
            path: 'login',
            element: (
              <LazyPage>
                <LoginPage />
              </LazyPage>
            ),
          },
          {
            path: 'register',
            element: (
              <LazyPage>
                <RegisterPage />
              </LazyPage>
            ),
          },
          {
            path: 'forgot-password',
            element: (
              <LazyPage>
                <ForgotPasswordPage />
              </LazyPage>
            ),
          },
        ],
      },
      {
        path: 'dashboard',
        element: (
          <ProtectedRoute>
            <DashboardLayout />
          </ProtectedRoute>
        ),
        children: [
          {
            index: true,
            element: (
              <LazyPage>
                <DashboardPage />
              </LazyPage>
            ),
          },
          {
            path: 'users',
            element: (
              <LazyPage>
                <UsersPage />
              </LazyPage>
            ),
          },
          {
            path: 'models',
            element: (
              <LazyPage>
                <ModelsPage />
              </LazyPage>
            ),
          },
          {
            path: 'models/:modelId',
            element: (
              <LazyPage>
                <ModelDetailPage />
              </LazyPage>
            ),
          },
          {
            path: 'chat',
            element: (
              <LazyPage>
                <ChatPage />
              </LazyPage>
            ),
          },
          {
            path: 'analytics',
            element: (
              <LazyPage>
                <AnalyticsPage />
              </LazyPage>
            ),
          },
          {
            path: 'financial',
            element: (
              <LazyPage>
                <FinancialPage />
              </LazyPage>
            ),
          },
          {
            path: 'settings',
            element: (
              <LazyPage>
                <SettingsPage />
              </LazyPage>
            ),
          },
          {
            path: 'settings/api-keys',
            element: (
              <LazyPage>
                <ApiKeysPage />
              </LazyPage>
            ),
          },
          {
            path: 'settings/webhooks',
            element: (
              <LazyPage>
                <WebhooksPage />
              </LazyPage>
            ),
          },
          {
            path: 'bulk-operations',
            element: (
              <LazyPage>
                <BulkOperationsPage />
              </LazyPage>
            ),
          },
          {
            path: 'sync',
            element: (
              <LazyPage>
                <SyncDashboardPage />
              </LazyPage>
            ),
          },
          {
            path: 'reports',
            element: (
              <LazyPage>
                <ReportsPage />
              </LazyPage>
            ),
          },
          {
            path: 'reports/builder',
            element: (
              <LazyPage>
                <ReportBuilderPage />
              </LazyPage>
            ),
          },
          {
            path: 'reports/builder/:templateId',
            element: (
              <LazyPage>
                <ReportBuilderPage />
              </LazyPage>
            ),
          },
          {
            path: 'reports/view/:templateId',
            element: (
              <LazyPage>
                <ReportViewerPage />
              </LazyPage>
            ),
          },
          {
            path: 'profile',
            element: (
              <LazyPage>
                <UserProfilePage />
              </LazyPage>
            ),
          },
          {
            path: 'agency',
            element: (
              <LazyPage>
                <AgencySettingsPage />
              </LazyPage>
            ),
          },
          {
            path: 'api-test',
            element: (
              <LazyPage>
                <ApiTestPage />
              </LazyPage>
            ),
          },
          {
            path: 'debug-analytics',
            element: (
              <LazyPage>
                <DebugAnalytics />
              </LazyPage>
            ),
          },
          {
            path: 'dashboard-debug',
            element: (
              <LazyPage>
                <DashboardDebug />
              </LazyPage>
            ),
          },
        ],
      },
      {
        path: '*',
        element: (
          <LazyPage>
            <NotFoundPage />
          </LazyPage>
        ),
      },
    ],
  },
]);
