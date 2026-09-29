import Hero from "../components/sections/Hero";
import TrustBar from "../components/sections/TrustBar";
import Features from "../components/sections/Features";
import HowItWorks from "../components/sections/HowItWorks";
import Workflow from "../components/sections/Workflow";
import ResumeAnalysis from "../components/sections/ResumeAnalysis";
import Solutions from "../components/sections/Solutions";
import Benefits from "../components/sections/Benefits";
import AnalyticsPreview from "../components/sections/AnalyticsPreview";
import Security from "../components/sections/Security";
import Faq from "../components/sections/Faq";
import Contact from "../components/sections/Contact";
import FinalCta from "../components/sections/FinalCta";
import { useDocumentMeta } from "../hooks/useDocumentMeta";
import { useSectionReveal } from "../hooks/useSectionReveal";
import { useI18n } from "../i18n";

export default function LandingPage() {
  const { t } = useI18n();
  useDocumentMeta(t.meta.title, t.meta.description);
  useSectionReveal();

  return (
    <>
      <Hero />
      <TrustBar />
      <Features />
      <HowItWorks />
      <Workflow />
      <ResumeAnalysis />
      <Solutions />
      <Benefits />
      <AnalyticsPreview />
      <Security />
      <Faq />
      <Contact />
      <FinalCta />
    </>
  );
}
