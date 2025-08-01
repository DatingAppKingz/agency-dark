import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { api } from '../services/api';
import { SUPPORTED_LANGUAGES } from './index';

interface LanguagePreferences {
  primaryLanguage: string;
  fallbackLanguages?: string[];
  autoTranslate: boolean;
  showOriginal: boolean;
  dateFormat?: string;
  timeFormat?: string;
  numberFormat?: string;
  currency: string;
  timezone: string;
}

interface LanguageContextType {
  currentLanguage: string;
  languages: typeof SUPPORTED_LANGUAGES;
  preferences: LanguagePreferences | null;
  changeLanguage: (language: string) => Promise<void>;
  updatePreferences: (preferences: Partial<LanguagePreferences>) => Promise<void>;
  isRTL: boolean;
}

const LanguageContext = createContext<LanguageContextType | undefined>(undefined);

export const useLanguage = () => {
  const context = useContext(LanguageContext);
  if (!context) {
    throw new Error('useLanguage must be used within a LanguageProvider');
  }
  return context;
};

interface LanguageProviderProps {
  children: ReactNode;
}

export const LanguageProvider: React.FC<LanguageProviderProps> = ({ children }) => {
  const { i18n } = useTranslation();
  const [preferences, setPreferences] = useState<LanguagePreferences | null>(null);
  const [loading, setLoading] = useState(true);

  // Fetch user language preferences
  useEffect(() => {
    const fetchPreferences = async () => {
      try {
        const response = await api.get('/translations/preferences');
        setPreferences(response.data);
        
        // Set the language if different from current
        if (response.data.primaryLanguage !== i18n.language) {
          await i18n.changeLanguage(response.data.primaryLanguage);
        }
      } catch (error) {
        console.error('Failed to fetch language preferences:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchPreferences();
  }, [i18n]);

  const changeLanguage = async (language: string) => {
    try {
      // Change i18n language
      await i18n.changeLanguage(language);
      
      // Update user preferences
      await updatePreferences({ primaryLanguage: language });
      
      // Update HTML dir attribute for RTL languages
      document.documentElement.dir = SUPPORTED_LANGUAGES[language]?.rtl ? 'rtl' : 'ltr';
      
      // Store in localStorage
      localStorage.setItem('agencydark_language', language);
    } catch (error) {
      console.error('Failed to change language:', error);
      throw error;
    }
  };

  const updatePreferences = async (newPreferences: Partial<LanguagePreferences>) => {
    try {
      const response = await api.patch('/translations/preferences', newPreferences);
      setPreferences(response.data);
      return response.data;
    } catch (error) {
      console.error('Failed to update language preferences:', error);
      throw error;
    }
  };

  const value: LanguageContextType = {
    currentLanguage: i18n.language,
    languages: SUPPORTED_LANGUAGES,
    preferences,
    changeLanguage,
    updatePreferences,
    isRTL: SUPPORTED_LANGUAGES[i18n.language]?.rtl || false,
  };

  if (loading) {
    return <div>Loading translations...</div>;
  }

  return (
    <LanguageContext.Provider value={value}>
      {children}
    </LanguageContext.Provider>
  );
};