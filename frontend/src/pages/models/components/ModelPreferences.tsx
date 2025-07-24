import { useState } from 'react';
import {
  Box,
  Grid,
  Typography,
  Paper,
  TextField,
  Switch,
  FormControlLabel,
  Chip,
  Button,
  InputAdornment,
  Divider,
} from '@mui/material';
import { Add, AttachMoney } from '@mui/icons-material';
import { useToast } from '@/components/common/Toaster';

interface ModelPreferencesProps {
  modelId: string;
}

export const ModelPreferences = ({ modelId }: ModelPreferencesProps) => {
  const { success } = useToast();
  
  const [preferences, setPreferences] = useState({
    autoReplyEnabled: true,
    welcomeMessage: "Hey there! Thanks for subscribing! 💕 I'm excited to connect with you. Feel free to message me anytime!",
    minTipAmount: 5,
    chatRatePerMinute: 0,
    contentCategories: ['Photos', 'Videos', 'Behind the Scenes', 'Personal Updates'],
    blockedWords: ['spam', 'scam', 'meet', 'phone'],
  });

  const [newCategory, setNewCategory] = useState('');
  const [newBlockedWord, setNewBlockedWord] = useState('');

  const handleSavePreferences = () => {
    // Save preferences API call would go here
    success('Preferences saved successfully');
  };

  const handleAddCategory = () => {
    if (newCategory && !preferences.contentCategories.includes(newCategory)) {
      setPreferences({
        ...preferences,
        contentCategories: [...preferences.contentCategories, newCategory],
      });
      setNewCategory('');
    }
  };

  const handleRemoveCategory = (category: string) => {
    setPreferences({
      ...preferences,
      contentCategories: preferences.contentCategories.filter(c => c !== category),
    });
  };

  const handleAddBlockedWord = () => {
    if (newBlockedWord && !preferences.blockedWords.includes(newBlockedWord.toLowerCase())) {
      setPreferences({
        ...preferences,
        blockedWords: [...preferences.blockedWords, newBlockedWord.toLowerCase()],
      });
      setNewBlockedWord('');
    }
  };

  const handleRemoveBlockedWord = (word: string) => {
    setPreferences({
      ...preferences,
      blockedWords: preferences.blockedWords.filter(w => w !== word),
    });
  };

  return (
    <Box sx={{ p: 3 }}>
      <Grid container spacing={3}>
        {/* Messaging Preferences */}
        <Grid item xs={12}>
          <Paper sx={{ p: 3 }}>
            <Typography variant="h6" gutterBottom>
              Messaging Preferences
            </Typography>
            
            <FormControlLabel
              control={
                <Switch
                  checked={preferences.autoReplyEnabled}
                  onChange={(e) => setPreferences({ ...preferences, autoReplyEnabled: e.target.checked })}
                />
              }
              label="Enable auto-reply for new subscribers"
              sx={{ mb: 2 }}
            />

            <TextField
              fullWidth
              multiline
              rows={4}
              label="Welcome Message"
              value={preferences.welcomeMessage}
              onChange={(e) => setPreferences({ ...preferences, welcomeMessage: e.target.value })}
              disabled={!preferences.autoReplyEnabled}
              helperText="This message will be automatically sent to new subscribers"
            />
          </Paper>
        </Grid>

        {/* Pricing Preferences */}
        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 3 }}>
            <Typography variant="h6" gutterBottom>
              Pricing Settings
            </Typography>
            
            <TextField
              fullWidth
              label="Minimum Tip Amount"
              type="number"
              value={preferences.minTipAmount}
              onChange={(e) => setPreferences({ ...preferences, minTipAmount: Number(e.target.value) })}
              InputProps={{
                startAdornment: (
                  <InputAdornment position="start">
                    <AttachMoney />
                  </InputAdornment>
                ),
                inputProps: { min: 0, step: 1 },
              }}
              sx={{ mb: 2 }}
            />

            <TextField
              fullWidth
              label="Chat Rate per Minute"
              type="number"
              value={preferences.chatRatePerMinute}
              onChange={(e) => setPreferences({ ...preferences, chatRatePerMinute: Number(e.target.value) })}
              InputProps={{
                startAdornment: (
                  <InputAdornment position="start">
                    <AttachMoney />
                  </InputAdornment>
                ),
                inputProps: { min: 0, step: 0.01 },
              }}
              helperText="Set to 0 for free chat"
            />
          </Paper>
        </Grid>

        {/* Content Categories */}
        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 3 }}>
            <Typography variant="h6" gutterBottom>
              Content Categories
            </Typography>
            
            <Box sx={{ display: 'flex', gap: 1, mb: 2 }}>
              <TextField
                size="small"
                placeholder="Add category"
                value={newCategory}
                onChange={(e) => setNewCategory(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && handleAddCategory()}
                sx={{ flexGrow: 1 }}
              />
              <Button variant="outlined" onClick={handleAddCategory} startIcon={<Add />}>
                Add
              </Button>
            </Box>

            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
              {preferences.contentCategories.map((category) => (
                <Chip
                  key={category}
                  label={category}
                  onDelete={() => handleRemoveCategory(category)}
                  color="primary"
                  variant="outlined"
                />
              ))}
            </Box>
          </Paper>
        </Grid>

        {/* Blocked Words */}
        <Grid item xs={12}>
          <Paper sx={{ p: 3 }}>
            <Typography variant="h6" gutterBottom>
              Content Moderation
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              Messages containing these words will be automatically flagged for review
            </Typography>
            
            <Box sx={{ display: 'flex', gap: 1, mb: 2 }}>
              <TextField
                size="small"
                placeholder="Add blocked word"
                value={newBlockedWord}
                onChange={(e) => setNewBlockedWord(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && handleAddBlockedWord()}
                sx={{ flexGrow: 1 }}
              />
              <Button variant="outlined" onClick={handleAddBlockedWord} startIcon={<Add />}>
                Add
              </Button>
            </Box>

            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
              {preferences.blockedWords.map((word) => (
                <Chip
                  key={word}
                  label={word}
                  onDelete={() => handleRemoveBlockedWord(word)}
                  color="error"
                  variant="outlined"
                  size="small"
                />
              ))}
            </Box>
          </Paper>
        </Grid>

        {/* Save Button */}
        <Grid item xs={12}>
          <Divider sx={{ my: 2 }} />
          <Box sx={{ display: 'flex', justifyContent: 'flex-end' }}>
            <Button
              variant="contained"
              size="large"
              onClick={handleSavePreferences}
            >
              Save Preferences
            </Button>
          </Box>
        </Grid>
      </Grid>
    </Box>
  );
};