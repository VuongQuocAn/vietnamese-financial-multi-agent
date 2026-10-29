import { expect, test, type Page } from "@playwright/test";
import { renderToStaticMarkup } from "react-dom/server";
import { execFileSync } from "node:child_process";
import { mkdtempSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { type EvidenceItem, groupEvidence } from "../lib/evidence";
import { FinancialTable } from "../components/evidence/financial-table";

const id = "00000000-0000-4000-8000-000000000006";
function observation(
  key: string,
  overrides: Partial<EvidenceItem> = {},
): EvidenceItem {
  return {
    evidence_id: key,
    source_item_code: "01",
    canonical_item_id: null,
    raw_label: "Chỉ tiêu synthetic",
    raw_header: "Kỳ A",
    value: {
      raw_value: "0",
      normalized_value: "0",
      unit: "VND",
      status: "resolved",
      issues: [],
    },
    context: {
      period: "Kỳ A",
      period_type: "fiscal_year",
      currency: "VND",
      scale: "1",
      reporting_scope: "separate",
      statement_type: "B02",
    },
    binding: { table: 0, row: 1, column: 1 },
    sources: [
      {
        content_id: "synthetic",
        pdf_page: 2,
        source_pointer: "/tables/0/cells/1",
        provenance_level: "cell",
      },
    ],
    extraction_issues: [],
    quality: {
      decision: "usable_with_caveat",
      caveats: ["missing_canonical_mapping"],
      issues: [],
    },
    financial_fact_verified: false,
    ...overrides,
  };
}

test("W06 grouping preserves periods, contexts, unbound observations and exact raw values", () => {
  const zero = observation("zero");
  const dash = observation("dash", {
    raw_header: "Kỳ B",
    context: { ...zero.context, period: "Kỳ B" },
    binding: { table: 0, row: 1, column: 2 },
    value: { ...zero.value, raw_value: "—", normalized_value: null },
  });
  const missing = observation("missing", {
    binding: { table: 0, row: 2, column: 1 },
    value: { ...zero.value, raw_value: null, normalized_value: null },
  });
  const exact = observation("exact", {
    source_item_code: "411a",
    binding: null,
    value: {
      ...zero.value,
      raw_value: "-9007199254740993.00100",
      normalized_value: "-9007199254740993.00100",
    },
  });
  const conflict = observation("conflict", {
    quality: { decision: "conflicted", caveats: [], issues: [] },
    value: { ...zero.value, raw_value: "9", normalized_value: "9" },
  });
  const items = [
    zero,
    dash,
    missing,
    exact,
    conflict,
    observation("scope", {
      context: { ...zero.context, reporting_scope: "consolidated" },
    }),
    observation("unit", { value: { ...zero.value, unit: "triệu VND" } }),
    observation("page", { sources: [{ ...zero.sources[0], pdf_page: 3 }] }),
    observation("unbound", { binding: null }),
  ];
  const grouped = groupEvidence(items);
  expect(grouped.rows).toHaveLength(8);
  expect(Object.values(grouped.rows[0].cells).map((cell) => cell.id)).toEqual([
    "zero",
    "dash",
  ]);
  expect(grouped.periods).toHaveLength(5);
  expect(
    grouped.rows
      .flatMap((row) => Object.values(row.cells).map((cell) => cell.id))
      .sort(),
  ).toEqual(items.map((i) => i.evidence_id).sort());
  const html = renderToStaticMarkup(<FinancialTable {...grouped} />);
  expect(html).toContain('class="raw-value">0</span>');
  expect(html).toContain('class="raw-value">—</span>');
  expect(html).toContain("Thiếu");
  expect(html).toContain("-9007199254740993.00100");
  expect(html).toContain("411a");
  expect(html).toContain("Xung đột — giá trị ứng viên");
  expect(html).not.toContain("Đã xác minh");
});

async function mockDocument(page: Page) {
  const folder = mkdtempSync(join(tmpdir(), "w06-smoke-"));
  let pdf: Buffer;
  try {
    const file = join(folder, "synthetic.pdf");
    execFileSync(
      process.env.PYTHON ??
        (process.platform === "win32"
          ? "../.venv/Scripts/python.exe"
          : "python"),
      [
        "-c",
        "import sys; from PIL import Image; pages=[Image.new('RGB',(120,160),c) for c in ['white','gray','navy']]; pages[0].save(sys.argv[1],format='PDF',save_all=True,append_images=pages[1:])",
        file,
      ],
    );
    pdf = readFileSync(file);
  } finally {
    rmSync(folder, { recursive: true });
  }
  await page.route(`**/api/documents/${id}/file?viewer=true`, (route) =>
    route.fulfill({ body: pdf, contentType: "application/octet-stream" }),
  );
  await page.route(`**/api/documents/${id}`, (route) =>
    route.fulfill({
      json: {
        id,
        filename: "synthetic.pdf",
        page_count: 3,
        state: "partial",
        metadata_revision: 2,
        metadata: {
          values: { company_name: "Synthetic smoke", reporting_year: null },
        },
        latest_result: { attempt_id: "saved-attempt", metadata_revision: 1 },
        job: { id: "different-current-attempt", operation: "extract" },
      },
    }),
  );
  await page.route(`**/api/documents/${id}/inventory?*`, (route) =>
    route.fulfill({
      json: {
        metadata_revision: 1,
        pages: [
          {
            pdf_page: 3,
            statement_type: "B09",
            classification: "notes",
            uncertainty: null,
          },
        ],
      },
    }),
  );
}
function envelope(
  items: EvidenceItem[],
  revision = 1,
  total = items.length,
  offset = 0,
) {
  return {
    document_id: id,
    attempt_id: "saved-attempt",
    metadata_revision: 1,
    snapshot_revision: revision,
    items,
    invalid_pages: [{ pdf_page: 1, issues: ["invalid_extraction_response"] }],
    offset,
    limit: 100,
    total,
  };
}

test("W06 document picker retries, paginates and opens the selected PDF", async ({
  page,
}) => {
  await mockDocument(page);
  let fail = true;
  await page.route("**/api/documents?*", (route) => {
    if (fail)
      return route.fulfill({
        status: 503,
        json: { error: { message: "Synthetic list unavailable" } },
      });
    const offset = Number(
      new URL(route.request().url()).searchParams.get("offset"),
    );
    const items =
      offset === 0
        ? Array.from({ length: 20 }, (_, index) => ({
            id: `synthetic-${index}`,
            filename: `synthetic-${index}.pdf`,
            state: "uploaded",
            company_name: null,
            reporting_year: null,
          }))
        : [
            {
              id,
              filename: "selected-synthetic.pdf",
              state: "completed",
              company_name: "Synthetic smoke",
              reporting_year: null,
            },
          ];
    return route.fulfill({ json: { items, total: 21, offset, limit: 20 } });
  });
  await page.route(`**/api/documents/${id}/evidence?*`, (route) =>
    route.fulfill({ json: envelope([]) }),
  );
  await page.goto("/evidence");
  const picker = page.getByRole("button", {
    name: "Chọn tài liệu",
    exact: true,
  });
  await expect(picker).toBeEnabled();
  await picker.click();
  await expect(
    page.getByRole("alert").filter({ hasText: "Synthetic list unavailable" }),
  ).toBeVisible();
  fail = false;
  await page.getByRole("button", { name: "Tải lại danh sách" }).click();
  await expect(
    page.getByRole("link", { name: /synthetic-0.pdf/ }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Danh sách tiếp" }).click();
  await page.getByRole("link", { name: /selected-synthetic.pdf/ }).click();
  await expect(page).toHaveURL(new RegExp(`/evidence/${id}(?:\\?page=1)?$`));
  await expect(
    page.locator('.react-pdf__Page[data-page-number="1"] canvas'),
  ).toBeVisible();
});

test("W06 financial cell links PDF and keeps selection across zoom and tabs with stale partial evidence", async ({
  page,
}) => {
  await mockDocument(page);
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  const cell = observation("selected", {
    sources: [
      observation("x").sources[0],
      { ...observation("x").sources[0], pdf_page: 3 },
    ],
  });
  await page.route(`**/api/documents/${id}/evidence?*`, (route) => {
    const query = new URL(route.request().url()).searchParams;
    expect(query.get("attempt_id")).toBe("saved-attempt");
    return route.fulfill({
      json: envelope(
        query.get("statement") === "B02"
          ? [
              cell,
              observation("no-source", {
                raw_label: "Không nguồn",
                sources: [],
              }),
            ]
          : [],
      ),
    });
  });
  await page.goto(`/evidence/${id}`);
  await page.getByRole("tab", { name: "B02", exact: false }).click();
  const selected = page.getByRole("button", {
    name: "Chỉ tiêu synthetic,",
    exact: false,
  });
  await selected.click();
  await expect(page).toHaveURL(/page=2$/);
  await expect(
    page.locator('.react-pdf__Page[data-page-number="2"] canvas'),
  ).toBeVisible();
  await expect(
    page.getByRole("status").filter({ hasText: "Metadata phiên cũ" }).first(),
  ).toBeVisible();
  await expect(
    page.getByRole("status").filter({ hasText: "trang chưa hợp lệ" }),
  ).toBeVisible();
  const details = page.getByLabel("Chi tiết nguồn");
  await expect(details).toContainText("missing_canonical_mapping");
  await expect(details).toContainText("Chưa xác minh");
  await page.getByRole("button", { name: "Nguồn 2 · PDF trang 3" }).click();
  await expect(page).toHaveURL(/page=3$/);
  await expect(
    page.locator('.react-pdf__Page[data-page-number="3"] canvas'),
  ).toBeVisible();
  await page.getByRole("button", { name: "Phóng to", exact: true }).click();
  await expect(selected).toHaveAttribute("aria-pressed", "true");
  await page.getByRole("tab", { name: "B09", exact: false }).click();
  await expect(page.getByRole("table")).toHaveCount(0);
  await expect(
    page
      .getByText("Chưa trích xuất nội dung thuyết minh.", { exact: false })
      .first(),
  ).toBeVisible();
  await page.getByRole("tab", { name: "B02", exact: false }).click();
  await expect(selected).toHaveAttribute("aria-pressed", "true");
  await page
    .getByRole("button", { name: "Không nguồn,", exact: false })
    .click();
  await expect(details).toContainText("Chưa có liên kết trang nguồn");
  await expect(page).toHaveURL(/page=3$/);
  expect(errors).toEqual([]);
});

test("W06 pagination restarts a changed snapshot and retries errors manually", async ({
  page,
}) => {
  await mockDocument(page);
  let revision = 1;
  let fail = false;
  const calls: number[] = [];
  await page.route(`**/api/documents/${id}/evidence?*`, (route) => {
    const offset = Number(
      new URL(route.request().url()).searchParams.get("offset"),
    );
    calls.push(offset);
    if (fail)
      return route.fulfill({
        status: 503,
        json: { error: { message: "Synthetic API failure" } },
      });
    if (offset > 0) revision = 2;
    const items = Array.from({ length: offset === 0 ? 100 : 1 }, (_, i) =>
      observation(`r${revision}-${offset + i}`, {
        raw_label: `Snapshot ${revision} observation ${offset + i}`,
        binding: null,
      }),
    );
    return route.fulfill({ json: envelope(items, revision, 101, offset) });
  });
  await page.goto(`/evidence/${id}`);
  await expect(
    page.getByText("100/101 observations", { exact: false }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Tải thêm số liệu" }).click();
  await expect(
    page.getByText("Snapshot 2 observation 0", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText("Snapshot 1 observation 0", { exact: true }),
  ).toHaveCount(0);
  await expect(
    page.getByText("100/101 observations", { exact: false }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Tải thêm số liệu" }).click();
  await expect(
    page.getByText("101/101 observations", { exact: false }),
  ).toBeVisible();
  expect(calls).toEqual([0, 100, 0, 100]);
  fail = true;
  await page.getByRole("button", { name: "Tải lại số liệu" }).click();
  const error = page
    .getByRole("alert")
    .filter({ hasText: "Synthetic API failure" });
  await expect(error).toBeVisible();
  await expect(page.getByLabel("Số trang PDF")).toBeVisible();
  fail = false;
  await page.getByRole("button", { name: "Tải lại số liệu" }).click();
  await expect(error).toHaveCount(0);
  await expect(
    page.getByText("100/101 observations", { exact: false }),
  ).toBeVisible();
});

test("W06 BBS persisted evidence source linking read only", async ({
  page,
  request,
}) => {
  const documentId = process.env.W06_REAL_DOCUMENT_ID;
  test.skip(!documentId, "NOT RUN: BBS storage not configured");
  const doc = await (await request.get(`/api/documents/${documentId}`)).json();
  const attempt = doc.latest_result.attempt_id;
  const evidence = await (
    await request.get(
      `/api/documents/${documentId}/evidence?attempt_id=${attempt}&limit=500`,
    )
  ).json();
  const items: EvidenceItem[] = evidence.items;
  console.log(
    "BBS persisted counts",
    JSON.stringify({
      total: evidence.total,
      numeric: items.filter((i) => i.value.normalized_value !== null).length,
      quality: items.reduce<Record<string, number>>((a, i) => {
        a[i.quality.decision] = (a[i.quality.decision] ?? 0) + 1;
        return a;
      }, {}),
    }),
  );
  await page.goto(`/evidence/${documentId}?page=1`);
  for (const [statement, pdfPage] of [
    ["B01", 5],
    ["B01", 6],
    ["B02", 7],
    ["B03", 8],
  ] as const) {
    await page.getByRole("tab", { name: statement, exact: false }).click();
    const item = items.find(
      (i) =>
        i.context.statement_type === statement &&
        i.sources.some((s) => s.pdf_page === pdfPage),
    )!;
    expect(item).toBeTruthy();
    const table = page.getByRole("table");
    await expect(table).toBeVisible();
    const cell = page
      .getByRole("button")
      .filter({ has: page.locator(".raw-value") });
    const byItem = () =>
      page.locator(`.cell-select[data-evidence-id="${item.evidence_id}"]`);
    // Pagination is explicit; load the remaining items if the source is on a later slice.
    if (await page.getByRole("button", { name: "Tải thêm số liệu" }).count())
      await page.getByRole("button", { name: "Tải thêm số liệu" }).click();
    await byItem().click();
    await expect(page).toHaveURL(new RegExp(`page=${pdfPage}$`));
    await expect(
      page.locator(`.react-pdf__Page[data-page-number="${pdfPage}"] canvas`),
    ).toBeVisible();
    await expect(page.getByLabel("Chi tiết nguồn")).toContainText(
      item.raw_label,
    );
    await expect(cell.first()).toBeVisible();
    if (statement === "B02") {
      const expected = groupEvidence(
        items.filter((i) => i.context.statement_type === "B02"),
      );
      expect(expected.periods.length).toBeGreaterThan(1);
      await expect(table.locator("thead th")).toHaveCount(
        expected.periods.length + 2,
      );
    }
  }
  for (const predicate of [
    (i: EvidenceItem) => i.value.normalized_value === "0",
    (i: EvidenceItem) =>
      i.value.normalized_value === null && !!i.value.raw_value,
    (i: EvidenceItem) => i.value.raw_value === null || i.value.raw_value === "",
    (i: EvidenceItem) => i.canonical_item_id === null,
  ]) {
    const item = items.find(predicate);
    if (!item) {
      console.log("BBS value case absent in persisted evidence");
      continue;
    }
    await page
      .getByRole("tab", { name: item.context.statement_type!, exact: false })
      .click();
    const button = page.locator(
      `.cell-select[data-evidence-id="${item.evidence_id}"]`,
    );
    await expect(page.getByRole("table")).toBeVisible();
    if (await page.getByRole("button", { name: "Tải thêm số liệu" }).count())
      await page.getByRole("button", { name: "Tải thêm số liệu" }).click();
    await expect(button.locator(".raw-value")).toHaveText(
      item.value.raw_value === null || item.value.raw_value === ""
        ? "Thiếu"
        : item.value.raw_value,
    );
    await button.click();
    await expect(page.getByLabel("Chi tiết nguồn")).toContainText(
      item.value.normalized_value ?? "Chưa xác định",
    );
  }
  await page.getByRole("tab", { name: "B09", exact: false }).click();
  await expect(page.getByRole("table")).toHaveCount(0);
  await page.getByRole("button", { name: "Trang 9", exact: true }).click();
  await expect(
    page.locator('.react-pdf__Page[data-page-number="9"] canvas'),
  ).toBeVisible();
  await page.screenshot({ path: "test-results/w06-bbs.png" });
});
