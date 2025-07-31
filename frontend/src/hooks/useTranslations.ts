import { useTranslation } from 'react-i18next';
import { useCallback } from 'react';

export const useTranslations = () => {
  const { t, i18n } = useTranslation();

  // Format date according to current locale
  const formatDate = useCallback((date: Date | string, options?: Intl.DateTimeFormatOptions) => {
    const dateObj = typeof date === 'string' ? new Date(date) : date;
    return new Intl.DateTimeFormat(i18n.language, options).format(dateObj);
  }, [i18n.language]);

  // Format number according to current locale
  const formatNumber = useCallback((number: number, options?: Intl.NumberFormatOptions) => {
    return new Intl.NumberFormat(i18n.language, options).format(number);
  }, [i18n.language]);

  // Format currency according to current locale
  const formatCurrency = useCallback((amount: number, currency: string = 'USD') => {
    return new Intl.NumberFormat(i18n.language, {
      style: 'currency',
      currency,
    }).format(amount);
  }, [i18n.language]);

  // Format relative time
  const formatRelativeTime = useCallback((date: Date | string) => {
    const dateObj = typeof date === 'string' ? new Date(date) : date;
    const now = new Date();
    const diffInSeconds = Math.floor((now.getTime() - dateObj.getTime()) / 1000);
    
    const rtf = new Intl.RelativeTimeFormat(i18n.language, { numeric: 'auto' });
    
    if (diffInSeconds < 60) {
      return rtf.format(-diffInSeconds, 'second');
    } else if (diffInSeconds < 3600) {
      return rtf.format(-Math.floor(diffInSeconds / 60), 'minute');
    } else if (diffInSeconds < 86400) {
      return rtf.format(-Math.floor(diffInSeconds / 3600), 'hour');
    } else if (diffInSeconds < 2592000) {
      return rtf.format(-Math.floor(diffInSeconds / 86400), 'day');
    } else if (diffInSeconds < 31536000) {
      return rtf.format(-Math.floor(diffInSeconds / 2592000), 'month');
    } else {
      return rtf.format(-Math.floor(diffInSeconds / 31536000), 'year');
    }
  }, [i18n.language]);

  // Get plural form
  const pluralize = useCallback((count: number, key: string, options?: Record<string, unknown>) => {
    return t(key, { count, ...options });
  }, [t]);

  // Check if language is RTL
  const isRTL = i18n.dir() === 'rtl' || ['ar', 'he', 'fa', 'ur'].includes(i18n.language);

  return {
    t,
    i18n,
    formatDate,
    formatNumber,
    formatCurrency,
    formatRelativeTime,
    pluralize,
    isRTL,
    currentLanguage: i18n.language,
    changeLanguage: i18n.changeLanguage.bind(i18n),
  };
};
