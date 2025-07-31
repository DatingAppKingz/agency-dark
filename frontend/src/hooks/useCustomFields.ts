import { useState, useCallback, useEffect } from 'react';
import { useAuthStore } from '@/store/authStore';
import {
  CustomField,
  CustomFieldValue,
  CustomFieldConfig,
  EntityType,
  CustomFieldSection } from '@/types/customFields';

const STORAGE_KEY = 'custom_fields';

// Mock API service - replace with actual API calls
const customFieldsApi = {
  getConfig: async (agencyId: string): Promise<CustomFieldConfig> => {
    const stored = localStorage.getItem(`${STORAGE_KEY}_${agencyId}`);
    if (stored) {
      return JSON.parse(stored);
    }
    return {
      agencyId,
      fields: [],
      sections: [],
      entityDefaults: {
        model: [],
        chatter: [],
        member: [],
        transaction: [],
        chat: [],
        agency: [] } };
  },
  
  saveConfig: async (config: CustomFieldConfig): Promise<void> => {
    localStorage.setItem(`${STORAGE_KEY}_${config.agencyId}`, JSON.stringify(config));
  },
  
  getValues: async (entityId: string, entityType: EntityType): Promise<CustomFieldValue[]> => {
    const stored = localStorage.getItem(`${STORAGE_KEY}_values_${entityId}`);
    if (stored) {
      return JSON.parse(stored);
    }
    return [];
  },
  
  saveValues: async (entityId: string, values: CustomFieldValue[]): Promise<void> => {
    localStorage.setItem(`${STORAGE_KEY}_values_${entityId}`, JSON.stringify(values));
  } };

export const useCustomFields = (entityType?: EntityType, entityId?: string) => {
  const { user } = useAuthStore();
  const [config, setConfig] = useState<CustomFieldConfig | null>(null);
  const [values, setValues] = useState<Record<string, any>>({});
  const [isPending, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);

  // Load configuration and values
  useEffect(() => {
    const loadData = async () => {
      if (!user?.agencyId) return;
      
      setIsLoading(true);
      try {
        // Load config
        const fieldConfig = await customFieldsApi.getConfig(user.agencyId);
        setConfig(fieldConfig);
        
        // Load values if entityId provided
        if (entityId && entityType) {
          const fieldValues = await customFieldsApi.getValues(entityId, entityType);
          const valueMap = fieldValues.reduce((acc, fv) => {
            acc[fv.fieldId] = fv.value;
            return acc;
          }, {} as Record<string, any>);
          setValues(valueMap);
        }
      } catch (error) {
        console.error('Error loading custom fields:', error);
      } finally {
        setIsLoading(false);
      }
    };
    
    loadData();
  }, [user?.agencyId, entityId, entityType]);

  // Get fields for specific entity type
  const getFieldsForEntity = useCallback((type: EntityType): CustomField[] => {
    if (!config) return [];
    return config.fields.filter(field => 
      field.appliesTo.includes(type) && field.visible
    ).sort((a, b) => a.order - b.order);
  }, [config]);

  // Group fields by section
  const getFieldsBySection = useCallback((type: EntityType) => {
    const fields = getFieldsForEntity(type);
    const sections = config?.sections || [];
    
    const grouped = new Map<string, CustomField[]>();
    
    // Add fields without section
    const noSection = fields.filter(f => !f.section);
    if (noSection.length > 0) {
      grouped.set('', noSection);
    }
    
    // Group by section
    sections.forEach(section => {
      const sectionFields = fields.filter(f => f.section === section.id);
      if (sectionFields.length > 0) {
        grouped.set(section.id, sectionFields);
      }
    });
    
    return { sections, grouped };
  }, [config, getFieldsForEntity]);

  // Create field
  const createField = useCallback(async (field: Omit<CustomField, 'id' | 'agencyId' | 'createdAt' | 'updatedAt'>) => {
    if (!config || !user?.agencyId) return;
    
    const newField: CustomField = {
      ...field,
      id: `field_${Date.now()}`,
      agencyId: user.agencyId,
      createdAt: new Date(),
      updatedAt: new Date() };
    
    const updatedConfig = {
      ...config,
      fields: [...config.fields, newField] };
    
    await customFieldsApi.saveConfig(updatedConfig);
    setConfig(updatedConfig);
    
    return newField;
  }, [config, user?.agencyId]);

  // Update field
  const updateField = useCallback(async (fieldId: string, updates: Partial<CustomField>) => {
    if (!config) return;
    
    const updatedConfig = {
      ...config,
      fields: config.fields.map(field =>
        field.id === fieldId
          ? { ...field, ...updates, updatedAt: new Date() }
          : field
      ) };
    
    await customFieldsApi.saveConfig(updatedConfig);
    setConfig(updatedConfig);
  }, [config]);

  // Delete field
  const deleteField = useCallback(async (fieldId: string) => {
    if (!config) return;
    
    const updatedConfig = {
      ...config,
      fields: config.fields.filter(field => field.id !== fieldId) };
    
    await customFieldsApi.saveConfig(updatedConfig);
    setConfig(updatedConfig);
  }, [config]);

  // Create section
  const createSection = useCallback(async (section: Omit<CustomFieldSection, 'id'>) => {
    if (!config) return;
    
    const newSection: CustomFieldSection = {
      ...section,
      id: `section_${Date.now()}` };
    
    const updatedConfig = {
      ...config,
      sections: [...config.sections, newSection] };
    
    await customFieldsApi.saveConfig(updatedConfig);
    setConfig(updatedConfig);
    
    return newSection;
  }, [config]);

  // Update section
  const updateSection = useCallback(async (sectionId: string, updates: Partial<CustomFieldSection>) => {
    if (!config) return;
    
    const updatedConfig = {
      ...config,
      sections: config.sections.map(section =>
        section.id === sectionId
          ? { ...section, ...updates }
          : section
      ) };
    
    await customFieldsApi.saveConfig(updatedConfig);
    setConfig(updatedConfig);
  }, [config]);

  // Delete section
  const deleteSection = useCallback(async (sectionId: string) => {
    if (!config) return;
    
    const updatedConfig = {
      ...config,
      sections: config.sections.filter(section => section.id !== sectionId),
      fields: config.fields.map(field =>
        field.section === sectionId
          ? { ...field, section: undefined }
          : field
      ) };
    
    await customFieldsApi.saveConfig(updatedConfig);
    setConfig(updatedConfig);
  }, [config]);

  // Update field value
  const updateValue = useCallback((fieldId: string, value: any) => {
    setValues(prev => ({ ...prev, [fieldId]: value }));
  }, []);

  // Save all values
  const saveValues = useCallback(async () => {
    if (!entityId || !entityType) return;
    
    setIsSaving(true);
    try {
      const fieldValues: CustomFieldValue[] = Object.entries(values).map(([fieldId, value]) => ({
        id: `value_${Date.now()}_${fieldId}`,
        fieldId,
        entityId,
        value,
        createdAt: new Date(),
        updatedAt: new Date() }));
      
      await customFieldsApi.saveValues(entityId, fieldValues);
    } catch (error) {
      console.error('Error saving custom field values:', error);
      throw error;
    } finally {
      setIsSaving(false);
    }
  }, [entityId, values]);

  // Validate field value
  const validateField = useCallback((field: CustomField, value: any): string | null => {
    const validation = field.validation;
    if (!validation) return null;
    
    // Required validation
    if (field.required && !value) {
      return `${field.label} is required`;
    }
    
    // Type-specific validations
    switch (field.type) {
      case 'text':
      case 'textarea':
      case 'email':
      case 'phone':
      case 'url':
        if (validation.minLength && value.length < validation.minLength) {
          return `${field.label} must be at least ${validation.minLength} characters`;
        }
        if (validation.maxLength && value.length > validation.maxLength) {
          return `${field.label} must be no more than ${validation.maxLength} characters`;
        }
        if (validation.pattern) {
          const regex = new RegExp(validation.pattern);
          if (!regex.test(value)) {
            return validation.patternMessage || `${field.label} is invalid`;
          }
        }
        break;
        
      case 'number':
      case 'rating':
        const numValue = Number(value);
        if (validation.min !== undefined && numValue < validation.min) {
          return `${field.label} must be at least ${validation.min}`;
        }
        if (validation.max !== undefined && numValue > validation.max) {
          return `${field.label} must be no more than ${validation.max}`;
        }
        break;
    }
    
    // Custom validation
    if (validation.customValidator) {
      return validation.customValidator(value);
    }
    
    return null;
  }, []);

  // Validate all fields
  const validateAll = useCallback((): Record<string, string> => {
    if (!entityType || !config) return {};
    
    const fields = getFieldsForEntity(entityType);
    const errors: Record<string, string> = {};
    
    fields.forEach(field => {
      const error = validateField(field, values[field.id]);
      if (error) {
        errors[field.id] = error;
      }
    });
    
    return errors;
  }, [config, getFieldsForEntity, validateField, values]);

  return {
    config,
    fields: entityType ? getFieldsForEntity(entityType) : [],
    fieldsBySection: entityType ? getFieldsBySection(entityType) : { sections: [], grouped: new Map() },
    values,
    isPending,
    isSaving,
    createField,
    updateField,
    deleteField,
    createSection,
    updateSection,
    deleteSection,
    updateValue,
    saveValues,
    validateField,
    validateAll };
};
