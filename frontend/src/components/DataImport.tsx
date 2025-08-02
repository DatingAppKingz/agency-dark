import React, { useState, useEffect, useCallback } from 'react';
import {
  Upload,
  FileUp,
  FileText,
  FileSpreadsheet,
  FileCode,
  CheckCircle,
  XCircle,
  AlertCircle,
  Download,
  RefreshCw
} from 'lucide-react';
import { useDropzone } from 'react-dropzone';
import { format } from 'date-fns';
import { apiClient } from '../services/api';
import { cn } from '../lib/utils';

interface ImportTemplate {
  id: string;
  name: string;
  description?: string;
  entityType: string;
  format: string;
  fieldMappings: Array<{
    sourceField: string;
    targetField: string;
  }>;
  sampleFileUrl: string;
}

interface ImportJob {
  importId: string;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  totalRecords?: number;
  successfulRecords?: number;
  failedRecords?: number;
  createdAt: string;
}

interface ValidationResult {
  totalRecords: number;
  validRecords: number;
  invalidRecords: number;
  errors: Array<{
    rowNumber: number;
    field?: string;
    value: string;
    error: string;
  }>;
  preview?: any[];
}

const ENTITY_TYPES = [
  { value: 'users', label: 'Users', icon: '👤', accepts: ['.csv', '.json', '.xlsx'] },
  { value: 'models', label: 'Models', icon: '⭐', accepts: ['.csv', '.json', '.xlsx'] },
  { value: 'transactions', label: 'Transactions', icon: '💰', accepts: ['.csv', '.json', '.xlsx'] },
];

export const DataImport: React.FC = () => {
  const [selectedEntity, setSelectedEntity] = useState('models');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [fieldMapping/*, setFieldMapping*/] = useState<Record<string, string>>({});
  const [updateExisting, setUpdateExisting] = useState(false);
  const [continueOnError, setContinueOnError] = useState(true);
  const [templates, setTemplates] = useState<ImportTemplate[]>([]);
  const [activeImports, setActiveImports] = useState<ImportJob[]>([]);
  const [validationResult, setValidationResult] = useState<ValidationResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [validating, setValidating] = useState(false);

  // Fetch templates
  useEffect(() => {
    fetchTemplates();
    fetchActiveImports();
  }, []);

  const fetchTemplates = async () => {
    try {
      const response = await apiClient.get('/imports/templates');
      setTemplates(response.data);
    } catch (error) {
      console.error('Failed to fetch templates:', error);
    }
  };

  const fetchActiveImports = async () => {
    try {
      const response = await apiClient.get('/imports/history?limit=5');
      setActiveImports(response.data);
    } catch (error) {
      console.error('Failed to fetch active imports:', error);
    }
  };

  const onDrop = useCallback((acceptedFiles: File[]) => {
    if (acceptedFiles.length > 0) {
      setSelectedFile(acceptedFiles[0]);
      setValidationResult(null);
    }
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'text/csv': ['.csv'],
      'application/json': ['.json'],
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'],
    },
    maxFiles: 1,
  });

  const handleValidate = async () => {
    if (!selectedFile) return;

    setValidating(true);
    try {
      const formData = new FormData();
      formData.append('file', selectedFile);
      formData.append('entity_type', selectedEntity);
      formData.append('format', getFileFormat(selectedFile.name));
      formData.append('update_existing', String(updateExisting));
      
      if (Object.keys(fieldMapping).length > 0) {
        formData.append('field_mapping', JSON.stringify(fieldMapping));
      }

      const response = await apiClient.post('/imports/validate', formData);
      setValidationResult(response.data);
    } catch (error) {
      console.error('Validation failed:', error);
    } finally {
      setValidating(false);
    }
  };

  const handleImport = async () => {
    if (!selectedFile) return;

    setLoading(true);
    try {
      const formData = new FormData();
      formData.append('file', selectedFile);
      formData.append('entity_type', selectedEntity);
      formData.append('format', getFileFormat(selectedFile.name));
      formData.append('update_existing', String(updateExisting));
      formData.append('continue_on_error', String(continueOnError));
      formData.append('validate_only', 'false');
      formData.append('send_notifications', 'true');
      
      if (Object.keys(fieldMapping).length > 0) {
        formData.append('field_mapping', JSON.stringify(fieldMapping));
      }

      const response = await apiClient.post('/imports', formData);

      // Start polling for status
      pollImportStatus(response.data.import_id);
      
      // Reset form
      setSelectedFile(null);
      setValidationResult(null);
      
      // Refresh active imports
      fetchActiveImports();
    } catch (error) {
      console.error('Import failed:', error);
    } finally {
      setLoading(false);
    }
  };

  const pollImportStatus = async (importId: string) => {
    const checkStatus = async () => {
      try {
        const response = await apiClient.get(`/imports/${importId}/status`);
        const status = response.data;

        // Update active imports
        setActiveImports(prev => {
          const existing = prev.find(i => i.importId === importId);
          if (existing) {
            return prev.map(i => 
              i.importId === importId 
                ? { ...i, ...status }
                : i
            );
          } else {
            return [...prev, {
              importId,
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
          fetchActiveImports();
        }
      } catch (error) {
        console.error('Failed to check import status:', error);
      }
    };

    checkStatus();
  };

  const handleDownloadTemplate = async (templateId: string) => {
    try {
      const response = await apiClient.get(`/imports/templates/${templateId}/sample`, {
        responseType: 'blob'
      });
      
      // Create download link
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `import_template_${templateId}.csv`);
      document.body.appendChild(link);
      link.click();
      link.remove();
    } catch (error) {
      console.error('Download failed:', error);
    }
  };

  const handleDownloadErrors = async (importId: string) => {
    try {
      const response = await apiClient.get(`/imports/${importId}/errors`, {
        responseType: 'blob'
      });
      
      // Create download link
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `import_errors_${importId}.csv`);
      document.body.appendChild(link);
      link.click();
      link.remove();
    } catch (error) {
      console.error('Download failed:', error);
    }
  };

  const getFileFormat = (filename: string): string => {
    const ext = filename.split('.').pop()?.toLowerCase();
    if (ext === 'xlsx' || ext === 'xls') return 'excel';
    if (ext === 'json') return 'json';
    return 'csv';
  };

  const getFileIcon = (filename: string) => {
    const format = getFileFormat(filename);
    switch (format) {
      case 'excel':
        return <FileSpreadsheet className="w-8 h-8" />;
      case 'json':
        return <FileCode className="w-8 h-8" />;
      default:
        return <FileText className="w-8 h-8" />;
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return <CheckCircle className="w-5 h-5 text-green-500" />;
      case 'failed':
        return <XCircle className="w-5 h-5 text-red-500" />;
      case 'processing':
        return <RefreshCw className="w-5 h-5 text-yellow-500 animate-spin" />;
      default:
        return <RefreshCw className="w-5 h-5 text-gray-500" />;
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <FileUp className="w-8 h-8 text-primary-400" />
          <h1 className="text-2xl font-bold text-white">Data Import</h1>
        </div>
      </div>

      {/* Import Configuration */}
      <div className="bg-gray-800 rounded-lg p-6 space-y-6">
        <h2 className="text-lg font-semibold text-white mb-4">Import Configuration</h2>

        {/* Entity Type Selection */}
        <div>
          <label className="block text-sm font-medium text-gray-400 mb-2">
            Data Type
          </label>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {ENTITY_TYPES.map((entity) => (
              <button
                key={entity.value}
                onClick={() => {
                  setSelectedEntity(entity.value);
                  setSelectedFile(null);
                  setValidationResult(null);
                }}
                className={cn(
                  "flex items-center gap-3 p-4 rounded-lg border-2 transition-all",
                  selectedEntity === entity.value
                    ? "border-primary-500 bg-primary-500/10 text-white"
                    : "border-gray-700 bg-gray-700/50 text-gray-400 hover:border-gray-600"
                )}
              >
                <span className="text-2xl">{entity.icon}</span>
                <div className="text-left">
                  <p className="font-medium">{entity.label}</p>
                  <p className="text-xs text-gray-500">
                    Accepts: {entity.accepts.join(', ')}
                  </p>
                </div>
              </button>
            ))}
          </div>
        </div>

        {/* File Upload */}
        <div>
          <label className="block text-sm font-medium text-gray-400 mb-2">
            Upload File
          </label>
          <div
            {...getRootProps()}
            className={cn(
              "border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors",
              isDragActive
                ? "border-primary-500 bg-primary-500/10"
                : "border-gray-600 hover:border-gray-500",
              selectedFile && "bg-gray-700/50"
            )}
          >
            <input {...getInputProps()} />
            {selectedFile ? (
              <div className="flex flex-col items-center gap-3">
                {getFileIcon(selectedFile.name)}
                <div>
                  <p className="font-medium text-white">{selectedFile.name}</p>
                  <p className="text-sm text-gray-400">
                    {(selectedFile.size / 1024 / 1024).toFixed(2)} MB
                  </p>
                </div>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    setSelectedFile(null);
                    setValidationResult(null);
                  }}
                  className="text-sm text-primary-400 hover:text-primary-300"
                >
                  Remove file
                </button>
              </div>
            ) : (
              <div className="flex flex-col items-center gap-3">
                <Upload className="w-12 h-12 text-gray-500" />
                <p className="text-gray-300">
                  {isDragActive
                    ? "Drop the file here..."
                    : "Drag & drop a file here, or click to select"}
                </p>
                <p className="text-sm text-gray-500">
                  CSV, JSON, or Excel files supported
                </p>
              </div>
            )}
          </div>
        </div>

        {/* Options */}
        <div className="space-y-3">
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={updateExisting}
              onChange={(e) => setUpdateExisting(e.target.checked)}
              className="rounded border-gray-600 text-primary-500 focus:ring-primary-500"
            />
            <span className="text-sm text-gray-300">Update existing records</span>
          </label>
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={continueOnError}
              onChange={(e) => setContinueOnError(e.target.checked)}
              className="rounded border-gray-600 text-primary-500 focus:ring-primary-500"
            />
            <span className="text-sm text-gray-300">Continue on error</span>
          </label>
        </div>

        {/* Action Buttons */}
        <div className="flex gap-3">
          <button
            onClick={handleValidate}
            disabled={!selectedFile || validating}
            className="flex items-center gap-2 px-6 py-3 bg-gray-700 text-white rounded-md hover:bg-gray-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            <AlertCircle className="w-5 h-5" />
            {validating ? 'Validating...' : 'Validate'}
          </button>
          <button
            onClick={handleImport}
            disabled={!selectedFile || loading || (validationResult && validationResult.invalidRecords > 0) || false}
            className="flex items-center gap-2 px-6 py-3 bg-primary-600 text-white rounded-md hover:bg-primary-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            <Upload className="w-5 h-5" />
            {loading ? 'Importing...' : 'Import Data'}
          </button>
        </div>
      </div>

      {/* Validation Results */}
      {validationResult && (
        <div className={cn(
          "rounded-lg p-6",
          validationResult.invalidRecords > 0 ? "bg-red-900/20" : "bg-green-900/20"
        )}>
          <h3 className="text-lg font-semibold text-white mb-4">
            Validation Results
          </h3>
          
          <div className="grid grid-cols-3 gap-6 mb-4">
            <div>
              <p className="text-sm text-gray-400">Total Records</p>
              <p className="text-2xl font-bold text-white">
                {validationResult.totalRecords}
              </p>
            </div>
            <div>
              <p className="text-sm text-gray-400">Valid Records</p>
              <p className="text-2xl font-bold text-green-400">
                {validationResult.validRecords}
              </p>
            </div>
            <div>
              <p className="text-sm text-gray-400">Invalid Records</p>
              <p className="text-2xl font-bold text-red-400">
                {validationResult.invalidRecords}
              </p>
            </div>
          </div>

          {validationResult.errors.length > 0 && (
            <div>
              <h4 className="text-sm font-medium text-white mb-2">
                Sample Errors (showing first 10)
              </h4>
              <div className="bg-gray-800 rounded p-4 space-y-2 max-h-60 overflow-y-auto">
                {validationResult.errors.slice(0, 10).map((error, index) => (
                  <div key={index} className="text-sm">
                    <span className="text-gray-400">Row {error.rowNumber}:</span>
                    <span className="text-red-400 ml-2">{error.error}</span>
                    {error.field && (
                      <span className="text-gray-500 ml-2">
                        (Field: {error.field})
                      </span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Templates */}
      <div className="bg-gray-800 rounded-lg p-6">
        <h2 className="text-lg font-semibold text-white mb-4">Import Templates</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {templates
            .filter(t => t.entityType === selectedEntity)
            .map((template) => (
              <div
                key={template.id}
                className="p-4 bg-gray-700/50 rounded-lg"
              >
                <h3 className="font-medium text-white mb-1">{template.name}</h3>
                {template.description && (
                  <p className="text-sm text-gray-400 mb-3">{template.description}</p>
                )}
                <div className="flex items-center justify-between">
                  <span className="text-xs text-gray-500">
                    {template.format.toUpperCase()} • {template.fieldMappings.length} fields
                  </span>
                  <button
                    onClick={() => handleDownloadTemplate(template.id)}
                    className="flex items-center gap-1 text-sm text-primary-400 hover:text-primary-300"
                  >
                    <Download className="w-4 h-4" />
                    Sample
                  </button>
                </div>
              </div>
            ))}
        </div>
      </div>

      {/* Active Imports */}
      {activeImports.length > 0 && (
        <div className="bg-gray-800 rounded-lg p-6">
          <h2 className="text-lg font-semibold text-white mb-4">Recent Imports</h2>
          <div className="space-y-3">
            {activeImports.map((job) => (
              <div
                key={job.importId}
                className="flex items-center justify-between p-4 bg-gray-700/50 rounded-lg"
              >
                <div className="flex items-center gap-4">
                  {getStatusIcon(job.status)}
                  <div>
                    <p className="font-medium text-white">
                      Import {job.importId.slice(0, 8)}...
                    </p>
                    <p className="text-sm text-gray-400">
                      {format(new Date(job.createdAt), 'MMM d, yyyy h:mm a')}
                    </p>
                    {job.totalRecords !== undefined && (
                      <p className="text-xs text-gray-500">
                        {job.successfulRecords}/{job.totalRecords} imported
                        {job.failedRecords && job.failedRecords > 0 && (
                          <span className="text-red-400">
                            {' '}• {job.failedRecords} failed
                          </span>
                        )}
                      </p>
                    )}
                  </div>
                </div>
                {job.status === 'completed' && job.failedRecords && job.failedRecords > 0 && (
                  <button
                    onClick={() => handleDownloadErrors(job.importId)}
                    className="flex items-center gap-2 px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700 transition-colors"
                  >
                    <Download className="w-4 h-4" />
                    Errors
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