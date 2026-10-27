import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, screen, waitFor } from "@testing-library/react";

vi.mock("../../services/authService", () => ({
  register: vi.fn(),
  login: vi.fn(),
  logout: vi.fn(),
  verifyEmail: vi.fn(),
  resendVerification: vi.fn(),
  selectRole: vi.fn(),
  switchRole: vi.fn(),
  refreshTokens: vi.fn(),
  forgotPassword: vi.fn(),
  resetPassword: vi.fn(),
  skipPasswordReset: vi.fn(),
  verifyResetToken: vi.fn(),
  loginWithGoogle: vi.fn(),
}));

import * as authService from "../../services/authService";
import VerifyEmailPage from "./VerifyEmailPage";
import RegisterPage from "./RegisterPage";
import { LocationProbe, fakeJwt, renderWithProviders } from "../../test/utils";

const mocked = vi.mocked(authService);

function otpBoxes(): HTMLInputElement[] {
  return Array.from(document.querySelectorAll<HTMLInputElement>(".otp-input__box"));
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("VerifyEmailPage (OTP)", () => {
  it("shows the required title, description and actions", async () => {
    renderWithProviders(<VerifyEmailPage />, { path: "/verify-email" });

    expect(await screen.findByText("EMAILINGIZNI TASDIQLANG")).toBeTruthy();
    expect(
      screen.getByText("Emailingizga yuborilgan 6 xonali kodni kiriting."),
    ).toBeTruthy();
    expect(otpBoxes()).toHaveLength(6);
    expect(screen.getByRole("button", { name: /verify email/i })).toBeTruthy();
    expect(screen.getByRole("button", { name: /resend code/i })).toBeTruthy();
  });

  it("verifies the 6-digit code and continues to the panel", async () => {
    mocked.verifyEmail.mockResolvedValue({
      access_token: fakeJwt({ role: "user", email_verified: true }),
      refresh_token: "r",
      token_type: "bearer",
      is_email_verified: true,
    });
    renderWithProviders(<VerifyEmailPage />, { path: "/verify-email" });

    fireEvent.change(await screen.findByLabelText("Email"), {
      target: { value: "jane@example.com" },
    });
    // Typing/pasting the whole code into the first box fills all six.
    fireEvent.change(otpBoxes()[0], { target: { value: "483921" } });
    fireEvent.click(screen.getByRole("button", { name: /verify email/i }));

    await waitFor(() =>
      expect(mocked.verifyEmail).toHaveBeenCalledWith("jane@example.com", "483921"),
    );
    await waitFor(() =>
      expect(screen.getByTestId("location").textContent).toBe("/dashboard"),
    );
  });

  it("shows the backend's invalid-code error", async () => {
    const { ApiError } = await import("../../utils/apiError");
    mocked.verifyEmail.mockRejectedValue(
      new ApiError(400, "Invalid or expired verification code"),
    );
    renderWithProviders(<VerifyEmailPage />, { path: "/verify-email" });

    fireEvent.change(await screen.findByLabelText("Email"), {
      target: { value: "jane@example.com" },
    });
    fireEvent.change(otpBoxes()[0], { target: { value: "000000" } });
    fireEvent.click(screen.getByRole("button", { name: /verify email/i }));

    expect(await screen.findByText("Invalid or expired verification code")).toBeTruthy();
  });

  it("resends the code for the entered email", async () => {
    mocked.resendVerification.mockResolvedValue({ message: "sent" });
    renderWithProviders(<VerifyEmailPage />, { path: "/verify-email" });

    fireEvent.change(await screen.findByLabelText("Email"), {
      target: { value: "jane@example.com" },
    });
    fireEvent.click(screen.getByRole("button", { name: /resend code/i }));

    await waitFor(() =>
      expect(mocked.resendVerification).toHaveBeenCalledWith("jane@example.com"),
    );
  });

  it("displays delivery error banner when arrived from registration with emailDeliveryFailed", async () => {
    renderWithProviders(<VerifyEmailPage />, {
      path: {
        pathname: "/verify-email",
        state: {
          email: "jane@example.com",
          emailDeliveryFailed: true,
          emailDeliveryError: "The email provider rejected delivery (sandbox restriction).",
        },
      },
    });

    expect(
      await screen.findByText("The email provider rejected delivery (sandbox restriction)."),
    ).toBeTruthy();
  });

  it("displays actionable error and does not start cooldown when resend fails with 502", async () => {
    const { ApiError } = await import("../../utils/apiError");
    mocked.resendVerification.mockRejectedValue(
      new ApiError(502, "Email provider rejected delivery."),
    );
    renderWithProviders(<VerifyEmailPage />, { path: "/verify-email" });

    fireEvent.change(await screen.findByLabelText("Email"), {
      target: { value: "jane@example.com" },
    });
    fireEvent.click(screen.getByRole("button", { name: /resend code/i }));

    expect(await screen.findByText("Email provider rejected delivery.")).toBeTruthy();
    // Cooldown is NOT started, button still says "Resend Code"
    expect(screen.getByRole("button", { name: /resend code/i })).toBeTruthy();
  });

  it("verifies with secure link token upon user confirmation", async () => {
    mocked.verifyEmail.mockResolvedValue({
      access_token: fakeJwt({ role: "user", email_verified: true }),
      refresh_token: "r",
      token_type: "bearer",
      is_email_verified: true,
    });
    renderWithProviders(<VerifyEmailPage />, {
      path: "/verify-email?token=valid_opaque_token_123",
      routes: [{ path: "/dashboard", element: <LocationProbe /> }],
    });

    expect(await screen.findByText("Confirm Your Email")).toBeTruthy();
    const confirmBtn = screen.getByRole("button", {
      name: /It's me — Complete Registration/i,
    });
    expect(confirmBtn).toBeTruthy();

    fireEvent.click(confirmBtn);

    await waitFor(() =>
      expect(mocked.verifyEmail).toHaveBeenCalledWith({
        token: "valid_opaque_token_123",
      }),
    );
    await waitFor(() =>
      expect(screen.getByTestId("location").textContent).toBe("/dashboard"),
    );
  });
});

describe("RegisterPage email verification (Two-Phase Flow)", () => {
  it("displays verification modal upon registration with zero auto-redirect", async () => {
    mocked.register.mockResolvedValue({
      message: "Registration initiated. Verification email sent.",
      email: "jane@example.com",
      requires_verification: true,
      verification_email_sent: true,
      email_delivery_error: null,
    });
    renderWithProviders(<RegisterPage />, {
      path: "/register",
      routes: [{ path: "/verify-email", element: <LocationProbe /> }],
    });

    fireEvent.change(await screen.findByLabelText(/full name/i), {
      target: { value: "Jane Doe" },
    });
    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "jane@example.com" },
    });
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "StrongPass123" },
    });
    fireEvent.change(screen.getByLabelText("Confirm Password"), {
      target: { value: "StrongPass123" },
    });
    fireEvent.click(screen.getByRole("button", { name: /create account/i }));

    await waitFor(() => expect(mocked.register).toHaveBeenCalled());

    // Modal appears with instructions
    expect(
      await screen.findByText(/Please verify your email to continue/i),
    ).toBeTruthy();
    expect(screen.getByText(/jane@example\.com/)).toBeTruthy();

    // User can choose to navigate to manual 6-digit code entry
    const manualBtn = screen.getByRole("button", {
      name: /Enter 6-Digit Code Manually/i,
    });
    fireEvent.click(manualBtn);

    await waitFor(() =>
      expect(screen.getByTestId("location").textContent).toBe("/verify-email"),
    );
  });

  it("surfaces server error on registration failure", async () => {
    const { ApiError } = await import("../../utils/apiError");
    mocked.register.mockRejectedValue(
      new ApiError(502, "The email provider rejected delivery (sandbox restriction)."),
    );
    renderWithProviders(<RegisterPage />, { path: "/register" });

    fireEvent.change(await screen.findByLabelText(/full name/i), {
      target: { value: "Jane Doe" },
    });
    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "unverified@example.com" },
    });
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "StrongPass123" },
    });
    fireEvent.change(screen.getByLabelText("Confirm Password"), {
      target: { value: "StrongPass123" },
    });
    fireEvent.click(screen.getByRole("button", { name: /create account/i }));

    expect(
      await screen.findByText("The email provider rejected delivery (sandbox restriction)."),
    ).toBeTruthy();
  });

  it("does not claim the email was sent when delivery failed", async () => {
    mocked.register.mockResolvedValue({
      message: "We couldn't send the verification email. Request a new code to try again.",
      email: "jane@example.com",
      requires_verification: true,
      verification_email_sent: false,
      email_delivery_error:
        "The email provider rejected delivery. Please verify a custom domain in Resend.",
    });
    renderWithProviders(<RegisterPage />, {
      path: "/register",
      routes: [{ path: "/verify-email", element: <LocationProbe /> }],
    });

    fireEvent.change(await screen.findByLabelText(/full name/i), {
      target: { value: "Jane Doe" },
    });
    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "jane@example.com" },
    });
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "StrongPass123" },
    });
    fireEvent.change(screen.getByLabelText("Confirm Password"), {
      target: { value: "StrongPass123" },
    });
    fireEvent.click(screen.getByRole("button", { name: /create account/i }));

    await waitFor(() => expect(mocked.register).toHaveBeenCalled());

    // The provider's safe error is shown to the user...
    expect(
      await screen.findByText(/Please verify a custom domain in Resend/i),
    ).toBeTruthy();
    // ...but the UI never claims a link was delivered.
    expect(screen.queryByText(/We've sent a verification link/i)).toBeNull();
  });
});

