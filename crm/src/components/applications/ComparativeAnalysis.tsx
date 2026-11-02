/**
 * ComparativeAnalysis component — displays two-dimensional candidate assessment.
 *
 * Shows both:
 * 1. Requirements Fit (independent AI analysis score)
 * 2. Relative Competitiveness (percentile compared to other candidates)
 *
 * This clearly separates the two dimensions to avoid misleading HR about what
 * each metric means.
 */

import { useEffect, useState } from "react";
import { TrendingUp, Users } from "lucide-react";
import { getApplicationComparison, type ApplicationComparisonResponse } from "../../services/applicationsService";
import Card from "../ui/Card";
import { Skeleton } from "../ui/Skeleton";
import { useLanguage } from "../../contexts/LanguageContext";

type ComparativeAnalysisProps = {
  applicationId: number;
  jobId: number;
  /** The requirements fit score from AI analysis (0-100) */
  requirementsFitScore: number;
  /** Whether the application has been analyzed */
  isAnalyzed: boolean;
};

export default function ComparativeAnalysis({
  applicationId,
  requirementsFitScore,
  isAnalyzed,
}: ComparativeAnalysisProps) {
  const { t } = useLanguage();
  const [comparison, setComparison] = useState<ApplicationComparisonResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function loadComparison() {
      if (!isAnalyzed) {
        setLoading(false);
        return;
      }

      setLoading(true);
      setError(null);

      try {
        const data = await getApplicationComparison(applicationId);
        if (!cancelled) {
          setComparison(data);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : t("assessment.failed_to_load"));
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    loadComparison();

    return () => {
      cancelled = true;
    };
  }, [applicationId, isAnalyzed, t]);

  if (!isAnalyzed) {
    return (
      <Card>
        <div className="card-header">
          <h2 className="card-title">{t("assessment.title")}</h2>
        </div>
        <div style={{ padding: "var(--card-padding)" }}>
          <p style={{ color: "var(--text-secondary)", marginBottom: 0 }}>
            {t("assessment.analysis_required")}
          </p>
        </div>
      </Card>
    );
  }

  if (loading) {
    return (
      <Card>
        <div className="card-header">
          <h2 className="card-title">{t("assessment.title")}</h2>
        </div>
        <div style={{ padding: "var(--card-padding)" }}>
          <Skeleton variant="title" />
          <Skeleton variant="text" />
        </div>
      </Card>
    );
  }

  if (error) {
    return (
      <Card>
        <div className="card-header">
          <h2 className="card-title">{t("assessment.title")}</h2>
        </div>
        <div style={{ padding: "var(--card-padding)" }}>
          <p style={{ color: "var(--error-600)", marginBottom: 0 }}>
            {error}
          </p>
        </div>
      </Card>
    );
  }

  const hasComparison = comparison?.has_comparison ?? false;
  const percentile = comparison?.relative_percentile ?? 0;
  const poolSize = comparison?.comparison_pool_size ?? 0;
  const rank = comparison?.rank ?? 0;

  // Get tone for requirements fit
  const getFitTone = (score: number): string => {
    if (score >= 80) return "var(--success-600)";
    if (score >= 60) return "var(--warning-600)";
    return "var(--error-600)";
  };

  // Get tone for percentile
  const getPercentileTone = (pct: number): string => {
    if (pct >= 75) return "var(--success-600)";
    if (pct >= 50) return "var(--warning-600)";
    return "var(--text-secondary)";
  };

  // Get descriptive label for percentile
  const getPercentileLabel = (pct: number): string => {
    if (pct >= 90) return t("assessment.tier.top");
    if (pct >= 75) return t("assessment.tier.upper");
    if (pct >= 50) return t("assessment.tier.mid");
    if (pct >= 25) return t("assessment.tier.lower");
    return t("assessment.tier.below_average");
  };

  return (
    <Card>
      <div className="card-header">
        <h2 className="card-title">{t("assessment.title")}</h2>
        <p className="card-description" style={{ marginTop: "0.25rem" }}>
          {t("assessment.subtitle")}
        </p>
      </div>

      <div style={{ padding: "var(--card-padding)" }}>
        <div style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
          gap: "1.5rem",
        }}>
          {/* Requirements Fit - Independent Score */}
          <div style={{
            padding: "1.25rem",
            backgroundColor: "var(--gray-50)",
            borderRadius: "var(--radius-lg)",
            border: "1px solid var(--gray-200)",
          }}>
            <div style={{
              display: "flex",
              alignItems: "center",
              gap: "0.5rem",
              marginBottom: "0.75rem",
            }}>
              <TrendingUp size={20} style={{ color: "var(--primary-600)" }} />
              <h3 style={{
                fontSize: "0.875rem",
                fontWeight: 600,
                color: "var(--text-primary)",
                margin: 0,
                textTransform: "uppercase",
                letterSpacing: "0.05em",
              }}>
                {t("assessment.requirements_fit")}
              </h3>
            </div>

            <div style={{
              fontSize: "2.5rem",
              fontWeight: 700,
              color: getFitTone(requirementsFitScore),
              lineHeight: 1,
              marginBottom: "0.5rem",
            }}>
              {Math.round(requirementsFitScore)}%
            </div>

            <p style={{
              fontSize: "0.875rem",
              color: "var(--text-secondary)",
              margin: 0,
              lineHeight: 1.5,
            }}>
              {t("assessment.requirements_fit_desc")}
            </p>
          </div>

          {/* Relative Competitiveness - Comparison */}
          <div style={{
            padding: "1.25rem",
            backgroundColor: "var(--gray-50)",
            borderRadius: "var(--radius-lg)",
            border: "1px solid var(--gray-200)",
          }}>
            <div style={{
              display: "flex",
              alignItems: "center",
              gap: "0.5rem",
              marginBottom: "0.75rem",
            }}>
              <Users size={20} style={{ color: "var(--primary-600)" }} />
              <h3 style={{
                fontSize: "0.875rem",
                fontWeight: 600,
                color: "var(--text-primary)",
                margin: 0,
                textTransform: "uppercase",
                letterSpacing: "0.05em",
              }}>
                {t("assessment.relative_competitiveness")}
              </h3>
            </div>

            {hasComparison ? (
              <>
                <div style={{
                  fontSize: "2.5rem",
                  fontWeight: 700,
                  color: getPercentileTone(percentile),
                  lineHeight: 1,
                  marginBottom: "0.25rem",
                }}>
                  {Math.round(percentile)}
                  <span style={{ fontSize: "1.25rem", fontWeight: 600, marginLeft: "2px" }}>
                    {t("assessment.ordinal_suffix")}
                  </span>
                </div>
                <div style={{
                  fontSize: "0.875rem",
                  fontWeight: 500,
                  color: "var(--text-secondary)",
                  marginBottom: "0.75rem",
                }}>
                  {getPercentileLabel(percentile)}
                </div>

                <div style={{
                  display: "flex",
                  gap: "1rem",
                  paddingTop: "0.75rem",
                  borderTop: "1px solid var(--gray-200)",
                  fontSize: "0.875rem",
                  color: "var(--text-secondary)",
                }}>
                  <div>
                    <div style={{ fontWeight: 500, color: "var(--text-primary)" }}>
                      {t("assessment.rank_info", { rank, pool: poolSize })}
                    </div>
                  </div>
                  <div>
                    <div style={{ fontWeight: 500, color: "var(--text-primary)" }}>
                      {t("assessment.pool_analyzed", { pool: poolSize })}
                    </div>
                  </div>
                </div>

                <p style={{
                  fontSize: "0.75rem",
                  color: "var(--text-tertiary)",
                  margin: "0.75rem 0 0 0",
                  lineHeight: 1.5,
                }}>
                  {poolSize === 1
                    ? t("assessment.compared_with_one", { count: poolSize })
                    : t("assessment.compared_with", { count: poolSize })}
                </p>
              </>
            ) : (
              <p style={{
                fontSize: "0.875rem",
                color: "var(--text-secondary)",
                margin: 0,
              }}>
                {comparison?.reason || t("assessment.not_enough_candidates")}
              </p>
            )}
          </div>
        </div>

        {/* Important Disclaimer */}
        <div style={{
          marginTop: "1.5rem",
          padding: "1rem",
          backgroundColor: "var(--blue-50)",
          borderLeft: "3px solid var(--blue-500)",
          borderRadius: "var(--radius-md)",
        }}>
          <p style={{
            fontSize: "0.8125rem",
            color: "var(--text-secondary)",
            margin: 0,
            lineHeight: 1.6,
          }}>
            <strong style={{ color: "var(--text-primary)" }}>{t("assessment.disclaimer_title")}</strong>{" "}
            {t("assessment.disclaimer")}
          </p>
        </div>
      </div>
    </Card>
  );
}
