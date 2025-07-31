export enum ReportType {
  REVENUE = 'revenue',
  USER_ACTIVITY = 'user_activity',
  MESSAGE_ANALYTICS = 'message_analytics',
  CONTENT_PERFORMANCE = 'content_performance',
  SUBSCRIPTION_METRICS = 'subscription_metrics',
  CUSTOM = 'custom',
}

export enum ChartType {
  LINE = 'line',
  BAR = 'bar',
  PIE = 'pie',
  AREA = 'area',
  SCATTER = 'scatter',
  HEATMAP = 'heatmap',
  TABLE = 'table',
  METRIC_CARD = 'metric_card',
}

export enum AggregationType {
  SUM = 'sum',
  AVERAGE = 'average',
  COUNT = 'count',
  MIN = 'min',
  MAX = 'max',
  DISTINCT = 'distinct',
}

export enum DateRangeType {
  TODAY = 'today',
  YESTERDAY = 'yesterday',
  LAST_7_DAYS = 'last_7_days',
  LAST_30_DAYS = 'last_30_days',
  LAST_90_DAYS = 'last_90_days',
  THIS_MONTH = 'this_month',
  LAST_MONTH = 'last_month',
  THIS_YEAR = 'this_year',
  CUSTOM = 'custom',
}

export interface ReportMetric {
  id: string;
  name: string;
  field: string;
  aggregation: AggregationType;
  format?: 'number' | 'currency' | 'percentage' | 'duration';
  color?: string;
}

export interface ReportDimension {
  id: string;
  name: string;
  field: string;
  type: 'date' | 'string' | 'number' | 'boolean';
  groupBy?: 'day' | 'week' | 'month' | 'year';
}

export interface ReportFilter {
  id: string;
  field: string;
  operator: 'equals' | 'not_equals' | 'contains' | 'greater_than' | 'less_than' | 'between' | 'in';
  value: any;
  label?: string;
}

export interface ChartConfig {
  type: ChartType;
  title: string;
  subtitle?: string;
  metrics: ReportMetric[];
  dimensions: ReportDimension[];
  filters: ReportFilter[];
  options?: {
    showLegend?: boolean;
    showGrid?: boolean;
    showTooltip?: boolean;
    showDataLabels?: boolean;
    stacked?: boolean;
    smooth?: boolean;
    colorScheme?: string;
  };
}

export interface ReportWidget {
  id: string;
  x: number;
  y: number;
  w: number;
  h: number;
  chartConfig: ChartConfig;
  data?: any;
  loading?: boolean;
  error?: string;
}

export interface ReportTemplate {
  id: string;
  name: string;
  description?: string;
  type: ReportType;
  widgets: ReportWidget[];
  globalFilters: ReportFilter[];
  dateRange: {
    type: DateRangeType;
    startDate?: string;
    endDate?: string;
  };
  refreshInterval?: number; // in seconds
  isPublic: boolean;
  createdBy: string;
  createdAt: string;
  updatedAt: string;
}

export interface ReportSchedule {
  id: string;
  reportTemplateId: string;
  name: string;
  enabled: boolean;
  frequency: 'daily' | 'weekly' | 'monthly';
  dayOfWeek?: number; // 0-6 for weekly
  dayOfMonth?: number; // 1-31 for monthly
  time: string; // HH:MM format
  recipients: string[];
  format: 'pdf' | 'excel' | 'csv';
  lastRunAt?: string;
  nextRunAt: string;
  createdAt: string;
  updatedAt: string;
}

export interface ReportExport {
  id: string;
  reportTemplateId: string;
  format: 'pdf' | 'excel' | 'csv' | 'png';
  status: 'pending' | 'processing' | 'completed' | 'failed';
  downloadUrl?: string;
  expiresAt?: string;
  createdAt: string;
  completedAt?: string;
  error?: string;
}

// Available metrics and dimensions for the report builder
export interface ReportBuilderConfig {
  metrics: {
    revenue: ReportMetric[];
    users: ReportMetric[];
    messages: ReportMetric[];
    content: ReportMetric[];
    subscriptions: ReportMetric[];
  };
  dimensions: {
    time: ReportDimension[];
    user: ReportDimension[];
    content: ReportDimension[];
    platform: ReportDimension[];
  };
  filters: {
    field: string;
    label: string;
    type: 'text' | 'number' | 'date' | 'select';
    operators: string[];
    options?: { value: string; label: string }[];
  }[];
}

export interface SaveReportTemplateRequest {
  name: string;
  description?: string;
  type: ReportType;
  widgets: Omit<ReportWidget, 'data' | 'loading' | 'error'>[];
  globalFilters: ReportFilter[];
  dateRange: {
    type: DateRangeType;
    startDate?: string;
    endDate?: string;
  };
  refreshInterval?: number;
  isPublic: boolean;
}

export interface GenerateReportRequest {
  templateId?: string;
  widgets?: ChartConfig[];
  dateRange: {
    type: DateRangeType;
    startDate?: string;
    endDate?: string;
  };
  filters?: ReportFilter[];
  format?: 'json' | 'csv';
}

export interface ReportDataResponse {
  widgets: {
    widgetId: string;
    data: any;
    metadata?: {
      totalRows: number;
      executionTime: number;
      cached: boolean;
    };
  }[];
  generatedAt: string;
}
