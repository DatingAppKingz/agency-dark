import React, { useState, useEffect } from 'react';
import {
  Download,
  FileDown,
  CheckCircle,
  XCircle,
  Clock,
  Mail,
  FileText,
  FileSpreadsheet,
  FileCode,
  Archive
} from 'lucide-react';
import { format } from 'date-fns';
import { apiClient } from '../services/api';
import { cn } from '../lib/utils';

interface ExportTemplate {
  id: string;
  name: string;
  description?: string;
  entityType: string;
  format: string;
  fields: string[];
}

interface ExportJob {
  exportId: string;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  filename?: string;
  downloadUrl?: string;
  recordCount?: number;
  createdAt: string;
}

const ENTITY_TYPES = [
  { value: 'users', label: 'Users', icon: '👤' },
  { value: 'models', label: 'Models', icon: '⭐' },
  { value: 'transactions', label: 'Transactions', icon: '💰' },
  { value: 'messages', label: 'Messages', icon: '💬' },
  { value: 'media', label: 'Media', icon: '📸' },
  { value: 'analytics', label: 'Analytics', icon: '📊' },
];

const EXPORT_FORMATS = [
  { value: 'csv', label: 'CSV', icon: FileText },
  { value: 'json', label: 'JSON', icon: FileCode },
  { value: 'excel', label: 'Excel', icon: FileSpreadsheet },
  { value: 'pdf', label: 'PDF', icon: FileText },
  { value: 'zip', label: 'ZIP Archive', icon: Archive },
];

export const DataExport: React.FC = () => {
  const [selectedEntity, setSelectedEntity] = useState('models');
  const [selectedFormat, setSelectedFormat] = useState('csv');
  const [selectedFields, setSelectedFields] = useState<string[]>([]);
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [emailDelivery, setEmailDelivery] = useState(false);
  const [templates, setTemplates] = useState<ExportTemplate[]>([]);
  const [activeExports, setActiveExports] = useState<ExportJob[]>([]);
  const [loading, setLoading] = useState(false);

  // Fetch templates
  useEffect(() => {
    fetchTemplates();
    fetchActiveExports();
  }, []);

  const fetchTemplates = async () => {
    try {
      const response = await apiClient.get('/exports/templates');
      setTemplates(response.data);
    } catch (error) {
      console.error('Failed to fetch templates:', error);
    }
  };

  const fetchActiveExports = async () => {
    try {
      const response = await apiClient.get('/exports/history?limit=5');
      setActiveExports(response.data);
    } catch (error) {
      console.error('Failed to fetch active exports:', error);
    }
  };

  const handleExport = async () => {
    setLoading(true);
    try {
      const response = await apiClient.post('/exports', {
        entity_type: selectedEntity,
        format: selectedFormat,
        fields: selectedFields.length > 0 ? selectedFields : undefined,
        date_from: dateFrom || undefined,
        date_to: dateTo || undefined,
        email_delivery: emailDelivery,
      });

      // Start polling for status
      pollExportStatus(response.data.export_id);
      
      // Refresh active exports
      fetchActiveExports();
    } catch (error) {
      console.error('Export failed:', error);
    } finally {
      setLoading(false);
    }
  };

  const pollExportStatus = async (exportId: string) => {
    const checkStatus = async () => {
      try {
        const response = await apiClient.get(`/exports/${exportId}/status`);
        const status = response.data;

        // Update active exports
        setActiveExports(prev => {
          const existing = prev.find(e => e.exportId === exportId);
          if (existing) {
            return prev.map(e => 
              e.exportId === exportId 
                ? { ...e, status: status.status }
                : e
            );
          } else {
            return [...prev, {
              exportId,
              status: status.status,
              createdAt: new Date().toISOString()
            }];
          }
        });

        // Continue polling if still processing
        if (status.status === 'pending' || status.status === 'processing') {
          setTimeout(() => checkStatus(), 2000);
        } else if (status.status === 'completed') {
          // Fetch final details
          fetchActiveExports();
        }
      } catch (error) {
        console.error('Failed to check export status:', error);
      }
    };

    checkStatus();
  };

  const handleDownload = async (exportId: string) => {
    try {
      const response = await apiClient.get(`/exports/${exportId}/download`, {
        responseType: 'blob'
      });
      
      // Create download link
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `export_${exportId}.${selectedFormat}`);
      document.body.appendChild(link);
      link.click();
      link.remove();
    } catch (error) {
      console.error('Download failed:', error);
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return <CheckCircle className="w-5 h-5 text-green-500" />;
      case 'failed':
        return <XCircle className="w-5 h-5 text-red-500" />;
      case 'processing':
        return <Clock className="w-5 h-5 text-yellow-500 animate-spin" />;
      default:
        return <Clock className="w-5 h-5 text-gray-500" />;
    }
  };

  const getFieldsForEntity = (entityType: string) => {
    const fieldMap: Record<string, string[]> = {
      users: ['email', 'username', 'first_name', 'last_name', 'role', 'created_at', 'last_login_at'],
      models: ['stage_name', 'real_name', 'email', 'phone', 'status', 'commission_rate', 'total_revenue', 'total_fans'],
      transactions: ['date', 'model_name', 'type', 'amount', 'currency', 'status', 'description'],
      messages: ['conversation_id', 'sender', 'content', 'type', 'created_at'],
      media: ['filename', 'file_type', 'size', 'tags', 'created_at'],
      analytics: ['metric', 'value', 'date', 'model_id'],
    };
    return fieldMap[entityType] || [];
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <FileDown className="w-8 h-8 text-primary-400" />
          <h1 className="text-2xl font-bold text-white">Data Export</h1>
        </div>
      </div>

      {/* Export Configuration */}
      <div className="bg-gray-800 rounded-lg p-6 space-y-6">
        <h2 className="text-lg font-semibold text-white mb-4">Export Configuration</h2>

        {/* Entity Type Selection */}
        <div>
          <label className="block text-sm font-medium text-gray-400 mb-2">
            Data Type
          </label>
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
            {ENTITY_TYPES.map((entity) => (
              <button
                key={entity.value}
                onClick={() => {
                  setSelectedEntity(entity.value);
                  setSelectedFields([]);
                }}
                className={cn(
                  "flex flex-col items-center gap-2 p-4 rounded-lg border-2 transition-all",
                  selectedEntity === entity.value
                    ? "border-primary-500 bg-primary-500/10 text-white"
                    : "border-gray-700 bg-gray-700/50 text-gray-400 hover:border-gray-600"
                )}
              >
                <span className="text-2xl">{entity.icon}</span>
                <span className="text-sm font-medium">{entity.label}</span>
              </button>
            ))}
          </div>
        </div>

        {/* Format Selection */}
        <div>
          <label className="block text-sm font-medium text-gray-400 mb-2">
            Export Format
          </label>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
            {EXPORT_FORMATS.map((format) => {
              const Icon = format.icon;
              return (
                <button
                  key={format.value}
                  onClick={() => setSelectedFormat(format.value)}
                  className={cn(
                    "flex items-center gap-2 p-3 rounded-lg border-2 transition-all",
                    selectedFormat === format.value
                      ? "border-primary-500 bg-primary-500/10 text-white"
                      : "border-gray-700 bg-gray-700/50 text-gray-400 hover:border-gray-600"
                  )}
                >
                  <Icon className="w-5 h-5" />
                  <span className="text-sm font-medium">{format.label}</span>
                </button>
              );
            })}
          </div>
        </div>

        {/* Field Selection */}
        <div>
          <label className="block text-sm font-medium text-gray-400 mb-2">
            Fields to Export (leave empty for all)
          </label>
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-2">
            {getFieldsForEntity(selectedEntity).map((field) => (
              <label
                key={field}
                className="flex items-center gap-2 p-2 rounded bg-gray-700/50 hover:bg-gray-700 cursor-pointer"
              >
                <input
                  type="checkbox"
                  checked={selectedFields.includes(field)}
                  onChange={(e) => {
                    if (e.target.checked) {
                      setSelectedFields([...selectedFields, field]);
                    } else {
                      setSelectedFields(selectedFields.filter(f => f !== field));
                    }
                  }}
                  className="rounded border-gray-600 text-primary-500 focus:ring-primary-500"
                />
                <span className="text-sm text-gray-300">{field}</span>
              </label>
            ))}
          </div>
        </div>

        {/* Date Range */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-400 mb-2">
              From Date
            </label>
            <input
              type="date"
              value={dateFrom}
              onChange={(e) => setDateFrom(e.target.value)}
              className="w-full px-4 py-2 bg-gray-700 text-white rounded-md focus:ring-2 focus:ring-primary-500"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-400 mb-2">
              To Date
            </label>
            <input
              type="date"
              value={dateTo}
              onChange={(e) => setDateTo(e.target.value)}
              className="w-full px-4 py-2 bg-gray-700 text-white rounded-md focus:ring-2 focus:ring-primary-500"
            />
          </div>
        </div>

        {/* Options */}
        <div className="flex items-center gap-6">
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={emailDelivery}
              onChange={(e) => setEmailDelivery(e.target.checked)}
              className="rounded border-gray-600 text-primary-500 focus:ring-primary-500"
            />
            <span className="text-sm text-gray-300">Email me when export is ready</span>
            <Mail className="w-4 h-4 text-gray-400" />
          </label>
        </div>

        {/* Export Button */}
        <div className="flex justify-end">
          <button
            onClick={handleExport}
            disabled={loading}
            className="flex items-center gap-2 px-6 py-3 bg-primary-600 text-white rounded-md hover:bg-primary-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            <Download className="w-5 h-5" />
            {loading ? 'Processing...' : 'Export Data'}
          </button>
        </div>
      </div>

      {/* Templates */}
      <div className="bg-gray-800 rounded-lg p-6">
        <h2 className="text-lg font-semibold text-white mb-4">Quick Export Templates</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {templates.map((template) => (
            <div
              key={template.id}
              className="p-4 bg-gray-700/50 rounded-lg hover:bg-gray-700 cursor-pointer transition-colors"
              onClick={() => {
                setSelectedEntity(template.entityType);
                setSelectedFormat(template.format);
                setSelectedFields(template.fields);
              }}
            >
              <h3 className="font-medium text-white mb-1">{template.name}</h3>
              {template.description && (
                <p className="text-sm text-gray-400 mb-2">{template.description}</p>
              )}
              <div className="flex items-center gap-4 text-xs text-gray-500">
                <span>{template.entityType}</span>
                <span>•</span>
                <span>{template.format.toUpperCase()}</span>
                <span>•</span>
                <span>{template.fields.length} fields</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Active Exports */}
      {activeExports.length > 0 && (
        <div className="bg-gray-800 rounded-lg p-6">
          <h2 className="text-lg font-semibold text-white mb-4">Recent Exports</h2>
          <div className="space-y-3">
            {activeExports.map((job) => (
              <div
                key={job.exportId}
                className="flex items-center justify-between p-4 bg-gray-700/50 rounded-lg"
              >
                <div className="flex items-center gap-4">
                  {getStatusIcon(job.status)}
                  <div>
                    <p className="font-medium text-white">
                      {job.filename || `Export ${job.exportId.slice(0, 8)}...`}
                    </p>
                    <p className="text-sm text-gray-400">
                      {format(new Date(job.createdAt), 'MMM d, yyyy h:mm a')}
                      {job.recordCount && ` • ${job.recordCount} records`}
                    </p>
                  </div>
                </div>
                {job.status === 'completed' && (
                  <button
                    onClick={() => handleDownload(job.exportId)}
                    className="flex items-center gap-2 px-4 py-2 bg-primary-600 text-white rounded-md hover:bg-primary-700 transition-colors"
                  >
                    <Download className="w-4 h-4" />
                    Download
                  </button>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};