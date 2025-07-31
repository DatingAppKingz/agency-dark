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
  async getAgencyBranding(event: string) {
    const { data } = await apiClient.get(`/whitelabel/agencies/${}/branding`);
    return data;
  },

  async updateAgencyBranding(event: string, branding: Partial<BrandingSettings>) {
    const { data } = await apiClient.put(`/whitelabel/agencies/${}/branding`, branding);
    return data;
  },

  async uploadLogo(event: string, file: File) {
    const formData = new FormData();
    formData.append('logo', file);
    
    const { data } = await apiClient.post(
      `/whitelabel/agencies/${}/branding/logo`,
      formData,
      { headers: { 'Content-Type': 'multipart/form-data' } }
    );
    return data;
  },

  // Theme Settings
  async getTheme(event: string) {
    const { data } = await apiClient.get(`/whitelabel/agencies/${}/theme`);
    return data;
  },

  async updateTheme(event: string, theme: Partial<ThemeSettings>) {
    const { data } = await apiClient.put(`/whitelabel/agencies/${}/theme`, theme);
    return data;
  },

  async previewTheme(event: string, theme: Partial<ThemeSettings>) {
    const { data } = await apiClient.post(`/whitelabel/agencies/${}/theme/preview`, theme);
    return data;
  },

  // Email Templates
  async getEmailTemplates(event: string) {
    const { data } = await apiClient.get(`/whitelabel/agencies/${}/email-templates`);
    return data;
  },

  async getEmailTemplate(event: string, templateId: string) {
    const { data } = await apiClient.get(`/whitelabel/agencies/${}/email-templates/${templateId}`);
    return data;
  },

  async createEmailTemplate(event: string, template: Omit<EmailTemplate, 'id'>) {
    const { data } = await apiClient.post(`/whitelabel/agencies/${}/email-templates`, template);
    return data;
  },

  async updateEmailTemplate(event: string, templateId: string, template: Partial<EmailTemplate>) {
    const { data } = await apiClient.put(
      `/whitelabel/agencies/${}/email-templates/${templateId}`,
      template
    );
    return data;
  },

  async deleteEmailTemplate(event: string, templateId: string) {
    await apiClient.delete(`/whitelabel/agencies/${}/email-templates/${templateId}`);
  },

  async previewEmailTemplate(event: string, templateId: string, variables: Record<string, string>) {
    const { data } = await apiClient.post(
      `/whitelabel/agencies/${}/email-templates/${templateId}/preview`,
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
  async getDomainSettings(event: string): Promise<DomainSettings> {
    console.warn('Domain settings not implemented in backend');
    return {
      subdomain: 'agency',
      ssl_enabled: true,
      verified: false };
  },

  async updateDomainSettings(event: string, settings: Partial<DomainSettings>): Promise<DomainSettings> {
    console.warn('Domain settings update not implemented in backend');
    return { ...settings } as DomainSettings;
  },

  async verifyDomain(event: string, : string): Promise<{ verified: boolean; dns_records: any[] }> {
    console.warn('Domain verification not implemented in backend');
    return { verified: false, dns_records: [] };
  } };
