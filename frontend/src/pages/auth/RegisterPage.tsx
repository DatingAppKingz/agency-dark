import { useState } from 'react';
import { Link as RouterLink, useNavigate } from 'react-router-dom';
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

const registerSchema = z.object({
  email: z.string().email('Invalid email address'),
  password: z.string().min(8, 'Password must be at least 8 characters'),
  confirmPassword: z.string(),
  full_name: z.string().min(2, 'Name must be at least 2 characters'),
  agency_name: z.string().min(2, 'Agency name must be at least 2 characters'),
}).refine((data) => data.password === data.confirmPassword, {
  message: "Passwords don't match",
  path: ["confirmPassword"],
});

type RegisterFormData = z.infer<typeof registerSchema>;

const RegisterPage = () => {
  const navigate = useNavigate();
  const { register: registerUser, isPending } = useAuthStore();
  const { success, error } = useToast();
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<RegisterFormData>({
    resolver: zodResolver(registerSchema),
  });

  const onSubmit = async (data: RegisterFormData) => {
    try {
      const { confirmPassword: _confirmPassword, ...registerData } = data;
      await registerUser(registerData);
      success('Registration successful!');
      navigate('/dashboard');
    } catch (err: any) {
      error(err.response?.data?.detail || 'Registration failed');
    }
  };

  return (
    <>
      <Typography component="h1" variant="h4" sx={{ mb: 1 }}>
        Create Account
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 4 }}>
        Start your agency with AgencyDark
      </Typography>

      <Box component="form" onSubmit={handleSubmit(onSubmit)} sx={{ width: '100%' }}>
        <TextField
          {...register('full_name')}
          fullWidth
          label="Full Name"
          error={!!errors.full_name}
          helperText={errors.full_name?.message}
          margin="normal"
          autoComplete="name"
          autoFocus
        />

        <TextField
          {...register('email')}
          fullWidth
          label="Email Address"
          type="email"
          error={!!errors.email}
          helperText={errors.email?.message}
          margin="normal"
          autoComplete="email"
        />

        <TextField
          {...register('agency_name')}
          fullWidth
          label="Agency Name"
          error={!!errors.agency_name}
          helperText={errors.agency_name?.message}
          margin="normal"
        />

        <TextField
          {...register('password')}
          fullWidth
          label="Password"
          type={showPassword ? 'text' : 'password'}
          error={!!errors.password}
          helperText={errors.password?.message}
          margin="normal"
          autoComplete="new-password"
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

        <TextField
          {...register('confirmPassword')}
          fullWidth
          label="Confirm Password"
          type={showConfirmPassword ? 'text' : 'password'}
          error={!!errors.confirmPassword}
          helperText={errors.confirmPassword?.message}
          margin="normal"
          autoComplete="new-password"
          InputProps={{
            endAdornment: (
              <InputAdornment position="end">
                <IconButton
                  aria-label="toggle password visibility"
                  onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                  edge="end"
                >
                  {showConfirmPassword ? <VisibilityOff /> : <Visibility />}
                </IconButton>
              </InputAdornment>
            ),
          }}
        />

        <Button
          type="submit"
          fullWidth
          variant="contained"
          size="large"
          disabled={isPending}
          sx={{ mt: 3, mb: 2 }}
        >
          {isPending ? 'Creating account...' : 'Create Account'}
        </Button>

        <Box sx={{ textAlign: 'center' }}>
          <Typography variant="body2" color="text.secondary">
            Already have an account?{' '}
            <Link component={RouterLink} to="/auth/login">
              Sign in
            </Link>
          </Typography>
        </Box>
      </Box>
    </>
  );
};

export default RegisterPage;
