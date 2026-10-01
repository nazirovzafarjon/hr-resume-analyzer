/**
 * Export Service - Universal table export functionality
 */

import { apiRequest } from "./apiClient";

export type ExportResource = "jobs" | "applications" | "candidates" | "interviews";
export type ExportFormat = "pdf" | "xlsx" | "docx";

export interface ExportFilters {
  company?: string;
  job_id?: number;
  use_latest_job?: boolean;
  application_status?: string;
  analysis_status?: string;
  hiring_status?: string;
  interview_status?: string;
  date_from?: string;
  date_to?: string;
  search?: string;
}

export interface ExportRequest {
  resource: ExportResource;
  filters: ExportFilters;
  columns: string[];
  format: ExportFormat;
}

/**
 * Export filtered table data to a file
 * @param request Export configuration
 * @returns Blob containing the exported file
 */
export async function exportTable(request: ExportRequest): Promise<Blob> {
  return apiRequest<Blob>("/exports", {
    method: "POST",
    body: request,
    auth: true,
    responseType: "blob",
  });
}

/**
 * Download a blob as a file
 * @param blob File blob
 * @param filename Suggested filename
 */
export function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  
  // Clean up after a delay
  setTimeout(() => URL.revokeObjectURL(url), 10_000);
}
