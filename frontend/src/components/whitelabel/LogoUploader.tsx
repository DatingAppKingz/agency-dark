import { useState, useRef } from 'react';
import {
  Box,
  Typography,
  Grid,
  Paper,
  Button,
  IconButton,
  List,
  ListItem,
  ListItemText,
  ListItemSecondaryAction,
  FormControlLabel,
  Switch,
  TextField,
  Divider } from '@mui/material';
import {
  CloudUpload,
  Delete,
  Image as ImageIcon,
  Visibility,
  ContentCopy } from '@mui/icons-material';
import { useToast } from '@/components/common/Toaster';

interface LogoUploaderProps {
  onChange: () => void;
}

interface LogoVariant {
  id: string;
  name: string;
  file?: File;
  url?: string;
  dimensions: string;
  maxSize: string;
  description: string;
}

export const LogoUploader = ({ onChange }: LogoUploaderProps) => {
  const { success, error } = useToast();
  const fileInputRefs = useRef<{ [key: string]: HTMLInputElement | null }>({});
  
  const [logos, setLogos] = useState<LogoVariant[]>([
    {
      id: 'primary',
      name: 'Primary Logo',
      url: '/logo-primary.png',
      dimensions: '512x512',
      maxSize: '1MB',
      description: 'Main logo used in navigation and login' },
    {
      id: 'light',
      name: 'Light Logo',
      url: '/logo-light.png',
      dimensions: '512x512',
      maxSize: '1MB',
      description: 'Logo for dark backgrounds' },
    {
      id: 'dark',
      name: 'Dark Logo',
      url: '/logo-dark.png',
      dimensions: '512x512',
      maxSize: '1MB',
      description: 'Logo for light backgrounds' },
    {
      id: 'favicon',
      name: 'Favicon',
      url: '/favicon.ico',
      dimensions: '32x32',
      maxSize: '100KB',
      description: 'Browser tab icon' },
    {
      id: 'email',
      name: 'Email Logo',
      url: '/logo-email.png',
      dimensions: '600x200',
      maxSize: '500KB',
      description: 'Logo for email templates' },
  ]);

  const [brandingSettings, setBrandingSettings] = useState({
    appName: 'AgencyDark',
    tagline: 'Premium Content Management Platform',
    copyrightText: '© 2024 AgencyDark. All rights reserved.',
    showPoweredBy: false,
    customCSS: '' });

  const handleFileSelect = (logoId: string, event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    // Validate file type
    if (!file.type.startsWith('image/')) {
      error('Please select an image file');
      return;
    }

    // Validate file size
    const logo = logos.find(l => l.id === logoId);
    if (!logo) return;

    const maxSizeInBytes = parseInt(logo.maxSize) * (logo.maxSize.includes('MB') ? 1024 * 1024 : 1024);
    if (file.size > maxSizeInBytes) {
      error(`File size must be less than ${logo.maxSize}`);
      return;
    }

    // Create preview URL
    const url = URL.createObjectURL(file);
    
    setLogos(prev => prev.map(l => 
      l.id === logoId ? { ...l, file, url } : l
    ));
    
    onChange();
    success(`${logo.name} uploaded successfully`);
  };

  const handleRemoveLogo = (logoId: string) => {
    setLogos(prev => prev.map(l => 
      l.id === logoId ? { ...l, file: undefined, url: undefined } : l
    ));
    onChange();
  };

  const handleBrandingChange = (field: string, value: string) => {
    setBrandingSettings(prev => ({ ...prev, [field]: value }));
    onChange();
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    success('Copied to clipboard');
  };

  return (
    <Box>
      <Grid container spacing={3}>
        {/* Logo Upload Section */}
        <Grid item xs={12}>
          <Paper sx={{ p: 3 }}>
            <Typography variant="h6" gutterBottom>
              Logo Management
            </Typography>
            <Typography variant="body2" color="text.secondary" gutterBottom>
              Upload different logo variants for various use cases
            </Typography>

            <List sx={{ mt: 3 }}>
              {logos.map((logo, index) => (
                <Box key={logo.id}>
                  {index > 0 && <Divider sx={{ my: 2 }} />}
                  <ListItem sx={{ px: 0 }}>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, width: '100%' }}>
                      <Box
                        sx={{
                          width: 80,
                          height: 80,
                          border: 2,
                          borderColor: 'divider',
                          borderRadius: 1,
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          backgroundColor: 'grey.100',
                          overflow: 'hidden' }}
                      >
                        {logo.url ? (
                          <img
                            src={logo.url}
                            alt={logo.name}
                            style={{
                              maxWidth: '100%',
                              maxHeight: '100%',
                              objectFit: 'contain' }}
                          />
                        ) : (
                          <ImageIcon sx={{ fontSize: 40, color: 'grey.400' }} />
                        )}
                      </Box>
                      
                      <Box sx={{ flexGrow: 1 }}>
                        <Typography variant="subtitle1">
                          {logo.name}
                        </Typography>
                        <Typography variant="body2" color="text.secondary">
                          {logo.description}
                        </Typography>
                        <Typography variant="caption" color="text.secondary">
                          Dimensions: {logo.dimensions} • Max size: {logo.maxSize}
                        </Typography>
                      </Box>
                      
                      <Box sx={{ display: 'flex', gap: 1 }}>
                        <input
                          ref={el => fileInputRefs.current[logo.id] = el}
                          type="file"
                          accept="image/*"
                          style={{ display: 'none' }}
                          onChange={(e) => handleFileSelect(logo.id, e)}
                        />
                        <Button
                          variant="outlined"
                          startIcon={<CloudUpload />}
                          onClick={() => fileInputRefs.current[logo.id]?.click()}
                          size="small"
                        >
                          Upload
                        </Button>
                        {logo.url && (
                          <>
                            <IconButton size="small">
                              <Visibility />
                            </IconButton>
                            <IconButton
                              size="small"
                              color="error"
                              onClick={() => handleRemoveLogo(logo.id)}
                            >
                              <Delete />
                            </IconButton>
                          </>
                        )}
                      </Box>
                    </Box>
                  </ListItem>
                </Box>
              ))}
            </List>
          </Paper>
        </Grid>

        {/* Branding Settings */}
        <Grid item xs={12}>
          <Paper sx={{ p: 3 }}>
            <Typography variant="h6" gutterBottom>
              Branding Settings
            </Typography>

            <Grid container spacing={3}>
              <Grid item xs={12} md={6}>
                <TextField
                  fullWidth
                  label="Application Name"
                  value={brandingSettings.appName}
                  onChange={(e) => handleBrandingChange('appName', e.target.value)}
                />
              </Grid>
              
              <Grid item xs={12} md={6}>
                <TextField
                  fullWidth
                  label="Tagline"
                  value={brandingSettings.tagline}
                  onChange={(e) => handleBrandingChange('tagline', e.target.value)}
                />
              </Grid>
              
              <Grid item xs={12}>
                <TextField
                  fullWidth
                  label="Copyright Text"
                  value={brandingSettings.copyrightText}
                  onChange={(e) => handleBrandingChange('copyrightText', e.target.value)}
                />
              </Grid>
              
              <Grid item xs={12}>
                <FormControlLabel
                  control={
                    <Switch
                      checked={brandingSettings.showPoweredBy}
                      onChange={(e) => handleBrandingChange('showPoweredBy', e.target.checked)}
                    />
                  }
                  label="Show 'Powered by AgencyDark' in footer"
                />
              </Grid>
            </Grid>
          </Paper>
        </Grid>

        {/* Custom CSS */}
        <Grid item xs={12}>
          <Paper sx={{ p: 3 }}>
            <Typography variant="h6" gutterBottom>
              Custom CSS
            </Typography>
            <Typography variant="body2" color="text.secondary" gutterBottom>
              Add custom CSS to further customize the appearance
            </Typography>
            
            <TextField
              fullWidth
              multiline
              rows={8}
              value={brandingSettings.customCSS}
              onChange={(e) => handleBrandingChange('customCSS', e.target.value)}
              placeholder={`/* Custom CSS */
.custom-class {
  color: #ff0000;
}`}
              sx={{ mt: 2, fontFamily: 'monospace' }}
            />
          </Paper>
        </Grid>

        {/* Logo URLs */}
        <Grid item xs={12}>
          <Paper sx={{ p: 3 }}>
            <Typography variant="h6" gutterBottom>
              Logo URLs
            </Typography>
            <Typography variant="body2" color="text.secondary" gutterBottom>
              Use these URLs to reference your logos
            </Typography>
            
            <List sx={{ mt: 2 }}>
              {logos.filter(l => l.url).map(logo => (
                <ListItem key={logo.id}>
                  <ListItemText
                    primary={logo.name}
                    secondary={`/api/branding/logo/${logo.id}`}
                  />
                  <ListItemSecondaryAction>
                    <IconButton
                      edge="end"
                      onClick={() => copyToClipboard(`/api/branding/logo/${logo.id}`)}
                    >
                      <ContentCopy />
                    </IconButton>
                  </ListItemSecondaryAction>
                </ListItem>
              ))}
            </List>
          </Paper>
        </Grid>
      </Grid>
    </Box>
  );
};
