// Agency-specific features management types

export interface Feature {
  id: string;
  name: string;
  description: string;
  category: FeatureCategory;
  enabled: boolean;
  permissions?: string[];
  settings?: Record<string, any>;
  limits?: FeatureLimits;
}

export type FeatureCategory = 
  | 'chat'
  | 'analytics'
  | 'financial'
  | 'models'
  | 'automation'
  | 'integrations'
  | 'security'
  | 'customization';

export interface FeatureLimits {
  maxUsers?: number;
  maxModels?: number;
  maxChatters?: number;
  maxTransactions?: number;
  maxStorage?: number; // in MB
  maxApiCalls?: number;
  maxRecipients?: number;
  customLimits?: Record<string, number>;
}

export interface AgencyFeatureConfig {
  agencyId: string;
  features: Feature[];
  customModules: CustomModule[];
  integrations: Integration[];
  limits: AgencyLimits;
  updatedAt: Date;
}

export interface CustomModule {
  id: string;
  name: string;
  description: string;
  icon?: string;
  route: string;
  component: string;
  permissions: string[];
  enabled: boolean;
  order: number;
}

export interface Integration {
  id: string;
  type: IntegrationType;
  name: string;
  enabled: boolean;
  config: Record<string, any>;
  lastSync?: Date;
  status: 'connected' | 'disconnected' | 'error';
}

export type IntegrationType = 
  | 'onlyfans'
  | 'payment_processor'
  | 'email'
  | 'sms'
  | 'analytics'
  | 'storage'
  | 'crm'
  | 'accounting'
  | 'webhook';

export interface AgencyLimits {
  users: LimitConfig;
  models: LimitConfig;
  chatters: LimitConfig;
  storage: LimitConfig;
  apiCalls: LimitConfig;
  customLimits: Record<string, LimitConfig>;
}

export interface LimitConfig {
  current: number;
  max: number;
  unit?: string;
  warningThreshold?: number; // percentage
}

export interface FeatureUsage {
  featureId: string;
  agencyId: string;
  period: 'daily' | 'weekly' | 'monthly';
  usage: number;
  limit: number;
  timestamp: Date;
}

// Predefined features catalog
export const FEATURE_CATALOG: Feature[] = [
  // Chat Features
  {
    id: 'chat-automation',
    name: 'Chat Automation',
    description: 'Automated responses and chat workflows',
    category: 'chat',
    enabled: false,
    settings: {
      enableAutoResponses: true,
      responseDelay: 2000,
      maxAutoResponses: 10,
    },
  },
  {
    id: 'voice-messages',
    name: 'Voice Messages',
    description: 'Send and receive voice messages in chat',
    category: 'chat',
    enabled: false,
  },
  {
    id: 'mass-messaging',
    name: 'Mass Messaging',
    description: 'Send bulk messages to multiple fans',
    category: 'chat',
    enabled: false,
    limits: {
      maxRecipients: 100,
    },
  },
  
  // Analytics Features
  {
    id: 'advanced-analytics',
    name: 'Advanced Analytics',
    description: 'Detailed analytics and reporting',
    category: 'analytics',
    enabled: false,
  },
  {
    id: 'predictive-insights',
    name: 'Predictive Insights',
    description: 'AI-powered predictive analytics',
    category: 'analytics',
    enabled: false,
  },
  {
    id: 'custom-reports',
    name: 'Custom Reports',
    description: 'Create and schedule custom reports',
    category: 'analytics',
    enabled: false,
  },
  
  // Financial Features
  {
    id: 'automated-payouts',
    name: 'Automated Payouts',
    description: 'Automatic payout distribution',
    category: 'financial',
    enabled: false,
  },
  {
    id: 'tax-reporting',
    name: 'Tax Reporting',
    description: 'Generate tax reports and forms',
    category: 'financial',
    enabled: false,
  },
  {
    id: 'multi-currency',
    name: 'Multi-Currency Support',
    description: 'Support for multiple currencies',
    category: 'financial',
    enabled: false,
  },
  
  // Model Features
  {
    id: 'model-onboarding',
    name: 'Automated Model Onboarding',
    description: 'Streamlined onboarding process for new models',
    category: 'models',
    enabled: false,
  },
  {
    id: 'performance-tracking',
    name: 'Model Performance Tracking',
    description: 'Track and analyze model performance',
    category: 'models',
    enabled: false,
  },
  {
    id: 'content-scheduling',
    name: 'Content Scheduling',
    description: 'Schedule content posts in advance',
    category: 'models',
    enabled: false,
  },
  
  // Security Features
  {
    id: 'two-factor-auth',
    name: 'Two-Factor Authentication',
    description: 'Enhanced security with 2FA',
    category: 'security',
    enabled: false,
  },
  {
    id: 'ip-whitelist',
    name: 'IP Whitelisting',
    description: 'Restrict access by IP address',
    category: 'security',
    enabled: false,
  },
  {
    id: 'audit-logs',
    name: 'Audit Logs',
    description: 'Detailed activity logs',
    category: 'security',
    enabled: false,
  },
];
