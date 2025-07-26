// Dashboard customization types

export type WidgetType = 
  | 'stats-card'
  | 'chart'
  | 'activity-feed'
  | 'metrics-grid'
  | 'quick-actions'
  | 'recent-items'
  | 'calendar'
  | 'tasks'
  | 'custom';

export interface WidgetConfig {
  id: string;
  type: WidgetType;
  title: string;
  description?: string;
  position: {
    x: number;
    y: number;
    w: number;
    h: number;
  };
  settings?: Record<string, any>;
  permissions?: string[];
  visible: boolean;
}

export interface DashboardLayout {
  id: string;
  name: string;
  description?: string;
  widgets: WidgetConfig[];
  gridCols: number;
  rowHeight: number;
  isDefault?: boolean;
  createdAt: Date;
  updatedAt: Date;
}

export interface UserDashboardPreferences {
  userId: string;
  role: string;
  selectedLayoutId?: string;
  customLayouts: DashboardLayout[];
  widgetSettings: Record<string, any>;
  theme?: {
    primaryColor?: string;
    secondaryColor?: string;
    darkMode?: boolean;
  };
}

export interface WidgetRegistry {
  [key: string]: {
    component: React.ComponentType<any>;
    defaultSettings?: Record<string, any>;
    settingsComponent?: React.ComponentType<any>;
    minWidth?: number;
    minHeight?: number;
    maxWidth?: number;
    maxHeight?: number;
  };
}