import { useRef, type ClipboardEvent, type KeyboardEvent } from "react";

type OtpInputProps = {
  /** Current code (digits only, may be shorter than `length`). */
  value: string;
  onChange: (value: string) => void;
  /** Number of boxes (default 6). */
  length?: number;
  disabled?: boolean;
  autoFocus?: boolean;
  label?: string;
};

/**
 * Accessible 6-box one-time-code input.
 *
 * Behaves like a single field: typing a digit advances automatically, pasting a
 * whole code fills every box, and Backspace clears/moves left — the user never
 * has to click each box between characters.
 */
export default function OtpInput({
  value,
  onChange,
  length = 6,
  disabled = false,
  autoFocus = false,
  label,
}: OtpInputProps) {
  const inputs = useRef<Array<HTMLInputElement | null>>([]);
  const digits = value.replace(/\D/g, "").slice(0, length).split("");

  function focusAt(index: number) {
    const target = Math.max(0, Math.min(length - 1, index));
    inputs.current[target]?.focus();
    inputs.current[target]?.select();
  }

  function setDigit(index: number, raw: string) {
    // Strip non-digits: a paste or autofill may drop the whole code in one box.
    const incoming = raw.replace(/\D/g, "");
    const next = digits.slice();
    if (!incoming) {
      next[index] = "";
      onChange(next.join(""));
      return;
    }
    const chars = incoming.split("");
    let cursor = index;
    for (const char of chars) {
      if (cursor >= length) break;
      next[cursor] = char;
      cursor += 1;
    }
    onChange(next.join("").slice(0, length));
    focusAt(cursor);
  }

  function handleKeyDown(index: number, event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "Backspace") {
      if (digits[index]) {
        // Clear the current box (default behaviour already does this).
        return;
      }
      event.preventDefault();
      const next = digits.slice();
      next[index - 1] = "";
      onChange(next.join(""));
      focusAt(index - 1);
    } else if (event.key === "ArrowLeft") {
      event.preventDefault();
      focusAt(index - 1);
    } else if (event.key === "ArrowRight") {
      event.preventDefault();
      focusAt(index + 1);
    }
  }

  function handlePaste(index: number, event: ClipboardEvent<HTMLInputElement>) {
    const pasted = event.clipboardData.getData("text").replace(/\D/g, "");
    if (!pasted) return;
    event.preventDefault();
    setDigit(index, pasted);
  }

  return (
    <div className="otp-input" role="group" aria-label={label}>
      {Array.from({ length }).map((_, index) => (
        <input
          key={index}
          ref={(element) => {
            inputs.current[index] = element;
          }}
          className="otp-input__box"
          type="text"
          inputMode="numeric"
          autoComplete={index === 0 ? "one-time-code" : "off"}
          maxLength={1}
          value={digits[index] ?? ""}
          onChange={(event) => setDigit(index, event.target.value)}
          onKeyDown={(event) => handleKeyDown(index, event)}
          onPaste={(event) => handlePaste(index, event)}
          onFocus={(event) => event.target.select()}
          disabled={disabled}
          autoFocus={autoFocus && index === 0}
          aria-label={`${label ?? "code"} ${index + 1}`}
        />
      ))}
    </div>
  );
}
