import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';

export interface SearchRequest {
  query: string;
  filters?: Record<string, any>;
  size?: number;
  offset?: number;
}

export interface ModelSearchRequest extends SearchRequest {
  platform?: string;
  is_active?: boolean;
  min_revenue?: number;
  max_revenue?: number;
  min_fans?: number;
  max_fans?: number;
  sort_by?: string;
}

export interface MessageSearchRequest extends SearchRequest {
  model_id?: string;
  fan_id?: string;
  date_from?: string;
  date_to?: string;
  has_media?: boolean;
  sentiment?: string;
}

export interface MediaSearchRequest extends SearchRequest {
  media_type?: string;
  tags?: string[];
  uploaded_by?: string;
  is_nsfw?: boolean;
  min_size?: number;
  max_size?: number;
}

export interface TransactionSearchRequest extends SearchRequest {
  model_id?: string;
  transaction_type?: string;
  status?: string;
  min_amount?: number;
  max_amount?: number;
  date_from?: string;
  date_to?: string;
}

export interface SavedSearchCreate {
  name: string;
  description?: string;
  query: string;
  filters?: Record<string, any>;
  search_type: string;
}

export const searchApi = {
  // Search all content types
  searchAll: (data: SearchRequest) => 
    axios.post(`${API_BASE_URL}/search/all`, data),

  // Type-specific searches
  searchModels: (data: ModelSearchRequest) => 
    axios.post(`${API_BASE_URL}/search/models`, data),

  searchMessages: (data: MessageSearchRequest) => 
    axios.post(`${API_BASE_URL}/search/messages`, data),

  searchMedia: (data: MediaSearchRequest) => 
    axios.post(`${API_BASE_URL}/search/media`, data),

  searchTransactions: (data: TransactionSearchRequest) => 
    axios.post(`${API_BASE_URL}/search/transactions`, data),

  // Search suggestions
  getSuggestions: (query: string, context?: string) => 
    axios.get(`${API_BASE_URL}/search/suggestions`, {
      params: { query, context }
    }),

  // Popular searches
  getPopularSearches: (limit: number = 10) => 
    axios.get(`${API_BASE_URL}/search/popular`, {
      params: { limit }
    }),

  // Saved searches
  saveSearch: (data: SavedSearchCreate) => 
    axios.post(`${API_BASE_URL}/search/saved`, data),

  getSavedSearches: () => 
    axios.get(`${API_BASE_URL}/search/saved`),

  deleteSavedSearch: (searchId: string) => 
    axios.delete(`${API_BASE_URL}/search/saved/${searchId}`),

  // Reindex agency data
  reindexAgencyData: () => 
    axios.post(`${API_BASE_URL}/search/reindex`),
};