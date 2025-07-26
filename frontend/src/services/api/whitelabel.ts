import apiClient from './client';

export interface ThemeSettings {
  primary_color: string;
  secondary_color: string;
  accent_color: string;
  background_color: string;
  text_color: string;
  font_family: string;
  border_radius: string;
  button_style: 'rounded' | 'square' | 'pill';
}

export interface BrandingSettings {
  logo_url?: string;
  favicon_url?: string;
  company_name: string;
  tagline?: string;
  footer_text?: string;
}

export interface EmailTemplate {
  id: string;
  name: string;
  subject: string;
  body: string;
  variables: string[];
  is_active: boolean;
}

export interface DomainSettings {
  custom_domain?: string;
  subdomain: string;
  ssl_enabled: boolean;
  verified: boolean;
}

export const whitelabelApi = {
  // Agency Branding
  async getAgencyBranding(agencyId: string) {
    const { data } = await apiClient.get(`/whitelabel/agencies/${agencyId}/branding`);
    return data;
  },

  async updateAgencyBranding(agencyId: string, branding: Partial<BrandingSettings>) {
    const { data } = await apiClient.put(`/whitelabel/agencies/${agencyId}/branding`, branding);
    return data;
  },

  async uploadLogo(agencyId: string, file: File) {
    const formData = new FormData();
    formData.append('logo', file);
    
    const { data } = await apiClient.post(
      `/whitelabel/agencies/${agencyId}/branding/logo`,
      formData,
      { headers: { 'Content-Type': 'multipart/form-data' } }
    );
    return data;
  },

  // Theme Settings
  async getTheme(agencyId: string) {
    const { data } = await apiClient.get(`/whitelabel/agencies/${agencyId}/theme`);
    return data;
  },

  async updateTheme(agencyId: string, theme: Partial<ThemeSettings>) {
    const { data } = await apiClient.put(`/whitelabel/agencies/${agencyId}/theme`, theme);
    return data;
  },

  async previewTheme(agencyId: string, theme: Partial<ThemeSettings>) {
    const { data } = await apiClient.post(`/whitelabel/agencies/${agencyId}/theme/preview`, theme);
    return data;
  },

  // Email Templates
  async getEmailTemplates(agencyId: string) {
    const { data } = await apiClient.get(`/whitelabel/agencies/${agencyId}/email-templates`);
    return data;
  },

  async getEmailTemplate(agencyId: string, templateId: string) {
    const { data } = await apiClient.get(`/whitelabel/agencies/${agencyId}/email-templates/${templateId}`);
    return data;
  },

  async createEmailTemplate(agencyId: string, template: Omit<EmailTemplate, 'id'>) {
    const { data } = await apiClient.post(`/whitelabel/agencies/${agencyId}/email-templates`, template);
    return data;
  },

  async updateEmailTemplate(agencyId: string, templateId: string, template: Partial<EmailTemplate>) {
    const { data } = await apiClient.put(
      `/whitelabel/agencies/${agencyId}/email-templates/${templateId}`,
      template
    );
    return data;
  },

  async deleteEmailTemplate(agencyId: string, templateId: string) {
    await apiClient.delete(`/whitelabel/agencies/${agencyId}/email-templates/${templateId}`);
  },

  async previewEmailTemplate(agencyId: string, templateId: string, variables: Record<string, string>) {
    const { data } = await apiClient.post(
      `/whitelabel/agencies/${agencyId}/email-templates/${templateId}/preview`,
      { variables }
    );
    return data;
  },

  // Model Branding
  async getModelBranding(modelId: string) {
    const { data } = await apiClient.get(`/whitelabel/models/${modelId}/branding`);
    return data;
  },

  async updateModelBranding(modelId: string, branding: any) {
    const { data } = await apiClient.put(`/whitelabel/models/${modelId}/branding`, branding);
    return data;
  },

  async uploadModelLogo(modelId: string, file: File) {
    const formData = new FormData();
    formData.append('logo', file);
    
    const { data } = await apiClient.post(
      `/whitelabel/models/${modelId}/branding/logo`,
      formData,
      { headers: { 'Content-Type': 'multipart/form-data' } }
    );
    return data;
  },

  // Domain Settings (placeholder - not in backend yet)
  async getDomainSettings(agencyId: string): Promise<DomainSettings> {
    console.warn('Domain settings not implemented in backend');
    return {
      subdomain: 'agency',
      ssl_enabled: true,
      verified: false,
    };
  },

  async updateDomainSettings(agencyId: string, settings: Partial<DomainSettings>): Promise<DomainSettings> {
    console.warn('Domain settings update not implemented in backend');
    return { ...settings } as DomainSettings;
  },

  async verifyDomain(agencyId: string, domain: string): Promise<{ verified: boolean; dns_records: any[] }> {
    console.warn('Domain verification not implemented in backend');
    return { verified: false, dns_records: [] };
  },
};