import { useState } from 'react';
import {
  Box,
  Typography,
  Grid,
  Paper,
  TextField,
  Button,
  Switch,
  FormControlLabel,
  Slider,
  IconButton,
  Chip } from '@mui/material';
import {
  Brightness4,
  Brightness7,
  RestartAlt,
  ContentCopy } from '@mui/icons-material';
import { HexColorPicker } from 'react-colorful';
import { useTheme } from '@mui/material/styles';

interface ThemeCustomizerProps {
  onChange: () => void;
}

export const ThemeCustomizer = ({ onChange }: ThemeCustomizerProps) => {
  const theme = useTheme();
  const [darkMode, setDarkMode] = useState(false);
  const [colors, setColors] = useState({
    primary: '#1976d2',
    secondary: '#dc004e',
    success: '#2e7d32',
    error: '#d32f2f',
    warning: '#ed6c02',
    info: '#0288d1',
    background: '#ffffff',
    surface: '#f5f5f5',
    text: '#000000' });
  const [borderRadius, setBorderRadius] = useState(8);
  const [elevation, setElevation] = useState(1);
  const [showColorPicker, setShowColorPicker] = useState<string | null>(null);

  const handleColorChange = (colorKey: string, value: string) => {
    setColors(prev => ({ ...prev, [colorKey]: value }));
    onChange();
  };

  const handleDarkModeToggle = () => {
    setDarkMode(!darkMode);
    onChange();
  };

  const handleReset = () => {
    setColors({
      primary: '#1976d2',
      secondary: '#dc004e',
      success: '#2e7d32',
      error: '#d32f2f',
      warning: '#ed6c02',
      info: '#0288d1',
      background: '#ffffff',
      surface: '#f5f5f5',
      text: '#000000' });
    setBorderRadius(8);
    setElevation(1);
    onChange();
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
  };

  const presetThemes = [
    { name: 'Default', primary: '#1976d2', secondary: '#dc004e' },
    { name: 'Elegant', primary: '#424242', secondary: '#ffd700' },
    { name: 'Nature', primary: '#2e7d32', secondary: '#81c784' },
    { name: 'Ocean', primary: '#0277bd', secondary: '#26c6da' },
    { name: 'Sunset', primary: '#f57c00', secondary: '#ffb74d' },
  ];

  return (
    <Box>
      <Grid container spacing={3}>
        {/* Theme Mode */}
        <Grid item xs={12}>
          <Paper sx={{ p: 3 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <Box>
                <Typography variant="h6" gutterBottom>
                  Theme Mode
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Choose between light and dark </Typography>
              </Box>
              <FormControlLabel
                control={
                  <Switch
                    checked={darkMode}
                    onChange={handleDarkModeToggle}
                    icon={<Brightness7 />}
                    checkedIcon={<Brightness4 />}
                  />
                }
                label={darkMode ? 'Dark' : 'Light'}
              />
            </Box>
          </Paper>
        </Grid>

        {/* Preset Themes */}
        <Grid item xs={12}>
          <Paper sx={{ p: 3 }}>
            <Typography variant="h6" gutterBottom>
              Preset Themes
            </Typography>
            <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap', mt: 2 }}>
              {presetThemes.map((preset) => (
                <Button
                  key={preset.name}
                  variant="outlined"
                  onClick={() => {
                    setColors(prev => ({
                      ...prev,
                      primary: preset.primary,
                      secondary: preset.secondary }));
                    onChange();
                  }}
                  sx={{
                    borderColor: preset.primary,
                    color: preset.primary,
                    '&:hover': {
                      backgroundColor: preset.primary,
                      color: 'white' } }}
                >
                  {preset.name}
                </Button>
              ))}
            </Box>
          </Paper>
        </Grid>

        {/* Color */}
        <Grid item xs={12}>
          <Paper sx={{ p: 3 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 3 }}>
              <Typography variant="h6">
                Color </Typography>
              <Button
                startIcon={<RestartAlt />}
                onClick={handleReset}
                size="small"
              >
                Reset Colors
              </Button>
            </Box>

            <Grid container spacing={2}>
              {Object.entries(colors).map(([key, value]) => (
                <Grid item xs={12} sm={6} md={4} key={key}>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                    <Box
                      sx={{
                        width: 40,
                        height: 40,
                        backgroundColor: value,
                        borderRadius: 1,
                        border: 1,
                        borderColor: 'divider',
                        cursor: 'pointer' }}
                      onClick={() => setShowColorPicker(showColorPicker === key ? null : key)}
                    />
                    <Box sx={{ flexGrow: 1 }}>
                      <Typography variant="body2" sx={{ textTransform: 'capitalize' }}>
                        {key}
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        {value}
                      </Typography>
                    </Box>
                    <IconButton
                      size="small"
                      onClick={() => copyToClipboard(value)}
                    >
                      <ContentCopy fontSize="small" />
                    </IconButton>
                  </Box>
                  
                  {showColorPicker === key && (
                    <Box sx={{ mt: 2 }}>
                      <HexColorPicker
                        color={value}
                        onChange={(newColor) => handleColorChange(key, newColor)}
                      />
                    </Box>
                  )}
                </Grid>
              ))}
            </Grid>
          </Paper>
        </Grid>

        {/* Design Settings */}
        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 3 }}>
            <Typography variant="h6" gutterBottom>
              Border Radius
            </Typography>
            <Box sx={{ px: 2 }}>
              <Slider
                value={borderRadius}
                onChange={ (value) => {
                  setBorderRadius(value as number);
                  onChange();
                 }}
                min={0}
                max={24}
                marks
                valueLabelDisplay="auto"
              />
            </Box>
            <Box sx={{ display: 'flex', gap: 1, mt: 2 }}>
              {[0, 4, 8, 12, 16].map(radius => (
                <Chip
                  key={radius}
                  label={`${radius}px`}
                  onClick={() => {
                    setBorderRadius(radius);
                    onChange();
                  }}
                  variant={borderRadius === radius ? 'filled' : 'outlined'}
                  size="small"
                />
              ))}
            </Box>
          </Paper>
        </Grid>

        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 3 }}>
            <Typography variant="h6" gutterBottom>
              Elevation (Shadow)
            </Typography>
            <Box sx={{ px: 2 }}>
              <Slider
                value={elevation}
                onChange={ (value) => {
                  setElevation(value as number);
                  onChange();
                 }}
                min={0}
                max={24}
                marks
                valueLabelDisplay="auto"
              />
            </Box>
            <Box sx={{ display: 'flex', gap: 2, mt: 2 }}>
              {[0, 1, 2, 4, 8].map(elev => (
                <Paper
                  key={elev}
                  elevation={elev}
                  sx={{
                    width: 60,
                    height: 60,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    cursor: 'pointer' }}
                  onClick={() => {
                    setElevation(elev);
                    onChange();
                  }}
                >
                  {elev}
                </Paper>
              ))}
            </Box>
          </Paper>
        </Grid>

        {/* Theme Export */}
        <Grid item xs={12}>
          <Paper sx={{ p: 3 }}>
            <Typography variant="h6" gutterBottom>
              Export Theme
            </Typography>
            <Typography variant="body2" color="text.secondary" gutterBottom>
              Copy this configuration to use in your application
            </Typography>
            <TextField
              fullWidth
              multiline
              rows={4}
              value={JSON.stringify({ darkMode, colors, borderRadius, elevation }, null, 2)}
              sx={{ mt: 2, fontFamily: 'monospace' }}
              InputProps={{
                readOnly: true,
                endAdornment: (
                  <InputAdornment position="end">
                    <IconButton
                      onClick={() => copyToClipboard(JSON.stringify({ darkMode, colors, borderRadius, elevation }))}
                    >
                      <ContentCopy />
                    </IconButton>
                  </InputAdornment>
                ) }}
            />
          </Paper>
        </Grid>
      </Grid>
    </Box>
  );
};
