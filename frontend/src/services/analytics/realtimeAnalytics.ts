import { EventEmitter } from '@/utils/EventEmitter';
import apiClient from '../api/client';

export enum MetricType {
  REVENUE = 'revenue',
  SUBSCRIBERS = 'subscribers',
  CONTENT_VIEWS = 'content_views',
  MESSAGES = 'messages',
  CONVERSION_RATE = 'conversion_rate',
  ENGAGEMENT_RATE = 'engagement_rate',
  CHURN_RATE = 'churn_rate',
  AVERAGE_ORDER_VALUE = 'average_order_value',
  LIFETIME_VALUE = 'lifetime_value'
}

export enum TimeWindow {
  MINUTE = '1m',
  FIVE_MINUTES = '5m',
  FIFTEEN_MINUTES = '15m',
  HOUR = '1h',
  DAY = '1d',
  WEEK = '1w',
  MONTH = '1mo'
}

export interface MetricData {
  value: number;
  count: number;
  min: number;
  max: number;
  avg: number;
  std_dev: number;
  timestamp: string;
}

export interface MetricUpdate {
  metric_type: MetricType;
  value: number;
  timestamp?: string;
  dimensions?: Record<string, any>;
  metadata?: Record<string, any>;
}

export interface RealtimeMetrics {
  [key: string]: MetricData[];
}

export interface MetricSummary {
  revenue: {
    total: number;
    count: number;
    average: number;
  };
  subscribers: {
    total: number;
    new: number;
    growth_rate: number;
  };
  engagement: {
    message_count: number;
    content_views: number;
    avg_response_time: number;
  };
  performance: {
    avg_processing_time: number;
    error_counts: Record<string, number>;
    active_subscribers: number;
  };
}

class RealtimeAnalyticsService extends EventEmitter {
  private ws: WebSocket | null = null;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectTimeout: number | null = null;
  private pingInterval: number | null = null;
  private agencyId: string | null = null;
  private modelId: string | null = null;
  private token: string | null = null;

  constructor() {
    super();
    this.setMaxListeners(20);
  }

  async connect(agencyId: string, modelId?: string, token?: string) {
    this.agencyId = agencyId;
    this.modelId = modelId || null;
    this.token = token || localStorage.getItem('auth_token') || null;

    if (!this.token) {
      throw new Error('Authentication token not found');
    }

    this.establishConnection();
  }

  private establishConnection() {
    if (this.ws?.readyState === WebSocket.OPEN) {
      return;
    }

    const wsUrl = this.buildWebSocketUrl();

    try {
      this.ws = new WebSocket(wsUrl);
      this.setupEventHandlers();
    } catch (error) {
      console.error('Failed to create WebSocket:', error);
      this.emit('error', error);
    }
  }

  private buildWebSocketUrl(): string {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = import.meta.env.VITE_WS_URL?.replace(/^wss?:\/\//, '') || window.location.host;
    let url = `${protocol}//${host}/api/v1/analytics/realtime/ws/${this.agencyId}`;
    
    if (this.modelId) {
      url += `?model_id=${this.modelId}`;
    }

    // Add auth token to URL
    const separator = this.modelId ? '&' : '?';
    url += `${separator}token=${this.token}`;

    return url;
  }

  private setupEventHandlers() {
    if (!this.ws) return;

    this.ws.onopen = () => {
      console.log('WebSocket connected');
      this.reconnectAttempts = 0;
      this.emit('connected');
      this.startPingInterval();
    };

    this.ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        this.handleMessage(data);
      } catch (error) {
        console.error('Failed to parse WebSocket message:', error);
      }
    };

    this.ws.onerror = (error) => {
      console.error('WebSocket error:', error);
      this.emit('error', error);
    };

    this.ws.onclose = () => {
      console.log('WebSocket disconnected');
      this.emit('disconnected');
      this.stopPingInterval();
      this.attemptReconnect();
    };
  }

  private handleMessage(data: any) {
    switch (data.type) {
      case 'initial':
        this.emit('initial', data.data);
        break;
      case 'update':
        this.emit('update', data.metrics);
        break;
      case 'error':
        this.emit('error', new Error(data.message));
        break;
      case 'pong':
        // Ping response received
        break;
      default:
        console.warn('Unknown message type:', data.type);
    }
  }

  private startPingInterval() {
    this.pingInterval = window.setInterval(() => {
      if (this.ws?.readyState === WebSocket.OPEN) {
        this.ws.send(JSON.stringify({ type: 'ping' }));
      }
    }, 30000); // Ping every 30 seconds
  }

  private stopPingInterval() {
    if (this.pingInterval) {
      clearInterval(this.pingInterval);
      this.pingInterval = null;
    }
  }

  private attemptReconnect() {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      this.emit('max_reconnect_reached');
      return;
    }

    const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts), 30000);
    this.reconnectAttempts++;

    this.reconnectTimeout = window.setTimeout(() => {
      console.log(`Attempting to reconnect (${this.reconnectAttempts}/${this.maxReconnectAttempts})`);
      this.establishConnection();
    }, delay);
  }

  subscribe(metrics: MetricType[]) {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({
        type: 'subscribe',
        metrics: metrics
      }));
    }
  }

  unsubscribe(metrics: MetricType[]) {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({
        type: 'unsubscribe',
        metrics: metrics
      }));
    }
  }

  disconnect() {
    if (this.reconnectTimeout) {
      clearTimeout(this.reconnectTimeout);
      this.reconnectTimeout = null;
    }

    this.stopPingInterval();

    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }

    this.removeAllListeners();
  }

  // HTTP API methods

  async getRealtimeMetrics(
    metricTypes: MetricType[],
    window: TimeWindow = TimeWindow.MINUTE,
    limit: number = 100,
    dimensions?: Record<string, any>
  ): Promise<RealtimeMetrics> {
    const params = new URLSearchParams();
    metricTypes.forEach(type => params.append('metric_types', type));
    params.append('window', window);
    params.append('limit', limit.toString());

    if (dimensions) {
      Object.entries(dimensions).forEach(([key, value]) => {
        params.append(key, value);
      });
    }

    const response = await apiClient.get(`/api/v1/analytics/realtime/metrics?${params}`);
    return response.data.metrics;
  }

  async getAnalyticsSummary(
    startDate?: Date,
    endDate?: Date
  ): Promise<MetricSummary> {
    const params = new URLSearchParams();
    if (startDate) {
      params.append('start_date', startDate.toISOString());
    }
    if (endDate) {
      params.append('end_date', endDate.toISOString());
    }

    const response = await apiClient.get(`/api/v1/analytics/realtime/summary?${params}`);
    return response.data;
  }

  async trackMetric(update: MetricUpdate): Promise<void> {
    await apiClient.post('/api/v1/analytics/realtime/track', update);
  }

  async getPerformanceMetrics(): Promise<any> {
    const response = await apiClient.get('/api/v1/analytics/realtime/performance');
    return response.data;
  }
}

// Singleton instance
const realtimeAnalyticsService = new RealtimeAnalyticsService();

export default realtimeAnalyticsService;