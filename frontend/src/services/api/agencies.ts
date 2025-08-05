import apiClient from './client';

export interface Agency {
  id: string;
  name: string;
  owner_id: string;
  created_at: string;
  updated_at: string;
  is_active: boolean;
  settings?: any;
}

export interface AgenciesResponse {
  data: Agency[];
  total: number;
  page: number;
  size: number;
}

export const agenciesService = {
  async getAgencies(params?: { page?: number; size?: number; search?: string }): Promise<AgenciesResponse> {
    try {
      const response = await fetch(`/api/v1/admin/agencies/list?page=${params?.page || 1}&size=${params?.size || 100}`, {
        credentials: 'include',
      });
      if (!response.ok) {
        throw new Error('Failed to fetch agencies');
      }
      const data = await response.json();
      // Map the response to match our interface
      return {
        ...data,
        data: data.data.map((agency: any) => ({
          ...agency,
          updated_at: agency.created_at, // Use created_at as updated_at
        })),
      };
    } catch (error) {
      console.error('Error fetching agencies:', error);
      // Return empty data on error
      return {
        data: [],
        total: 0,
        page: params?.page || 1,
        size: params?.size || 10,
      };
    }
  },

  async getAgency(id: string): Promise<Agency> {
    const response = await apiClient.get(`/api/v1/agencies/${id}`);
    return response.data;
  },

  async createAgency(data: Partial<Agency>): Promise<Agency> {
    const response = await apiClient.post('/api/v1/agencies', data);
    return response.data;
  },

  async updateAgency(id: string, data: Partial<Agency>): Promise<Agency> {
    const response = await apiClient.put(`/api/v1/agencies/${id}`, data);
    return response.data;
  },

  async deleteAgency(id: string): Promise<void> {
    await apiClient.delete(`/api/v1/agencies/${id}`);
  },
};