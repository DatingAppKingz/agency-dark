import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { 
  Languages, 
  Plus, 
  Edit2, 
  Trash2, 
  Check, 
  X, 
  Upload, 
  Download,
  Globe,
  AlertCircle,
  Search,
  Filter
} from 'lucide-react';
import { api } from '../services/api';
import { useLanguage } from '../i18n/LanguageProvider';
import { cn } from '../lib/utils';

interface Translation {
  id: string;
  key: string;
  language: string;
  value: string;
  context?: string;
  isVerified: boolean;
  verifiedBy?: string;
  createdAt: string;
  updatedAt: string;
}

interface TranslationStats {
  [language: string]: {
    total: number;
    verified: number;
    unverified: number;
    percentage: number;
  };
}

export const TranslationManager: React.FC = () => {
  const { t } = useTranslation();
  const { languages } = useLanguage();
  const [translations, setTranslations] = useState<Translation[]>([]);
  const [stats, setStats] = useState<TranslationStats>({});
  const [loading, setLoading] = useState(true);
  const [selectedLanguage, setSelectedLanguage] = useState('en');
  const [searchTerm, setSearchTerm] = useState('');
  const [showUnverifiedOnly, setShowUnverifiedOnly] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editValue, setEditValue] = useState('');
  const [isCreating, setIsCreating] = useState(false);
  const [newTranslation, setNewTranslation] = useState({
    key: '',
    value: '',
    context: '',
  });

  // Fetch translations
  const fetchTranslations = async () => {
    try {
      setLoading(true);
      const params = new URLSearchParams({
        language: selectedLanguage,
        ...(searchTerm && { search: searchTerm }),
        ...(showUnverifiedOnly && { verified: 'false' }),
      });
      
      const response = await api.get(`/translations?${params}`);
      setTranslations(response.data);
    } catch (error) {
      console.error('Failed to fetch translations:', error);
    } finally {
      setLoading(false);
    }
  };

  // Fetch translation stats
  const fetchStats = async () => {
    try {
      const response = await api.get('/translations/stats');
      setStats(response.data.stats);
    } catch (error) {
      console.error('Failed to fetch translation stats:', error);
    }
  };

  useEffect(() => {
    fetchTranslations();
    fetchStats();
  }, [selectedLanguage, searchTerm, showUnverifiedOnly]);

  // Create translation
  const handleCreate = async () => {
    try {
      await api.post('/translations', {
        ...newTranslation,
        language: selectedLanguage,
        isVerified: true,
      });
      
      setIsCreating(false);
      setNewTranslation({ key: '', value: '', context: '' });
      fetchTranslations();
      fetchStats();
    } catch (error) {
      console.error('Failed to create translation:', error);
    }
  };

  // Update translation
  const handleUpdate = async (id: string) => {
    try {
      await api.patch(`/translations/${id}`, {
        value: editValue,
        isVerified: true,
      });
      
      setEditingId(null);
      setEditValue('');
      fetchTranslations();
      fetchStats();
    } catch (error) {
      console.error('Failed to update translation:', error);
    }
  };

  // Delete translation
  const handleDelete = async (id: string) => {
    if (!confirm(t('translations.confirm_delete'))) return;
    
    try {
      await api.delete(`/translations/${id}`);
      fetchTranslations();
      fetchStats();
    } catch (error) {
      console.error('Failed to delete translation:', error);
    }
  };

  // Export translations
  const handleExport = async () => {
    try {
      const response = await api.get(`/translations/export/${selectedLanguage}?format=json`);
      const blob = new Blob([JSON.stringify(response.data.translations, null, 2)], {
        type: 'application/json',
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `translations_${selectedLanguage}.json`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (error) {
      console.error('Failed to export translations:', error);
    }
  };

  // Import translations
  const handleImport = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    try {
      const formData = new FormData();
      formData.append('file', file);
      
      await api.post(`/translations/import/file?language=${selectedLanguage}`, formData);
      fetchTranslations();
      fetchStats();
    } catch (error) {
      console.error('Failed to import translations:', error);
    }
  };

  const currentStats = stats[selectedLanguage] || { total: 0, verified: 0, unverified: 0, percentage: 0 };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Languages className="w-8 h-8 text-primary-400" />
          <h1 className="text-2xl font-bold text-white">
            {t('translations.title')}
          </h1>
        </div>
        
        <div className="flex items-center gap-4">
          <label className="relative cursor-pointer">
            <input
              type="file"
              accept=".json"
              onChange={handleImport}
              className="hidden"
            />
            <button className="flex items-center gap-2 px-4 py-2 bg-gray-700 text-white rounded-md hover:bg-gray-600 transition-colors">
              <Upload className="w-4 h-4" />
              {t('common.import')}
            </button>
          </label>
          
          <button
            onClick={handleExport}
            className="flex items-center gap-2 px-4 py-2 bg-gray-700 text-white rounded-md hover:bg-gray-600 transition-colors"
          >
            <Download className="w-4 h-4" />
            {t('common.export')}
          </button>
          
          <button
            onClick={() => setIsCreating(true)}
            className="flex items-center gap-2 px-4 py-2 bg-primary-600 text-white rounded-md hover:bg-primary-700 transition-colors"
          >
            <Plus className="w-4 h-4" />
            {t('translations.add_translation')}
          </button>
        </div>
      </div>

      {/* Language selector and stats */}
      <div className="bg-gray-800 rounded-lg p-6">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div>
            <label className="block text-sm font-medium text-gray-400 mb-2">
              {t('settings.language')}
            </label>
            <select
              value={selectedLanguage}
              onChange={(e) => setSelectedLanguage(e.target.value)}
              className="w-full px-4 py-2 bg-gray-700 text-white rounded-md focus:ring-2 focus:ring-primary-500"
            >
              {Object.entries(languages).map(([code, info]) => (
                <option key={code} value={code}>
                  {info.nativeName} ({info.name})
                </option>
              ))}
            </select>
          </div>
          
          <div className="space-y-2">
            <div className="flex items-center justify-between text-sm">
              <span className="text-gray-400">{t('translations.progress')}</span>
              <span className="text-white font-medium">
                {currentStats.percentage.toFixed(0)}%
              </span>
            </div>
            <div className="w-full bg-gray-700 rounded-full h-2.5">
              <div
                className="bg-primary-600 h-2.5 rounded-full transition-all duration-300"
                style={{ width: `${currentStats.percentage}%` }}
              />
            </div>
            <div className="flex items-center justify-between text-xs text-gray-500">
              <span>{currentStats.verified} {t('translations.verified')}</span>
              <span>{currentStats.unverified} {t('translations.unverified')}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-4">
        <div className="flex-1 relative">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-gray-400" />
          <input
            type="text"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder={t('common.search')}
            className="w-full pl-10 pr-4 py-2 bg-gray-800 text-white rounded-md focus:ring-2 focus:ring-primary-500"
          />
        </div>
        
        <button
          onClick={() => setShowUnverifiedOnly(!showUnverifiedOnly)}
          className={cn(
            "flex items-center gap-2 px-4 py-2 rounded-md transition-colors",
            showUnverifiedOnly
              ? "bg-primary-600 text-white"
              : "bg-gray-800 text-gray-300 hover:bg-gray-700"
          )}
        >
          <Filter className="w-4 h-4" />
          {t('translations.show_unverified')}
        </button>
      </div>

      {/* Create new translation form */}
      {isCreating && (
        <div className="bg-gray-800 rounded-lg p-6 space-y-4">
          <h3 className="text-lg font-semibold text-white mb-4">
            {t('translations.new_translation')}
          </h3>
          
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <input
              type="text"
              value={newTranslation.key}
              onChange={(e) => setNewTranslation({ ...newTranslation, key: e.target.value })}
              placeholder={t('translations.key')}
              className="px-4 py-2 bg-gray-700 text-white rounded-md focus:ring-2 focus:ring-primary-500"
            />
            
            <input
              type="text"
              value={newTranslation.value}
              onChange={(e) => setNewTranslation({ ...newTranslation, value: e.target.value })}
              placeholder={t('translations.value')}
              className="px-4 py-2 bg-gray-700 text-white rounded-md focus:ring-2 focus:ring-primary-500"
            />
            
            <input
              type="text"
              value={newTranslation.context}
              onChange={(e) => setNewTranslation({ ...newTranslation, context: e.target.value })}
              placeholder={t('translations.context')}
              className="px-4 py-2 bg-gray-700 text-white rounded-md focus:ring-2 focus:ring-primary-500"
            />
          </div>
          
          <div className="flex items-center gap-2">
            <button
              onClick={handleCreate}
              disabled={!newTranslation.key || !newTranslation.value}
              className="flex items-center gap-2 px-4 py-2 bg-primary-600 text-white rounded-md hover:bg-primary-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              <Check className="w-4 h-4" />
              {t('common.save')}
            </button>
            
            <button
              onClick={() => {
                setIsCreating(false);
                setNewTranslation({ key: '', value: '', context: '' });
              }}
              className="flex items-center gap-2 px-4 py-2 bg-gray-700 text-white rounded-md hover:bg-gray-600 transition-colors"
            >
              <X className="w-4 h-4" />
              {t('common.cancel')}
            </button>
          </div>
        </div>
      )}

      {/* Translations table */}
      <div className="bg-gray-800 rounded-lg overflow-hidden">
        <table className="w-full">
          <thead className="bg-gray-900">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">
                {t('translations.key')}
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">
                {t('translations.value')}
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">
                {t('translations.context')}
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">
                {t('translations.status')}
              </th>
              <th className="px-6 py-3 text-right text-xs font-medium text-gray-400 uppercase tracking-wider">
                {t('common.actions')}
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-700">
            {loading ? (
              <tr>
                <td colSpan={5} className="px-6 py-12 text-center text-gray-400">
                  {t('common.loading')}
                </td>
              </tr>
            ) : translations.length === 0 ? (
              <tr>
                <td colSpan={5} className="px-6 py-12 text-center text-gray-400">
                  {t('translations.no_translations')}
                </td>
              </tr>
            ) : (
              translations.map((translation) => (
                <tr key={translation.id} className="hover:bg-gray-700/50">
                  <td className="px-6 py-4 text-sm text-gray-300 font-mono">
                    {translation.key}
                  </td>
                  <td className="px-6 py-4 text-sm text-white">
                    {editingId === translation.id ? (
                      <input
                        type="text"
                        value={editValue}
                        onChange={(e) => setEditValue(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter') handleUpdate(translation.id);
                          if (e.key === 'Escape') {
                            setEditingId(null);
                            setEditValue('');
                          }
                        }}
                        className="w-full px-2 py-1 bg-gray-700 text-white rounded focus:ring-2 focus:ring-primary-500"
                        autoFocus
                      />
                    ) : (
                      translation.value
                    )}
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-400">
                    {translation.context || '-'}
                  </td>
                  <td className="px-6 py-4">
                    {translation.isVerified ? (
                      <span className="inline-flex items-center gap-1 px-2 py-1 text-xs font-medium bg-green-900/50 text-green-400 rounded-full">
                        <Check className="w-3 h-3" />
                        {t('translations.verified')}
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 px-2 py-1 text-xs font-medium bg-yellow-900/50 text-yellow-400 rounded-full">
                        <AlertCircle className="w-3 h-3" />
                        {t('translations.unverified')}
                      </span>
                    )}
                  </td>
                  <td className="px-6 py-4 text-right">
                    {editingId === translation.id ? (
                      <div className="flex items-center justify-end gap-2">
                        <button
                          onClick={() => handleUpdate(translation.id)}
                          className="p-1 text-green-400 hover:text-green-300"
                        >
                          <Check className="w-4 h-4" />
                        </button>
                        <button
                          onClick={() => {
                            setEditingId(null);
                            setEditValue('');
                          }}
                          className="p-1 text-red-400 hover:text-red-300"
                        >
                          <X className="w-4 h-4" />
                        </button>
                      </div>
                    ) : (
                      <div className="flex items-center justify-end gap-2">
                        <button
                          onClick={() => {
                            setEditingId(translation.id);
                            setEditValue(translation.value);
                          }}
                          className="p-1 text-gray-400 hover:text-white"
                        >
                          <Edit2 className="w-4 h-4" />
                        </button>
                        <button
                          onClick={() => handleDelete(translation.id)}
                          className="p-1 text-gray-400 hover:text-red-400"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    )}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};