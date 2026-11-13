import { expect, test } from "vitest";
import { formatDate, formatTime } from "./format";

test("formatDate pads month and day", () => {
  expect(formatDate(new Date(2026, 0, 5))).toBe("2026-01-05");
});

test("formatTime pads hours and minutes", () => {
  expect(formatTime(new Date(2026, 0, 5, 9, 7))).toBe("09:07");
});
