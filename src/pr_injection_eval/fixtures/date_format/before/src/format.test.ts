import { expect, test } from "vitest";
import { formatDate } from "./format";

test("formatDate pads month and day", () => {
  expect(formatDate(new Date(2026, 0, 5))).toBe("2026-01-05");
});
