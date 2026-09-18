import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { analyzeVacancy, createJob, publishApplicationForm } from "../../services/jobsService";
import { AI_PROCESSING_STEPS } from "../../data/mock/jobAi";
import { buildDefaultApplicationFields, reviewFieldsFromAnalysis } from "../../utils/applicationFields";
import PageHeader from "../../components/ui/PageHeader";
import Card from "../../components/ui/Card";
import Button from "../../components/ui/Button";
import TextInput from "../../components/forms/TextInput";
import TextArea from "../../components/forms/TextArea";
import SkillsInput from "../../components/forms/SkillsInput";
import RequirementFileUpload from "../../components/jobs/RequirementFileUpload";
import AIProcessingCard from "../../components/jobs/AIProcessingCard";
import JobAIAnalysisCard from "../../components/jobs/JobAIAnalysisCard";
import ApplicationFormBuilder from "../../components/application-form/ApplicationFormBuilder";
import ApplicationLinkCard from "../../components/application-form/ApplicationLinkCard";
import type { ApplicationFieldDef } from "../../types/applicationForm";
import type { JobAIAnalysisResult } from "../../types/job";
import type { JobRequirementSource } from "../../types/job";
import { getErrorMessage } from "../../utils/apiError";

type Step = "input" | "processing" | "review" | "published";

/**
 * /jobs/create — AI-driven vacancy flow with real backend integration.
 * Manual input and/or requirement file upload + extra AI instructions go
 * through a real AI analysis, then show structured results for review
 * before creating the job.
 */
export default function JobCreatePage() {
  const navigate = useNavigate();
  const [company, setCompany] = useState("");
  const [position, setPosition] = useState("");
  const [experience, setExperience] = useState("");
  const [skills, setSkills] = useState<string[]>([]);
  const [description, setDescription] = useState("");
  const [fileName, setFileName] = useState<string | null>(null);
  const [instructions, setInstructions] = useState("");
  const [companyError, setCompanyError] = useState<string | undefined>();
  const [positionError, setPositionError] = useState<string | undefined>();
  const [step, setStep] = useState<Step>("input");
  const [doneCount, setDoneCount] = useState(0);
  const [analysis, setAnalysis] = useState<JobAIAnalysisResult | null>(null);
  const [formFields, setFormFields] = useState<ApplicationFieldDef[]>(buildDefaultApplicationFields());
  const [token, setToken] = useState<string | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [analysisError, setAnalysisError] = useState<string | null>(null);
  const [publishing, setPublishing] = useState(false);
  const [createdJobId, setCreatedJobId] = useState<number | null>(null);
  const timerRef = useRef<number[]>([]);

  useEffect(() => {
    const timers = timerRef.current;
    return () => {
      timers.forEach((t) => window.clearTimeout(t));
    };
  }, []);

  const source: JobRequirementSource =
    fileName && (description.trim() || skills.length > 0)
      ? "both"
      : fileName
        ? "file"
        : "manual";

  function buildVacancyContent(): string {
    const parts: string[] = [];
    if (company.trim()) parts.push(`Company: ${company.trim()}`);
    if (position.trim()) parts.push(`Position: ${position.trim()}`);
    if (description.trim()) parts.push(`Description: ${description.trim()}`);
    if (skills.length > 0) parts.push(`Required Skills: ${skills.join(", ")}`);
    if (experience) parts.push(`Experience Level: ${experience}`);
    if (fileName) parts.push(`Requirement File Name: ${fileName}`);
    if (instructions.trim()) parts.push(`Additional Instructions: ${instructions.trim()}`);
    return parts.join("\n\n");
  }

  function handleAnalyse() {
    const content = buildVacancyContent();
    if (!content.trim()) {
      setAnalysisError("Add a position, company, description, skills or upload a file first.");
      return;
    }
    if (company.trim().length < 2) {
      setCompanyError("Company name must be at least 2 characters.");
      return;
    }
    if (position.trim().length < 2) {
      setPositionError("Position must be at least 2 characters.");
      return;
    }
    setAnalysisError(null);
    setAnalyzing(true);
    setDoneCount(0);
    const timers: number[] = [];
    AI_PROCESSING_STEPS.forEach((_, i) => {
      const t = window.setTimeout(() => setDoneCount(i + 1), 400 * (i + 1));
      timers.push(t);
    });
    setTimeout(() => {
      analyzeVacancy(content)
        .then((result) => {
          setAnalysis(result);
          // AI drafts the questions; HR reviews them in the builder below.
          setFormFields(reviewFieldsFromAnalysis(result.application_fields));
          setStep("review");
        })
        .catch((err) => {
          // ApiError already carries the backend's friendly `detail` message.
          setAnalysisError(getErrorMessage(err, "Analysis failed. Please try again."));
          setStep("input");
        })
        .finally(() => {
          setAnalyzing(false);
        });
    }, AI_PROCESSING_STEPS.length * 400 + 600);
    timerRef.current = timers;
  }

  async function handleCreateJob() {
    if (!analysis) return;
    setPublishing(true);
    try {
      const job = await createJob({
        company_name: analysis.company_name.trim(),
        position: analysis.position.trim(),
        description: analysis.description.trim(),
        required_skills: analysis.required_skills.trim(),
        required_experience: analysis.required_experience.trim(),
        // How the vacancy requirements were provided (manual / file / both).
        requirement_source: source,
        requirement_file_name: fileName ?? undefined,
        ai_instructions: instructions.trim() || undefined,
        // Job + reviewed form are stored atomically; the public token comes
        // back with the job, so the shared link exists immediately.
        application_form: formFields.length > 0 ? { fields: formFields } : undefined,
      });
      setCreatedJobId(job.id);
      let publicToken = job.application_form?.public_token ?? null;
      if (!publicToken && formFields.length > 0) {
        // Defensive: publish only if the backend did not return a token.
        publicToken = (await publishApplicationForm(job.id)).public_token;
      }
      if (!publicToken) {
        // Nothing shareable yet — finish the form from the job page.
        navigate(`/jobs/${job.id}`);
        return;
      }
      setToken(publicToken);
      setStep("published");
      setTimeout(() => navigate(`/jobs/${job.id}`), 2000);
    } catch (err) {
      setAnalysisError(getErrorMessage(err, "Failed to create job. Please try again."));
    } finally {
      setPublishing(false);
    }
  }

  function handleRegenerateToken() {
    if (!createdJobId) return;
    setPublishing(true);
    // Rotating the token immediately invalidates the previously shared link.
    publishApplicationForm(createdJobId, true)
      .then((result) => setToken(result.public_token))
      .catch(() => {})
      .finally(() => setPublishing(false));
  }

  function openDetails() {
    if (createdJobId) navigate(`/jobs/${createdJobId}`);
  }

  return (
    <div className="page">
      <PageHeader
        title="Create a job"
        description="Add a vacancy, analyse it with AI, then share a public application link."
      />
      <div className="stack">
        <div className="two-col">
          <Card>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                handleAnalyse();
              }}
            >
              <TextInput
                label="Company name"
                required
                value={company}
                onChange={(v) => {
                  setCompany(v);
                  setCompanyError(undefined);
                }}
                placeholder="Acme Corp"
                error={companyError}
                disabled={analyzing}
              />
              <TextInput
                label="Position"
                required
                value={position}
                onChange={(v) => {
                  setPosition(v);
                  setPositionError(undefined);
                }}
                placeholder="Senior Python Developer"
                error={positionError}
                disabled={analyzing}
              />
              <TextArea
                label="Description"
                value={description}
                onChange={(v) => setDescription(v)}
                rows={4}
                placeholder="Tell candidates what this role is about."
                hint="Optional — AI can infer more from a requirement file."
                disabled={analyzing}
              />
              <TextInput
                label="Required experience"
                value={experience}
                onChange={(v) => setExperience(v)}
                placeholder="3+ years"
                hint="Optional"
                disabled={analyzing}
              />
              <SkillsInput
                label="Required skills"
                skills={skills}
                onSkillsChange={setSkills}
                hint="Optional"
                disabled={analyzing}
              />
              <RequirementFileUpload
                fileName={fileName}
                onFileSelect={(file) => setFileName(file?.name ?? null)}
                disabled={analyzing}
              />
              <TextArea
                label="Additional AI instructions"
                value={instructions}
                onChange={(v) => setInstructions(v)}
                rows={2}
                placeholder="Optional — tone, seniority, etc."
                hint="Optional"
                disabled={analyzing}
              />
              <div className="job-form-actions">
                <Button variant="secondary" to="/jobs">
                  Cancel
                </Button>
                <Button onClick={handleAnalyse} loading={analyzing} disabled={analyzing}>
                  {analyzing ? "Analysing…" : "Analyse with AI"}
                </Button>
              </div>
              {analysisError && (
                <p className="field-error" role="alert">
                  {analysisError}
                </p>
              )}
            </form>
          </Card>
        </div>
        {step === "processing" && (
          <div className="stack">
            <Card>
              <AIProcessingCard doneCount={doneCount} />
            </Card>
          </div>
        )}
        {(step === "review" || step === "published") && analysis && (
          <div className="stack">
            <JobAIAnalysisCard analysis={analysis} />
            <Card title="Review & Edit Job Details" subtitle="AI-generated draft — review and edit before creating the job.">
              <TextInput
                label="Company name"
                required
                value={analysis.company_name}
                onChange={(v) => setAnalysis((prev) => (prev ? { ...prev, company_name: v } : null))}
                placeholder="Acme Corp"
              />
              <TextInput
                label="Position"
                required
                value={analysis.position}
                onChange={(v) => setAnalysis((prev) => (prev ? { ...prev, position: v } : null))}
                placeholder="Senior Python Developer"
              />
              <TextInput
                label="Required experience"
                value={analysis.required_experience}
                onChange={(v) => setAnalysis((prev) => (prev ? { ...prev, required_experience: v } : null))}
                placeholder="3+ years"
                hint="Optional"
              />
              <TextArea
                label="Description"
                value={analysis.description}
                onChange={(v) => setAnalysis((prev) => (prev ? { ...prev, description: v } : null))}
                rows={4}
                placeholder="Job description…"
                hint="Optional"
              />
              <TextInput
                label="Required skills"
                value={analysis.required_skills}
                onChange={(v) => setAnalysis((prev) => (prev ? { ...prev, required_skills: v } : null))}
                placeholder="Python, FastAPI, PostgreSQL"
                hint="Optional — comma separated"
              />
            </Card>
            <ApplicationFormBuilder
              fields={formFields}
              onFieldsChange={setFormFields}
            />
            {step === "published" && token && (
              <>
                <ApplicationLinkCard
                  token={token}
                  jobTitle={analysis.position || position || "New vacancy"}
                  onRegenerate={handleRegenerateToken}
                  regenerating={publishing}
                />
                <Card>
                  <div className="job-form-actions">
                    <Button variant="secondary" to="/jobs">
                      Back to jobs
                    </Button>
                    <Button onClick={openDetails}>Open job details</Button>
                  </div>
                </Card>
              </>
            )}
            {step === "review" && (
              <Card>
                <div className="job-form-actions">
                  <Button variant="secondary" to="/jobs">
                    Back
                  </Button>
                  <Button onClick={handleCreateJob} loading={publishing} disabled={publishing}>
                    {publishing ? "Creating…" : "Create Job & Share Link"}
                  </Button>
                </div>
              </Card>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
