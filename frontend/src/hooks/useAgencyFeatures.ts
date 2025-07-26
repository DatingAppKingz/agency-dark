import { useState, useCallback, useEffect } from 'react';
import { useAuthStore } from '@/store/auth';
import {
  Feature,
  AgencyFeatureConfig,
  CustomModule,
  Integration,
  FeatureUsage,
  FEATURE_CATALOG,
  IntegrationType,
} from '@/types/agencyFeatures';

const STORAGE_KEY = 'agency_features';

// Mock API service - replace with actual API calls
const agencyFeaturesApi = {
  getConfig: async (agencyId: string): Promise<AgencyFeatureConfig> => {
    const stored = localStorage.getItem(`${STORAGE_KEY}_${agencyId}`);
    if (stored) {
      return JSON.parse(stored);
    }
    
    // Default config
    return {
      agencyId,
      features: FEATURE_CATALOG.map(f => ({ ...f, enabled: false })),
      customModules: [],
      integrations: [],
      limits: {
        users: { current: 0, max: 50 },
        models: { current: 0, max: 20 },
        chatters: { current: 0, max: 30 },
        storage: { current: 0, max: 10240, unit: 'MB' },
        apiCalls: { current: 0, max: 10000, unit: 'per month' },
        customLimits: {},
      },
      updatedAt: new Date(),
    };
  },
  
  saveConfig: async (config: AgencyFeatureConfig): Promise<void> => {
    localStorage.setItem(`${STORAGE_KEY}_${config.agencyId}`, JSON.stringify(config));
  },
  
  getUsage: async (agencyId: string, featureId: string): Promise<FeatureUsage[]> => {
    // Mock usage data
    return [];
  },
};

export const useAgencyFeatures = () => {
  const { user } = useAuthStore();
  const [config, setConfig] = useState<AgencyFeatureConfig | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);

  // Load configuration
  useEffect(() => {
    const loadConfig = async () => {
      if (!user?.agencyId) return;
      
      setIsLoading(true);
      try {
        const featureConfig = await agencyFeaturesApi.getConfig(user.agencyId);
        setConfig(featureConfig);
      } catch (error) {
        console.error('Error loading agency features:', error);
      } finally {
        setIsLoading(false);
      }
    };
    
    loadConfig();
  }, [user?.agencyId]);

  // Save configuration
  const saveConfig = useCallback(async (newConfig: AgencyFeatureConfig) => {
    setIsSaving(true);
    try {
      await agencyFeaturesApi.saveConfig(newConfig);
      setConfig(newConfig);
    } catch (error) {
      console.error('Error saving agency features:', error);
      throw error;
    } finally {
      setIsSaving(false);
    }
  }, []);

  // Toggle feature
  const toggleFeature = useCallback(async (featureId: string) => {
    if (!config) return;
    
    const updatedConfig = {
      ...config,
      features: config.features.map(feature =>
        feature.id === featureId
          ? { ...feature, enabled: !feature.enabled }
          : feature
      ),
      updatedAt: new Date(),
    };
    
    await saveConfig(updatedConfig);
  }, [config, saveConfig]);

  // Update feature settings
  const updateFeatureSettings = useCallback(async (featureId: string, settings: Record<string, any>) => {
    if (!config) return;
    
    const updatedConfig = {
      ...config,
      features: config.features.map(feature =>
        feature.id === featureId
          ? { ...feature, settings: { ...feature.settings, ...settings } }
          : feature
      ),
      updatedAt: new Date(),
    };
    
    await saveConfig(updatedConfig);
  }, [config, saveConfig]);

  // Add custom module
  const addCustomModule = useCallback(async (module: Omit<CustomModule, 'id'>) => {
    if (!config) return;
    
    const newModule: CustomModule = {
      ...module,
      id: `module_${Date.now()}`,
    };
    
    const updatedConfig = {
      ...config,
      customModules: [...config.customModules, newModule],
      updatedAt: new Date(),
    };
    
    await saveConfig(updatedConfig);
    return newModule;
  }, [config, saveConfig]);

  // Update custom module
  const updateCustomModule = useCallback(async (moduleId: string, updates: Partial<CustomModule>) => {
    if (!config) return;
    
    const updatedConfig = {
      ...config,
      customModules: config.customModules.map(module =>
        module.id === moduleId
          ? { ...module, ...updates }
          : module
      ),
      updatedAt: new Date(),
    };
    
    await saveConfig(updatedConfig);
  }, [config, saveConfig]);

  // Delete custom module
  const deleteCustomModule = useCallback(async (moduleId: string) => {
    if (!config) return;
    
    const updatedConfig = {
      ...config,
      customModules: config.customModules.filter(module => module.id !== moduleId),
      updatedAt: new Date(),
    };
    
    await saveConfig(updatedConfig);
  }, [config, saveConfig]);

  // Add integration
  const addIntegration = useCallback(async (type: IntegrationType, name: string, config: Record<string, any>) => {
    if (!config) return;
    
    const newIntegration: Integration = {
      id: `integration_${Date.now()}`,
      type,
      name,
      enabled: false,
      config,
      status: 'disconnected',
    };
    
    const updatedConfig = {
      ...config,
      integrations: [...config.integrations, newIntegration],
      updatedAt: new Date(),
    };
    
    await saveConfig(updatedConfig);
    return newIntegration;
  }, [config, saveConfig]);

  // Update integration
  const updateIntegration = useCallback(async (integrationId: string, updates: Partial<Integration>) => {
    if (!config) return;
    
    const updatedConfig = {
      ...config,
      integrations: config.integrations.map(integration =>
        integration.id === integrationId
          ? { ...integration, ...updates }
          : integration
      ),
      updatedAt: new Date(),
    };
    
    await saveConfig(updatedConfig);
  }, [config, saveConfig]);

  // Delete integration
  const deleteIntegration = useCallback(async (integrationId: string) => {
    if (!config) return;
    
    const updatedConfig = {
      ...config,
      integrations: config.integrations.filter(integration => integration.id !== integrationId),
      updatedAt: new Date(),
    };
    
    await saveConfig(updatedConfig);
  }, [config, saveConfig]);

  // Check if feature is enabled
  const isFeatureEnabled = useCallback((featureId: string): boolean => {
    if (!config) return false;
    const feature = config.features.find(f => f.id === featureId);
    return feature?.enabled || false;
  }, [config]);

  // Get feature by ID
  const getFeature = useCallback((featureId: string): Feature | undefined => {
    if (!config) return undefined;
    return config.features.find(f => f.id === featureId);
  }, [config]);

  // Check limit
  const checkLimit = useCallback((limitType: keyof AgencyFeatureConfig['limits']): boolean => {
    if (!config) return false;
    const limit = config.limits[limitType];
    if (!limit || typeof limit !== 'object') return true;
    return limit.current < limit.max;
  }, [config]);

  // Get limit usage percentage
  const getLimitUsage = useCallback((limitType: keyof AgencyFeatureConfig['limits']): number => {
    if (!config) return 0;
    const limit = config.limits[limitType];
    if (!limit || typeof limit !== 'object') return 0;
    return (limit.current / limit.max) * 100;
  }, [config]);

  return {
    config,
    isLoading,
    isSaving,
    toggleFeature,
    updateFeatureSettings,
    addCustomModule,
    updateCustomModule,
    deleteCustomModule,
    addIntegration,
    updateIntegration,
    deleteIntegration,
    isFeatureEnabled,
    getFeature,
    checkLimit,
    getLimitUsage,
  };
};