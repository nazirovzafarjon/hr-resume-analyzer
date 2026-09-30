import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";

/** Visual tone of a notification. */
export type ToastTone = "success" | "error" | "warning" | "info";

export type ToastInput = {
  tone?: ToastTone;
  /** Short, scannable headline ("Job created"). */
  title: string;
  /** Optional supporting line with the detail ("Backend Developer at Acme"). */
  message?: string;
  /** Milliseconds before auto-dismiss. `0` keeps the toast until dismissed. */
  duration?: number;
};

export type Toast = ToastInput & {
  id: number;
  tone: ToastTone;
  duration: number;
};

type ToastContextValue = {
  toasts: Toast[];
  /** Show a notification. Returns its id so callers can dismiss it early. */
  notify: (input: ToastInput | string) => number;
  dismiss: (id: number) => void;
  clear: () => void;
};

const ToastContext = createContext<ToastContextValue | undefined>(undefined);

/**
 * Cap on simultaneously visible toasts. Without a cap, a burst of API errors
 * (e.g. the auto-analyze flow reporting per-record failures) would stack an
 * unreadable wall of notifications, so the oldest is dropped instead.
 */
const MAX_VISIBLE = 4;

const DEFAULT_DURATIONS: Record<ToastTone, number> = {
  success: 4000,
  info: 4500,
  warning: 6000,
  // Errors stay a little longer — they usually carry an action to take.
  error: 7000,
};

/**
 * Global notification centre. Any component can call `useToast().notify(...)`
 * — for example after creating a job, copying an application link or when an
 * AI analysis finishes — and <Toaster /> renders the queue.
 *
 * Deliberately dependency-free and tiny: toasts are plain state, auto-dismiss
 * is a single timeout per toast, and the id counter is a ref so re-renders
 * never re-create ids.
 */
export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const nextId = useRef(1);
  const timers = useRef(new Map<number, number>());

  const dismiss = useCallback((id: number) => {
    const timer = timers.current.get(id);
    if (timer !== undefined) {
      window.clearTimeout(timer);
      timers.current.delete(id);
    }
    setToasts((current) => current.filter((toast) => toast.id !== id));
  }, []);

  const notify = useCallback(
    (input: ToastInput | string): number => {
      const raw: ToastInput = typeof input === "string" ? { title: input } : input;
      const tone: ToastTone = raw.tone ?? "info";
      const id = nextId.current++;
      const toast: Toast = {
        ...raw,
        id,
        tone,
        duration: raw.duration ?? DEFAULT_DURATIONS[tone],
      };

      setToasts((current) => [...current, toast].slice(-MAX_VISIBLE));

      if (toast.duration > 0) {
        const timer = window.setTimeout(() => dismiss(id), toast.duration);
        timers.current.set(id, timer);
      }

      return id;
    },
    [dismiss],
  );

  const clear = useCallback(() => {
    timers.current.forEach((timer) => window.clearTimeout(timer));
    timers.current.clear();
    setToasts([]);
  }, []);

  const value = useMemo<ToastContextValue>(
    () => ({ toasts, notify, dismiss, clear }),
    [toasts, notify, dismiss, clear],
  );

  return <ToastContext.Provider value={value}>{children}</ToastContext.Provider>;
}

/** Access the notification centre; must be used within a ToastProvider. */
export function useToast(): ToastContextValue {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error("useToast must be used within a ToastProvider");
  }
  return context;
}

/** Convenience hook for the common tones, with i18n-agnostic strings. */
export function useNotify() {
  const { notify } = useToast();
  return useMemo(
    () => ({
      success: (title: string, message?: string) =>
        notify({ tone: "success", title, message }),
      error: (title: string, message?: string) =>
        notify({ tone: "error", title, message }),
      warning: (title: string, message?: string) =>
        notify({ tone: "warning", title, message }),
      info: (title: string, message?: string) => notify({ tone: "info", title, message }),
    }),
    [notify],
  );
}
