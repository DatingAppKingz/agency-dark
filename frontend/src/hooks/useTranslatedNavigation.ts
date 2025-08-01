import { useTranslation } from 'react-i18next';
import { useMemo } from 'react';
import {
  Dashboard,
  People,
  Message,
  Analytics,
  PermMedia,
  AttachMoney,
  Settings,
  Notifications,
  Search,
  Help,
} from '@mui/icons-material';

export interface NavigationItem {
  title: string;
  path: string;
  icon: React.ComponentType;
  badge?: number;
}

export const useTranslatedNavigation = () => {
  const { t } = useTranslation();

  const navigationItems = useMemo<NavigationItem[]>(() => [
    {
      title: t('nav.dashboard'),
      path: '/',
      icon: Dashboard,
    },
    {
      title: t('nav.models'),
      path: '/models',
      icon: People,
    },
    {
      title: t('nav.messages'),
      path: '/messages',
      icon: Message,
    },
    {
      title: t('nav.analytics'),
      path: '/analytics',
      icon: Analytics,
    },
    {
      title: t('nav.media'),
      path: '/media',
      icon: PermMedia,
    },
    {
      title: t('nav.transactions'),
      path: '/transactions',
      icon: AttachMoney,
    },
    {
      title: t('nav.settings'),
      path: '/settings',
      icon: Settings,
    },
    {
      title: t('nav.notifications'),
      path: '/notifications',
      icon: Notifications,
    },
    {
      title: t('nav.search'),
      path: '/search',
      icon: Search,
    },
    {
      title: t('nav.help'),
      path: '/help',
      icon: Help,
    },
  ], [t]);

  return navigationItems;
};