import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Globe, Check, ChevronDown } from 'lucide-react';
import { useLanguage } from '../i18n/LanguageProvider';
import { cn } from '../lib/utils';

export const LanguageSwitcher: React.FC<{ className?: string }> = ({ className }) => {
  const { t } = useTranslation();
  const { currentLanguage, languages, changeLanguage } = useLanguage();
  const [isOpen, setIsOpen] = useState(false);
  const [isChanging, setIsChanging] = useState(false);

  const handleLanguageChange = async (langCode: string) => {
    if (langCode === currentLanguage) {
      setIsOpen(false);
      return;
    }

    setIsChanging(true);
    try {
      await changeLanguage(langCode);
      setIsOpen(false);
    } catch (error) {
      console.error('Failed to change language:', error);
    } finally {
      setIsChanging(false);
    }
  };

  const currentLangInfo = languages[currentLanguage];

  return (
    <div className={cn("relative", className)}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        disabled={isChanging}
        className={cn(
          "flex items-center gap-2 px-3 py-2 text-sm font-medium rounded-md",
          "bg-gray-800 text-gray-300 hover:bg-gray-700 hover:text-white",
          "transition-colors duration-200",
          "focus:outline-none focus:ring-2 focus:ring-primary-500",
          isChanging && "opacity-50 cursor-not-allowed"
        )}
      >
        <Globe className="w-4 h-4" />
        <span>{currentLangInfo?.nativeName || currentLanguage}</span>
        <ChevronDown className={cn(
          "w-4 h-4 transition-transform",
          isOpen && "rotate-180"
        )} />
      </button>

      {isOpen && (
        <>
          <div
            className="fixed inset-0 z-10"
            onClick={() => setIsOpen(false)}
          />
          <div className="absolute right-0 z-20 mt-2 py-2 w-56 bg-gray-800 rounded-md shadow-xl border border-gray-700">
            <div className="px-4 py-2 text-xs font-semibold text-gray-400 uppercase tracking-wide">
              {t('common.select_language')}
            </div>
            <div className="mt-1">
              {Object.entries(languages).map(([code, info]) => (
                <button
                  key={code}
                  onClick={() => handleLanguageChange(code)}
                  className={cn(
                    "w-full flex items-center justify-between px-4 py-2 text-sm",
                    "hover:bg-gray-700 transition-colors duration-150",
                    code === currentLanguage
                      ? "text-primary-400 bg-gray-700/50"
                      : "text-gray-300"
                  )}
                >
                  <div className="flex items-center gap-3">
                    <span className="text-lg">{info.nativeName}</span>
                    <span className="text-xs text-gray-500">{info.name}</span>
                  </div>
                  {code === currentLanguage && (
                    <Check className="w-4 h-4 text-primary-400" />
                  )}
                </button>
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  );
};