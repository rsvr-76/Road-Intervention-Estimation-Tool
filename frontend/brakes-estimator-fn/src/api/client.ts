/**
 * API Client for BRAKES Backend Communication
 * 
 * Handles all HTTP requests to the FastAPI backend with proper
 * error handling, type safety, and progress tracking.
 */

import axios, { type AxiosError, type AxiosProgressEvent } from 'axios';

// API Configuration
const API_BASE = 'http://localhost:8000';
const API_TIMEOUT = 60000; // 60 seconds

// Configure axios instance
const apiClient = axios.create({
  baseURL: API_BASE,
  timeout: API_TIMEOUT,
  headers: {
    'Content-Type': 'application/json',
  },
});

// TypeScript Types
export interface Intervention {
  type: string;
  quantity: number;
  unit: string;
  location: string;
  confidence: number;
  extraction_method: string;
}

export interface Material {
  name: string;
  quantity: number;
  unit: string;
  unit_price: number;
  total_cost: number;
  irc_clause: string;
  price_source: string;
  fetched_date: string;
}

export interface EstimateItem {
  intervention: Intervention;
  materials: Material[];
  total_cost: number;
  audit_trail: Record<string, any>;
  assumptions: string[];
}

export interface Estimate {
  estimate_id: string;
  filename: string;
  created_at: string;
  status: string;
  items: EstimateItem[];
  total_cost: number;
  confidence: number;
  metadata: Record<string, any>;
}

export interface EstimateResponse {
  success: boolean;
  estimate_id: string;
  filename: string;
  status: string;
  extraction_method: string;
  extraction_confidence: number;
  interventions_found: number;
  total_cost: number;
  overall_confidence: number;
  processing_time_ms: number;
  verification: {
    status: string;
    passed_count: number;
    warning_count: number;
    error_count: number;
  };
  metadata: Record<string, any>;
  items: Array<{
    intervention_type: string;
    quantity: number;
    unit: string;
    location: string;
    confidence: number;
    total_cost: number;
    materials_count: number;
    warnings: string[];
  }>;
}

export interface EstimatesListResponse {
  success: boolean;
  estimates: Estimate[];
  total: number;
  limit: number;
  offset: number;
  has_more: boolean;
}

export interface DeleteResponse {
  success: boolean;
  deleted: boolean;
  estimate_id: string;
  message: string;
}

export interface ApiError {
  error: boolean;
  status_code: number;
  message: string;
  details?: any;
  path?: string;
}

// Error Handler
function handleApiError(error: unknown): never {
  if (axios.isAxiosError(error)) {
    const axiosError = error as AxiosError<ApiError>;
    
    if (axiosError.response) {
      // Server responded with error status
      const apiError = axiosError.response.data;
      throw new Error(
        apiError?.message || `API Error: ${axiosError.response.status}`
      );
    } else if (axiosError.request) {
      // Request made but no response
      throw new Error('Network error: Unable to reach the server. Please check your connection.');
    } else {
      // Something else happened
      throw new Error(`Request error: ${axiosError.message}`);
    }
  }
  
  // Unknown error type
  throw new Error('An unexpected error occurred');
}

/**
 * Upload PDF file for cost estimation
 * 
 * @param file - PDF file to upload
 * @param onProgress - Optional callback for upload progress (0-100)
 * @returns Promise with estimate response
 */
export async function uploadPDF(
  file: File,
  onProgress?: (progress: number) => void
): Promise<EstimateResponse> {
  try {
    // Validate file type
    if (file.type !== 'application/pdf') {
      throw new Error('Invalid file type. Please upload a PDF file.');
    }

    // Validate file size (25 MB limit)
    const MAX_SIZE = 25 * 1024 * 1024;
    if (file.size > MAX_SIZE) {
      throw new Error('File size exceeds 25 MB limit.');
    }

    // Create FormData
    const formData = new FormData();
    formData.append('file', file);

    // Upload with progress tracking
    const response = await apiClient.post<EstimateResponse>(
      '/api/upload',
      formData,
      {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
        onUploadProgress: (progressEvent: AxiosProgressEvent) => {
          if (progressEvent.total && onProgress) {
            const percentCompleted = Math.round(
              (progressEvent.loaded * 100) / progressEvent.total
            );
            onProgress(percentCompleted);
          }
        },
      }
    );

    return response.data;
  } catch (error) {
    handleApiError(error);
  }
}

/**
 * Get a complete estimate by ID
 * 
 * @param id - Estimate ID
 * @returns Promise with full estimate data
 */
export async function getEstimate(id: string): Promise<Estimate> {
  try {
    const response = await apiClient.get<{ success: boolean; estimate: Estimate }>(
      `/api/estimate/${id}`
    );
    return response.data.estimate;
  } catch (error) {
    handleApiError(error);
  }
}

/**
 * List all estimates with pagination
 * 
 * @param limit - Maximum number of results (default: 20)
 * @param offset - Number of results to skip (default: 0)
 * @param statusFilter - Optional status filter
 * @returns Promise with paginated estimates list
 */
export async function listEstimates(
  limit: number = 20,
  offset: number = 0,
  statusFilter?: string
): Promise<EstimatesListResponse> {
  try {
    const params: Record<string, any> = { limit, offset };
    if (statusFilter) {
      params.status_filter = statusFilter;
    }

    const response = await apiClient.get<EstimatesListResponse>(
      '/api/estimates',
      { params }
    );
    return response.data;
  } catch (error) {
    handleApiError(error);
  }
}

/**
 * Delete an estimate
 * 
 * @param id - Estimate ID to delete
 * @returns Promise with deletion confirmation
 */
export async function deleteEstimate(id: string): Promise<DeleteResponse> {
  try {
    const response = await apiClient.delete<DeleteResponse>(
      `/api/estimate/${id}`
    );
    return response.data;
  } catch (error) {
    handleApiError(error);
  }
}

/**
 * Export an estimate in specified format
 * 
 * @param id - Estimate ID
 * @param format - Export format (csv, json, or pdf)
 * @returns Promise with file blob for download
 */
export async function exportEstimate(
  id: string,
  format: 'csv' | 'json' | 'pdf'
): Promise<Blob> {
  try {
    const response = await apiClient.get(
      `/api/estimate/${id}/export`,
      {
        params: { format },
        responseType: 'blob',
      }
    );
    return response.data;
  } catch (error) {
    handleApiError(error);
  }
}

/**
 * Get estimate summary (lightweight version)
 * 
 * @param id - Estimate ID
 * @returns Promise with estimate summary
 */
export async function getEstimateSummary(id: string): Promise<{
  success: boolean;
  estimate_id: string;
  filename: string;
  created_at: string;
  status: string;
  total_cost: number;
  confidence: number;
  items_count: number;
  items_summary: Array<{
    type: string;
    quantity: number;
    unit: string;
    cost: number;
  }>;
  requires_review: boolean;
}> {
  try {
    const response = await apiClient.get(`/api/estimate/${id}/summary`);
    return response.data;
  } catch (error) {
    handleApiError(error);
  }
}

/**
 * Search material prices
 * 
 * @param query - Search query
 * @param limit - Maximum results (default: 10)
 * @returns Promise with matching materials
 */
export async function searchMaterialPrices(
  query: string,
  limit: number = 10
): Promise<{
  success: boolean;
  query: string;
  count: number;
  results: Material[];
}> {
  try {
    const response = await apiClient.get('/api/pricing/search', {
      params: { q: query, limit }
    });
    return response.data;
  } catch (error) {
    handleApiError(error);
  }
}

/**
 * Get material price by name
 * 
 * @param materialName - Material name
 * @returns Promise with material price details
 */
export async function getMaterialPrice(materialName: string): Promise<{
  success: boolean;
  material: Material;
}> {
  try {
    const response = await apiClient.get(`/api/pricing/${materialName}`);
    return response.data;
  } catch (error) {
    handleApiError(error);
  }
}

/**
 * Get all material categories
 * 
 * @returns Promise with list of categories
 */
export async function getMaterialCategories(): Promise<{
  success: boolean;
  count: number;
  categories: string[];
}> {
  try {
    const response = await apiClient.get('/api/pricing/categories');
    return response.data;
  } catch (error) {
    handleApiError(error);
  }
}

/**
 * Get pricing statistics
 * 
 * @returns Promise with pricing database statistics
 */
export async function getPricingStatistics(): Promise<{
  success: boolean;
  statistics: Record<string, any>;
}> {
  try {
    const response = await apiClient.get('/api/pricing/statistics');
    return response.data;
  } catch (error) {
    handleApiError(error);
  }
}

/**
 * Check API health status
 * 
 * @returns Promise with health status
 */
export async function checkHealthStatus(): Promise<{
  status: string;
  timestamp: number;
  version: string;
  services: Record<string, any>;
}> {
  try {
    const response = await apiClient.get('/health');
    return response.data;
  } catch (error) {
    handleApiError(error);
  }
}

/**
 * Download exported file
 * 
 * Helper function to trigger browser download of exported estimate
 * 
 * @param blob - File blob
 * @param filename - Suggested filename
 */
export function downloadFile(blob: Blob, filename: string): void {
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  window.URL.revokeObjectURL(url);
}

export default {
  uploadPDF,
  getEstimate,
  listEstimates,
  deleteEstimate,
  exportEstimate,
  getEstimateSummary,
  searchMaterialPrices,
  getMaterialPrice,
  getMaterialCategories,
  getPricingStatistics,
  checkHealthStatus,
  downloadFile,
};
