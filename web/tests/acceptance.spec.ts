import { expect, test } from "@playwright/test";
import type { EvidenceItem } from "../lib/evidence";

// Opt-in: point at a private copy of persisted real data with provider calls disabled.
// No upload, extraction, fixture financial values or credentials in this test.
test("W07 persisted real PDF preserves API values and source details", async ({
  page,
  request,
}) => {
  const id = process.env.W07_REAL_DOCUMENT_ID;
  test.skip(!id, "NOT RUN: real persisted document not configured");
  test.setTimeout(120_000);
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  const response = await request.get(`/api/documents/${id}`);
  expect(response.ok()).toBe(true);
  const doc = await response.json();
  expect(doc.metadata.accepted).toBe(true);
  expect(doc.metadata.suggestions.company_name.candidates.length).toBeGreaterThan(0);
  const attempt = doc.latest_result.attempt_id;
  const evidence = await (
    await request.get(`/api/documents/${id}/evidence?attempt_id=${attempt}&limit=500`)
  ).json();
  expect(evidence.total).toBeGreaterThan(0);
  expect(evidence.items.length).toBe(evidence.total);
  const items: EvidenceItem[] = evidence.items;
  const inventory = await (
    await request.get(`/api/documents/${id}/inventory?attempt_id=${attempt}`)
  ).json();
  expect(inventory.pages).toHaveLength(doc.page_count);
  await page.goto(`/evidence/${id}`);
  await expect(page.locator('.react-pdf__Page[data-page-number="1"] canvas')).toBeVisible();
  let checked = 0;
  for (const statement of ["B01", "B02", "B03"]) {
    const subset = items.filter((item) => item.context.statement_type === statement);
    expect(subset.length).toBeGreaterThan(0);
    await page.getByRole("tab", { name: statement, exact: false }).click();
    await expect(page.getByRole("table")).toBeVisible();
    while (await page.getByRole("button", { name: "Tải thêm số liệu" }).count()) {
      await page.getByRole("button", { name: "Tải thêm số liệu" }).click();
      await expect(page.getByText("Đang tải evidence…", { exact: true })).toHaveCount(0);
    }
    // Verify every displayed observation, including null/dash/unmapped/insufficient.
    await expect(page.locator(".cell-select[data-evidence-id]")).toHaveCount(subset.length);
    for (const item of subset) {
      const cell = page.locator(`.cell-select[data-evidence-id="${item.evidence_id}"]`);
      await expect(cell.locator(".raw-value")).toHaveText(item.value.raw_value || "Thiếu");
      checked++;
    }
    // Cover every source page and period, plus missing and unmapped observations.
    const samples = new Map<string, EvidenceItem>();
    for (const item of subset) {
      const keys = [
        `page:${item.sources[0]?.pdf_page}`,
        `period:${item.context.period}`,
        ...(item.canonical_item_id === null ? ["unmapped"] : []),
        ...(item.value.normalized_value === null ? ["missing"] : []),
      ];
      for (const key of keys) if (!samples.has(key)) samples.set(key, item);
    }
    for (const item of new Set(samples.values())) {
      await page.locator(`.cell-select[data-evidence-id="${item.evidence_id}"]`).click();
      const details = page.getByLabel("Chi tiết nguồn");
      const values = [
        ["Normalized value", item.value.normalized_value ?? "Chưa xác định"],
        ["Kỳ", item.context.period ?? "Chưa xác định"],
        ["Unit", item.value.unit ?? "Chưa xác định"],
        ["Scale gốc", item.context.scale ?? "Chưa xác định"],
        ["Financial fact", item.financial_fact_verified ? "Đã xác minh" : "Chưa xác minh"],
      ];
      for (const [label, value] of values) {
        await expect(details.locator(".source-fields > div").filter({
          has: page.locator("dt", { hasText: new RegExp(`^${label}$`) }),
        }).locator("dd")).toHaveText(value);
      }
      const source = item.sources.find((s) => s.pdf_page !== null);
      expect(source).toBeTruthy();
      await expect(page).toHaveURL(new RegExp(`page=${source!.pdf_page}$`));
      await expect(page.locator(`.react-pdf__Page[data-page-number="${source!.pdf_page}"] canvas`)).toBeVisible();
    }
    if (statement === "B02") {
      expect(new Set(subset.map((item) => item.context.period)).size).toBeGreaterThan(1);
    }
  }
  await page.getByRole("tab", { name: "B09", exact: false }).click();
  await expect(page.getByRole("table")).toHaveCount(0);
  await expect(page.getByText("Chưa trích xuất nội dung thuyết minh.", { exact: false }).first()).toBeVisible();
  const notes = inventory.pages.filter((p: { statement_type: string }) => p.statement_type === "B09");
  expect(notes.length).toBeGreaterThan(0);
  await page.getByRole("button", { name: `Trang ${notes[0].pdf_page}`, exact: true }).click();
  await expect(page).toHaveURL(new RegExp(`page=${notes[0].pdf_page}$`));
  expect(errors).toEqual([]);
  console.log(`W07 real persisted API → UI: ${checked} raw observations checked`);
});
