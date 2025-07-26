import React from 'react';
import { Box, Typography, Paper, Grid, Button } from '@mui/material';
import { useTranslations } from '@/hooks/useTranslations';

export const TranslationExample: React.FC = () => {
  const { t, formatDate, formatCurrency, formatNumber, formatRelativeTime } = useTranslations();

  const sampleDate = new Date('2024-01-15');
  const sampleAmount = 12345.67;
  const sampleNumber = 1234567;
  const recentDate = new Date(Date.now() - 1000 * 60 * 30); // 30 minutes ago

  return (
    <Paper sx={{ p: 3 }}>
      <Typography variant="h5" gutterBottom>
        {t('common.appName')} - Translation Examples
      </Typography>

      <Grid container spacing={3}>
        <Grid item xs={12} md={6}>
          <Typography variant="h6" gutterBottom>
            {t('common.language')}
          </Typography>
          
          <Box sx={{ mb: 2 }}>
            <Typography variant="subtitle2">Basic Translation:</Typography>
            <Typography>{t('auth.login')}</Typography>
            <Typography>{t('dashboard.welcome', { name: 'John' })}</Typography>
          </Box>

          <Box sx={{ mb: 2 }}>
            <Typography variant="subtitle2">Navigation:</Typography>
            <Typography>{t('navigation.dashboard')}</Typography>
            <Typography>{t('navigation.users')}</Typography>
            <Typography>{t('navigation.analytics')}</Typography>
          </Box>

          <Box sx={{ mb: 2 }}>
            <Typography variant="subtitle2">Actions:</Typography>
            <Button variant="contained" size="small" sx={{ mr: 1 }}>
              {t('common.save')}
            </Button>
            <Button variant="outlined" size="small" sx={{ mr: 1 }}>
              {t('common.cancel')}
            </Button>
            <Button variant="text" size="small" color="error">
              {t('common.delete')}
            </Button>
          </Box>
        </Grid>

        <Grid item xs={12} md={6}>
          <Typography variant="h6" gutterBottom>
            Formatting Examples
          </Typography>

          <Box sx={{ mb: 2 }}>
            <Typography variant="subtitle2">Date Formatting:</Typography>
            <Typography>
              Short: {formatDate(sampleDate, { dateStyle: 'short' })}
            </Typography>
            <Typography>
              Long: {formatDate(sampleDate, { dateStyle: 'long' })}
            </Typography>
            <Typography>
              Full: {formatDate(sampleDate, { dateStyle: 'full' })}
            </Typography>
          </Box>

          <Box sx={{ mb: 2 }}>
            <Typography variant="subtitle2">Number Formatting:</Typography>
            <Typography>
              Standard: {formatNumber(sampleNumber)}
            </Typography>
            <Typography>
              Currency: {formatCurrency(sampleAmount)}
            </Typography>
            <Typography>
              Currency (EUR): {formatCurrency(sampleAmount, 'EUR')}
            </Typography>
          </Box>

          <Box sx={{ mb: 2 }}>
            <Typography variant="subtitle2">Relative Time:</Typography>
            <Typography>
              {formatRelativeTime(recentDate)}
            </Typography>
            <Typography>
              {formatRelativeTime(sampleDate)}
            </Typography>
          </Box>
        </Grid>

        <Grid item xs={12}>
          <Typography variant="h6" gutterBottom>
            Role Translations
          </Typography>
          <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
            <Typography>{t('roles.superAdmin')}</Typography>
            <Typography>{t('roles.agencyOwner')}</Typography>
            <Typography>{t('roles.model')}</Typography>
            <Typography>{t('roles.chatter')}</Typography>
          </Box>
        </Grid>
      </Grid>
    </Paper>
  );
};