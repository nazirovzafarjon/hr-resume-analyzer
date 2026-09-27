import { Component, type ReactNode } from "react";
import { AlertTriangle } from "lucide-react";

type ErrorBoundaryProps = { children: ReactNode };
type ErrorBoundaryState = { error: Error | null };

const LANGUAGE_STORAGE_KEY = "resume-analyzer-language";

/**
 * Minimal, dependency-free copy for the 4 required languages.
 *
 * This boundary sits outside every provider in App.tsx (including
 * LanguageProvider) on purpose, so it can still catch a provider that itself
 * throws during mount. That means it cannot call useLanguage() — instead it
 * reads the persisted language preference directly from localStorage, the
 * same technique index.html's inline theme/language bootstrap script uses.
 */
const COPY: Record<string, { title: string; message: string; reload: string }> = {
  en: {
    title: "Something went wrong",
    message:
      "The application hit an unexpected error. Reload the page to continue — your data is safe.",
    reload: "Reload page",
  },
  ru: {
    title: "Что-то пошло не так",
    message:
      "В приложении произошла непредвиденная ошибка. Перезагрузите страницу, чтобы продолжить — ваши данные в безопасности.",
    reload: "Перезагрузить страницу",
  },
  uz: {
    title: "Xatolik yuz berdi",
    message:
      "Ilovada kutilmagan xatolik yuz berdi. Davom etish uchun sahifani qayta yuklang — ma'lumotlaringiz xavfsiz.",
    reload: "Sahifani qayta yuklash",
  },
  kiril: {
    title: "Хатолик юз берди",
    message:
      "Иловада кутилмаган хатолик юз берди. Давом этиш учун саҳифани қайта юкланг — маълумотларингиз хавфсиз.",
    reload: "Саҳифани қайта юклаш",
  },
};

function getCopy() {
  try {
    const lang = localStorage.getItem(LANGUAGE_STORAGE_KEY);
    if (lang && lang in COPY) return COPY[lang];
  } catch {
    // localStorage can throw in private mode — fall back to English.
  }
  return COPY.en;
}

/**
 * Catches uncaught render/effect errors below it and shows a recoverable error
 * card instead of letting the whole app unmount into a blank screen.
 *
 * Without a boundary a single runtime error - a broken third-party script, a
 * provider that throws during mount, a bad localStorage value - takes down the
 * entire UI with no way back. The boundary also always logs the full error so
 * developers keep the details without exposing them in the UI.
 */
export default class ErrorBoundary extends Component<
  ErrorBoundaryProps,
  ErrorBoundaryState
> {
  state: ErrorBoundaryState = { error: null };

  /** React calls this when a child throws during render. */
  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { error };
  }

  override componentDidUpdate(
    _prevProps: ErrorBoundaryProps,
    prevState: ErrorBoundaryState,
  ): void {
    if (this.state.error && this.state.error !== prevState.error) {
      console.error("[error-boundary] fatal error:", this.state.error);
    }
  }

  override render(): ReactNode {
    if (this.state.error) {
      const copy = getCopy();
      return (
        <div className="error-boundary" role="alert">
          <span className="error-boundary-icon" aria-hidden="true">
            <AlertTriangle size={22} />
          </span>
          <h1>{copy.title}</h1>
          <p>{copy.message}</p>
          <button type="button" className="btn" onClick={() => window.location.reload()}>
            {copy.reload}
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
