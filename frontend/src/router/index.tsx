import { createBrowserRouter, Navigate } from 'react-router-dom';
import { lazy, Suspense } from 'react';
import { RootLayout } from '@/layouts/RootLayout';
import { AuthLayout } from '@/layouts/AuthLayout';
import { DashboardLayout } from '@/layouts/DashboardLayout';
import { ProtectedRoute } from '@/components/auth/ProtectedRoute';
import { RoleProtectedRoute } from '@/components/auth/RoleProtectedRoute';
import { UserRole } from '@/types/auth';
import { PageLoader } from '@/components/common/PageLoader';
import { ErrorBoundary } from '@/components/common/ErrorBoundary';

// Lazy load pages for code splitting
const LoginPage = lazy(() => import('@/pages/auth/LoginPage'));
const RegisterPage = lazy(() => import('@/pages/auth/RegisterPage'));
const ForgotPasswordPage = lazy(() => import('@/pages/auth/ForgotPasswordPage'));
const OAuthCallback = lazy(() => import('@/pages/auth/OAuthCallback'));
const DashboardPage = lazy(() => import('@/pages/dashboard/DashboardPage'));
const UsersPage = lazy(() => import('@/pages/users/UsersPage'));
const ModelOverviewPage = lazy(() => import('@/pages/models/ModelOverviewPage'));
const ModelDetailsPage = lazy(() => import('@/pages/models/ModelDetailsPage'));
const ChatPage = lazy(() => import('@/pages/chat/ChatPage'));
const AnalyticsPage = lazy(() => import('@/pages/analytics/AnalyticsPage'));
const FinancialPage = lazy(() => import('@/pages/financial/FinancialPage'));
const SettingsPage = lazy(() => import('@/pages/settings/SettingsPage'));
const ApiKeysPage = lazy(() => import('@/pages/settings/ApiKeysPage'));
const WebhooksPage = lazy(() => import('@/pages/settings/WebhooksPage'));
const BulkOperationsPage = lazy(() => import('@/pages/bulk/BulkOperationsPage'));
const AdminUsersPage = lazy(() => import('@/pages/admin/AdminUsersPage'));
const SyncDashboardPage = lazy(() => import('@/pages/sync/SyncDashboardPage'));
const UserProfilePage = lazy(() => import('@/pages/profile/UserProfilePage'));
const ReportsPage = lazy(() => import('@/pages/reports/ReportsPage'));
const ReportBuilderPage = lazy(() => import('@/pages/reports/ReportBuilderPage'));
const ReportViewerPage = lazy(() => import('@/pages/reports/ReportViewerPage'));
const AgencySettingsPage = lazy(() => import('@/pages/agency/AgencySettingsPage'));
const AgenciesListPage = lazy(() => import('@/pages/agencies/AgenciesListPage'));
const NotFoundPage = lazy(() => import('@/pages/NotFoundPage'));
const ApiTestPage = lazy(() => import('@/pages/ApiTestPage'));
const DebugAnalytics = lazy(() => import('@/pages/DebugAnalytics'));
const DashboardDebug = lazy(() => import('@/pages/dashboard/DashboardDebug'));
const MLInsightsPage = lazy(() => import('@/pages/ml/MLInsightsPage'));
const PendingApprovalsPage = lazy(() => import('@/pages/models/PendingApprovalsPage'));
const ModelOnboardingPage = lazy(() => import('@/pages/models/ModelOnboardingPage'));
const PayoutsPage = lazy(() => import('@/pages/financial/PayoutsPage'));
const TransactionsPage = lazy(() => import('@/pages/financial/TransactionsPage'));

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
        path: 'callback',
        element: (
          <LazyPage>
            <OAuthCallback />
          </LazyPage>
        ),
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
              <RoleProtectedRoute allowedRoles={[UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN]}>
                <LazyPage>
                  <UsersPage />
                </LazyPage>
              </RoleProtectedRoute>
            ),
          },
          {
            path: 'models',
            element: (
              <RoleProtectedRoute allowedRoles={[UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN, UserRole.MODEL]}>
                <LazyPage>
                  <ModelOverviewPage />
                </LazyPage>
              </RoleProtectedRoute>
            ),
          },
          {
            path: 'models/:modelId',
            element: (
              <LazyPage>
                <ModelDetailsPage />
              </LazyPage>
            ),
          },
          {
            path: 'models/pending',
            element: (
              <LazyPage>
                <PendingApprovalsPage />
              </LazyPage>
            ),
          },
          {
            path: 'models/onboarding',
            element: (
              <LazyPage>
                <ModelOnboardingPage />
              </LazyPage>
            ),
          },
          {
            path: 'chat',
            element: (
              <RoleProtectedRoute allowedRoles={[UserRole.MODEL, UserRole.CHATTER]}>
                <LazyPage>
                  <ChatPage />
                </LazyPage>
              </RoleProtectedRoute>
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
            path: 'ml-insights',
            element: (
              <LazyPage>
                <MLInsightsPage />
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
            path: 'financial/payouts',
            element: (
              <LazyPage>
                <PayoutsPage />
              </LazyPage>
            ),
          },
          {
            path: 'financial/transactions',
            element: (
              <LazyPage>
                <TransactionsPage />
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
              <RoleProtectedRoute allowedRoles={[UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER]}>
                <LazyPage>
                  <ApiKeysPage />
                </LazyPage>
              </RoleProtectedRoute>
            ),
          },
          {
            path: 'settings/webhooks',
            element: (
              <RoleProtectedRoute allowedRoles={[UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER]}>
                <LazyPage>
                  <WebhooksPage />
                </LazyPage>
              </RoleProtectedRoute>
            ),
          },
          {
            path: 'bulk-operations',
            element: (
              <RoleProtectedRoute allowedRoles={[UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN]}>
                <LazyPage>
                  <BulkOperationsPage />
                </LazyPage>
              </RoleProtectedRoute>
            ),
          },
          {
            path: 'admin/users',
            element: (
              <RoleProtectedRoute allowedRoles={[UserRole.SUPER_ADMIN]}>
                <LazyPage>
                  <AdminUsersPage />
                </LazyPage>
              </RoleProtectedRoute>
            ),
          },
          {
            path: 'sync',
            element: (
              <RoleProtectedRoute allowedRoles={[UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN]}>
                <LazyPage>
                  <SyncDashboardPage />
                </LazyPage>
              </RoleProtectedRoute>
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
            path: 'agencies',
            element: (
              <RoleProtectedRoute allowedRoles={[UserRole.SUPER_ADMIN]}>
                <LazyPage>
                  <AgenciesListPage />
                </LazyPage>
              </RoleProtectedRoute>
            ),
          },
          {
            path: 'agency',
            element: (
              <RoleProtectedRoute allowedRoles={[UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN]}>
                <LazyPage>
                  <AgencySettingsPage />
                </LazyPage>
              </RoleProtectedRoute>
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
