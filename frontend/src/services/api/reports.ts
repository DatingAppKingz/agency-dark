import apiClient from './client';
import {
  ReportTemplate,
  ReportSchedule,
  ReportExport,
  ReportBuilderConfig,
  SaveReportTemplateRequest,
  GenerateReportRequest,
  ReportDataResponse,
  DateRange,
  ReportFilter,
} from '@/types/reports';

export const reportsService = {
  // Report Templates
  async getTemplates(params?: {
    type?: string;
    search?: string;
    limit?: number;
    offset?: number;
  }): Promise<{ items: ReportTemplate[]; total: number }> {
    const response = await apiClient.get('/api/v1/reports/templates', { params });
    return response.data;
  },

  async getTemplate(id: string): Promise<ReportTemplate> {
    const response = await apiClient.get(`/api/v1/reports/templates/${id}`);
    return response.data;
  },

  async createTemplate(data: SaveReportTemplateRequest): Promise<ReportTemplate> {
    const response = await apiClient.post('/api/v1/reports/templates', data);
    return response.data;
  },

  async updateTemplate(id: string, data: SaveReportTemplateRequest): Promise<ReportTemplate> {
    const response = await apiClient.put(`/api/v1/reports/templates/${id}`, data);
    return response.data;
  },

  async deleteTemplate(id: string): Promise<void> {
    await apiClient.delete(`/api/v1/reports/templates/${id}`);
  },

  async duplicateTemplate(id: string, name: string): Promise<ReportTemplate> {
    const response = await apiClient.post(`/api/v1/reports/templates/${id}/duplicate`, { name });
    return response.data;
  },

  // Report Generation
  async generateReport(data: GenerateReportRequest): Promise<ReportDataResponse> {
    const response = await apiClient.post('/api/v1/reports/generate', data);
    return response.data;
  },

  async getReportData(templateId: string, params?: {
    dateRange?: DateRange;
    filters?: ReportFilter[];
  }): Promise<ReportDataResponse> {
    const response = await apiClient.get(`/api/v1/reports/templates/${templateId}/data`, { params });
    return response.data;
  },

  // Report Scheduling
  async getSchedules(params?: {
    templateId?: string;
    enabled?: boolean;
    limit?: number;
    offset?: number;
  }): Promise<{ items: ReportSchedule[]; total: number }> {
    const response = await apiClient.get('/api/v1/reports/schedules', { params });
    return response.data;
  },

  async getSchedule(id: string): Promise<ReportSchedule> {
    const response = await apiClient.get(`/api/v1/reports/schedules/${id}`);
    return response.data;
  },

  async createSchedule(data: Omit<ReportSchedule, 'id' | 'createdAt' | 'updatedAt' | 'lastRunAt' | 'nextRunAt'>): Promise<ReportSchedule> {
    const response = await apiClient.post('/api/v1/reports/schedules', data);
    return response.data;
  },

  async updateSchedule(id: string, data: Partial<ReportSchedule>): Promise<ReportSchedule> {
    const response = await apiClient.put(`/api/v1/reports/schedules/${id}`, data);
    return response.data;
  },

  async deleteSchedule(id: string): Promise<void> {
    await apiClient.delete(`/api/v1/reports/schedules/${id}`);
  },

  async runSchedule(id: string): Promise<{ message: string }> {
    const response = await apiClient.post(`/api/v1/reports/schedules/${id}/run`);
    return response.data;
  },

  // Report Exports
  async exportReport(templateId: string, format: 'pdf' | 'excel' | 'csv' | 'png'): Promise<ReportExport> {
    const response = await apiClient.post(`/api/v1/reports/templates/${templateId}/export`, { format });
    return response.data;
  },

  async getExport(id: string): Promise<ReportExport> {
    const response = await apiClient.get(`/api/v1/reports/exports/${id}`);
    return response.data;
  },

  async downloadExport(id: string): Promise<Blob> {
    const response = await apiClient.get(`/api/v1/reports/exports/${id}/download`, {
      responseType: 'blob',
    });
    return response.data;
  },

  // Report Builder Configuration
  async getBuilderConfig(): Promise<ReportBuilderConfig> {
    const response = await apiClient.get('/api/v1/reports/builder-config');
    return response.data;
  },

  // Predefined report templates
  async getPredefinedTemplates(): Promise<ReportTemplate[]> {
    const response = await apiClient.get('/api/v1/reports/templates/predefined');
    return response.data;
  },

  // Analytics data endpoints
  async getRevenueMetrics(params: {
    startDate: string;
    endDate: string;
    groupBy?: 'day' | 'week' | 'month';
    modelId?: string;
  }): Promise<any> {
    const response = await apiClient.get('/api/v1/reports/analytics/revenue', { params });
    return response.data;
  },

  async getUserActivityMetrics(params: {
    startDate: string;
    endDate: string;
    groupBy?: 'day' | 'week' | 'month';
    modelId?: string;
  }): Promise<any> {
    const response = await apiClient.get('/api/v1/reports/analytics/user-activity', { params });
    return response.data;
  },

  async getMessageMetrics(params: {
    startDate: string;
    endDate: string;
    groupBy?: 'day' | 'week' | 'month';
    modelId?: string;
  }): Promise<any> {
    const response = await apiClient.get('/api/v1/reports/analytics/messages', { params });
    return response.data;
  },

  async getContentMetrics(params: {
    startDate: string;
    endDate: string;
    groupBy?: 'day' | 'week' | 'month';
    modelId?: string;
  }): Promise<any> {
    const response = await apiClient.get('/api/v1/reports/analytics/content', { params });
    return response.data;
  },
};
