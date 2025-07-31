import { useState } from 'react';
import { Link as RouterLink, useNavigate, useLocation } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import {
  Box,
  Button,
  TextField,
  Typography,
  Link,
  IconButton,
  InputAdornment,
} from '@mui/material';
import { Visibility, VisibilityOff } from '@mui/icons-material';
import { useAuthStore } from '@/store/authStore';
import { useToast } from '@/components/common/Toaster';
import { LoginCredentials } from '@/types/auth';
import { SEOHead } from '@/components/seo/SEOHead';
import { StructuredData } from '@/components/seo/StructuredData';

const loginSchema = z.object({
  email: z.string().email('Invalid email address'),
  password: z.string().min(6, 'Password must be at least 6 characters'),
});

const LoginPage = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { login, isPending } = useAuthStore();
  const { success, error } = useToast();
  const [showPassword, setShowPassword] = useState(false);

  const from = location.state?.from?.pathname || '/dashboard';

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<LoginCredentials>({
    resolver: zodResolver(loginSchema),
  });

  const onSubmit = async (data: LoginCredentials) => {
    try {
      await login(data);
      success('Login successful!');
      navigate(from, { replace: true });
    } catch (err: any) {
      error(err.response?.data?.detail || 'Login failed');
    }
  };

  return (
    <>
      <SEOHead
        title="Login"
        description="Sign in to your Agency Dark account to manage models, chatters, and agency operations"
      />
      <StructuredData
        type="WebPage"
        data={{
          name: 'Login - Agency Dark',
          description: 'Sign in to access your OnlyFans agency management platform',
        }}
      />
      <Typography component="h1" variant="h4" sx={{ mb: 1 }}>
        Welcome Back
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 4 }}>
        Sign in to your account to continue
      </Typography>

      <Box component="form" onSubmit={handleSubmit(onSubmit)} sx={{ width: '100%' }}>
        <TextField
          {...register('email')}
          fullWidth
          label="Email Address"
          type="email"
          error={!!errors.email}
          helperText={errors.email?.message}
          margin="normal"
          autoComplete="email"
          autoFocus
        />

        <TextField
          {...register('password')}
          fullWidth
          label="Password"
          type={showPassword ? 'text' : 'password'}
          error={!!errors.password}
          helperText={errors.password?.message}
          margin="normal"
          autoComplete="current-password"
          InputProps={{
            endAdornment: (
              <InputAdornment position="end">
                <IconButton
                  aria-label="toggle password visibility"
                  onClick={() => setShowPassword(!showPassword)}
                  edge="end"
                >
                  {showPassword ? <VisibilityOff /> : <Visibility />}
                </IconButton>
              </InputAdornment>
            ),
          }}
        />

        <Box sx={{ mt: 1, mb: 2, textAlign: 'right' }}>
          <Link component={RouterLink} to="/auth/forgot-password" variant="body2">
            Forgot password?
          </Link>
        </Box>

        <Button
          type="submit"
          fullWidth
          variant="contained"
          size="large"
          disabled={isPending}
          sx={{ mb: 2 }}
        >
          {isPending ? 'Signing in...' : 'Sign In'}
        </Button>

        <Box sx={{ textAlign: 'center' }}>
          <Typography variant="body2" color="text.secondary">
            Don't have an account?{' '}
            <Link component={RouterLink} to="/auth/register">
              Sign up
            </Link>
          </Typography>
        </Box>
      </Box>
    </>
  );
};

export default LoginPage;
