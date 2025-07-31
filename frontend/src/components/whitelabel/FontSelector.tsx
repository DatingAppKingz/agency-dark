import { useState } from 'react';
import {
  Box,
  Typography,
  Grid,
  Paper,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Slider,
  TextField,
  Button,
  Divider,
  Chip } from '@mui/material';
import {
  RestartAlt,
  Add } from '@mui/icons-material';

interface FontSelectorProps {
  onChange: () => void;
}

interface FontSettings {
  primary: string;
  secondary: string;
  mono: string;
  customFonts: string[];
  sizes: {
    base: number;
    scale: number;
  };
  weights: {
    light: number;
    regular: number;
    medium: number;
    bold: number;
  };
  lineHeight: number;
  letterSpacing: number;
}

export const FontSelector = ({ onChange }: FontSelectorProps) => {
  const [fontSettings, setFontSettings] = useState<FontSettings>({
    primary: 'Inter',
    secondary: 'Inter',
    mono: 'Fira Code',
    customFonts: [],
    sizes: {
      base: 16,
      scale: 1.2 },
    weights: {
      light: 300,
      regular: 400,
      medium: 500,
      bold: 700 },
    lineHeight: 1.5,
    letterSpacing: 0 });

  const [customFontUrl, setCustomFontUrl] = useState('');

  const googleFonts = [
    'Inter',
    'Roboto',
    'Open Sans',
    'Lato',
    'Montserrat',
    'Poppins',
    'Raleway',
    'Playfair Display',
    'Merriweather',
    'Source Sans Pro',
    'Nunito',
    'Work Sans',
    'Quicksand',
    'Karla',
    'Rubik',
  ];

  const monoFonts = [
    'Fira Code',
    'JetBrains Mono',
    'Source Code Pro',
    'IBM Plex Mono',
    'Roboto Mono',
    'Cascadia Code',
    'Inconsolata',
  ];

  const handleFontChange = (type: 'primary' | 'secondary' | 'mono', value: string) => {
    setFontSettings(prev => ({ ...prev, [type]: value }));
    onChange();
  };

  const handleSizeChange = (field: 'base' | 'scale', value: number) => {
    setFontSettings(prev => ({
      ...prev,
      sizes: { ...prev.sizes, [field]: value } }));
    onChange();
  };

  const handleWeightChange = (weight: keyof FontSettings['weights'], value: number) => {
    setFontSettings(prev => ({
      ...prev,
      weights: { ...prev.weights, [weight]: value } }));
    onChange();
  };

  const addCustomFont = () => {
    if (customFontUrl && !fontSettings.customFonts.includes(customFontUrl)) {
      setFontSettings(prev => ({
        ...prev,
        customFonts: [...prev.customFonts, customFontUrl] }));
      setCustomFontUrl('');
      onChange();
    }
  };

  const removeCustomFont = (font: string) => {
    setFontSettings(prev => ({
      ...prev,
      customFonts: prev.customFonts.filter(f => f !== font) }));
    onChange();
  };

  const resetToDefaults = () => {
    setFontSettings({
      primary: 'Inter',
      secondary: 'Inter',
      mono: 'Fira Code',
      customFonts: [],
      sizes: {
        base: 16,
        scale: 1.2 },
      weights: {
        light: 300,
        regular: 400,
        medium: 500,
        bold: 700 },
      lineHeight: 1.5,
      letterSpacing: 0 });
    onChange();
  };

  const generateTypographyScale = () => {
    const { base, scale } = fontSettings.sizes;
    return {
      h1: Math.round(base * Math.pow(scale, 5)),
      h2: Math.round(base * Math.pow(scale, 4)),
      h3: Math.round(base * Math.pow(scale, 3)),
      h4: Math.round(base * Math.pow(scale, 2)),
      h5: Math.round(base * scale),
      h6: base,
      body1: base,
      body2: Math.round(base * 0.875),
      caption: Math.round(base * 0.75) };
  };

  const typographyScale = generateTypographyScale();

  return (
    <Box>
      <Grid container spacing={3}>
        {/* Font Selection */}
        <Grid item xs={12}>
          <Paper sx={{ p: 3 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 3 }}>
              <Typography variant="h6">
                Font Family
              </Typography>
              <Button
                startIcon={<RestartAlt />}
                onClick={resetToDefaults}
                size="small"
              >
                Reset to Defaults
              </Button>
            </Box>

            <Grid container spacing={3}>
              <Grid item xs={12} md={4}>
                <FormControl fullWidth>
                  <InputLabel>Primary Font</InputLabel>
                  <Select
                    value={fontSettings.primary}
                    onChange={() => handleFontChange('primary', .target.value)}
                    label="Primary Font"
                  >
                    {googleFonts.map(font => (
                      <MenuItem key={font} value={font} sx={{ fontFamily: font }}>
                        {font}
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>
              </Grid>

              <Grid item xs={12} md={4}>
                <FormControl fullWidth>
                  <InputLabel>Secondary Font</InputLabel>
                  <Select
                    value={fontSettings.secondary}
                    onChange={() => handleFontChange('secondary', .target.value)}
                    label="Secondary Font"
                  >
                    {googleFonts.map(font => (
                      <MenuItem key={font} value={font} sx={{ fontFamily: font }}>
                        {font}
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>
              </Grid>

              <Grid item xs={12} md={4}>
                <FormControl fullWidth>
                  <InputLabel>Monospace Font</InputLabel>
                  <Select
                    value={fontSettings.mono}
                    onChange={() => handleFontChange('mono', .target.value)}
                    label="Monospace Font"
                  >
                    {monoFonts.map(font => (
                      <MenuItem key={font} value={font} sx={{ fontFamily: font }}>
                        {font}
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>
              </Grid>
            </Grid>
          </Paper>
        </Grid>

        {/* Typography Scale */}
        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 3 }}>
            <Typography variant="h6" gutterBottom>
              Typography Scale
            </Typography>
            
            <Box sx={{ mb: 3 }}>
              <Typography gutterBottom>Base Size: {fontSettings.sizes.base}px</Typography>
              <Slider
                value={fontSettings.sizes.base}
                onChange={(value) => handleSizeChange('base', value as number)}
                min={12}
                max={20}
                marks
                valueLabelDisplay="auto"
              />
            </Box>

            <Box sx={{ mb: 3 }}>
              <Typography gutterBottom>Scale Ratio: {fontSettings.sizes.scale}</Typography>
              <Slider
                value={fontSettings.sizes.scale}
                onChange={(value) => handleSizeChange('scale', value as number)}
                min={1.1}
                max={1.5}
                step={0.05}
                marks
                valueLabelDisplay="auto"
              />
            </Box>

            <Divider sx={{ my: 2 }} />

            <Box sx={{ mt: 2 }}>
              {Object.entries(typographyScale).map(([variant, size]) => (
                <Box key={variant} sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                  <Typography variant="body2" sx={{ width: 60 }}>
                    {variant}:
                  </Typography>
                  <Typography
                    sx={{
                      fontSize: `${size}px`,
                      fontFamily: fontSettings.primary,
                      ml: 2 }}
                  >
                    {size}px
                  </Typography>
                </Box>
              ))}
            </Box>
          </Paper>
        </Grid>

        {/* Font Weights */}
        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 3 }}>
            <Typography variant="h6" gutterBottom>
              Font Weights
            </Typography>

            {Object.entries(fontSettings.weights).map(([weight, value]) => (
              <Box key={weight} sx={{ mb: 3 }}>
                <Typography gutterBottom sx={{ textTransform: 'capitalize' }}>
                  {weight}: {value}
                </Typography>
                <Slider
                  value={value}
                  onChange={(val) => handleWeightChange(weight as keyof FontSettings['weights'], val as number)}
                  min={100}
                  max={900}
                  step={100}
                  marks
                  valueLabelDisplay="auto"
                />
              </Box>
            ))}
          </Paper>
        </Grid>

        {/* Line Height & Letter Spacing */}
        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 3 }}>
            <Typography variant="h6" gutterBottom>
              Line Height
            </Typography>
            <Slider
              value={fontSettings.lineHeight}
              onChange={(value) => {
                setFontSettings(prev => ({ ...prev, lineHeight: value as number }));
                onChange();
              }}
              min={1}
              max={2}
              step={0.1}
              marks
              valueLabelDisplay="auto"
            />
            <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
              Current: {fontSettings.lineHeight}
            </Typography>
          </Paper>
        </Grid>

        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 3 }}>
            <Typography variant="h6" gutterBottom>
              Letter Spacing
            </Typography>
            <Slider
              value={fontSettings.letterSpacing}
              onChange={(value) => {
                setFontSettings(prev => ({ ...prev, letterSpacing: value as number }));
                onChange();
              }}
              min={-0.05}
              max={0.1}
              step={0.01}
              marks
              valueLabelDisplay="auto"
            />
            <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
              Current: {fontSettings.letterSpacing}em
            </Typography>
          </Paper>
        </Grid>

        {/* Custom Fonts */}
        <Grid item xs={12}>
          <Paper sx={{ p: 3 }}>
            <Typography variant="h6" gutterBottom>
              Custom Fonts
            </Typography>
            <Typography variant="body2" color="text.secondary" gutterBottom>
              Add custom web fonts by providing their URL
            </Typography>

            <Box sx={{ display: 'flex', gap: 2, mt: 2 }}>
              <TextField
                fullWidth
                label="Font URL"
                value={customFontUrl}
                onChange={() => setCustomFontUrl(event.target.value)}
                placeholder="https://fonts.googleapis.com/css2?family=..."
              />
              <Button
                variant="contained"
                startIcon={<Add />}
                onClick={addCustomFont}
                disabled={!customFontUrl}
              >
                Add
              </Button>
            </Box>

            {fontSettings.customFonts.length > 0 && (
              <Box sx={{ mt: 2, display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                {fontSettings.customFonts.map(font => (
                  <Chip
                    key={font}
                    label={font}
                    onDelete={() => removeCustomFont(font)}
                  />
                ))}
              </Box>
            )}
          </Paper>
        </Grid>

        {/* Preview */}
        <Grid item xs={12}>
          <Paper sx={{ p: 3 }}>
            <Typography variant="h6" gutterBottom>
              Preview
            </Typography>
            
            <Box sx={{ fontFamily: fontSettings.primary, lineHeight: fontSettings.lineHeight, letterSpacing: `${fontSettings.letterSpacing}em` }}>
              <Typography variant="h1" sx={{ fontSize: `${typographyScale.h1}px`, fontWeight: fontSettings.weights.bold, mb: 2 }}>
                Heading 1
              </Typography>
              <Typography variant="h2" sx={{ fontSize: `${typographyScale.h2}px`, fontWeight: fontSettings.weights.bold, mb: 2 }}>
                Heading 2
              </Typography>
              <Typography variant="h3" sx={{ fontSize: `${typographyScale.h3}px`, fontWeight: fontSettings.weights.medium, mb: 2 }}>
                Heading 3
              </Typography>
              <Typography sx={{ fontSize: `${typographyScale.body1}px`, fontWeight: fontSettings.weights.regular, mb: 2 }}>
                This is body text using the primary font family. Lorem ipsum dolor sit amet, consectetur adipiscing elit. 
                Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.
              </Typography>
              <Typography sx={{ fontFamily: fontSettings.mono, fontSize: `${typographyScale.body2}px`, backgroundColor: 'grey.100', p: 2, borderRadius: 1 }}>
                const example = 'This is monospace font';
              </Typography>
            </Box>
          </Paper>
        </Grid>
      </Grid>
    </Box>
  );
};
