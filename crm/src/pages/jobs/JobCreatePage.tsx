import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Check } from "lucide-react";
import { analyzeVacancy, createJob, publishApplicationForm } from "../../services/jobsService";
import { buildDefaultApplicationFields, reviewFieldsFromAnalysis, validateApplicationFields } from "../../utils/applicationFields";
import { useLanguage } from "../../contexts/LanguageContext";
import { useNotify } from "../../contexts/ToastContext";
import PageHeader from "../../components/ui/PageHeader";
import BackButton from "../../components/ui/BackButton";
import PageMeta from "../../components/seo/PageMeta";
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
import { getErrorMessage } from "../../utils/apiError";

type Step = "input" | "processing" | "review" | "published";

/**
 * /jobs/create — AI-driven vacancy flow with real backend integration.
 * Manual input and/or an uploaded .txt requirement file, plus extra AI
 * instructions, are sent to POST /jobs/analyze; the structured result is
 * then reviewed and edited before the job is created.
 */
export default function JobCreatePage() {
  const navigate = useNavigate();
  const { t } = useLanguage();
  const notify = useNotify();
  const [company, setCompany] = useState("");
  const [position, setPosition] = useState("");
  const [experience, setExperience] = useState("");
  const [skills, setSkills] = useState<string[]>([]);
  const [description, setDescription] = useState("");
  const [fileName, setFileName] = useState<string | null>(null);
  const [fileSize, setFileSize] = useState<number | null>(null);
  const [fileText, setFileText] = useState("");
  const [instructions, setInstructions] = useState("");
  const [companyError, setCompanyError] = useState<string | undefined>();
  const [positionError, setPositionError] = useState<string | undefined>();
  const [step, setStep] = useState<Step>("input");
  const [analysis, setAnalysis] = useState<JobAIAnalysisResult | null>(null);
  const [formFields, setFormFields] = useState<ApplicationFieldDef[]>(buildDefaultApplicationFields());
  const [token, setToken] = useState<string | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [analysisError, setAnalysisError] = useState<string | null>(null);
  const [publishing, setPublishing] = useState(false);
  const [createdJobId, setCreatedJobId] = useState<number | null>(null);
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  function buildVacancyContent(): string {
    const parts: string[] = [];
    if (company.trim()) parts.push(`Company: ${company.trim()}`);
    if (position.trim()) parts.push(`Position: ${position.trim()}`);
    if (description.trim()) parts.push(`Description: ${description.trim()}`);
    if (skills.length > 0) parts.push(`Required Skills: ${skills.join(", ")}`);
    if (experience) parts.push(`Experience Level: ${experience}`);
    if (fileText.trim()) parts.push(`Requirement file (${fileName}):\n${fileText.trim()}`);
    if (instructions.trim()) parts.push(`Additional Instructions: ${instructions.trim()}`);
    return parts.join("\n\n");
  }

  /** Reads the real text of a .txt requirement file — no backend upload exists, so this is the only format we can honestly parse client-side. */
  async function handleFileSelect(file: File | null) {
    if (!file) {
      setFileName(null);
      setFileSize(null);
      setFileText("");
      return;
    }
    setFileName(file.name);
    setFileSize(file.size);
    setFileText(await file.text());
  }

  function handleAnalyse() {
    const content = buildVacancyContent();
    // Validate everything together so all problems surface at once, not one
    // analyse-click at a time.
    let hasError = false;
    if (!content.trim()) {
      setAnalysisError(t("jobs.analysisErrorEmpty"));
      hasError = true;
    } else {
      setAnalysisError(null);
    }
    if (company.trim().length < 2) {
      setCompanyError(t("jobs.companyNameError"));
      hasError = true;
    } else {
      setCompanyError(undefined);
    }
    if (position.trim().length < 2) {
      setPositionError(t("jobs.positionError"));
      hasError = true;
    } else {
      setPositionError(undefined);
    }
    if (hasError) return;

    setAnalyzing(true);
    setStep("processing");
    analyzeVacancy(content)
      .then((result) => {
        if (!mountedRef.current) return;
        setAnalysis(result);
        // AI drafts the questions; HR reviews them in the builder below.
        setFormFields(reviewFieldsFromAnalysis(result.application_fields));
        setStep("review");
      })
      .catch((err) => {
        if (!mountedRef.current) return;
        // ApiError already carries the backend's friendly `detail` message.
        setAnalysisError(getErrorMessage(err, t("jobs.analysisFailed")));
        setStep("input");
      })
      .finally(() => {
        if (mountedRef.current) setAnalyzing(false);
      });
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
    } catch (err) {
      setAnalysisError(getErrorMessage(err, t("jobs.createJobFailed")));
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
      .catch((err) =>
        notify.error(t("applicationForm.link.regenerateFailed") || "Failed to regenerate the application link", getErrorMessage(err)),
      )
      .finally(() => setPublishing(false));
  }

  function openDetails() {
    if (createdJobId) navigate(`/jobs/${createdJobId}`);
  }

  const stepMarkers: { key: string; label: string; done: boolean; current: boolean }[] = [
    {
      key: "jobInfo",
      label: t("jobs.steps.jobInfo") || "Job Information",
      done: step !== "input",
      current: step === "input" || step === "processing",
    },
    {
      key: "reviewAndForm",
      label: t("jobs.steps.reviewAndForm") || "Review & Application Form",
      done: step === "published",
      current: step === "review",
    },
    {
      key: "publish",
      label: t("jobs.steps.publish") || "Publish",
      done: false,
      current: step === "published",
    },
  ];

  const previewJobInfo = analysis
    ? {
        company_name: analysis.company_name,
        position: analysis.position,
        description: analysis.description,
        required_skills: analysis.required_skills,
        required_experience: analysis.required_experience,
      }
    : undefined;

  const isDirty =
    step !== "published" &&
    Boolean(
      company.trim() ||
        position.trim() ||
        experience.trim() ||
        description.trim() ||
        skills.length > 0 ||
        fileText.trim() ||
        instructions.trim() ||
        step === "review",
    );

  return (
    <div className="page">
      <PageMeta title={t("jobs.createPageTitle")} noindex />
      <PageHeader
        title={t("jobs.createPageTitle")}
        description={t("jobs.createPageDescription")}
        backButton={<BackButton fallbackPath="/jobs" isDirty={isDirty} />}
      />

      <ol className="create-steps" aria-label={t("jobs.stepsAriaLabel") || "Job creation progress"}>
        {stepMarkers.map((marker, index) => (
          <li
            key={marker.key}
            className={`create-step${marker.current ? " is-current" : ""}${marker.done ? " is-done" : ""}`}
          >
            <span className="create-step-marker" aria-hidden="true">
              {marker.done ? <Check size={13} /> : index + 1}
            </span>
            <span className="create-step-label">{marker.label}</span>
          </li>
        ))}
      </ol>

      <div className="stack">
        {step === "input" && (
          <Card>
            <form
              className="job-form"
              onSubmit={(e) => {
                e.preventDefault();
                handleAnalyse();
              }}
            >
              <fieldset className="form-section">
                <legend className="form-section-title">{t("jobs.sections.basics")}</legend>
                <p className="form-section-hint">{t("jobs.sections.basicsHint")}</p>
                <div className="two-col">
              <TextInput
                label={t("jobs.companyName")}
                required
                value={company}
                onChange={(v) => {
                  setCompany(v);
                  setCompanyError(undefined);
                }}
                placeholder={t("jobs.companyNamePlaceholder")}
                error={companyError}
                disabled={analyzing}
              />
              <TextInput
                label={t("jobs.position")}
                required
                value={position}
                onChange={(v) => {
                  setPosition(v);
                  setPositionError(undefined);
                }}
                placeholder={t("jobs.positionPlaceholder")}
                error={positionError}
                disabled={analyzing}
              />
                </div>
              <TextArea
                label={t("jobs.description")}
                value={description}
                onChange={(v) => setDescription(v)}
                rows={4}
                placeholder={t("jobs.descriptionPlaceholder")}
                hint={t("jobs.descriptionHint")}
                disabled={analyzing}
              />
              </fieldset>

              <fieldset className="form-section">
                <legend className="form-section-title">{t("jobs.sections.requirements")}</legend>
                <p className="form-section-hint">{t("jobs.sections.requirementsHint")}</p>
              <TextInput
                label={t("jobs.requiredExperience")}
                value={experience}
                onChange={(v) => setExperience(v)}
                placeholder={t("jobs.experiencePlaceholder")}
                hint={t("jobs.optional")}
                disabled={analyzing}
              />
              <SkillsInput
                label={t("jobs.skills")}
                skills={skills}
                onSkillsChange={setSkills}
                disabled={analyzing}
              />
              </fieldset>

              <fieldset className="form-section">
                <legend className="form-section-title">{t("jobs.sections.ai")}</legend>
                <p className="form-section-hint">{t("jobs.sections.aiHint")}</p>
              <RequirementFileUpload
                fileName={fileName}
                fileSize={fileSize}
                onFileSelect={handleFileSelect}
                disabled={analyzing}
              />
              <TextArea
                label={t("jobs.aiInstructionsLabel")}
                value={instructions}
                onChange={(v) => setInstructions(v)}
                rows={2}
                placeholder={t("jobs.aiInstructionsPlaceholder")}
                disabled={analyzing}
              />
              </fieldset>
              <div className="job-form-actions">
                <BackButton
                  fallbackPath="/jobs"
                  label={t("jobs.cancel")}
                  variant="secondary"
                  size="md"
                  isDirty={isDirty}
                />
                <Button onClick={handleAnalyse} loading={analyzing} disabled={analyzing}>
                  {analyzing ? t("jobs.analysing") : t("jobs.analyseButton")}
                </Button>
              </div>
              {analysisError && (
                <p className="field-error" role="alert">
                  {analysisError}
                </p>
              )}
            </form>
          </Card>
        )}

        {step === "processing" && (
          <Card>
            <AIProcessingCard />
          </Card>
        )}

        {(step === "review" || step === "published") && analysis && (
          <div className="stack">
            <JobAIAnalysisCard analysis={analysis} />
            <Card title={t("jobs.reviewTitle")} subtitle={t("jobs.reviewSubtitle")}>
              <TextInput
                label={t("jobs.companyName")}
                required
                value={analysis.company_name}
                onChange={(v) => setAnalysis((prev) => (prev ? { ...prev, company_name: v } : null))}
                placeholder={t("jobs.companyNamePlaceholder")}
                disabled={step === "published"}
              />
              <TextInput
                label={t("jobs.position")}
                required
                value={analysis.position}
                onChange={(v) => setAnalysis((prev) => (prev ? { ...prev, position: v } : null))}
                placeholder={t("jobs.positionPlaceholder")}
                disabled={step === "published"}
              />
              <TextInput
                label={t("jobs.requiredExperience")}
                value={analysis.required_experience}
                onChange={(v) => setAnalysis((prev) => (prev ? { ...prev, required_experience: v } : null))}
                placeholder={t("jobs.experiencePlaceholder")}
                hint={t("jobs.optional")}
                disabled={step === "published"}
              />
              <TextArea
                label={t("jobs.description")}
                value={analysis.description}
                onChange={(v) => setAnalysis((prev) => (prev ? { ...prev, description: v } : null))}
                rows={4}
                placeholder={t("jobs.descriptionPlaceholder")}
                hint={t("jobs.optional")}
                disabled={step === "published"}
              />
              <SkillsInput
                label={t("jobs.skills")}
                skills={analysis.required_skills ? analysis.required_skills.split(/,\s*/).filter(Boolean) : []}
                onSkillsChange={(nextSkills) =>
                  setAnalysis((prev) => (prev ? { ...prev, required_skills: nextSkills.join(", ") } : null))
                }
                hint={t("jobs.optionalCommaSeparated")}
                disabled={step === "published"}
              />
            </Card>
            <ApplicationFormBuilder
              fields={formFields}
              onFieldsChange={setFormFields}
              errors={step === "review" ? validateApplicationFields(formFields) : undefined}
              previewJobInfo={previewJobInfo}
            />
            {step === "published" && token && (
              <>
                <ApplicationLinkCard
                  token={token}
                  jobTitle={analysis.position || position || t("jobs.newVacancy")}
                  onRegenerate={handleRegenerateToken}
                  regenerating={publishing}
                />
                <Card>
                  <div className="job-form-actions">
                    <Button variant="secondary" to="/jobs">
                      {t("jobs.backToJobs")}
                    </Button>
                    <Button onClick={openDetails}>{t("jobs.openJobDetails")}</Button>
                  </div>
                </Card>
              </>
            )}
            {step === "review" && (
              <Card>
                <div className="job-form-actions">
                  <Button variant="secondary" onClick={() => setStep("input")} disabled={publishing}>
                    {t("jobs.back")}
                  </Button>
                  <Button onClick={handleCreateJob} loading={publishing} disabled={publishing}>
                    {publishing ? t("jobs.creating") : t("jobs.createJobShare")}
                  </Button>
                </div>
                {analysisError && (
                  <p className="field-error" role="alert">
                    {analysisError}
                  </p>
                )}
              </Card>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
