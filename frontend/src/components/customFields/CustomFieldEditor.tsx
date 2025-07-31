import React, { useState } from 'react';
import {
  Box,
  Paper,
  Typography,
  Button,
  List,
  ListItem,
  ListItemText,
  ListItemSecondaryAction,
  IconButton,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Switch,
  FormControlLabel,
  Chip,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Tabs,
  Tab,
  Checkbox,
  FormGroup,
  FormLabel } from '@mui/material';
import {
  Add,
  Edit,
  Delete,
  ExpandMore } from '@mui/icons-material';
import { DragDropContext, Droppable, Draggable } from 'react-beautiful-dnd';
import { useCustomFields } from '@/hooks/useCustomFields';
import { CustomField, FieldType, EntityType, SelectOption } from '@/types/customFields';

interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}

const TabPanel = ({ children, value, index }: TabPanelProps) => (
  <div hidden={value !== index}>
    {value === index && <Box sx={{ p: 3 }}>{children}</Box>}
  </div>
);

export const CustomFieldEditor: React.FC = () => {
  const {
    config,
    createField,
    updateField,
    deleteField,
    createSection,
    deleteSection } = useCustomFields();

  const [tabValue, setTabValue] = useState(0);
  const [fieldDialog, setFieldDialog] = useState(false);
  const [sectionDialog, setSectionDialog] = useState(false);
  const [editingField, setEditingField] = useState<CustomField | null>(null);
  const [deleteConfirmId, setDeleteConfirmId] = useState<string | null>(null);

  // Field form state
  const [fieldForm, setFieldForm] = useState({
    name: '',
    label: '',
    type: 'text' as FieldType,
    description: '',
    placeholder: '',
    required: false,
    section: '',
    appliesTo: [] as EntityType[],
    options: [] as SelectOption[] });

  // Section form state
  const [sectionForm, setSectionForm] = useState({
    name: '',
    description: '' });

  const fieldTypes: { value: FieldType; label: string }[] = [
    { value: 'text', label: 'Text' },
    { value: 'number', label: 'Number' },
    { value: 'date', label: 'Date' },
    { value: 'datetime', label: 'Date & Time' },
    { value: 'boolean', label: 'Yes/No' },
    { value: 'select', label: 'Dropdown' },
    { value: 'multiselect', label: 'Multi-Select' },
    { value: 'textarea', label: 'Text Area' },
    { value: 'email', label: 'Email' },
    { value: 'phone', label: 'Phone' },
    { value: 'url', label: 'URL' },
    { value: 'file', label: 'File Upload' },
    { value: 'color', label: 'Color Picker' },
    { value: 'rating', label: 'Rating' },
  ];

  const entityTypes: { value: EntityType; label: string }[] = [
    { value: 'model', label: 'Models' },
    { value: 'chatter', label: 'Chatters' },
    { value: 'member', label: 'Members' },
    { value: 'transaction', label: 'Transactions' },
    { value: 'chat', label: 'Chats' },
    { value: 'agency', label: 'Agency' },
  ];

  const handleCreateField = async () => {
    if (!fieldForm.name || !fieldForm.label || fieldForm.appliesTo.length === 0) return;

    await createField({
      name: fieldForm.name,
      label: fieldForm.label,
      type: fieldForm.type,
      description: fieldForm.description,
      placeholder: fieldForm.placeholder,
      required: fieldForm.required,
      section: fieldForm.section || undefined,
      appliesTo: fieldForm.appliesTo,
      options: fieldForm.options.length > 0 ? fieldForm.options : undefined,
      visible: true,
      order: config?.fields.length || 0 });

    setFieldDialog(false);
    resetFieldForm();
  };

  const handleUpdateField = async () => {
    if (!editingField) return;

    await updateField(editingField.id, {
      name: fieldForm.name,
      label: fieldForm.label,
      type: fieldForm.type,
      description: fieldForm.description,
      placeholder: fieldForm.placeholder,
      required: fieldForm.required,
      section: fieldForm.section || undefined,
      appliesTo: fieldForm.appliesTo,
      options: fieldForm.options.length > 0 ? fieldForm.options : undefined });

    setFieldDialog(false);
    setEditingField(null);
    resetFieldForm();
  };

  const handleEditField = (field: CustomField) => {
    setEditingField(field);
    setFieldForm({
      name: field.name,
      label: field.label,
      type: field.type,
      description: field.description || '',
      placeholder: field.placeholder || '',
      required: field.required,
      section: field.section || '',
      appliesTo: field.appliesTo,
      options: field.options || [] });
    setFieldDialog(true);
  };

  const handleDeleteField = async (fieldId: string) => {
    await deleteField(fieldId);
    setDeleteConfirmId(null);
  };

  const handleCreateSection = async () => {
    if (!sectionForm.name) return;

    await createSection({
      name: sectionForm.name,
      description: sectionForm.description,
      order: config?.sections.length || 0 });

    setSectionDialog(false);
    setSectionForm({ name: '', description: '' });
  };

  const resetFieldForm = () => {
    setFieldForm({
      name: '',
      label: '',
      type: 'text',
      description: '',
      placeholder: '',
      required: false,
      section: '',
      appliesTo: [],
      options: [] });
  };

  const handleAddOption = () => {
    setFieldForm(prev => ({
      ...prev,
      options: [...prev.options, { value: '', label: '' }] }));
  };

  const handleUpdateOption = (index: number, field: 'value' | 'label', value: string) => {
    setFieldForm(prev => ({
      ...prev,
      options: prev.options.map((opt, i) =>
        i === index ? { ...opt, [field]: value } : opt
      ) }));
  };

  const handleRemoveOption = (index: number) => {
    setFieldForm(prev => ({
      ...prev,
      options: prev.options.filter((_, i) => i !== index) }));
  };

  if (!config) {
    return <Box>Loading...</Box>;
  }

  return (
    <Box>
      <Paper sx={{ mb: 3 }}>
        <Tabs value={tabValue} onChange={(v) => setTabValue(v)}>
          <Tab label="Custom Fields" />
          <Tab label="Sections" />
          <Tab label="Entity " />
        </Tabs>

        <TabPanel value={tabValue} index={0}>
          {/* Custom Fields Tab */}
          <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 3 }}>
            <Typography variant="h6">Custom Fields</Typography>
            <Button
              startIcon={<Add />}
              variant="contained"
              onClick={() => setFieldDialog(true)}
            >
              Add Field
            </Button>
          </Box>

          <List>
            {config.fields.map((field) => (
              <ListItem
                key={field.id}
                sx={{
                  border: 1,
                  borderColor: 'divider',
                  borderRadius: 1,
                  mb: 1 }}
              >
                <ListItemText
                  primary={
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                      <Typography variant="subtitle1">{field.label}</Typography>
                      <Chip label={field.type} size="small" />
                      {field.required && <Chip label="Required" size="small" color="error" />}
                    </Box>
                  }
                  secondary={
                    <Box>
                      <Typography variant="body2" color="text.secondary">
                        Name: {field.name}
                        {field.description && ` • ${field.description}`}
                      </Typography>
                      <Box sx={{ display: 'flex', gap: 0.5, mt: 0.5 }}>
                        {field.appliesTo.map(entity => (
                          <Chip key={entity} label={entity} size="small" variant="outlined" />
                        ))}
                      </Box>
                    </Box>
                  }
                />
                <ListItemSecondaryAction>
                  <IconButton onClick={() => handleEditField(field)}>
                    <Edit />
                  </IconButton>
                  <IconButton
                    onClick={() => setDeleteConfirmId(field.id)}
                    color="error"
                  >
                    <Delete />
                  </IconButton>
                </ListItemSecondaryAction>
              </ListItem>
            ))}
          </List>
        </TabPanel>

        <TabPanel value={tabValue} index={1}>
          {/* Sections Tab */}
          <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 3 }}>
            <Typography variant="h6">Field Sections</Typography>
            <Button
              startIcon={<Add />}
              variant="contained"
              onClick={() => setSectionDialog(true)}
            >
              Add Section
            </Button>
          </Box>

          <List>
            {config.sections.map((section) => (
              <ListItem
                key={section.id}
                sx={{
                  border: 1,
                  borderColor: 'divider',
                  borderRadius: 1,
                  mb: 1 }}
              >
                <ListItemText
                  primary={section.name}
                  secondary={section.description}
                />
                <ListItemSecondaryAction>
                  <IconButton
                    onClick={() => deleteSection(section.id)}
                    color="error"
                  >
                    <Delete />
                  </IconButton>
                </ListItemSecondaryAction>
              </ListItem>
            ))}
          </List>
        </TabPanel>

        <TabPanel value={tabValue} index={2}>
          {/* Entity Tab */}
          <Typography variant="h6" gutterBottom>
            Default Fields by Entity Type
          </Typography>
          <Typography variant="body2" color="text.secondary" paragraph>
            Configure which fields are shown by default for each entity type.
          </Typography>
          
          {entityTypes.map(({ value, label }) => (
            <Accordion key={value}>
              <AccordionSummary expandIcon={<ExpandMore />}>
                <Typography>{label}</Typography>
              </AccordionSummary>
              <AccordionDetails>
                <FormGroup>
                  {config.fields
                    .filter(field => field.appliesTo.includes(value))
                    .map(field => (
                      <FormControlLabel
                        key={field.id}
                        control={
                          <Checkbox
                            checked={config.entityDefaults[value]?.includes(field.id) || false}
                          />
                        }
                        label={field.label}
                      />
                    ))}
                </FormGroup>
              </AccordionDetails>
            </Accordion>
          ))}
        </TabPanel>
      </Paper>

      {/* Field Dialog */}
      <Dialog
        open={fieldDialog}
        onClose={() => {
          setFieldDialog(false);
          setEditingField(null);
          resetFieldForm();
        }}
        maxWidth="md"
        fullWidth
      >
        <DialogTitle>
          {editingField ? 'Edit Field' : 'Create Field'}
        </DialogTitle>
        <DialogContent>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 1 }}>
            <TextField
              label="Field Name (lowercase, no spaces)"
              value={fieldForm.name}
              onChange={(e) => setFieldForm(prev => ({ ...prev, name: e.target.value.toLowerCase().replace(/\s/g, '_') }))}
              fullWidth
              required
            />
            <TextField
              label="Display Label"
              value={fieldForm.label}
              onChange={(e) => setFieldForm(prev => ({ ...prev, label: e.target.value }))}
              fullWidth
              required
            />
            <FormControl fullWidth>
              <InputLabel>Field Type</InputLabel>
              <Select
                value={fieldForm.type}
                onChange={(e) => setFieldForm(prev => ({ ...prev, type: e.target.value as FieldType }))}
                label="Field Type"
              >
                {fieldTypes.map(type => (
                  <MenuItem key={type.value} value={type.value}>
                    {type.label}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
            <TextField
              label="Description"
              value={fieldForm.description}
              onChange={(e) => setFieldForm(prev => ({ ...prev, description: e.target.value }))}
              fullWidth
              multiline
              rows={2}
            />
            <TextField
              label="Placeholder"
              value={fieldForm.placeholder}
              onChange={(e) => setFieldForm(prev => ({ ...prev, placeholder: e.target.value }))}
              fullWidth
            />
            <FormControl fullWidth>
              <InputLabel>Section</InputLabel>
              <Select
                value={fieldForm.section}
                onChange={(e) => setFieldForm(prev => ({ ...prev, section: e.target.value }))}
                label="Section"
              >
                <MenuItem value="">No Section</MenuItem>
                {config.sections.map(section => (
                  <MenuItem key={section.id} value={section.id}>
                    {section.name}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
            <FormControl fullWidth required>
              <FormLabel>Applies To</FormLabel>
              <FormGroup row>
                {entityTypes.map(({ value, label }) => (
                  <FormControlLabel
                    key={value}
                    control={
                      <Checkbox
                        checked={fieldForm.appliesTo.includes(value)}
                        onChange={() => {
                          if (.target.checked) {
                            setFieldForm(prev => ({
                              ...prev,
                              appliesTo: [...prev.appliesTo, value] }));
                          } else {
                            setFieldForm(prev => ({
                              ...prev,
                              appliesTo: prev.appliesTo.filter(t => t !== value) }));
                          }
                        }}
                      />
                    }
                    label={label}
                  />
                ))}
              </FormGroup>
            </FormControl>
            <FormControlLabel
              control={
                <Switch
                  checked={fieldForm.required}
                  onChange={(e) => setFieldForm(prev => ({ ...prev, required: e.target.checked }))}
                />
              }
              label="Required Field"
            />

            {/* Options for select/multiselect */}
            {(fieldForm.type === 'select' || fieldForm.type === 'multiselect') && (
              <Box>
                <Typography variant="subtitle2" gutterBottom>
                  Options
                </Typography>
                {fieldForm.options.map((option, index) => (
                  <Box key={index} sx={{ display: 'flex', gap: 1, mb: 1 }}>
                    <TextField
                      label="Value"
                      value={option.value}
                      onChange={() => handleUpdateOption(index, 'value', .target.value)}
                      size="small"
                    />
                    <TextField
                      label="Label"
                      value={option.label}
                      onChange={() => handleUpdateOption(index, 'label', .target.value)}
                      size="small"
                    />
                    <IconButton
                      onClick={() => handleRemoveOption(index)}
                      color="error"
                    >
                      <Delete />
                    </IconButton>
                  </Box>
                ))}
                <Button
                  startIcon={<Add />}
                  onClick={handleAddOption}
                  size="small"
                >
                  Add Option
                </Button>
              </Box>
            )}
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => {
            setFieldDialog(false);
            setEditingField(null);
            resetFieldForm();
          }}>
            Cancel
          </Button>
          <Button
            onClick={editingField ? handleUpdateField : handleCreateField}
            variant="contained"
          >
            {editingField ? 'Update' : 'Create'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Section Dialog */}
      <Dialog
        open={sectionDialog}
        onClose={() => setSectionDialog(false)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>Create Section</DialogTitle>
        <DialogContent>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 1 }}>
            <TextField
              label="Section Name"
              value={sectionForm.name}
              onChange={(e) => setSectionForm(prev => ({ ...prev, name: e.target.value }))}
              fullWidth
              required
            />
            <TextField
              label="Description"
              value={sectionForm.description}
              onChange={(e) => setSectionForm(prev => ({ ...prev, description: e.target.value }))}
              fullWidth
              multiline
              rows={2}
            />
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setSectionDialog(false)}>Cancel</Button>
          <Button onClick={handleCreateSection} variant="contained">
            Create
          </Button>
        </DialogActions>
      </Dialog>

      {/* Delete Confirmation */}
      <Dialog
        open={Boolean(deleteConfirmId)}
        onClose={() => setDeleteConfirmId(null)}
      >
        <DialogTitle>Delete Field?</DialogTitle>
        <DialogContent>
          <Typography>
            Are you sure you want to delete this field? All data associated with this field will be lost.
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDeleteConfirmId(null)}>Cancel</Button>
          <Button
            onClick={() => deleteConfirmId && handleDeleteField(deleteConfirmId)}
            color="error"
            variant="contained"
          >
            Delete
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};
