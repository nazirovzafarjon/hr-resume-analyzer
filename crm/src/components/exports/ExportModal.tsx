/**
 * ExportModal - Universal export modal for table data
 * 
 * Adapts dynamically based on the resource type, showing relevant filters
 * and columns for jobs, applications, candidates, and interviews.
 */

import { useState, useEffect } from "react";
import { FileText, FileSpreadsheet, FileType } from "lucide-react";
import Modal from "../ui/Modal";
import Button from "../ui/Button";
import {
  ExportResource,
  ExportFormat,
  ExportFilters,
  ExportRequest,
  exportTable,
  downloadBlob,
} from "../../services/exportService";

interface ExportModalProps {
  open: boolean;
  onClose: () => void;
  resource: ExportResource;
  // Available filter options (fetched from API or passed from parent)
  companies?: string[];
  jobs?: Array<{ id: number; title: string }>;
  // Default filters from current page state
  defaultFilters?: Partial<ExportFilters>;
}

// Column definitions for each resource
const RESOURCE_COLUMNS: Record<ExportResource, Record<string, string>> = {
  jobs: {
    company: "Company",
    position: "Position",
    description: "Description",
    required_skills: "Required Skills",
    required_experience: "Required Experience",
    leads_count: "Applications",
    created_at: "Created At",
  },
  applications: {
    name: "Candidate",
    email: "Email",
    company: "Company",
    position: "Position",
    application_status: "Status",
    analysis_status: "AI Status",
    ai_score: "AI Score",
    hiring_status: "Hiring Status",
    interview_status: "Interview Status",
    submitted_at: "Submitted At",
  },
  candidates: {
    name: "Candidate",
    email: "Email",
    company: "Company",
    position: "Position",
    hiring_status: "Hiring Status",
    interview_status: "Interview Status",
    ai_score: "AI Score",
    candidate_at: "Candidate Since",
  },
  interviews: {
    candidate_name: "Candidate",
    company: "Company",
    position: "Position",
    interviewer: "Interviewer",
    scheduled_at: "Scheduled",
    duration_minutes: "Duration (min)",
    status: "Status",
    meeting_link: "Meeting Link",
  },
};

// Default selected columns for each resource
const DEFAULT_COLUMNS: Record<ExportResource, string[]> = {
  jobs: ["company", "position", "required_skills", "leads_count", "created_at"],
  applications: ["name", "email", "company", "position", "application_status", "ai_score", "submitted_at"],
  candidates: ["name", "email", "company", "position", "hiring_status", "ai_score"],
  interviews: ["candidate_name", "company", "position", "interviewer", "scheduled_at", "status"],
};

export function ExportModal({
  open,
  onClose,
  resource,
  companies = [],
  jobs = [],
  defaultFilters = {},
}: ExportModalProps) {
  const [filters, setFilters] = useState<ExportFilters>({});
  const [selectedColumns, setSelectedColumns] = useState<string[]>([]);
  const [format, setFormat] = useState<ExportFormat>("xlsx");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Initialize filters and columns when modal opens
  useEffect(() => {
    if (open) {
      setFilters(defaultFilters);
      setSelectedColumns(DEFAULT_COLUMNS[resource]);
      setFormat("xlsx");
      setError(null);
    }
  }, [open, resource, defaultFilters]);

  const availableColumns = RESOURCE_COLUMNS[resource];
  const columnKeys = Object.keys(availableColumns);

  const handleToggleColumn = (column: string) => {
    setSelectedColumns((prev) =>
      prev.includes(column)
        ? prev.filter((c) => c !== column)
        : [...prev, column]
    );
  };

  const handleSelectAll = () => {
    setSelectedColumns(columnKeys);
  };

  const handleClearAll = () => {
    setSelectedColumns([]);
  };

  const handleExport = async () => {
    if (selectedColumns.length === 0) {
      setError("Please select at least one column to export.");
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const request: ExportRequest = {
        resource,
        filters,
        columns: selectedColumns,
        format,
      };

      const blob = await exportTable(request);
      
      // Generate filename
      const timestamp = new Date().toISOString().split("T")[0];
      const extension = format;
      const filename = `${resource}_report_${timestamp}.${extension}`;
      
      downloadBlob(blob, filename);
      
      // Close modal on success
      onClose();
    } catch (err: any) {
      console.error("Export failed:", err);
      setError(err.message || "Failed to generate export. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  const resourceTitle = resource.charAt(0).toUpperCase() + resource.slice(1);

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={`Export ${resourceTitle}`}
      description="Select filters, columns, and format for your export"
      size="lg"
      busy={loading}
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={loading}>
            Cancel
          </Button>
          <Button onClick={handleExport} loading={loading}>
            Export
          </Button>
        </>
      }
    >
      <div className="export-modal-content">
        {/* Filters Section */}
        <section className="export-section">
          <h3 className="export-section-title">Filters</h3>
          <div className="export-filters">
            {/* Company Filter */}
            {companies.length > 0 && (
              <label className="export-label">
                Company
                <select
                  className="field-select"
                  value={filters.company || ""}
                  onChange={(e) =>
                    setFilters({ ...filters, company: e.target.value || undefined })
                  }
                >
                  <option value="">All Companies</option>
                  {companies.map((company) => (
                    <option key={company} value={company}>
                      {company}
                    </option>
                  ))}
                </select>
              </label>
            )}

            {/* Job Filter */}
            {(resource === "applications" || resource === "candidates" || resource === "interviews") && (
              <label className="export-label">
                Job / Position
                <select
                  className="field-select"
                  value={
                    filters.use_latest_job
                      ? "latest"
                      : filters.job_id?.toString() || ""
                  }
                  onChange={(e) => {
                    const value = e.target.value;
                    if (value === "latest") {
                      setFilters({
                        ...filters,
                        use_latest_job: true,
                        job_id: undefined,
                      });
                    } else if (value === "") {
                      setFilters({
                        ...filters,
                        use_latest_job: false,
                        job_id: undefined,
                      });
                    } else {
                      setFilters({
                        ...filters,
                        use_latest_job: false,
                        job_id: parseInt(value),
                      });
                    }
                  }}
                >
                  <option value="">All Jobs</option>
                  <option value="latest">Latest Job</option>
                  {jobs.map((job) => (
                    <option key={job.id} value={job.id}>
                      {job.title}
                    </option>
                  ))}
                </select>
              </label>
            )}

            {/* Application Status Filter */}
            {(resource === "applications") && (
              <label className="export-label">
                Application Status
                <select
                  className="field-select"
                  value={filters.application_status || ""}
                  onChange={(e) =>
                    setFilters({
                      ...filters,
                      application_status: e.target.value || undefined,
                    })
                  }
                >
                  <option value="">All Statuses</option>
                  <option value="new">New</option>
                  <option value="reviewing">Reviewing</option>
                  <option value="shortlisted">Shortlisted</option>
                  <option value="interview">Interview</option>
                  <option value="hired">Hired</option>
                  <option value="rejected">Rejected</option>
                </select>
              </label>
            )}

            {/* Hiring Status Filter */}
            {(resource === "candidates") && (
              <label className="export-label">
                Hiring Status
                <select
                  className="field-select"
                  value={filters.hiring_status || ""}
                  onChange={(e) =>
                    setFilters({
                      ...filters,
                      hiring_status: e.target.value || undefined,
                    })
                  }
                >
                  <option value="">All Statuses</option>
                  <option value="strong_hire">Strong Hire</option>
                  <option value="hire">Hire</option>
                  <option value="weak_hire">Weak Hire</option>
                  <option value="do_not_hire">Do Not Hire</option>
                </select>
              </label>
            )}

            {/* Interview Status Filter */}
            {resource === "interviews" && (
              <label className="export-label">
                Interview Status
                <select
                  className="field-select"
                  value={filters.interview_status || ""}
                  onChange={(e) =>
                    setFilters({
                      ...filters,
                      interview_status: e.target.value || undefined,
                    })
                  }
                >
                  <option value="">All Statuses</option>
                  <option value="upcoming">Upcoming</option>
                  <option value="completed">Completed</option>
                  <option value="cancelled">Cancelled</option>
                </select>
              </label>
            )}

            {/* Date Range Filters */}
            <div className="export-date-range">
              <label className="export-label">
                Date From
                <input
                  type="date"
                  className="field-input"
                  value={filters.date_from || ""}
                  onChange={(e) =>
                    setFilters({ ...filters, date_from: e.target.value || undefined })
                  }
                />
              </label>
              <label className="export-label">
                Date To
                <input
                  type="date"
                  className="field-input"
                  value={filters.date_to || ""}
                  onChange={(e) =>
                    setFilters({ ...filters, date_to: e.target.value || undefined })
                  }
                />
              </label>
            </div>

            {/* Search Filter */}
            {(resource === "applications" || resource === "candidates" || resource === "interviews") && (
              <label className="export-label export-label-full">
                Search (Name/Email)
                <input
                  type="text"
                  className="field-input"
                  placeholder="Search..."
                  value={filters.search || ""}
                  onChange={(e) =>
                    setFilters({ ...filters, search: e.target.value || undefined })
                  }
                />
              </label>
            )}
          </div>
        </section>

        {/* Columns Section */}
        <section className="export-section">
          <div className="export-section-header">
            <h3 className="export-section-title">Columns to Include</h3>
            <div className="export-column-actions">
              <button
                type="button"
                className="export-link-button"
                onClick={handleSelectAll}
              >
                Select All
              </button>
              <span className="export-separator">·</span>
              <button
                type="button"
                className="export-link-button"
                onClick={handleClearAll}
              >
                Clear All
              </button>
            </div>
          </div>
          <div className="export-columns">
            {columnKeys.map((column) => (
              <label key={column} className="export-checkbox-label">
                <input
                  type="checkbox"
                  checked={selectedColumns.includes(column)}
                  onChange={() => handleToggleColumn(column)}
                />
                <span>{availableColumns[column]}</span>
              </label>
            ))}
          </div>
          {selectedColumns.length === 0 && (
            <p className="export-hint export-hint-warning">
              Please select at least one column
            </p>
          )}
        </section>

        {/* Format Section */}
        <section className="export-section">
          <h3 className="export-section-title">Export Format</h3>
          <div className="export-formats">
            <label
              className={`export-format-card ${
                format === "pdf" ? "export-format-card-selected" : ""
              }`}
            >
              <input
                type="radio"
                name="format"
                value="pdf"
                checked={format === "pdf"}
                onChange={(e) => setFormat(e.target.value as ExportFormat)}
              />
              <FileText size={24} />
              <span className="export-format-label">PDF</span>
              <span className="export-format-desc">Portable Document</span>
            </label>

            <label
              className={`export-format-card ${
                format === "xlsx" ? "export-format-card-selected" : ""
              }`}
            >
              <input
                type="radio"
                name="format"
                value="xlsx"
                checked={format === "xlsx"}
                onChange={(e) => setFormat(e.target.value as ExportFormat)}
              />
              <FileSpreadsheet size={24} />
              <span className="export-format-label">Excel</span>
              <span className="export-format-desc">Spreadsheet (.xlsx)</span>
            </label>

            <label
              className={`export-format-card ${
                format === "docx" ? "export-format-card-selected" : ""
              }`}
            >
              <input
                type="radio"
                name="format"
                value="docx"
                checked={format === "docx"}
                onChange={(e) => setFormat(e.target.value as ExportFormat)}
              />
              <FileType size={24} />
              <span className="export-format-label">Word</span>
              <span className="export-format-desc">Document (.docx)</span>
            </label>
          </div>
        </section>

        {/* Error Message */}
        {error && (
          <div className="export-error">
            <p>{error}</p>
          </div>
        )}
      </div>
    </Modal>
  );
}
