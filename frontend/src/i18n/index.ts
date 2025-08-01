import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import LanguageDetector from 'i18next-browser-languagedetector';
import Backend from 'i18next-http-backend';
import { format as formatDate, formatDistance, formatRelative } from 'date-fns';
import { enUS, es, fr, de, it, pt, ar, hi, zh, ja } from 'date-fns/locale';

// Supported languages
export const SUPPORTED_LANGUAGES = {
  en: { name: 'English', nativeName: 'English', locale: enUS },
  es: { name: 'Spanish', nativeName: 'Español', locale: es },
  fr: { name: 'French', nativeName: 'Français', locale: fr },
  de: { name: 'German', nativeName: 'Deutsch', locale: de },
  it: { name: 'Italian', nativeName: 'Italiano', locale: it },
  pt: { name: 'Portuguese', nativeName: 'Português', locale: pt },
  ar: { name: 'Arabic', nativeName: 'العربية', locale: ar, rtl: true },
  hi: { name: 'Hindi', nativeName: 'हिन्दी', locale: hi },
  zh: { name: 'Chinese', nativeName: '中文', locale: zh },
  ja: { name: 'Japanese', nativeName: '日本語', locale: ja },
};

// Date formatting helper
export const formatDateLocalized = (date: Date | string, format: string, language: string) => {
  const dateObj = typeof date === 'string' ? new Date(date) : date;
  const locale = SUPPORTED_LANGUAGES[language]?.locale || enUS;
  return formatDate(dateObj, format, { locale });
};

// Relative time formatting
export const formatDistanceLocalized = (date: Date | string, baseDate: Date, language: string) => {
  const dateObj = typeof date === 'string' ? new Date(date) : date;
  const locale = SUPPORTED_LANGUAGES[language]?.locale || enUS;
  return formatDistance(dateObj, baseDate, { locale, addSuffix: true });
};

// Initialize i18n
i18n
  .use(Backend)
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    fallbackLng: 'en',
    debug: process.env.NODE_ENV === 'development',
    
    interpolation: {
      escapeValue: false, // React already escapes values
      format: (value, format, lng) => {
        if (format === 'number') {
          return new Intl.NumberFormat(lng).format(value);
        }
        if (format === 'currency') {
          return new Intl.NumberFormat(lng, {
            style: 'currency',
            currency: 'USD', // This should be dynamic based on user preferences
          }).format(value);
        }
        if (format === 'percent') {
          return new Intl.NumberFormat(lng, {
            style: 'percent',
            minimumFractionDigits: 0,
            maximumFractionDigits: 2,
          }).format(value / 100);
        }
        if (format?.startsWith('date:')) {
          const dateFormat = format.substring(5);
          return formatDateLocalized(value, dateFormat, lng);
        }
        return value;
      },
    },
    
    backend: {
      loadPath: '/api/v1/translations/export/{{lng}}?format=json',
      allowMultiLoading: false,
      crossDomain: false,
      withCredentials: true,
    },
    
    detection: {
      order: ['localStorage', 'cookie', 'navigator', 'htmlTag'],
      caches: ['localStorage', 'cookie'],
      lookupLocalStorage: 'agencydark_language',
      lookupCookie: 'agencydark_language',
    },
    
    react: {
      useSuspense: false,
    },
    
    ns: ['common', 'auth', 'models', 'messages', 'dashboard', 'settings', 'notifications'],
    defaultNS: 'common',
    
    keySeparator: '.',
    nsSeparator: ':',
    
    saveMissing: true,
    saveMissingTo: 'current',
    missingKeyHandler: (lngs, ns, key, fallbackValue) => {
      if (process.env.NODE_ENV === 'development') {
        console.warn(`Missing translation: ${ns}:${key}`);
        // Send missing translation to backend
        fetch('/api/v1/translations/requests', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            key: `${ns}.${key}`,
            source_language: 'en',
            target_language: lngs[0],
            source_text: fallbackValue || key,
            priority: 'normal',
          }),
        }).catch(err => console.error('Failed to report missing translation:', err));
      }
    },
  });

export default i18n;