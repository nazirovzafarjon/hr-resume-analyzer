/**
 * English copy — the reference dictionary. Its shape is the `Dictionary` type
 * every other language must satisfy.
 *
 * Copy rule: describe only what the product actually does today. Numbers that
 * appear in illustrations are sample data and are labelled as such.
 */
export const en = {
  meta: {
    title: "Resume Analyzer — Smarter Hiring for HR Teams",
    description:
      "Resume Analyzer helps HR teams publish vacancies, collect applications, analyze resumes against job requirements and manage candidates, interviews and hiring decisions in one place.",
  },
  common: {
    appName: "Resume Analyzer",
    sampleData: "Sample data for illustration",
    skipToContent: "Skip to content",
  },
  nav: {
    label: "Main",
    features: "Features",
    howItWorks: "How it works",
    solutions: "Solutions",
    faq: "FAQ",
    contact: "Contact",
    login: "Log in",
    getStarted: "Get started",
    openWorkspace: "Open workspace",
    openMenu: "Open menu",
    closeMenu: "Close menu",
    language: "Language",
    theme: "Theme",
    themeLight: "Light",
    themeDark: "Dark",
    themeSystem: "System",
    home: "Resume Analyzer home",
  },
  hero: {
    eyebrow: "Recruitment workspace for HR teams",
    titleLead: "Hire smarter.",
    titleTail: "Find the right talent faster.",
    subtitle:
      "A simpler way to publish vacancies, collect applications, analyze resumes and keep every candidate, interview and hiring decision organized in one place.",
    primaryCta: "Get started",
    secondaryCta: "Explore features",
    note: "Your HR workspace is ready as soon as you create an account.",
    mockupLabel:
      "Illustrative preview of the Resume Analyzer dashboard showing jobs, applications, candidates and interviews with sample data.",
  },
  mockup: {
    nav: ["Dashboard", "Jobs", "Applications", "Candidates", "Interviews", "Analytics"],
    title: "Overview",
    subtitle: "Recruitment activity",
    newJob: "New job",
    kpis: ["Active jobs", "Applications", "Candidates", "Interviews"],
    chartTitle: "Applications per week",
    listTitle: "Recent candidates",
    match: "match",
    candidates: [
      { name: "Aziza K.", role: "Python Developer", status: "Interview" },
      { name: "Timur R.", role: "Data Analyst", status: "Reviewing" },
      { name: "Laylo S.", role: "HR Specialist", status: "New" },
    ],
  },
  trust: {
    label: "What Resume Analyzer gives your team",
    items: [
      { title: "AI-assisted resume analysis", text: "Resumes scored against each job's requirements" },
      { title: "Centralized candidates", text: "Every application in one organized workspace" },
      { title: "Clear hiring workflow", text: "Statuses and interviews tracked per candidate" },
      { title: "Data-driven decisions", text: "Dashboards built from your own hiring activity" },
    ],
  },
  features: {
    eyebrow: "Features",
    title: "Everything your hiring workflow needs, in one place",
    subtitle:
      "From the first vacancy to the final decision, Resume Analyzer keeps the work structured so your team can focus on people, not paperwork.",
    items: [
      {
        title: "Resume analysis",
        text: "Compare each resume with the job's requirements and see a match score, matched skills and missing skills at a glance.",
      },
      {
        title: "Job management",
        text: "Create vacancies with company, position, required skills and experience — or let AI extract requirements from a job description file.",
      },
      {
        title: "Shareable application forms",
        text: "Build an application form for each job and share a public link. Candidates apply and upload their resume without an account.",
      },
      {
        title: "Candidate management",
        text: "Keep every applicant, resume and note organized in one searchable list instead of scattered inboxes and spreadsheets.",
      },
      {
        title: "Hiring workflow",
        text: "Track each candidate's hiring status and schedule interviews, so everyone knows where every application stands.",
      },
      {
        title: "Analytics",
        text: "Follow recruitment activity through dashboards for jobs, candidates, applications and interviews.",
      },
    ],
  },
  how: {
    eyebrow: "How it works",
    title: "From vacancy to decision in four steps",
    subtitle: "No setup projects, no training sessions. Create an account and start with your first job.",
    steps: [
      { title: "Create a job", text: "Define the position, required skills and experience level." },
      { title: "Collect applications", text: "Share the job's application link. Candidates submit their details and resume." },
      { title: "Analyze candidates", text: "Resumes are evaluated against the job's requirements with a clear match breakdown." },
      { title: "Move through hiring", text: "Review candidates, schedule interviews and update hiring status." },
    ],
  },
  workflow: {
    eyebrow: "Recruitment journey",
    title: "One connected path from job to hire",
    subtitle: "Each stage feeds the next, so nothing gets lost between a vacancy and a decision.",
    stages: [
      { title: "Job", text: "Vacancy and requirements" },
      { title: "Application", text: "Form and resume submitted" },
      { title: "Resume analysis", text: "Match against requirements" },
      { title: "Candidate review", text: "Shortlist and compare" },
      { title: "Interview", text: "Schedule and record outcome" },
      { title: "Hiring decision", text: "Made by your team" },
    ],
    note: "Resume Analyzer supports your decisions — it never makes them for you. Your team stays in control at every step.",
  },
  analysis: {
    eyebrow: "Resume analysis",
    title: "See how well a candidate fits before you open the resume",
    subtitle:
      "Resume Analyzer reads the resume, compares it with the skills the job requires and gives your team a structured starting point for review.",
    points: [
      { title: "Match score", text: "A percentage that shows how closely the resume aligns with the job." },
      { title: "Matched and missing skills", text: "See exactly which requirements are covered and which are not." },
      { title: "Summary and recommendation", text: "A short written assessment to speed up screening — you make the final call." },
    ],
    card: {
      label: "Resume analysis",
      candidate: "Candidate",
      name: "Aziza K.",
      role: "Python Developer",
      match: "Match",
      matched: "Matched skills",
      missing: "Missing skills",
      summaryLabel: "Summary",
      summary: "Strong alignment with the required backend skills. Containerization experience is not mentioned.",
      recommendationLabel: "Recommendation",
      recommendation: "Hire",
    },
  },
  solutions: {
    eyebrow: "Who it's for",
    title: "Built for the people who run hiring",
    subtitle: "Whether you hire occasionally or every week, Resume Analyzer gives your process structure without adding complexity.",
    items: [
      {
        title: "Recruiters",
        text: "Manage several vacancies and candidate pipelines at once, and spend less time on first-pass resume screening.",
      },
      {
        title: "HR teams",
        text: "Centralize recruitment activity and candidate information so the whole team works from the same picture.",
      },
      {
        title: "Growing companies",
        text: "Introduce an organized hiring workflow early, without heavy enterprise tooling or long onboarding.",
      },
    ],
  },
  benefits: {
    eyebrow: "Benefits",
    title: "Less busywork. More clarity.",
    items: [
      { title: "Less repetitive work", text: "Automated resume analysis takes over the first read." },
      { title: "Organized candidates", text: "Applications, resumes and notes live in one place." },
      { title: "Clearer workflows", text: "Every candidate has a visible status and next step." },
      { title: "Faster resume review", text: "Start from matched and missing skills, not a blank page." },
      { title: "Centralized information", text: "No more searching across email threads and files." },
      { title: "Better visibility", text: "Dashboards show what is happening across your hiring." },
    ],
  },
  analytics: {
    eyebrow: "Analytics",
    title: "Understand your recruitment at a glance",
    subtitle:
      "The dashboard turns your own jobs, candidates, applications and interviews into a clear overview, so you can see where hiring is moving and where it is stuck.",
    points: [
      "Totals for jobs, candidates and applications",
      "Applications by status, hiring recommendation and interview outcome",
      "Application trends, score distribution and top jobs over time",
    ],
    card: {
      title: "Recruitment overview",
      period: "Last 30 days",
      kpis: ["Total jobs", "Candidates", "Applications", "Interviews"],
      pipelineTitle: "Hiring pipeline",
      stages: ["New", "Reviewing", "Shortlisted", "Interview"],
    },
  },
  security: {
    eyebrow: "Security",
    title: "Your hiring data stays yours",
    subtitle: "Protection is built into how accounts and data work — here is exactly what is in place today.",
    items: [
      { title: "Secure authentication", text: "Sign in with email and password or with your Google account." },
      { title: "Token-based sessions", text: "JWT access tokens with short lifetimes and single-use refresh tokens." },
      { title: "Hashed passwords", text: "Passwords are stored as bcrypt hashes, never as plain text." },
      { title: "Protected resources", text: "Every HR endpoint requires an authenticated session." },
      { title: "Per-user data access", text: "Ownership checks ensure you only see your own jobs and candidates." },
    ],
  },
  faq: {
    eyebrow: "FAQ",
    title: "Frequently asked questions",
    subtitle: "Can't find your answer? Get in touch through the contact section below.",
    items: [
      {
        q: "What is Resume Analyzer?",
        a: "Resume Analyzer is a recruitment workspace for HR teams. It helps you publish vacancies, collect applications, analyze resumes against job requirements and manage candidates, interviews and hiring decisions in one place.",
      },
      {
        q: "Who is Resume Analyzer for?",
        a: "It is designed for recruiters, HR specialists and hiring teams — from companies that hire occasionally to teams managing several open positions at once.",
      },
      {
        q: "What can I manage with Resume Analyzer?",
        a: "Job vacancies and their requirements, application forms and their public links, candidates and their resumes, resume analysis results, interviews and each candidate's hiring status. A dashboard and analytics page summarize the activity.",
      },
      {
        q: "How does resume analysis work?",
        a: "The resume text is compared with the skills and experience the job requires. You get a match percentage, the lists of matched and missing skills, a short summary and a hiring recommendation. The result is a starting point for your review — the decision is always yours.",
      },
      {
        q: "Do I need technical knowledge?",
        a: "No. Resume Analyzer is built around everyday HR tasks: creating jobs, reviewing candidates and scheduling interviews. If you can use email and spreadsheets, you can use Resume Analyzer.",
      },
      {
        q: "Can I manage multiple vacancies?",
        a: "Yes. You can create and manage as many of your own jobs as you need, each with its own requirements, application form and candidates.",
      },
      {
        q: "Can I change a candidate's hiring status?",
        a: "Yes. Each candidate has a hiring status that you can update as they move through your process, and interviews can be scheduled and tracked alongside it.",
      },
      {
        q: "Is my account protected?",
        a: "Yes. Passwords are stored as bcrypt hashes, sessions use JWT access tokens with single-use refresh tokens, and every HR resource checks that it belongs to the signed-in user. You can also sign in with Google and reset a forgotten password by email.",
      },
      {
        q: "Can I use dark mode?",
        a: "Yes. Both this site and the HR workspace support light and dark themes, and can follow your system setting automatically.",
      },
      {
        q: "Can I change the language?",
        a: "Yes. Use the language selector in the navigation bar to switch between Uzbek (Latin and Cyrillic), Russian and English.",
      },
      {
        q: "How can I contact the team?",
        a: "Use the contact section at the bottom of this page.",
      },
    ],
  },
  contact: {
    eyebrow: "Contact",
    title: "Have a question? We're here to help.",
    subtitle: "Questions about Resume Analyzer, your account or how it fits your hiring process — write to us.",
    emailLabel: "Email",
    firstName: "First name",
    lastName: "Last name",
    email: "Email",
    message: "Message",
    firstNamePlaceholder: "Jane",
    lastNamePlaceholder: "Doe",
    emailPlaceholder: "you@company.com",
    messagePlaceholder: "How can we help?",
    submit: "Send message",
    sending: "Sending…",
    submitHint: "We'll reply to the email address you enter. No account needed.",
    required: "This field is required.",
    invalidEmail: "Enter a valid email address.",
    tooLong: "Use at most {max} characters.",
    successTitle: "Message sent",
    success: "Thanks for reaching out! We'll get back to you soon.",
    sendAnother: "Send another message",
    errorNetwork: "We couldn't reach the server. Check your connection and try again.",
    errorValidation: "Some fields don't look right. Check them and try again.",
    errorRateLimited: "You've sent several messages in a short time. Please try again later.",
    errorServer: "Something went wrong on our side. Please try again in a moment.",
    alreadyUser: "Already have an account?",
    alreadyUserLink: "Log in to your workspace",
    signedInUser: "You're signed in.",
    signedInLink: "Open your workspace",
  },
  cta: {
    title: "Ready to simplify your hiring workflow?",
    subtitle: "Create your account and publish your first vacancy today.",
    primary: "Get started",
    secondary: "Log in",
  },
  footer: {
    tagline: "Smarter hiring workflows for modern HR teams.",
    product: "Product",
    company: "Company",
    legal: "Legal",
    features: "Features",
    howItWorks: "How it works",
    analytics: "Analytics",
    about: "Who it's for",
    contact: "Contact",
    faq: "FAQ",
    privacy: "Privacy Policy",
    terms: "Terms of Service",
    rights: "All rights reserved.",
  },
  legal: {
    privacyTitle: "Privacy Policy",
    termsTitle: "Terms of Service",
    placeholder:
      "This document is being prepared and will be published here. If you have a question about how your data is handled in the meantime, please use the contact section.",
    back: "Back to home",
  },
  notFound: {
    title: "Page not found",
    text: "The page you are looking for doesn't exist or has moved.",
    back: "Back to home",
  },
};

export type Dictionary = typeof en;
