import React, { useState } from 'react';
import {
  Box,
  Paper,
  Typography,
  FormControl,
  RadioGroup,
  FormControlLabel,
  Radio,
  Button,
  Alert,
  Divider,
  Grid,
  Card,
  CardContent,
} from '@mui/material';
import { useTranslation } from 'react-i18next';
import { supportedLanguages } from '@/i18n/config';
import { LanguageSelector } from '@/components/i18n/LanguageSelector';
import { TranslationExample } from '@/components/i18n/TranslationExample';

export const LanguageSettings: React.FC = () => {
  const { t, i18n } = useTranslation();
  const [selectedLanguage, setSelectedLanguage] = useState(i18n.language);
  const [saved, setSaved] = useState(false);

  const handleLanguageChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setSelectedLanguage(event.target.value);
    setSaved(false);
  };

  const handleSave = () => {
    i18n.changeLanguage(selectedLanguage);
    localStorage.setItem('i18nextLng', selectedLanguage);
    
    // Update document direction for RTL languages
    const lang = supportedLanguages[selectedLanguage as keyof typeof supportedLanguages];
    document.dir = lang.dir;
    
    setSaved(true);
    setTimeout(() => setSaved(false), 3000);
  };

  return (
    <Box>
      <Typography variant="h4" gutterBottom>
        {t('settings.language')}
      </Typography>

      <Grid container spacing={3}>
        <Grid item xs={12} md={8}>
          <Paper sx={{ p: 3, mb: 3 }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
              <Typography variant="h6">
                {t('common.language')} Settings
              </Typography>
              <LanguageSelector />
            </Box>

            <Divider sx={{ mb: 3 }} />

            <FormControl component="fieldset">
              <RadioGroup
                value={selectedLanguage}
                onChange={handleLanguageChange}
              >
                {Object.entries(supportedLanguages).map(([code, lang]) => (
                  <FormControlLabel
                    key={code}
                    value={code}
                    control={<Radio />}
                    label={
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <Typography variant="h6">{lang.flag}</Typography>
                        <Box>
                          <Typography>{lang.name}</Typography>
                          <Typography variant="caption" color="text.secondary">
                            {code.toUpperCase()}
                          </Typography>
                        </Box>
                      </Box>
                    }
                    sx={{ mb: 2 }}
                  />
                ))}
              </RadioGroup>
            </FormControl>

            <Box sx={{ mt: 3, display: 'flex', gap: 2 }}>
              <Button
                variant="contained"
                onClick={handleSave}
                disabled={selectedLanguage === i18n.language}
              >
                {t('common.save')}
              </Button>
              <Button
                variant="outlined"
                onClick={() => setSelectedLanguage(i18n.language)}
                disabled={selectedLanguage === i18n.language}
              >
                {t('common.cancel')}
              </Button>
            </Box>

            {saved && (
              <Alert severity="success" sx={{ mt: 2 }}>
                {t('success.saved')}
              </Alert>
            )}
          </Paper>

          <Paper sx={{ p: 3 }}>
            <Typography variant="h6" gutterBottom>
              Translation Coverage
            </Typography>
            <Typography variant="body2" color="text.secondary" paragraph>
              Current translation coverage for available languages:
            </Typography>
            
            <Grid container spacing={2}>
              {Object.entries(supportedLanguages).map(([code, lang]) => (
                <Grid item xs={6} sm={4} key={code}>
                  <Card variant="outlined">
                    <CardContent>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                        <Typography variant="h6">{lang.flag}</Typography>
                        <Typography variant="subtitle2">{lang.name}</Typography>
                      </Box>
                      <Typography variant="caption" color="text.secondary">
                        {code === 'en' ? '100% Complete' : 
                         code === 'es' ? '60% Complete' : 
                         'Not yet translated'}
                      </Typography>
                    </CardContent>
                  </Card>
                </Grid>
              ))}
            </Grid>

            <Alert severity="info" sx={{ mt: 3 }}>
              Want to help translate? Contact our support team to contribute translations for your language.
            </Alert>
          </Paper>
        </Grid>

        <Grid item xs={12} md={4}>
          <Paper sx={{ p: 3, position: 'sticky', top: 24 }}>
            <Typography variant="h6" gutterBottom>
              About Language Settings
            </Typography>
            <Typography variant="body2" color="text.secondary" paragraph>
              Choose your preferred language for the interface. This setting will be saved and applied across all pages.
            </Typography>
            
            <Divider sx={{ my: 2 }} />
            
            <Typography variant="subtitle2" gutterBottom>
              Features:
            </Typography>
            <Typography variant="body2" component="ul" sx={{ pl: 2 }}>
              <li>Interface translation</li>
              <li>Date and time formatting</li>
              <li>Number and currency formatting</li>
              <li>RTL support for Arabic</li>
              <li>Automatic browser detection</li>
            </Typography>

            <Alert severity="warning" sx={{ mt: 2 }}>
              Some features may not be fully translated in all languages. English is the most complete translation.
            </Alert>
          </Paper>
        </Grid>
      </Grid>

      <Box sx={{ mt: 3 }}>
        <Typography variant="h5" gutterBottom>
          Translation Preview
        </Typography>
        <TranslationExample />
      </Box>
    </Box>
  );
};
