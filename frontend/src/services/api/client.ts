import axios, { AxiosError, AxiosInstance, InternalAxiosRequestConfig } from 'axios';
import { authService } from '../auth/authService';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';

// Create axios instance
const apiClient: AxiosInstance = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  withCredentials: true, // For cookies
});

// Request interceptor
apiClient.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    // No need to add Authorization header - cookies are sent automatically
    
    // Debug logging
    console.log('🚀 API Request:', {
      method: config.method?.toUpperCase(),
      url: config.url,
      baseURL: config.baseURL,
      headers: config.headers,
      data: config.data,
    });
    
    return config;
  },
  (error: AxiosError) => {
    console.error('❌ Request Error:', error);
    return Promise.reject(error);
  }
);

// Response interceptor
apiClient.interceptors.response.use(
  (response) => {
    // Debug logging for successful responses
    console.log('✅ API Response:', {
      status: response.status,
      url: response.config.url,
      data: response.data,
    });
    return response;
  },
  async (error: AxiosError) => {
    const originalRequest = error.config as InternalAxiosRequestConfig & { _retry?: boolean };

    // Debug logging for errors
    console.error('❌ API Error:', {
      status: error.response?.status,
      url: originalRequest?.url,
      message: error.message,
      response: error.response?.data,
    });

    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;

      try {
        await authService.refreshToken();
        // Retry the original request - cookies will be sent automatically
        return apiClient(originalRequest);
      } catch (refreshError) {
        await authService.logout();
        window.location.href = '/auth/login';
        return Promise.reject(refreshError);
      }
    }

    return Promise.reject(error);
  }
);

export default apiClient;
