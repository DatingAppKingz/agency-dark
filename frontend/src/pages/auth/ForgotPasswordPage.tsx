import { useState } from 'react';
import { Link as RouterLink } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import {
  Box,
  Button,
  TextField,
  Typography,
  Link,
  Alert,
} from '@mui/material';
import { ArrowBack } from '@mui/icons-material';
import { authService } from '@/services/auth/authService';
import { useToast } from '@/components/common/Toaster';

const forgotPasswordSchema = z.object({
  email: z.string().email('Invalid email address'),
});

type ForgotPasswordFormData = z.infer<typeof forgotPasswordSchema>;

const ForgotPasswordPage = () => {
  const { success, error } = useToast();
  const [isSubmitted, setIsSubmitted] = useState(false);
  const [isPending, setIsLoading] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<ForgotPasswordFormData>({
    resolver: zodResolver(forgotPasswordSchema),
  });

  const onSubmit = async (data: ForgotPasswordFormData) => {
    setIsLoading(true);
    try {
      await authService.forgotPassword(data.email);
      setIsSubmitted(true);
      success('Password reset link sent to your email');
    } catch (err: any) {
      error(err.response?.data?.detail || 'Failed to send reset link');
    } finally {
      setIsLoading(false);
    }
  };

  if (isSubmitted) {
    return (
      <>
        <Typography component="h1" variant="h4" sx={{ mb: 2 }}>
          Check Your Email
        </Typography>
        <Alert severity="success" sx={{ mb: 3, width: '100%' }}>
          We've sent a password reset link to your email address. Please check your inbox and follow the instructions.
        </Alert>
        <Button
          component={RouterLink}
          to="/auth/login"
          fullWidth
          variant="contained"
          startIcon={<ArrowBack />}
        >
          Back to Login
        </Button>
      </>
    );
  }

  return (
    <>
      <Typography component="h1" variant="h4" sx={{ mb: 1 }}>
        Forgot Password?
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 4, textAlign: 'center' }}>
        No worries! Enter your email and we'll send you reset instructions.
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

        <Button
          type="submit"
          fullWidth
          variant="contained"
          size="large"
          disabled={isPending}
          sx={{ mt: 3, mb: 2 }}
        >
          {isPending ? 'Sending...' : 'Send Reset Link'}
        </Button>

        <Box sx={{ textAlign: 'center' }}>
          <Link component={RouterLink} to="/auth/login" sx={{ display: 'inline-flex', alignItems: 'center' }}>
            <ArrowBack sx={{ mr: 0.5, fontSize: 20 }} />
            Back to login
          </Link>
        </Box>
      </Box>
    </>
  );
};

export default ForgotPasswordPage;
