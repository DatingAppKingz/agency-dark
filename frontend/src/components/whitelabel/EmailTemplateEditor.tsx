import { useState } from 'react';
import {
  Box,
  Typography,
  Grid,
  Paper,
  TextField,
  Button,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Tabs,
  Tab,
  Chip,
  IconButton,
  Alert,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow } from '@mui/material';
import {
  Preview,
  Code,
  Send,
  Save,
  RestartAlt,
  ContentCopy,
  Edit } from '@mui/icons-material';
import { useToast } from '@/components/common/Toaster';

interface EmailTemplateEditorProps {
  onChange: () => void;
}

interface EmailTemplate {
  id: string;
  name: string;
  subject: string;
  htmlContent: string;
  textContent: string;
  variables: string[];
  category: string;
}

interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}

const TabPanel = ({ children, value, index }: TabPanelProps) => {
  return (
    <Box hidden={value !== index}>
      {value === index && children}
    </Box>
  );
};

export const EmailTemplateEditor = ({ onChange }: EmailTemplateEditorProps) => {
  const { success, error } = useToast();
  const [selectedTemplate, setSelectedTemplate] = useState('welcome');
  const [previewMode, setPreviewMode] = useState<'desktop' | 'mobile'>('desktop');
  const [editTab, setEditTab] = useState(0);
  const [testEmail, setTestEmail] = useState('');

  const [templates, setTemplates] = useState<EmailTemplate[]>([
    {
      id: 'welcome',
      name: 'Welcome Email',
      subject: 'Welcome to {{appName}}!',
      htmlContent: `<!DOCTYPE html>
<html>
<head>
  <style>
    body { font-family: Arial, sans-serif; }
    .container { max-width: 600px; margin: 0 auto; }
    .header { background: #1976d2; color: white; padding: 20px; text-align: center; }
    .content { padding: 20px; }
    .footer { background: #f5f5f5; padding: 20px; text-align: center; }
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <h1>Welcome to {{appName}}</h1>
    </div>
    <div class="content">
      <p>Hi {{userName}},</p>
      <p>Thank you for joining {{appName}}! We're excited to have you on board.</p>
      <p>Get started by exploring your dashboard and setting up your profile.</p>
      <a href="{{dashboardUrl}}" style="background: #1976d2; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; display: inline-block;">Go to Dashboard</a>
    </div>
    <div class="footer">
      <p>&copy; 2024 {{appName}}. All rights reserved.</p>
    </div>
  </div>
</body>
</html>`,
      textContent: `Welcome to {{appName}}!

Hi {{userName}},

Thank you for joining {{appName}}! We're excited to have you on board.

Get started by exploring your dashboard and setting up your profile.

Go to Dashboard: {{dashboardUrl}}

© 2024 {{appName}}. All rights reserved.`,
      variables: ['appName', 'userName', 'dashboardUrl'],
      category: 'system' },
    {
      id: 'password-reset',
      name: 'Password Reset',
      subject: 'Reset your {{appName}} password',
      htmlContent: `<!DOCTYPE html>
<html>
<head>
  <style>
    body { font-family: Arial, sans-serif; }
    .container { max-width: 600px; margin: 0 auto; }
    .header { background: #1976d2; color: white; padding: 20px; text-align: center; }
    .content { padding: 20px; }
    .footer { background: #f5f5f5; padding: 20px; text-align: center; }
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <h1>Password Reset Request</h1>
    </div>
    <div class="content">
      <p>Hi {{userName}},</p>
      <p>We received a request to reset your password. Click the button below to create a new password:</p>
      <a href="{{resetUrl}}" style="background: #1976d2; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; display: inline-block;">Reset Password</a>
      <p>This link will expire in 24 hours.</p>
      <p>If you didn't request this, please ignore this email.</p>
    </div>
    <div class="footer">
      <p>&copy; 2024 {{appName}}. All rights reserved.</p>
    </div>
  </div>
</body>
</html>`,
      textContent: `Password Reset Request

Hi {{userName}},

We received a request to reset your password. Click the link below to create a new password:

{{resetUrl}}

This link will expire in 24 hours.

If you didn't request this, please ignore this email.

© 2024 {{appName}}. All rights reserved.`,
      variables: ['appName', 'userName', 'resetUrl'],
      category: 'system' },
    {
      id: 'new-message',
      name: 'New Message Notification',
      subject: 'New message from {{senderName}}',
      htmlContent: `<!DOCTYPE html>
<html>
<head>
  <style>
    body { font-family: Arial, sans-serif; }
    .container { max-width: 600px; margin: 0 auto; }
    .header { background: #1976d2; color: white; padding: 20px; text-align: center; }
    .content { padding: 20px; }
    .message-preview { background: #f5f5f5; padding: 15px; border-radius: 5px; margin: 15px 0; }
    .footer { background: #f5f5f5; padding: 20px; text-align: center; }
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <h1>New Message</h1>
    </div>
    <div class="content">
      <p>Hi {{userName}},</p>
      <p>You have a new message from {{senderName}}:</p>
      <div class="message-preview">
        <p>{{messagePreview}}</p>
      </div>
      <a href="{{conversationUrl}}" style="background: #1976d2; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; display: inline-block;">View Conversation</a>
    </div>
    <div class="footer">
      <p>&copy; 2024 {{appName}}. All rights reserved.</p>
    </div>
  </div>
</body>
</html>`,
      textContent: `New Message

Hi {{userName}},

You have a new message from {{senderName}}:

"{{messagePreview}}"

View Conversation: {{conversationUrl}}

© 2024 {{appName}}. All rights reserved.`,
      variables: ['appName', 'userName', 'senderName', 'messagePreview', 'conversationUrl'],
      category: 'notification' },
  ]);

  const currentTemplate = templates.find(t => t.id === selectedTemplate);

  const handleTemplateChange = (field: keyof EmailTemplate, value: any) => {
    setTemplates(prev => prev.map(t => 
      t.id === selectedTemplate ? { ...t, [field]: value } : t
    ));
    onChange();
  };

  const handleSendTestEmail = () => {
    if (!testEmail) {
      error('Please enter a test email address');
      return;
    }
    // TODO: Implement test email sending
    success(`Test email sent to ${testEmail}`);
  };

  const handleResetTemplate = () => {
    // TODO: Reset to default template
    success('Template reset to default');
  };

  const getPreviewContent = () => {
    if (!currentTemplate) return '';
    
    let content = currentTemplate.htmlContent;
    const sampleData: Record<string, string> = {
      appName: 'AgencyDark',
      userName: 'John Doe',
      dashboardUrl: 'https://app.agencydark.com/dashboard',
      resetUrl: 'https://app.agencydark.com/reset-password?token=abc123',
      senderName: 'Jane Smith',
      messagePreview: 'Hey! Just wanted to check in and see how you\'re doing...',
      conversationUrl: 'https://app.agencydark.com/chat/123' };

    // Replace variables with sample data
    Object.entries(sampleData).forEach(([key, value]) => {
      content = content.replace(new RegExp(`{{${key}}}`, 'g'), value);
    });

    return content;
  };

  return (
    <Box>
      <Grid container spacing={3}>
        {/* Template Selector */}
        <Grid item xs={12}>
          <Paper sx={{ p: 3 }}>
            <Typography variant="h6" gutterBottom>
              Templates
            </Typography>
            
            <FormControl fullWidth sx={{ mt: 2 }}>
              <InputLabel>Select Template</InputLabel>
              <Select
                value={selectedTemplate}
                onChange={() => setSelectedTemplate(event.target.value)}
                label="Select Template"
              >
                {templates.map(template => (
                  <MenuItem key={template.id} value={template.id}>
                    {template.name}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          </Paper>
        </Grid>

        {/* Template Editor */}
        {currentTemplate && (
          <Grid item xs={12} lg={6}>
            <Paper sx={{ p: 3 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
                <Typography variant="h6">
                  Edit Template
                </Typography>
                <Button
                  startIcon={<RestartAlt />}
                  onClick={handleResetTemplate}
                  size="small"
                >
                  Reset
                </Button>
              </Box>

              <TextField
                fullWidth
                label="Subject"
                value={currentTemplate.subject}
                onChange={(e) => handleTemplateChange('subject', e.target.value)}
                sx={{ mb: 2 }}
              />

              <Tabs value={editTab} onChange={(_, v) => setEditTab(v)} sx={{ mb: 2 }}>
                <Tab icon={<Code />} label="HTML" />
                <Tab icon={<Edit />} label="Text" />
                <Tab icon={<Preview />} label="Variables" />
              </Tabs>

              <TabPanel value={editTab} index={0}>
                <TextField
                  fullWidth
                  multiline
                  rows={15}
                  value={currentTemplate.htmlContent}
                  onChange={(e) => handleTemplateChange('htmlContent', e.target.value)}
                  sx={{ fontFamily: 'monospace', fontSize: '0.875rem' }}
                />
              </TabPanel>

              <TabPanel value={editTab} index={1}>
                <TextField
                  fullWidth
                  multiline
                  rows={15}
                  value={currentTemplate.textContent}
                  onChange={(e) => handleTemplateChange('textContent', e.target.value)}
                  sx={{ fontFamily: 'monospace', fontSize: '0.875rem' }}
                />
              </TabPanel>

              <TabPanel value={editTab} index={2}>
                <Alert severity="info" sx={{ mb: 2 }}>
                  Use these variables in your template with double curly braces: {'{{variableName}}'}
                </Alert>
                <TableContainer>
                  <Table size="small">
                    <TableHead>
                      <TableRow>
                        <TableCell>Variable</TableCell>
                        <TableCell>Description</TableCell>
                        <TableCell width={50}></TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {currentTemplate.variables.map(variable => (
                        <TableRow key={variable}>
                          <TableCell>
                            <Chip label={`{{${variable}}}`} size="small" />
                          </TableCell>
                          <TableCell>
                            {variable.replace(/([A-Z])/g, ' $1').toLowerCase()}
                          </TableCell>
                          <TableCell>
                            <IconButton
                              size="small"
                              onClick={() => {
                                navigator.clipboard.writeText(`{{${variable}}}`);
                                success('Copied to clipboard');
                              }}
                            >
                              <ContentCopy fontSize="small" />
                            </IconButton>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>
              </TabPanel>

              <Box sx={{ mt: 2, display: 'flex', gap: 2 }}>
                <Button
                  variant="contained"
                  startIcon={<Save />}
                  onClick={() => success('Template saved')}
                >
                  Save Template
                </Button>
              </Box>
            </Paper>
          </Grid>
        )}

        {/* Preview */}
        {currentTemplate && (
          <Grid item xs={12} lg={6}>
            <Paper sx={{ p: 3 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
                <Typography variant="h6">
                  Preview
                </Typography>
                <Box sx={{ display: 'flex', gap: 1 }}>
                  <Chip
                    label="Desktop"
                    onClick={() => setPreviewMode('desktop')}
                    color={previewMode === 'desktop' ? 'primary' : 'default'}
                  />
                  <Chip
                    label="Mobile"
                    onClick={() => setPreviewMode('mobile')}
                    color={previewMode === 'mobile' ? 'primary' : 'default'}
                  />
                </Box>
              </Box>

              <Box
                sx={{
                  border: 1,
                  borderColor: 'divider',
                  borderRadius: 1,
                  height: 500,
                  overflow: 'auto',
                  backgroundColor: 'grey.50',
                  p: 2 }}
              >
                <Box
                  sx={{
                    maxWidth: previewMode === 'mobile' ? 375 : '100%',
                    mx: 'auto',
                    backgroundColor: 'white',
                    boxShadow: 1 }}
                  dangerouslySetInnerHTML={{ __html: getPreviewContent() }}
                />
              </Box>

              <Box sx={{ mt: 2, display: 'flex', gap: 2 }}>
                <TextField
                  fullWidth
                  label="Test Address"
                  value={testEmail}
                  onChange={() => setTestEmail(event.target.value)}
                  size="small"
                />
                <Button
                  variant="outlined"
                  startIcon={<Send />}
                  onClick={handleSendTestEmail}
                >
                  Send Test
                </Button>
              </Box>
            </Paper>
          </Grid>
        )}
      </Grid>
    </Box>
  );
};
