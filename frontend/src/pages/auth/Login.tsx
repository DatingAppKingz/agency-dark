/**
 * OAuth Login Page
 * Provides OAuth login flow with social provider support
 */

import React, { useState, useEffect } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import { 
  Box, 
  Button, 
  Container, 
  Divider, 
  Paper, 
  TextField, 
  Typography, 
  Alert,
  CircularProgress,
  Stack,
  IconButton,
  InputAdornment,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Checkbox,
  FormControlLabel
} from '@mui/material';
import {
  Google as GoogleIcon,
  Instagram as InstagramIcon,
  Microsoft as MicrosoftIcon,
  Visibility,
  VisibilityOff,
  Business,
  Login as LoginIcon
} from '@mui/icons-material';

// Provider configuration
const OAUTH_PROVIDERS = [
  {
    id: 'google',
    name: 'Google',
    icon: GoogleIcon,
    color: '#4285F4',
    enabled: true,
  },
  {
    id: 'instagram',
    name: 'Instagram',
    icon: InstagramIcon,
    color: '#E4405F',
    enabled: true,
  },
  {
    id: 'microsoft',
    name: 'Microsoft',
    icon: MicrosoftIcon,
    color: '#0078D4',
    enabled: true,
  },
];

/**
 * Login Page Component
 */
const Login: React.FC = () => {
  const navigate = useNavigate();
  const { initiateOAuthFlow, connectProvider, isAuthenticated, isLoading, error } = useAuth();
  
  // Form state
  const [agency, setAgency] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [rememberMe, setRememberMe] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [showJWTFallback, setShowJWTFallback] = useState(false);

  // Redirect if already authenticated
  useEffect(() => {
    if (isAuthenticated && !isLoading) {
      navigate('/dashboard');
    }
  }, [isAuthenticated, isLoading, navigate]);

  // Detect agency from subdomain
  useEffect(() => {
    const hostname = window.location.hostname;
    const parts = hostname.split('.');
    if (parts.length > 2) {
      setAgency(parts[0]);
    }
  }, []);

  /**
   * Handle OAuth login
   */
  const handleOAuthLogin = async () => {
    try {
      setIsSubmitting(true);
      setFormError(null);
      
      // Store agency preference
      if (agency) {
        sessionStorage.setItem('selected_agency', agency);
      }
      
      // Initiate OAuth flow
      await initiateOAuthFlow('login');
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Login failed';
      setFormError(message);
    } finally {
      setIsSubmitting(false);
    }
  };

  /**
   * Handle social provider login
   */
  const handleSocialLogin = async (providerId: string) => {
    try {
      setIsSubmitting(true);
      setFormError(null);
      
      // Store agency preference
      if (agency) {
        sessionStorage.setItem('selected_agency', agency);
      }
      
      // Connect to provider
      await connectProvider(providerId);
    } catch (err) {
      const message = err instanceof Error ? err.message : `Failed to connect to ${providerId}`;
      setFormError(message);
    } finally {
      setIsSubmitting(false);
    }
  };

  /**
   * Handle JWT fallback login (if enabled)
   */
  const handleJWTLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!email || !password) {
      setFormError('Please enter email and password');
      return;
    }
    
    try {
      setIsSubmitting(true);
      setFormError(null);
      
      // This would call a JWT login endpoint if available
      // For now, show message
      setFormError('JWT authentication is being phased out. Please use OAuth login.');
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Login failed';
      setFormError(message);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Container component="main" maxWidth="sm">
      <Box
        sx={{
          marginTop: 8,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
        }}
      >
        <Paper
          elevation={3}
          sx={{
            padding: 4,
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            width: '100%',
          }}
        >
          {/* Logo/Title */}
          <Typography component="h1" variant="h4" sx={{ mb: 3 }}>
            Agency Dark
          </Typography>
          
          <Typography variant="h6" sx={{ mb: 3 }}>
            Sign in to your account
          </Typography>

          {/* Error Alert */}
          {(formError || error) && (
            <Alert severity="error" sx={{ width: '100%', mb: 2 }}>
              {formError || error}
            </Alert>
          )}

          {/* Agency Selection */}
          <FormControl fullWidth sx={{ mb: 3 }}>
            <InputLabel id="agency-label">
              <Business sx={{ mr: 1, verticalAlign: 'middle' }} />
              Agency
            </InputLabel>
            <Select
              labelId="agency-label"
              value={agency}
              label="Agency"
              onChange={(e) => setAgency(e.target.value)}
              disabled={isSubmitting}
            >
              <MenuItem value="">Select Agency</MenuItem>
              <MenuItem value="demo">Demo Agency</MenuItem>
              <MenuItem value="test">Test Agency</MenuItem>
              {/* Add more agencies dynamically */}
            </Select>
          </FormControl>

          {/* OAuth Login Button */}
          <Button
            fullWidth
            variant="contained"
            size="large"
            onClick={handleOAuthLogin}
            disabled={isSubmitting || !agency}
            startIcon={isSubmitting ? <CircularProgress size={20} /> : <LoginIcon />}
            sx={{ mb: 2 }}
          >
            {isSubmitting ? 'Signing in...' : 'Sign in with OAuth'}
          </Button>

          {/* Divider */}
          <Divider sx={{ width: '100%', my: 2 }}>
            <Typography variant="body2" color="text.secondary">
              OR
            </Typography>
          </Divider>

          {/* Social Login Buttons */}
          <Stack spacing={2} sx={{ width: '100%', mb: 2 }}>
            {OAUTH_PROVIDERS.filter(p => p.enabled).map((provider) => {
              const Icon = provider.icon;
              return (
                <Button
                  key={provider.id}
                  fullWidth
                  variant="outlined"
                  onClick={() => handleSocialLogin(provider.id)}
                  disabled={isSubmitting || !agency}
                  startIcon={<Icon />}
                  sx={{
                    borderColor: provider.color,
                    color: provider.color,
                    '&:hover': {
                      borderColor: provider.color,
                      backgroundColor: `${provider.color}10`,
                    },
                  }}
                >
                  Continue with {provider.name}
                </Button>
              );
            })}
          </Stack>

          {/* JWT Fallback Toggle */}
          {process.env.REACT_APP_JWT_FALLBACK_ENABLED === 'true' && (
            <>
              <Button
                variant="text"
                size="small"
                onClick={() => setShowJWTFallback(!showJWTFallback)}
                sx={{ mb: 2 }}
              >
                Use legacy login
              </Button>

              {/* JWT Login Form */}
              {showJWTFallback && (
                <Box
                  component="form"
                  onSubmit={handleJWTLogin}
                  sx={{ width: '100%' }}
                >
                  <TextField
                    margin="normal"
                    required
                    fullWidth
                    id="email"
                    label="Email Address"
                    name="email"
                    autoComplete="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    disabled={isSubmitting}
                  />
                  
                  <TextField
                    margin="normal"
                    required
                    fullWidth
                    name="password"
                    label="Password"
                    type={showPassword ? 'text' : 'password'}
                    id="password"
                    autoComplete="current-password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    disabled={isSubmitting}
                    InputProps={{
                      endAdornment: (
                        <InputAdornment position="end">
                          <IconButton
                            onClick={() => setShowPassword(!showPassword)}
                            edge="end"
                          >
                            {showPassword ? <VisibilityOff /> : <Visibility />}
                          </IconButton>
                        </InputAdornment>
                      ),
                    }}
                  />
                  
                  <FormControlLabel
                    control={
                      <Checkbox
                        value="remember"
                        color="primary"
                        checked={rememberMe}
                        onChange={(e) => setRememberMe(e.target.checked)}
                      />
                    }
                    label="Remember me"
                  />
                  
                  <Button
                    type="submit"
                    fullWidth
                    variant="contained"
                    sx={{ mt: 3, mb: 2 }}
                    disabled={isSubmitting}
                  >
                    {isSubmitting ? <CircularProgress size={24} /> : 'Sign In (Legacy)'}
                  </Button>
                </Box>
              )}
            </>
          )}

          {/* Links */}
          <Stack
            direction="row"
            justifyContent="space-between"
            alignItems="center"
            sx={{ width: '100%', mt: 2 }}
          >
            <Link to="/forgot-password" style={{ textDecoration: 'none' }}>
              <Typography variant="body2" color="primary">
                Forgot password?
              </Typography>
            </Link>
            
            <Link to="/register" style={{ textDecoration: 'none' }}>
              <Typography variant="body2" color="primary">
                Don't have an account? Sign up
              </Typography>
            </Link>
          </Stack>

          {/* Footer */}
          <Typography
            variant="body2"
            color="text.secondary"
            align="center"
            sx={{ mt: 4 }}
          >
            By signing in, you agree to our{' '}
            <Link to="/terms" style={{ textDecoration: 'none', color: 'inherit' }}>
              Terms of Service
            </Link>{' '}
            and{' '}
            <Link to="/privacy" style={{ textDecoration: 'none', color: 'inherit' }}>
              Privacy Policy
            </Link>
          </Typography>
        </Paper>
      </Box>
    </Container>
  );
};

export default Login;