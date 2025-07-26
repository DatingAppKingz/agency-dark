import { useState, useCallback, useEffect } from 'react';
import { useAuthStore } from '@/store/authStore';
import { 
  DashboardLayout, 
  UserDashboardPreferences, 
  WidgetConfig 
} from '@/types/dashboard';

const STORAGE_KEY = 'dashboard_preferences';

// Default layouts for different roles
const defaultLayouts: Record<string, DashboardLayout> = {
  SUPER_ADMIN: {
    id: 'default-super-admin',
    name: 'Super Admin Dashboard',
    gridCols: 12,
    rowHeight: 60,
    isDefault: true,
    createdAt: new Date(),
    updatedAt: new Date(),
    widgets: [
      {
        id: 'platform-stats',
        type: 'stats-card',
        title: 'Platform Overview',
        position: { x: 0, y: 0, w: 12, h: 2 },
        visible: true,
      },
      {
        id: 'revenue-chart',
        type: 'chart',
        title: 'Revenue Trends',
        position: { x: 0, y: 2, w: 8, h: 4 },
        settings: { chartType: 'line', period: '30d' },
        visible: true,
      },
      {
        id: 'activity-feed',
        type: 'activity-feed',
        title: 'Recent Activity',
        position: { x: 8, y: 2, w: 4, h: 4 },
        visible: true,
      },
    ],
  },
  AGENCY_OWNER: {
    id: 'default-agency-owner',
    name: 'Agency Owner Dashboard',
    gridCols: 12,
    rowHeight: 60,
    isDefault: true,
    createdAt: new Date(),
    updatedAt: new Date(),
    widgets: [
      {
        id: 'agency-stats',
        type: 'stats-card',
        title: 'Agency Performance',
        position: { x: 0, y: 0, w: 12, h: 2 },
        visible: true,
      },
      {
        id: 'model-metrics',
        type: 'metrics-grid',
        title: 'Model Performance',
        position: { x: 0, y: 2, w: 6, h: 4 },
        visible: true,
      },
      {
        id: 'revenue-chart',
        type: 'chart',
        title: 'Revenue Overview',
        position: { x: 6, y: 2, w: 6, h: 4 },
        settings: { chartType: 'bar', period: '7d' },
        visible: true,
      },
    ],
  },
  MODEL: {
    id: 'default-model',
    name: 'Model Dashboard',
    gridCols: 12,
    rowHeight: 60,
    isDefault: true,
    createdAt: new Date(),
    updatedAt: new Date(),
    widgets: [
      {
        id: 'earnings-stats',
        type: 'stats-card',
        title: 'Earnings Overview',
        position: { x: 0, y: 0, w: 12, h: 2 },
        visible: true,
      },
      {
        id: 'subscriber-chart',
        type: 'chart',
        title: 'Subscriber Growth',
        position: { x: 0, y: 2, w: 6, h: 3 },
        settings: { chartType: 'line', period: '30d' },
        visible: true,
      },
      {
        id: 'recent-messages',
        type: 'recent-items',
        title: 'Recent Messages',
        position: { x: 6, y: 2, w: 6, h: 3 },
        visible: true,
      },
    ],
  },
};

export const useDashboardCustomization = () => {
  const { user } = useAuthStore();
  const [preferences, setPreferences] = useState<UserDashboardPreferences | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // Load preferences from localStorage
  useEffect(() => {
    if (user) {
      const stored = localStorage.getItem(`${STORAGE_KEY}_${user.id}`);
      if (stored) {
        setPreferences(JSON.parse(stored));
      } else {
        // Initialize with default layout
        const defaultLayout = defaultLayouts[user.role] || defaultLayouts.MODEL;
        const newPreferences: UserDashboardPreferences = {
          userId: user.id,
          role: user.role,
          customLayouts: [defaultLayout],
          selectedLayoutId: defaultLayout.id,
          widgetSettings: {},
        };
        setPreferences(newPreferences);
        localStorage.setItem(`${STORAGE_KEY}_${user.id}`, JSON.stringify(newPreferences));
      }
    }
    setIsLoading(false);
  }, [user]);

  // Save preferences
  const savePreferences = useCallback((newPreferences: UserDashboardPreferences) => {
    if (user) {
      localStorage.setItem(`${STORAGE_KEY}_${user.id}`, JSON.stringify(newPreferences));
      setPreferences(newPreferences);
    }
  }, [user]);

  // Get current layout
  const getCurrentLayout = useCallback((): DashboardLayout | null => {
    if (!preferences) return null;
    return preferences.customLayouts.find(
      layout => layout.id === preferences.selectedLayoutId
    ) || preferences.customLayouts[0];
  }, [preferences]);

  // Update widget position
  const updateWidgetPosition = useCallback((widgetId: string, position: WidgetConfig['position']) => {
    if (!preferences) return;
    
    const currentLayout = getCurrentLayout();
    if (!currentLayout) return;

    const updatedLayout = {
      ...currentLayout,
      widgets: currentLayout.widgets.map(widget =>
        widget.id === widgetId ? { ...widget, position } : widget
      ),
      updatedAt: new Date(),
    };

    const updatedPreferences = {
      ...preferences,
      customLayouts: preferences.customLayouts.map(layout =>
        layout.id === currentLayout.id ? updatedLayout : layout
      ),
    };

    savePreferences(updatedPreferences);
  }, [preferences, getCurrentLayout, savePreferences]);

  // Toggle widget visibility
  const toggleWidgetVisibility = useCallback((widgetId: string) => {
    if (!preferences) return;
    
    const currentLayout = getCurrentLayout();
    if (!currentLayout) return;

    const updatedLayout = {
      ...currentLayout,
      widgets: currentLayout.widgets.map(widget =>
        widget.id === widgetId ? { ...widget, visible: !widget.visible } : widget
      ),
      updatedAt: new Date(),
    };

    const updatedPreferences = {
      ...preferences,
      customLayouts: preferences.customLayouts.map(layout =>
        layout.id === currentLayout.id ? updatedLayout : layout
      ),
    };

    savePreferences(updatedPreferences);
  }, [preferences, getCurrentLayout, savePreferences]);

  // Add widget
  const addWidget = useCallback((widget: WidgetConfig) => {
    if (!preferences) return;
    
    const currentLayout = getCurrentLayout();
    if (!currentLayout) return;

    const updatedLayout = {
      ...currentLayout,
      widgets: [...currentLayout.widgets, widget],
      updatedAt: new Date(),
    };

    const updatedPreferences = {
      ...preferences,
      customLayouts: preferences.customLayouts.map(layout =>
        layout.id === currentLayout.id ? updatedLayout : layout
      ),
    };

    savePreferences(updatedPreferences);
  }, [preferences, getCurrentLayout, savePreferences]);

  // Remove widget
  const removeWidget = useCallback((widgetId: string) => {
    if (!preferences) return;
    
    const currentLayout = getCurrentLayout();
    if (!currentLayout) return;

    const updatedLayout = {
      ...currentLayout,
      widgets: currentLayout.widgets.filter(widget => widget.id !== widgetId),
      updatedAt: new Date(),
    };

    const updatedPreferences = {
      ...preferences,
      customLayouts: preferences.customLayouts.map(layout =>
        layout.id === currentLayout.id ? updatedLayout : layout
      ),
    };

    savePreferences(updatedPreferences);
  }, [preferences, getCurrentLayout, savePreferences]);

  // Update widget settings
  const updateWidgetSettings = useCallback((widgetId: string, settings: Record<string, any>) => {
    if (!preferences) return;
    
    const currentLayout = getCurrentLayout();
    if (!currentLayout) return;

    const updatedLayout = {
      ...currentLayout,
      widgets: currentLayout.widgets.map(widget =>
        widget.id === widgetId ? { ...widget, settings: { ...widget.settings, ...settings } } : widget
      ),
      updatedAt: new Date(),
    };

    const updatedPreferences = {
      ...preferences,
      customLayouts: preferences.customLayouts.map(layout =>
        layout.id === currentLayout.id ? updatedLayout : layout
      ),
    };

    savePreferences(updatedPreferences);
  }, [preferences, getCurrentLayout, savePreferences]);

  // Create new layout
  const createLayout = useCallback((name: string, description?: string) => {
    if (!preferences) return;

    const newLayout: DashboardLayout = {
      id: `custom-${Date.now()}`,
      name,
      description,
      widgets: [],
      gridCols: 12,
      rowHeight: 60,
      isDefault: false,
      createdAt: new Date(),
      updatedAt: new Date(),
    };

    const updatedPreferences = {
      ...preferences,
      customLayouts: [...preferences.customLayouts, newLayout],
      selectedLayoutId: newLayout.id,
    };

    savePreferences(updatedPreferences);
  }, [preferences, savePreferences]);

  // Delete layout
  const deleteLayout = useCallback((layoutId: string) => {
    if (!preferences) return;

    const layoutToDelete = preferences.customLayouts.find(l => l.id === layoutId);
    if (!layoutToDelete || layoutToDelete.isDefault) return;

    const updatedPreferences = {
      ...preferences,
      customLayouts: preferences.customLayouts.filter(l => l.id !== layoutId),
      selectedLayoutId: preferences.selectedLayoutId === layoutId 
        ? preferences.customLayouts[0].id 
        : preferences.selectedLayoutId,
    };

    savePreferences(updatedPreferences);
  }, [preferences, savePreferences]);

  // Switch layout
  const switchLayout = useCallback((layoutId: string) => {
    if (!preferences) return;

    const updatedPreferences = {
      ...preferences,
      selectedLayoutId: layoutId,
    };

    savePreferences(updatedPreferences);
  }, [preferences, savePreferences]);

  // Reset to default
  const resetToDefault = useCallback(() => {
    if (!user) return;

    const defaultLayout = defaultLayouts[user.role] || defaultLayouts.MODEL;
    const newPreferences: UserDashboardPreferences = {
      userId: user.id,
      role: user.role,
      customLayouts: [defaultLayout],
      selectedLayoutId: defaultLayout.id,
      widgetSettings: {},
    };

    savePreferences(newPreferences);
  }, [user, savePreferences]);

  return {
    preferences,
    currentLayout: getCurrentLayout(),
    isLoading,
    updateWidgetPosition,
    toggleWidgetVisibility,
    addWidget,
    removeWidget,
    updateWidgetSettings,
    createLayout,
    deleteLayout,
    switchLayout,
    resetToDefault,
  };
};