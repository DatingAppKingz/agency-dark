import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface UIState {
  // Theme
  theme: 'light' | 'dark';
  toggleTheme: () => void;
  
  // Sidebar
  sidebarOpen: boolean;
  toggleSidebar: () => void;
  setSidebarOpen: (open: boolean) => void;
  
  // Loading states
  isLoading: boolean;
  setLoading: (loading: boolean) => void;
  
  // Filters
  userFilters: {
    search: string;
    role?: string;
    status?: string;
  };
  setUserFilters: (filters: Partial<UIState['userFilters']>) => void;
  resetUserFilters: () => void;
}

export const useUIStore = create<UIState>()(
  persist(
    (set) => ({
      // Theme
      theme: 'light',
      toggleTheme: () => set((state) => ({ 
        theme: state.theme === 'light' ? 'dark' : 'light' 
      })),
      
      // Sidebar
      sidebarOpen: true,
      toggleSidebar: () => set((state) => ({ 
        sidebarOpen: !state.sidebarOpen 
      })),
      setSidebarOpen: (open) => set({ sidebarOpen: open }),
      
      // Loading
      isLoading: false,
      setLoading: (loading) => set({ isLoading: loading }),
      
      // Filters
      userFilters: {
        search: '',
      },
      setUserFilters: (filters) => set((state) => ({
        userFilters: { ...state.userFilters, ...filters }
      })),
      resetUserFilters: () => set({ 
        userFilters: { search: '' } 
      }),
    }),
    {
      name: 'agencydark-ui',
      partialize: (state) => ({ 
        theme: state.theme,
        sidebarOpen: state.sidebarOpen 
      }),
    }
  )
);