import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import {
  X,
  Key,
  Shield,
  Eye,
  EyeOff,
  Copy,
  AlertCircle,
  Check,
  RefreshCw,
  RotateCw,
  Activity,
  Clock,
  FileText
} from 'lucide-react';
import { format } from 'date-fns';
import { apiKeysService } from '@/services/api/apiKeys';
import {
  ApiKey,
  ApiKeyProvider,
  ApiKeyCreateRequest,
  ApiKeyRotateRequest,
  ApiKeyUsageStats,
  ApiKeyAuditLog
} from '@/types/apiKeys';
import { cn } from '@/lib/utils';
import { useNotification } from '@/hooks/useNotification';

interface ApiKeyManagerProps {
  apiKey?: ApiKey | null;
  onClose: () => void;
  onSaved: () => void;
}

export const ApiKeyManager: React.FC<ApiKeyManagerProps> = ({
  apiKey,
  onClose,
  onSaved
}) => {
  const { t } = useTranslation();
  const { showNotification } = useNotification();
  const [activeTab, setActiveTab] = useState<'details' | 'stats' | 'audit' | 'rotate'>('details');
  const [loading, setLoading] = useState(false);
  const [showKey, setShowKey] = useState(false);
  const [copiedKey, setCopiedKey] = useState(false);
  
  // Form state
  const [formData, setFormData] = useState<ApiKeyCreateRequest>({
    name: '',
    provider: ApiKeyProvider.INFLOW,
    key: '',
    scopes: [],
    expires_at: undefined
  });
  
  // Stats and audit data
  const [usageStats, setUsageStats] = useState<ApiKeyUsageStats | null>(null);
  const [auditLogs, setAuditLogs] = useState<ApiKeyAuditLog[]>([]);
  const [newKeyValue, setNewKeyValue] = useState('');
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null);

  useEffect(() => {
    if (apiKey) {
      setFormData({
        name: apiKey.name,
        provider: apiKey.provider,
        key: '',
        scopes: apiKey.scopes,
        expires_at: apiKey.expires_at || undefined
      });
      
      if (activeTab === 'stats') {
        fetchUsageStats();
      } else if (activeTab === 'audit') {
        fetchAuditLogs();
      }
    }
  }, [apiKey, activeTab]);

  const fetchUsageStats = async () => {
    if (!apiKey) return;
    
    try {
      const stats = await apiKeysService.getUsageStats(apiKey.id);
      setUsageStats(stats);
    } catch (error) {
      console.error('Failed to fetch usage stats:', error);
    }
  };

  const fetchAuditLogs = async () => {
    if (!apiKey) return;
    
    try {
      const response = await apiKeysService.getAuditLogs(apiKey.id);
      setAuditLogs(response);
    } catch (error) {
      console.error('Failed to fetch audit logs:', error);
    }
  };

  const handleSubmit = async () => {
    if (!formData.name || (!apiKey && !formData.key)) {
      showNotification({
        title: t('common.error'),
        message: t('apiKeys.fillRequired'),
        type: 'error'
      });
      return;
    }

    setLoading(true);
    try {
      if (apiKey) {
        // Update existing key
        await apiKeysService.update(apiKey.id, {
          name: formData.name,
          scopes: formData.scopes,
          is_active: true
        });
        showNotification({
          title: t('common.success'),
          message: t('apiKeys.updated'),
          type: 'success'
        });
      } else {
        // Create new key
        await apiKeysService.create(formData);
        showNotification({
          title: t('common.success'),
          message: t('apiKeys.created'),
          type: 'success'
        });
      }
      onSaved();
    } catch (error) {
      console.error('Failed to save API key:', error);
      showNotification({
        title: t('common.error'),
        message: t('apiKeys.saveError'),
        type: 'error'
      });
    } finally {
      setLoading(false);
    }
  };

  const handleRotate = async () => {
    if (!apiKey || !newKeyValue) {
      showNotification({
        title: t('common.error'),
        message: t('apiKeys.enterNewKey'),
        type: 'error'
      });
      return;
    }

    setLoading(true);
    try {
      const rotateData: ApiKeyRotateRequest = { new_key: newKeyValue };
      await apiKeysService.rotate(apiKey.id, rotateData);
      showNotification({
        title: t('common.success'),
        message: t('apiKeys.rotated'),
        type: 'success'
      });
      onSaved();
    } catch (error) {
      console.error('Failed to rotate API key:', error);
      showNotification({
        title: t('common.error'),
        message: t('apiKeys.rotateError'),
        type: 'error'
      });
    } finally {
      setLoading(false);
    }
  };

  const handleTest = async () => {
    if (!apiKey) return;
    
    setTesting(true);
    setTestResult(null);
    
    try {
      const result = await apiKeysService.testConnection(apiKey.id);
      setTestResult(result);
    } catch (error) {
      console.error('Failed to test API key:', error);
      setTestResult({
        success: false,
        message: t('apiKeys.testFailed')
      });
    } finally {
      setTesting(false);
    }
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedKey(true);
    setTimeout(() => setCopiedKey(false), 2000);
    showNotification({
      title: t('common.copied'),
      message: t('apiKeys.keyCopied'),
      type: 'success'
    });
  };

  const getProviderScopes = (provider: ApiKeyProvider): string[] => {
    switch (provider) {
      case ApiKeyProvider.INFLOW:
        return ['subscribers.read', 'messages.read', 'messages.write', 'analytics.read'];
      case ApiKeyProvider.ONLYFANS:
        return ['profile.read', 'posts.read', 'posts.write', 'messages.read', 'messages.write'];
      case ApiKeyProvider.STRIPE:
        return ['payments.read', 'customers.read', 'subscriptions.read'];
      case ApiKeyProvider.PAYPAL:
        return ['payments.read', 'invoices.read'];
      default:
        return [];
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-gray-800 rounded-lg max-w-2xl w-full max-h-[90vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="px-6 py-4 border-b border-gray-700 flex items-center justify-between">
          <h2 className="text-xl font-semibold text-white flex items-center gap-3">
            <Key className="w-6 h-6 text-primary-400" />
            {apiKey ? t('apiKeys.editKey') : t('apiKeys.createKey')}
          </h2>
          <button
            onClick={onClose}
            className="p-2 text-gray-400 hover:text-white transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Tabs */}
        {apiKey && (
          <div className="px-6 pt-4 flex gap-4 border-b border-gray-700">
            <button
              onClick={() => setActiveTab('details')}
              className={cn(
                "pb-3 px-1 text-sm font-medium transition-colors relative",
                activeTab === 'details' 
                  ? "text-primary-400" 
                  : "text-gray-400 hover:text-white"
              )}
            >
              {t('apiKeys.details')}
              {activeTab === 'details' && (
                <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-primary-400" />
              )}
            </button>
            <button
              onClick={() => setActiveTab('stats')}
              className={cn(
                "pb-3 px-1 text-sm font-medium transition-colors relative",
                activeTab === 'stats' 
                  ? "text-primary-400" 
                  : "text-gray-400 hover:text-white"
              )}
            >
              {t('apiKeys.usageStats')}
              {activeTab === 'stats' && (
                <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-primary-400" />
              )}
            </button>
            <button
              onClick={() => setActiveTab('audit')}
              className={cn(
                "pb-3 px-1 text-sm font-medium transition-colors relative",
                activeTab === 'audit' 
                  ? "text-primary-400" 
                  : "text-gray-400 hover:text-white"
              )}
            >
              {t('apiKeys.auditLogs')}
              {activeTab === 'audit' && (
                <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-primary-400" />
              )}
            </button>
            <button
              onClick={() => setActiveTab('rotate')}
              className={cn(
                "pb-3 px-1 text-sm font-medium transition-colors relative",
                activeTab === 'rotate' 
                  ? "text-primary-400" 
                  : "text-gray-400 hover:text-white"
              )}
            >
              {t('apiKeys.rotateKey')}
              {activeTab === 'rotate' && (
                <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-primary-400" />
              )}
            </button>
          </div>
        )}

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6">
          {activeTab === 'details' && (
            <div className="space-y-4">
              {/* Name */}
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">
                  {t('apiKeys.keyName')} *
                </label>
                <input
                  type="text"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-md text-white focus:outline-none focus:ring-2 focus:ring-primary-500"
                  placeholder={t('apiKeys.keyNamePlaceholder')}
                />
              </div>

              {/* Provider */}
              {!apiKey && (
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-2">
                    {t('apiKeys.provider')} *
                  </label>
                  <select
                    value={formData.provider}
                    onChange={(e) => setFormData({ ...formData, provider: e.target.value as ApiKeyProvider })}
                    className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-md text-white focus:outline-none focus:ring-2 focus:ring-primary-500"
                  >
                    {Object.values(ApiKeyProvider).map(provider => (
                      <option key={provider} value={provider}>
                        {provider}
                      </option>
                    ))}
                  </select>
                </div>
              )}

              {/* API Key */}
              {!apiKey && (
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-2">
                    {t('apiKeys.apiKey')} *
                  </label>
                  <div className="relative">
                    <input
                      type={showKey ? 'text' : 'password'}
                      value={formData.key}
                      onChange={(e) => setFormData({ ...formData, key: e.target.value })}
                      className="w-full px-3 py-2 pr-20 bg-gray-700 border border-gray-600 rounded-md text-white focus:outline-none focus:ring-2 focus:ring-primary-500 font-mono"
                      placeholder="sk_live_..."
                    />
                    <div className="absolute right-2 top-2 flex gap-2">
                      <button
                        type="button"
                        onClick={() => setShowKey(!showKey)}
                        className="p-1 text-gray-400 hover:text-white transition-colors"
                      >
                        {showKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                      </button>
                      {formData.key && (
                        <button
                          type="button"
                          onClick={() => copyToClipboard(formData.key)}
                          className="p-1 text-gray-400 hover:text-white transition-colors"
                        >
                          {copiedKey ? <Check className="w-4 h-4 text-green-500" /> : <Copy className="w-4 h-4" />}
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              )}

              {/* Scopes */}
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">
                  {t('apiKeys.scopes')}
                </label>
                <div className="space-y-2">
                  {getProviderScopes(formData.provider).map(scope => (
                    <label key={scope} className="flex items-center gap-3">
                      <input
                        type="checkbox"
                        checked={formData.scopes.includes(scope)}
                        onChange={(e) => {
                          if (e.target.checked) {
                            setFormData({ ...formData, scopes: [...formData.scopes, scope] });
                          } else {
                            setFormData({ ...formData, scopes: formData.scopes.filter(s => s !== scope) });
                          }
                        }}
                        className="w-4 h-4 text-primary-600 bg-gray-700 border-gray-600 rounded focus:ring-primary-500"
                      />
                      <span className="text-sm text-gray-300">{scope}</span>
                    </label>
                  ))}
                </div>
              </div>

              {/* Expiration */}
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">
                  {t('apiKeys.expiresAt')}
                </label>
                <input
                  type="datetime-local"
                  value={formData.expires_at || ''}
                  onChange={(e) => setFormData({ ...formData, expires_at: e.target.value || undefined })}
                  className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-md text-white focus:outline-none focus:ring-2 focus:ring-primary-500"
                />
                <p className="text-xs text-gray-500 mt-1">{t('apiKeys.expiresHelp')}</p>
              </div>

              {/* Test Connection */}
              {apiKey && (
                <div className="bg-gray-900 rounded-lg p-4">
                  <div className="flex items-center justify-between mb-3">
                    <h3 className="text-sm font-medium text-white">{t('apiKeys.testConnection')}</h3>
                    <button
                      onClick={handleTest}
                      disabled={testing}
                      className={cn(
                        "flex items-center gap-2 px-3 py-1.5 text-sm rounded-md transition-colors",
                        testing 
                          ? "bg-gray-700 text-gray-400 cursor-not-allowed" 
                          : "bg-primary-600 text-white hover:bg-primary-700"
                      )}
                    >
                      {testing && <RefreshCw className="w-3 h-3 animate-spin" />}
                      {t('apiKeys.test')}
                    </button>
                  </div>
                  
                  {testResult && (
                    <div className={cn(
                      "flex items-start gap-3 p-3 rounded-md",
                      testResult.success ? "bg-green-900/20" : "bg-red-900/20"
                    )}>
                      <AlertCircle className={cn(
                        "w-5 h-5 mt-0.5",
                        testResult.success ? "text-green-500" : "text-red-500"
                      )} />
                      <div>
                        <p className={cn(
                          "text-sm font-medium",
                          testResult.success ? "text-green-500" : "text-red-500"
                        )}>
                          {testResult.success ? t('apiKeys.testSuccess') : t('apiKeys.testFailed')}
                        </p>
                        <p className="text-xs text-gray-400 mt-1">{testResult.message}</p>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {activeTab === 'stats' && usageStats && (
            <div className="space-y-6">
              {/* Summary Stats */}
              <div className="grid grid-cols-2 gap-4">
                <div className="bg-gray-900 rounded-lg p-4">
                  <p className="text-sm text-gray-400 mb-1">{t('apiKeys.totalRequests')}</p>
                  <p className="text-2xl font-bold text-white">{usageStats.total_requests.toLocaleString()}</p>
                </div>
                <div className="bg-gray-900 rounded-lg p-4">
                  <p className="text-sm text-gray-400 mb-1">{t('apiKeys.errorRate')}</p>
                  <p className="text-2xl font-bold text-white">
                    {usageStats.total_requests > 0 
                      ? ((usageStats.total_errors / usageStats.total_requests) * 100).toFixed(2) 
                      : 0
                    }%
                  </p>
                </div>
              </div>

              {/* Daily Usage Chart */}
              <div>
                <h3 className="text-sm font-medium text-white mb-3">{t('apiKeys.dailyUsage')}</h3>
                <div className="bg-gray-900 rounded-lg p-4">
                  <div className="space-y-2">
                    {usageStats.daily_usage.slice(-7).map((day) => (
                      <div key={day.date} className="flex items-center gap-3">
                        <span className="text-xs text-gray-400 w-20">
                          {format(new Date(day.date), 'MMM dd')}
                        </span>
                        <div className="flex-1 bg-gray-700 rounded-full h-6 relative overflow-hidden">
                          <div
                            className="absolute left-0 top-0 h-full bg-primary-500 rounded-full"
                            style={{ 
                              width: `${Math.min((day.count / Math.max(...usageStats.daily_usage.map(d => d.count))) * 100, 100)}%` 
                            }}
                          />
                          <span className="absolute left-2 top-0.5 text-xs text-white">
                            {day.count}
                          </span>
                        </div>
                        {day.errors > 0 && (
                          <span className="text-xs text-red-500">{day.errors} errors</span>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              {/* Additional Stats */}
              <div className="bg-gray-900 rounded-lg p-4 space-y-2">
                <div className="flex justify-between">
                  <span className="text-sm text-gray-400">{t('apiKeys.avgResponseTime')}</span>
                  <span className="text-sm text-white">{usageStats.average_response_time.toFixed(0)}ms</span>
                </div>
                {usageStats.last_error && (
                  <div className="flex justify-between">
                    <span className="text-sm text-gray-400">{t('apiKeys.lastError')}</span>
                    <span className="text-sm text-red-500">{usageStats.last_error}</span>
                  </div>
                )}
              </div>
            </div>
          )}

          {activeTab === 'audit' && (
            <div className="space-y-4">
              {auditLogs.length === 0 ? (
                <div className="text-center py-8">
                  <FileText className="w-12 h-12 text-gray-600 mx-auto mb-3" />
                  <p className="text-gray-400">{t('apiKeys.noAuditLogs')}</p>
                </div>
              ) : (
                <div className="space-y-3">
                  {auditLogs.map((log) => (
                    <div key={log.id} className="bg-gray-900 rounded-lg p-4">
                      <div className="flex items-start justify-between mb-2">
                        <div className="flex items-center gap-3">
                          <div className={cn(
                            "w-2 h-2 rounded-full",
                            log.action === 'failed' ? 'bg-red-500' : 'bg-green-500'
                          )} />
                          <span className="text-sm font-medium text-white">{log.action}</span>
                        </div>
                        <span className="text-xs text-gray-400">
                          {format(new Date(log.created_at), 'MMM dd, yyyy HH:mm')}
                        </span>
                      </div>
                      
                      <div className="text-xs text-gray-400 space-y-1">
                        <p>{t('apiKeys.user')}: {log.user_email}</p>
                        <p>{t('apiKeys.ip')}: {log.ip_address}</p>
                        {log.user_agent && (
                          <p className="truncate">{t('apiKeys.userAgent')}: {log.user_agent}</p>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {activeTab === 'rotate' && (
            <div className="space-y-4">
              <div className="bg-yellow-900/20 border border-yellow-700 rounded-lg p-4 flex items-start gap-3">
                <AlertCircle className="w-5 h-5 text-yellow-500 mt-0.5" />
                <div className="text-sm text-gray-300">
                  <p className="font-semibold text-yellow-500 mb-1">{t('apiKeys.rotateWarning')}</p>
                  <p>{t('apiKeys.rotateWarningMessage')}</p>
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">
                  {t('apiKeys.newApiKey')} *
                </label>
                <div className="relative">
                  <input
                    type={showKey ? 'text' : 'password'}
                    value={newKeyValue}
                    onChange={(e) => setNewKeyValue(e.target.value)}
                    className="w-full px-3 py-2 pr-20 bg-gray-700 border border-gray-600 rounded-md text-white focus:outline-none focus:ring-2 focus:ring-primary-500 font-mono"
                    placeholder="sk_live_..."
                  />
                  <div className="absolute right-2 top-2 flex gap-2">
                    <button
                      type="button"
                      onClick={() => setShowKey(!showKey)}
                      className="p-1 text-gray-400 hover:text-white transition-colors"
                    >
                      {showKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                    </button>
                  </div>
                </div>
                <p className="text-xs text-gray-500 mt-1">{t('apiKeys.rotateHelp')}</p>
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-gray-700 flex items-center justify-end gap-3">
          <button
            onClick={onClose}
            className="px-4 py-2 text-gray-300 hover:text-white transition-colors"
          >
            {t('common.cancel')}
          </button>
          
          {activeTab === 'rotate' ? (
            <button
              onClick={handleRotate}
              disabled={loading || !newKeyValue}
              className={cn(
                "flex items-center gap-2 px-4 py-2 rounded-md transition-colors",
                loading || !newKeyValue
                  ? "bg-gray-700 text-gray-400 cursor-not-allowed"
                  : "bg-primary-600 text-white hover:bg-primary-700"
              )}
            >
              {loading && <RefreshCw className="w-4 h-4 animate-spin" />}
              <RotateCw className="w-4 h-4" />
              {t('apiKeys.rotate')}
            </button>
          ) : activeTab === 'details' ? (
            <button
              onClick={handleSubmit}
              disabled={loading}
              className={cn(
                "flex items-center gap-2 px-4 py-2 rounded-md transition-colors",
                loading
                  ? "bg-gray-700 text-gray-400 cursor-not-allowed"
                  : "bg-primary-600 text-white hover:bg-primary-700"
              )}
            >
              {loading && <RefreshCw className="w-4 h-4 animate-spin" />}
              {apiKey ? t('common.update') : t('common.create')}
            </button>
          ) : null}
        </div>
      </div>
    </div>
  );
};