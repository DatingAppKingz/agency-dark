import { forwardRef } from 'react';
import { TextField, TextFieldProps, FormControl, FormHelperText, InputLabel, Select, SelectProps } from '@mui/material';
import { generateId } from '@/utils/accessibility';

// Accessible TextField with proper ARIA attributes
export const AccessibleTextField = forwardRef<HTMLDivElement, TextFieldProps>((props, ref) => {
  const { id = generateId('textfield'), error, helperText, label, required, ...rest } = props;
  const helperId = helperText ? `${id}-helper` : undefined;
  const errorId = error && helperText ? `${id}-error` : undefined;

  return (
    <TextField
      ref={ref}
      id={id}
      label={label}
      required={required}
      error={error}
      helperText={helperText}
      InputProps={{
        'aria-describedby': [helperId, errorId].filter(Boolean).join(' ') || undefined,
        'aria-invalid': error || undefined,
        'aria-required': required || undefined,
        ...rest.InputProps,
      }}
      FormHelperTextProps={{
        id: error ? errorId : helperId,
        role: error ? 'alert' : undefined,
        'aria-live': error ? 'polite' : undefined,
      }}
      {...rest}
    />
  );
});

AccessibleTextField.displayName = 'AccessibleTextField';

// Accessible Select with proper ARIA attributes
type AccessibleSelectProps = Omit<SelectProps, 'label'> & {
  label: string;
  helperText?: string;
  error?: boolean;
};

export const AccessibleSelect = forwardRef<HTMLDivElement, AccessibleSelectProps>((props, ref) => {
  const { id = generateId('select'), label, helperText, error, required, children, ...rest } = props;
  const labelId = `${id}-label`;
  const helperId = helperText ? `${id}-helper` : undefined;

  return (
    <FormControl fullWidth error={error} required={required} ref={ref}>
      <InputLabel id={labelId}>{label}</InputLabel>
      <Select
        labelId={labelId}
        id={id}
        label={label}
        inputProps={{
          'aria-describedby': helperId,
          'aria-invalid': error || undefined,
          'aria-required': required || undefined,
        }}
        {...rest}
      >
        {children}
      </Select>
      {helperText && (
        <FormHelperText id={helperId} role={error ? 'alert' : undefined}>
          {helperText}
        </FormHelperText>
      )}
    </FormControl>
  );
});

AccessibleSelect.displayName = 'AccessibleSelect';

// Form validation announcer
export const FormValidationAnnouncer = ({ errors }: { errors: Record<string, string> }) => {
  const errorMessages = Object.values(errors).filter(Boolean);
  
  if (errorMessages.length === 0) return null;

  return (
    <div
      role="alert"
      aria-live="polite"
      aria-atomic="true"
      style={{
        position: 'absolute',
        left: '-10000px',
        width: '1px',
        height: '1px',
        overflow: 'hidden',
      }}
    >
      {errorMessages.length} validation {errorMessages.length === 1 ? 'error' : 'errors'} found.
      {errorMessages.join('. ')}
    </div>
  );
};
