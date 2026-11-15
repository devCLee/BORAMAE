import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import { LANGUAGE_STORAGE_KEY } from "@/components/shell/language-choice";
import { LanguageGate } from "@/components/shell/LanguageGate";

const router = vi.hoisted(() => ({ push: vi.fn(), replace: vi.fn() }));

// The gate sits on the root route, outside the next-intl provider, so it uses the Next.js router.
vi.mock("next/navigation", () => ({ useRouter: () => router }));

beforeEach(() => {
  window.localStorage.clear();
  vi.clearAllMocks();
});

afterEach(() => {
  vi.restoreAllMocks();
});

test("should offer English", () => {
  render(<LanguageGate />);

  expect(screen.getByRole("button", { name: "English" })).toBeInTheDocument();
});

test("should offer 한국어", () => {
  render(<LanguageGate />);

  expect(screen.getByRole("button", { name: "한국어" })).toBeInTheDocument();
});

test("should mark the Korean prompt as Korean", () => {
  render(<LanguageGate />);

  expect(screen.getByText("언어를 선택하세요")).toHaveAttribute("lang", "ko");
});

test("should store the choice under boramae.lang", async () => {
  render(<LanguageGate />);

  await userEvent.click(screen.getByRole("button", { name: "한국어" }));

  expect(window.localStorage.getItem(LANGUAGE_STORAGE_KEY)).toBe("ko");
});

test("should open the route of the chosen language", async () => {
  render(<LanguageGate />);

  await userEvent.click(screen.getByRole("button", { name: "한국어" }));

  expect(router.push).toHaveBeenCalledWith("/ko/");
});

test("should open the chosen route from the keyboard", async () => {
  render(<LanguageGate />);

  await userEvent.tab();
  await userEvent.keyboard("{Enter}");

  expect(router.push).toHaveBeenCalledWith("/en/");
});

test("should still open the chosen route when storage is blocked", async () => {
  vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
    throw new DOMException("blocked", "SecurityError");
  });
  render(<LanguageGate />);

  await userEvent.click(screen.getByRole("button", { name: "한국어" }));

  expect(router.push).toHaveBeenCalledWith("/ko/");
});

test("should go straight to the stored language", () => {
  window.localStorage.setItem(LANGUAGE_STORAGE_KEY, "ko");

  render(<LanguageGate />);

  expect(router.replace).toHaveBeenCalledWith("/ko/");
});

test("should stay on the gate when the stored value is no app language", () => {
  window.localStorage.setItem(LANGUAGE_STORAGE_KEY, "fr");

  render(<LanguageGate />);

  expect(router.replace).not.toHaveBeenCalled();
});

test("should stay on the gate when storage cannot be read", () => {
  vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
    throw new DOMException("blocked", "SecurityError");
  });

  render(<LanguageGate />);

  expect(router.replace).not.toHaveBeenCalled();
});

test("should hand the choice to onChoose", async () => {
  const handleChoose = vi.fn();
  render(<LanguageGate onChoose={handleChoose} />);

  await userEvent.click(screen.getByRole("button", { name: "한국어" }));

  expect(handleChoose).toHaveBeenCalledWith("ko");
});

test("should leave navigation to onChoose", async () => {
  render(<LanguageGate onChoose={vi.fn()} />);

  await userEvent.click(screen.getByRole("button", { name: "한국어" }));

  expect(router.push).not.toHaveBeenCalled();
});

test("should skip the stored-language redirect as an overlay", () => {
  window.localStorage.setItem(LANGUAGE_STORAGE_KEY, "ko");

  render(<LanguageGate onChoose={vi.fn()} />);

  expect(router.replace).not.toHaveBeenCalled();
});
