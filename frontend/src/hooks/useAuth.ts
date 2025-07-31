import { useAuthStore } from '@/store/authStore';

export const useAuth = () => {
  const { user, isAuthenticated, isPending, error, login, register, logout, checkAuth, clearError } = useAuthStore();

  return {
    user,
    isAuthenticated,
    isPending,
    error,
    login,
    register,
    logout,
    checkAuth,
    clearError,
  };
};
