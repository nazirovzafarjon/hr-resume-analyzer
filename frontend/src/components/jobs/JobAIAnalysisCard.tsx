import type { CSSProperties } from "react";
import Card from "../ui/Card";
import type { JobAIAnalysis } from "../../types/job";
import type { JobAIAnalysisResult } from "../../types/job";

type AnalysisCardProps = {
  analysis: JobAIAnalysis | JobAIAnalysisResult;
};

/** Renders the structured vacancy analysis produced by the AI. */
export default function JobAIAnalysisCard({ analysis }: AnalysisCardProps) {
  // Check if it's the new API result format
  const isApiResult = "company_name" in analysis && !("seniority_score" in analysis);

  if (isApiResult) {
    const apiAnalysis = analysis as JobAIAnalysisResult;
    return (
      <Card title="AI Vacancy Analysis" subtitle="Structured result from the AI analysis.">
        <div className="two-col">
          <div>
            <h4 className="mini-heading">Company</h4>
            <p className="muted-note">{apiAnalysis.company_name || "Not specified"}</p>
            <h4 className="mini-heading">Position</h4>
            <p className="muted-note">{apiAnalysis.position || "Not specified"}</p>
            <h4 className="mini-heading">Required Experience</h4>
            <p className="muted-note">{apiAnalysis.required_experience || "Not specified"}</p>
          </div>
          <div>
            <h4 className="mini-heading">Required Skills</h4>
            <div className="chip-row">
              {apiAnalysis.required_skills
                .split(",")
                .map((s) => s.trim())
                .filter((s) => s.length > 0)
                .map((skill) => (
                  <span key={skill} className="chip chip--info">
                    {skill}
                  </span>
                ))}
              {apiAnalysis.required_skills.length === 0 && <span className="muted-note">Not specified</span>}
            </div>
          </div>
        </div>
        <div>
          <h4 className="mini-heading">Description</h4>
          <p className="analysis-summary">{apiAnalysis.description || "Not specified"}</p>
        </div>
      </Card>
    );
  }

  const mockAnalysis = analysis as JobAIAnalysis;
  const scores = [
    { label: "Seniority fit", value: mockAnalysis.seniority_score },
    { label: "Clarity", value: mockAnalysis.clarity_score },
    { label: "Completeness", value: mockAnalysis.completeness_score },
  ];
  return (
    <Card title="AI Vacancy Analysis" subtitle="Structured result from the simulated AI pass.">
      <p className="analysis-summary">{mockAnalysis.summary}</p>

      <div className="score-grid">
        {scores.map((score) => (
          <div key={score.label} className="score-item">
            <div
              className="analysis-score-ring analysis-score-ring--sm"
              style={{ "--score": `${score.value * 3.6}deg` } as CSSProperties}
            >
              <span>{score.value}%</span>
            </div>
            <p>{score.label}</p>
          </div>
        ))}
      </div>

      <div className="two-col">
        <div>
          <h4 className="mini-heading">Responsibilities</h4>
          <ul className="bullet-list">
            {mockAnalysis.responsibilities.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
        <div>
          <h4 className="mini-heading">Experience level</h4>
          <p className="muted-note">{mockAnalysis.experience_level}</p>
          <h4 className="mini-heading">Required skills</h4>
          <div className="chip-row">
            {mockAnalysis.required_skills.map((skill) => (
              <span key={skill} className="chip chip--info">{skill}</span>
            ))}
          </div>
          <h4 className="mini-heading">Nice to have</h4>
          <div className="chip-row">
            {mockAnalysis.nice_to_have_skills.map((skill) => (
              <span key={skill} className="chip">{skill}</span>
            ))}
          </div>
        </div>
      </div>

      <div>
        <h4 className="mini-heading">Suggestions to improve the vacancy</h4>
        <ul className="bullet-list">
          {mockAnalysis.suggestions.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      </div>
    </Card>
  );
}
