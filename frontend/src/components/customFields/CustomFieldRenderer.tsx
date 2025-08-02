import React from 'react';
import {
  TextField,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  FormControlLabel,
  Switch,
  FormHelperText,
  Box,
  Typography,
  Rating,
  Chip,
  OutlinedInput } from '@mui/material';
import { DatePicker, DateTimePicker } from '@mui/x-date-pickers';
import { LocalizationProvider } from '@mui/x-date-pickers/LocalizationProvider';
import { AdapterDateFns } from '@mui/x-date-pickers/AdapterDateFns';
import { CustomField, EntityType } from '@/types/customFields';
import { useCustomFields } from '@/hooks/useCustomFields';

interface CustomFieldRendererProps {
  entityType: EntityType;
  entityId?: string;
  onSubmit?: (values: Record<string, any>) => void;
  readOnly?: boolean;
}

export const CustomFieldRenderer: React.FC<CustomFieldRendererProps> = ({
  entityType,
  entityId,
  onSubmit,
  readOnly = false }) => {
  const {
    fieldsBySection,
    values,
    updateValue,
    validateField,
    validateAll,
    saveValues } = useCustomFields(entityType, entityId);

  const [errors, setErrors] = React.useState<Record<string, string>>({});

  const handleFieldChange = (fieldId: string, value: any, field: CustomField) => {
    updateValue(fieldId, value);
    
    // Validate on change
    const error = validateField(field, value);
    setErrors(prev => ({
      ...prev,
      [fieldId]: error || '' }));
  };

  const handleSubmit = async () => {
    const validationErrors = validateAll();
    setErrors(validationErrors);
    
    if (Object.keys(validationErrors).length === 0) {
      await saveValues();
      onSubmit?.(values);
    }
  };

  const renderField = (field: CustomField) => {
    const value = values[field.id] ?? field.defaultValue ?? '';
    const error = errors[field.id];

    switch (field.type) {
      case 'text':
      case 'email':
      case 'phone':
      case 'url':
        return (
          <TextField
            key={field.id}
            fullWidth
            label={field.label}
            value={value}
            onChange={(e) => handleFieldChange(field.id, e.target.value, field)}
            placeholder={field.placeholder}
            required={field.required}
            error={Boolean(error)}
            helperText={error || field.description}
            disabled={readOnly}
            type={field.type === 'email' ? 'email' : field.type === 'url' ? 'url' : 'text'}
            InputProps={{
              readOnly }}
          />
        );

      case 'number':
        return (
          <TextField
            key={field.id}
            fullWidth
            label={field.label}
            value={value}
            onChange={(e) => handleFieldChange(field.id, Number(e.target.value), field)}
            placeholder={field.placeholder}
            required={field.required}
            error={Boolean(error)}
            helperText={error || field.description}
            disabled={readOnly}
            type="number"
            InputProps={{
              readOnly,
              inputProps: {
                min: field.validation?.min,
                max: field.validation?.max } }}
          />
        );

      case 'textarea':
        return (
          <TextField
            key={field.id}
            fullWidth
            label={field.label}
            value={value}
            onChange={(e) => handleFieldChange(field.id, e.target.value, field)}
            placeholder={field.placeholder}
            required={field.required}
            error={Boolean(error)}
            helperText={error || field.description}
            disabled={readOnly}
            multiline
            rows={4}
            InputProps={{
              readOnly }}
          />
        );

      case 'boolean':
        return (
          <FormControlLabel
            key={field.id}
            control={
              <Switch
                checked={Boolean(value)}
                onChange={(e) => handleFieldChange(field.id, e.target.checked, field)}
                disabled={readOnly}
              />
            }
            label={field.label}
          />
        );

      case 'select':
        return (
          <FormControl key={field.id} fullWidth error={Boolean(error)}>
            <InputLabel>{field.label}</InputLabel>
            <Select
              value={value}
              onChange={(e) => handleFieldChange(field.id, e.target.value, field)}
              label={field.label}
              disabled={readOnly}
              required={field.required}
            >
              {field.options?.map(option => (
                <MenuItem key={option.value} value={option.value}>
                  {option.label}
                </MenuItem>
              ))}
            </Select>
            <FormHelperText>{error || field.description}</FormHelperText>
          </FormControl>
        );

      case 'multiselect':
        return (
          <FormControl key={field.id} fullWidth error={Boolean(error)}>
            <InputLabel>{field.label}</InputLabel>
            <Select
              multiple
              value={Array.isArray(value) ? value : []}
              onChange={(e) => handleFieldChange(field.id, e.target.value, field)}
              input={<OutlinedInput label={field.label} />}
              renderValue={(selected) => (
                <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                  { (selected as string[]).map((val) => {
                    const option = field.options?.find(opt => opt.value === val);
                    return <Chip key={val} label={option?.label || val} size="small" />;
                  })}
                </Box>
              )}
              disabled={readOnly}
              required={field.required}
            >
              {field.options?.map(option => (
                <MenuItem key={option.value} value={option.value}>
                  {option.label}
                </MenuItem>
              ))}
            </Select>
            <FormHelperText>{error || field.description}</FormHelperText>
          </FormControl>
        );

      case 'date':
        return (
          <DatePicker
            key={field.id}
            label={field.label}
            value={value && typeof value !== 'boolean' ? new Date(value) : null}
            onChange={(date) => handleFieldChange(field.id, date?.toISOString(), field)}
            disabled={readOnly}
            slotProps={{
              textField: {
                fullWidth: true,
                required: field.required,
                error: Boolean(error),
                helperText: error || field.description } }}
          />
        );

      case 'datetime':
        return (
          <DateTimePicker
            key={field.id}
            label={field.label}
            value={value && typeof value !== 'boolean' ? new Date(value) : null}
            onChange={(date) => handleFieldChange(field.id, date?.toISOString(), field)}
            disabled={readOnly}
            slotProps={{
              textField: {
                fullWidth: true,
                required: field.required,
                error: Boolean(error),
                helperText: error || field.description } }}
          />
        );

      case 'rating':
        return (
          <Box key={field.id}>
            <Typography component="legend">{field.label}</Typography>
            <Rating
              value={Number(value) || 0}
              onChange={(_, newValue) => handleFieldChange(field.id, newValue, field)}
              disabled={readOnly}
              max={field.validation?.max || 5}
            />
            {(error || field.description) && (
              <FormHelperText error={Boolean(error)}>
                {error || field.description}
              </FormHelperText>
            )}
          </Box>
        );

      case 'color':
        return (
          <Box key={field.id}>
            <Typography variant="body2" gutterBottom>
              {field.label}
            </Typography>
            <input
              type="color"
              value={typeof value === 'string' ? value : '#000000'}
              onChange={(e) => handleFieldChange(field.id, e.target.value, field)}
              disabled={readOnly}
              style={{
                width: '100%',
                height: 40,
                cursor: readOnly ? 'not-allowed' : 'pointer' }}
            />
            {(error || field.description) && (
              <FormHelperText error={Boolean(error)}>
                {error || field.description}
              </FormHelperText>
            )}
          </Box>
        );

      case 'file':
        return (
          <Box key={field.id}>
            <Typography variant="body2" gutterBottom>
              {field.label}
            </Typography>
            <input
              type="file"
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) {
                  handleFieldChange(field.id, file, field);
                }
              }}
              disabled={readOnly}
              style={{
                width: '100%',
                padding: '8px 0' }}
            />
            {(error || field.description) && (
              <FormHelperText error={Boolean(error)}>
                {error || field.description}
              </FormHelperText>
            )}
          </Box>
        );

      default:
        return null;
    }
  };

  const { sections, grouped } = fieldsBySection;

  return (
    <LocalizationProvider dateAdapter={AdapterDateFns}>
      <Box>
      {/* Fields without section */}
      {grouped.get('') && (
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, mb: 3 }}>
          {grouped.get('')!.map(renderField)}
        </Box>
      )}

      {/* Fields grouped by section */}
      {sections.map(section => {
        const fields = grouped.get(section.id);
        if (!fields || fields.length === 0) return null;

        return (
          <Box key={section.id} sx={{ mb: 4 }}>
            <Typography variant="h6" gutterBottom>
              {section.name}
            </Typography>
            {section.description && (
              <Typography variant="body2" color="text.secondary" gutterBottom>
                {section.description}
              </Typography>
            )}
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
              {fields.map(renderField)}
            </Box>
          </Box>
        );
      })}

      {!readOnly && onSubmit && (
        <Box sx={{ mt: 3 }}>
          <button onClick={handleSubmit} className="btn btn-primary">
            Save Custom Fields
          </button>
        </Box>
      )}
      </Box>
    </LocalizationProvider>
  );
};
