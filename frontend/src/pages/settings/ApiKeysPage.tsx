import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Key,
  Plus,
  RefreshCw,
  Shield,
  Activity,
  Eye,
  EyeOff,
  Copy,
  Trash2,
  RotateCw,
  Clock,
  AlertCircle
} from 'lucide-react';
import { format } from 'date-fns';
import { ApiKeyManager } from '@/components/settings/ApiKeyManager';
import { apiKeysService } from '@/services/api/apiKeys';
import { ApiKey, ApiKeyProvider } from '@/types/apiKeys';
import { cn } from '@/lib/utils';
import { useNotification } from '@/hooks/useNotification';
import { useAuth } from '@/hooks/useAuth';


export const ApiKeysPage: React.FC = () => {
  const { t } = useTranslation();
  const { showNotification } = useNotification();
  const { user } = useAuth();
  const [apiKeys, setApiKeys] = useState<ApiKey[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedKey, setSelectedKey] = useState<ApiKey | null>(null);
  const [showManager, setShowManager] = useState(false);
  const [showSecret, setShowSecret] = useState<{ [key: string]: boolean }>({});

  // Check if user has permission to manage API keys
  const canManageApiKeys = ['super_admin', 'agency_owner', 'agency_admin'].includes(user?.role || '');

  useEffect(() => {
    if (canManageApiKeys) {
      fetchApiKeys();
    }
  }, [canManageApiKeys]);

  const fetchApiKeys = async () => {
    try {
      setLoading(true);
      const response = await apiKeysService.list();
      setApiKeys(response.keys);
    } catch (error) {
      console.error('Failed to fetch API keys:', error);
      showNotification({
        title: t('apiKeys.fetchError'),
        message: t('apiKeys.fetchErrorMessage'),
        type: 'error'
      });
    } finally {
      setLoading(false);
    }
  };

  const handleCreateKey = () => {
    setSelectedKey(null);
    setShowManager(true);
  };

  const handleEditKey = (key: ApiKey) => {
    setSelectedKey(key);
    setShowManager(true);
  };

  const handleDeleteKey = async (key: ApiKey) => {
    if (!confirm(t('apiKeys.deleteConfirm', { name: key.name }))) return;

    try {
      await apiKeysService.delete(key.id);
      showNotification({
        title: t('apiKeys.deleted'),
        message: t('apiKeys.deletedMessage', { name: key.name }),
        type: 'success'
      });
      fetchApiKeys();
    } catch (error) {
      console.error('Failed to delete API key:', error);
      showNotification({
        title: t('apiKeys.deleteError'),
        message: t('apiKeys.deleteErrorMessage'),
        type: 'error'
      });
    }
  };

  const handleRotateKey = async (key: ApiKey) => {
    setSelectedKey(key);
    setShowManager(true);
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    showNotification({
      title: t('common.copied'),
      message: t('apiKeys.keyCopied'),
      type: 'success'
    });
  };

  const getProviderColor = (provider: ApiKeyProvider) => {
    switch (provider) {
      case ApiKeyProvider.INFLOW:
        return 'bg-blue-500';
      case ApiKeyProvider.ONLYFANS:
        return 'bg-purple-500';
      case ApiKeyProvider.STRIPE:
        return 'bg-indigo-500';
      case ApiKeyProvider.PAYPAL:
        return 'bg-yellow-500';
      default:
        return 'bg-gray-500';
    }
  };

  const getStatusColor = (key: ApiKey) => {
    if (!key.is_active) return 'text-red-500';
    if (key.expires_at && new Date(key.expires_at) < new Date()) return 'text-red-500';
    return 'text-green-500';
  };

  const getStatusText = (key: ApiKey) => {
    if (!key.is_active) return t('common.inactive');
    if (key.expires_at && new Date(key.expires_at) < new Date()) return t('common.expired');
    return t('common.active');
  };

  if (!canManageApiKeys) {
    return (
      <div className="p-8">
        <div className="bg-red-900/20 border border-red-700 rounded-lg p-4 flex items-start gap-3">
          <AlertCircle className="w-5 h-5 text-red-500 mt-0.5" />
          <div className="text-sm text-gray-300">
            <p className="font-semibold text-red-500">{t('common.accessDenied')}</p>
            <p>{t('apiKeys.noPermission')}</p>
          </div>
        </div>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <RefreshCw className="w-8 h-8 text-gray-400 animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-3">
            <Key className="w-8 h-8 text-primary-400" />
            {t('apiKeys.title')}
          </h1>
          <p className="text-gray-400 mt-2">{t('apiKeys.description')}</p>
        </div>
        
        <button
          onClick={handleCreateKey}
          className="flex items-center gap-2 px-4 py-2 bg-primary-600 text-white rounded-md hover:bg-primary-700 transition-colors"
        >
          <Plus className="w-4 h-4" />
          {t('apiKeys.addKey')}
        </button>
      </div>

      {/* Security Notice */}
      <div className="bg-yellow-900/20 border border-yellow-700 rounded-lg p-4 flex items-start gap-3">
        <Shield className="w-5 h-5 text-yellow-500 mt-0.5" />
        <div className="text-sm text-gray-300">
          <p className="font-semibold text-yellow-500 mb-1">{t('apiKeys.securityNotice')}</p>
          <p>{t('apiKeys.securityMessage')}</p>
        </div>
      </div>

      {/* API Keys List */}
      <div className="bg-gray-800 rounded-lg overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-700">
          <h2 className="text-lg font-semibold text-white">{t('apiKeys.yourKeys')}</h2>
        </div>

        {apiKeys.length === 0 ? (
          <div className="p-12 text-center">
            <Key className="w-12 h-12 text-gray-600 mx-auto mb-4" />
            <p className="text-gray-400 mb-4">{t('apiKeys.noKeys')}</p>
            <button
              onClick={handleCreateKey}
              className="px-4 py-2 bg-primary-600 text-white rounded-md hover:bg-primary-700 transition-colors"
            >
              {t('apiKeys.createFirst')}
            </button>
          </div>
        ) : (
          <div className="divide-y divide-gray-700">
            {apiKeys.map((key) => (
              <div key={key.id} className="p-6 hover:bg-gray-750 transition-colors">
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-3 mb-2">
                      <h3 className="text-lg font-medium text-white">{key.name}</h3>
                      <span className={cn(
                        "px-2 py-1 text-xs rounded-full text-white",
                        getProviderColor(key.provider)
                      )}>
                        {key.provider}
                      </span>
                      <span className={cn("text-sm font-medium", getStatusColor(key))}>
                        {getStatusText(key)}
                      </span>
                    </div>

                    <div className="flex items-center gap-4 text-sm text-gray-400 mb-3">
                      <div className="flex items-center gap-1">
                        <span className="font-mono bg-gray-900 px-2 py-1 rounded">
                          {key.key_prefix}...
                        </span>
                        <button
                          onClick={() => copyToClipboard(key.key_prefix)}
                          className="p-1 hover:text-white transition-colors"
                        >
                          <Copy className="w-3 h-3" />
                        </button>
                      </div>
                      
                      {key.scopes.length > 0 && (
                        <div className="flex items-center gap-1">
                          <Shield className="w-3 h-3" />
                          {key.scopes.length} {t('apiKeys.scopes')}
                        </div>
                      )}

                      {key.last_used && (
                        <div className="flex items-center gap-1">
                          <Clock className="w-3 h-3" />
                          {t('apiKeys.lastUsed')}: {format(new Date(key.last_used), 'PPp')}
                        </div>
                      )}

                      <div className="flex items-center gap-1">
                        <Activity className="w-3 h-3" />
                        {key.usage_count.toLocaleString()} {t('apiKeys.requests')}
                      </div>
                    </div>

                    {key.expires_at && (
                      <div className="flex items-center gap-2 text-sm">
                        <AlertCircle className={cn(
                          "w-4 h-4",
                          new Date(key.expires_at) < new Date() ? 'text-red-500' : 'text-yellow-500'
                        )} />
                        <span className={cn(
                          new Date(key.expires_at) < new Date() ? 'text-red-500' : 'text-yellow-500'
                        )}>
                          {new Date(key.expires_at) < new Date() 
                            ? t('apiKeys.expired') 
                            : t('apiKeys.expiresOn', { date: format(new Date(key.expires_at), 'PP') })
                          }
                        </span>
                      </div>
                    )}
                  </div>

                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => handleEditKey(key)}
                      className="p-2 text-gray-400 hover:text-white transition-colors"
                      title={t('common.edit')}
                    >
                      <Eye className="w-4 h-4" />
                    </button>
                    
                    <button
                      onClick={() => handleRotateKey(key)}
                      className="p-2 text-gray-400 hover:text-white transition-colors"
                      title={t('apiKeys.rotate')}
                    >
                      <RotateCw className="w-4 h-4" />
                    </button>
                    
                    <button
                      onClick={() => handleDeleteKey(key)}
                      className="p-2 text-gray-400 hover:text-red-500 transition-colors"
                      title={t('common.delete')}
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* API Key Manager Modal */}
      {showManager && (
        <ApiKeyManager
          apiKey={selectedKey}
          onClose={() => {
            setShowManager(false);
            setSelectedKey(null);
          }}
          onSaved={() => {
            setShowManager(false);
            setSelectedKey(null);
            fetchApiKeys();
          }}
        />
      )}
    </div>
  );
};

export default ApiKeysPage;
