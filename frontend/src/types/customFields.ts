// Custom fields system types

export type FieldType = 
  | 'text'
  | 'number'
  | 'date'
  | 'datetime'
  | 'boolean'
  | 'select'
  | 'multiselect'
  | 'textarea'
  | 'email'
  | 'phone'
  | 'url'
  | 'file'
  | 'color'
  | 'rating';

export interface FieldValidation {
  required?: boolean;
  min?: number;
  max?: number;
  minLength?: number;
  maxLength?: number;
  pattern?: string;
  patternMessage?: string;
  customValidator?: (value: any) => string | null;
}

export interface SelectOption {
  value: string;
  label: string;
  color?: string;
  icon?: string;
}

export interface CustomField {
  id: string;
  agencyId: string;
  name: string;
  label: string;
  type: FieldType;
  description?: string;
  placeholder?: string;
  defaultValue?: any;
  options?: SelectOption[]; // For select/multiselect
  validation?: FieldValidation;
  required: boolean;
  visible: boolean;
  order: number;
  section?: string;
  appliesTo: EntityType[];
  metadata?: Record<string, any>;
  createdAt: Date;
  updatedAt: Date;
}

export type EntityType = 'model' | 'chatter' | 'member' | 'transaction' | 'chat' | 'agency';

export interface CustomFieldValue {
  id: string;
  fieldId: string;
  entityId: string;
  entityType: EntityType;
  value: any;
  createdAt: Date;
  updatedAt: Date;
}

export interface CustomFieldSection {
  id: string;
  name: string;
  description?: string;
  order: number;
  collapsed?: boolean;
}

export interface CustomFieldGroup {
  section: CustomFieldSection;
  fields: CustomField[];
}

export interface CustomFieldConfig {
  agencyId: string;
  fields: CustomField[];
  sections: CustomFieldSection[];
  entityDefaults: Record<EntityType, string[]>; // Default field IDs per entity type
}
