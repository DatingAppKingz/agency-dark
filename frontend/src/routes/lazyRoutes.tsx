import { lazyLoad, lazyLoadWithRetry, preloadComponent } from '@/utils/lazyLoad';

// Auth Pages
export const LoginPage = lazyLoad(() => import('@/pages/auth/LoginPage'));
export const RegisterPage = lazyLoad(() => import('@/pages/auth/RegisterPage'));
export const ForgotPasswordPage = lazyLoad(() => import('@/pages/auth/ForgotPasswordPage'));
export const ResetPasswordPage = lazyLoad(() => import('@/pages/auth/ResetPasswordPage'));

// Dashboard Pages (with retry for critical pages)
export const DashboardPage = lazyLoadWithRetry(() => import('@/pages/dashboard/DashboardPage'));

// User Management
export const UsersPage = lazyLoad(() => import('@/pages/users/UsersPage'));
export const UserProfilePage = lazyLoad(() => import('@/pages/profile/UserProfilePage'));

// Model Management
export const ModelsPage = lazyLoad(() => import('@/pages/models/ModelsPage'));
export const ModelDetailsPage = lazyLoad(() => import('@/pages/models/ModelDetailsPage'));

// Chat
export const ChatPage = lazyLoadWithRetry(() => import('@/pages/chat/ChatPage'));

// Analytics
export const AnalyticsPage = lazyLoad(() => import('@/pages/analytics/AnalyticsPage'));

// Financial
export const FinancialPage = lazyLoad(() => import('@/pages/financial/FinancialPage'));
export const TransactionsPage = lazyLoad(() => import('@/pages/financial/TransactionsPage'));
export const PayoutsPage = lazyLoad(() => import('@/pages/financial/PayoutsPage'));

// Settings
export const SettingsPage = lazyLoad(() => import('@/pages/settings/SettingsPage'));
export const WhiteLabelPage = lazyLoad(() => import('@/pages/settings/WhiteLabelPage'));
export const LanguageSettings = lazyLoad(() => import('@/pages/settings/LanguageSettings'));

// Agency
export const AgencySettingsPage = lazyLoad(() => import('@/pages/agency/AgencySettingsPage'));

// Error Pages
export const NotFoundPage = lazyLoad(() => import('@/pages/errors/NotFoundPage'));
export const ServerErrorPage = lazyLoad(() => import('@/pages/errors/ServerErrorPage'));

// Preload critical routes
export const preloadCriticalRoutes = () => {
  // Preload dashboard immediately after login
  preloadComponent(() => import('@/pages/dashboard/DashboardPage'));
  
  // Preload chat page as it's frequently used
  setTimeout(() => {
    preloadComponent(() => import('@/pages/chat/ChatPage'));
  }, 2000);
};

// Route-based code splitting configuration
export const routeConfig = {
  auth: {
    login: '/login',
    register: '/register',
    forgotPassword: '/forgot-password',
    resetPassword: '/reset-password/:token',
  },
  dashboard: {
    home: '/dashboard',
  },
  users: {
    list: '/users',
    profile: '/profile/:id?',
  },
  models: {
    list: '/models',
    details: '/models/:id',
  },
  chat: {
    main: '/chat',
    conversation: '/chat/:conversationId',
  },
  analytics: {
    main: '/analytics',
  },
  financial: {
    overview: '/financial',
    transactions: '/financial/transactions',
    payouts: '/financial/payouts',
  },
  settings: {
    main: '/settings',
    whiteLabel: '/settings/white-label',
    language: '/settings/language',
  },
  agency: {
    settings: '/agency/settings',
  },
  errors: {
    notFound: '/404',
    serverError: '/500',
  },
};
