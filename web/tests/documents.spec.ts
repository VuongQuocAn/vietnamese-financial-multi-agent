import { expect, test } from "@playwright/test";
import { execFileSync } from "node:child_process";
import { mkdtempSync, readFileSync, unlinkSync, rmdirSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import type { Suggestion } from "../lib/documents";

let folder: string;
let pdf: string;
test.beforeAll(() => {
  folder = mkdtempSync(join(tmpdir(), "w03-browser-"));
  pdf = join(folder, "synthetic-scan.pdf");
  const python =
    process.env.PYTHON ??
    (process.platform === "win32" ? "../.venv/Scripts/python.exe" : "python");
  execFileSync(python, [
    "-c",
    "import sys; from PIL import Image, ImageDraw; im=Image.new('RGB',(480,640),'white'); ImageDraw.Draw(im).text((20,30),'SYNTHETIC METADATA TEST ONLY',fill='black'); im.save(sys.argv[1],format='PDF'); im.close()",
    pdf,
  ]);
});
test.afterAll(() => {
  unlinkSync(pdf);
  rmdirSync(folder);
});

test("same-origin proxy accepts a valid PDF above its old 10 MiB limit", async ({
  request,
}) => {
  const original = readFileSync(pdf);
  const trailer = original.subarray(
    original.lastIndexOf(Buffer.from("startxref")),
  );
  const largePdf = Buffer.concat([
    original,
    Buffer.alloc(11 * 1024 * 1024, 32),
    trailer,
  ]);
  const response = await request.post("/api/documents", {
    multipart: {
      file: {
        name: "synthetic-proxy-limit.pdf",
        mimeType: "application/pdf",
        buffer: largePdf,
      },
    },
  });
  expect(response.status()).toBe(201);
  expect((await response.json()).size_bytes).toBe(largePdf.length);
});

for (const width of [1440, 390]) {
  test(`real upload, manual confirmation and document list at ${width}px`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 950 });
    const filename = `synthetic-review-${width}-${Date.now()}.pdf`;
    await page.goto(width === 390 ? "/documents" : "/");
    await page.getByLabel("Tệp PDF").setInputFiles({
      name: filename,
      mimeType: "application/pdf",
      buffer: readFileSync(pdf),
    });
    await expect(page.getByText(new RegExp(filename))).toBeVisible();
    await page.getByRole("button", { name: "Tải lên và nhận diện" }).click();
    await expect(page).toHaveURL(/\/documents\/[0-9a-f-]{36}$/);
    await expect(
      page.getByRole("heading", { name: "Thông tin tài liệu", level: 1 }),
    ).toBeVisible();
    await expect(
      page
        .getByRole("navigation")
        .getByRole("link", { name: "Tài liệu", exact: true }),
    ).toHaveAttribute("aria-current", "page");
    await expect(
      page.getByRole("status").filter({ hasText: "Nhận diện thất bại" }),
    ).toBeVisible();
    await expect(
      page.getByText("Hệ thống chưa sẵn sàng nhận diện.", { exact: false }),
    ).toBeVisible();
    await page.getByRole("button", { name: "Chỉnh sửa thông tin" }).click();
    await page
      .getByLabel("Tên công ty", { exact: true })
      .fill("Synthetic Browser Company");
    await page.getByLabel("Năm báo cáo", { exact: true }).fill("2025");
    await page
      .getByRole("button", { name: "Lưu thông tin", exact: true })
      .click();
    await expect(
      page.getByRole("status").filter({ hasText: "Sẵn sàng" }),
    ).toBeVisible();
    await expect(
      page.getByText("Thông tin do người dùng cập nhật", { exact: false }),
    ).toBeVisible();
    await expect(
      page.getByText("chưa có kết quả trích xuất.", { exact: false }),
    ).toBeVisible();
    await expect(
      page.getByRole("link", { name: "Mở PDF gốc" }),
    ).toHaveAttribute("href", /\/api\/documents\/.+\/file$/);
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.screenshot({
      path: `test-results/metadata-review-${width}.png`,
      fullPage: true,
    });
    await page.getByRole("link", { name: "← Danh sách tài liệu" }).click();
    await expect(
      page.getByRole("link", { name: new RegExp(filename) }),
    ).toBeVisible();
  });
}

test("drag/drop upload and client/server validation errors", async ({
  page,
}) => {
  await page.goto("/documents");
  await page.getByLabel("Tệp PDF").setInputFiles({
    name: "wrong.txt",
    mimeType: "text/plain",
    buffer: Buffer.from("wrong"),
  });
  await expect(
    page.getByRole("alert").filter({ hasText: "đúng một tệp PDF" }),
  ).toBeVisible();
  await page.getByLabel("Tệp PDF").setInputFiles({
    name: "broken.pdf",
    mimeType: "application/pdf",
    buffer: Buffer.from("%PDF-broken"),
  });
  await page.getByRole("button", { name: "Tải lên và nhận diện" }).click();
  await expect(
    page.getByRole("alert").filter({ hasText: "PDF hỏng" }),
  ).toBeVisible();
  const transfer = await page.evaluateHandle(
    (bytes) => {
      const data = new DataTransfer();
      data.items.add(
        new File([new Uint8Array(bytes)], "synthetic-drag-drop.pdf", {
          type: "application/pdf",
        }),
      );
      return data;
    },
    Array.from(readFileSync(pdf)),
  );
  await page
    .locator(".upload-zone")
    .dispatchEvent("drop", { dataTransfer: transfer });
  await page.getByRole("button", { name: "Tải lên và nhận diện" }).click();
  await expect(page).toHaveURL(/\/documents\/[0-9a-f-]{36}$/);
  await expect(
    page.getByRole("status").filter({ hasText: "Nhận diện thất bại" }),
  ).toBeVisible();
  const request = page.waitForResponse(
    (r) => r.url().endsWith("/process") && r.request().method() === "POST",
  );
  await page.getByRole("button", { name: "Thử nhận diện lại" }).click();
  expect((await request).status()).toBe(202);
  await expect(
    page.getByRole("status").filter({ hasText: "Nhận diện thất bại" }),
  ).toBeVisible();
});

test("AI candidates, page sources, polling and revision conflict (synthetic responses)", async ({
  page,
}) => {
  const id = "11111111-1111-4111-8111-111111111111";
  const unresolved = { status: "unresolved", candidates: [], issues: [] };
  const suggestions = {
    company_name: {
      status: "resolved",
      candidates: [
        {
          value: "Synthetic AI Company",
          raw_text: "SYNTHETIC PAGE TEXT",
          sources: [{ pdf_page: 2, content_id: "sha256:synthetic" }],
        },
      ],
      issues: [],
    },
    reporting_year: {
      status: "uncertain",
      candidates: [2024, 2025].map((year) => ({
        value: year,
        raw_text: `Year ${year}`,
        sources: [{ pdf_page: 2, content_id: "sha256:synthetic" }],
      })),
      issues: ["conflicting_candidates"],
    },
    stock_ticker: unresolved,
    reporting_period: unresolved,
    reporting_scope: unresolved,
  };
  let loads = 0;
  await page.route(`**/api/documents/${id}`, (route) => {
    loads += 1;
    return route.fulfill({
      json: {
        id,
        filename: "Synthetic UI fixture.pdf",
        page_count: 6,
        size_bytes: 1024,
        state: loads === 1 ? "processing" : "needs_metadata",
        metadata_revision: 0,
        metadata: {
          values: {
            company_name: null,
            stock_ticker: null,
            reporting_year: null,
            reporting_period: null,
            reporting_scope: null,
          },
          confirmed: false,
          edits: [],
          suggestions,
          preflight:
            loads === 1
              ? null
              : {
                  analyzed_pages: [1, 2, 3, 4, 5, 6],
                  stop_reason: "pages_exhausted",
                  issues: [],
                },
        },
        job: {
          id,
          state: loads === 1 ? "processing" : "needs_metadata",
          revision: loads,
          progress: { preflight: { completed_pages: 4, total_pages: 6 } },
        },
      },
    });
  });
  await page.route(`**/api/documents/${id}/metadata`, (route) =>
    route.fulfill({
      status: 409,
      json: { error: { message: "Thông tin đã thay đổi. Hãy tải lại." } },
    }),
  );
  await page.goto(`/documents/${id}`);
  await expect(
    page.getByText("Đã phân tích 4/6 trang.", { exact: false }),
  ).toBeVisible();
  await expect(
    page.getByRole("status").filter({ hasText: "Cần bổ sung thông tin" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Chỉnh sửa thông tin" }).click();
  await expect(page.getByLabel("Tên công ty", { exact: true })).toHaveValue(
    "Synthetic AI Company",
  );
  await expect(page.getByLabel("Năm báo cáo", { exact: true })).toHaveValue("");
  await expect(page.getByText("Cần xem xét", { exact: true })).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Trang 2", exact: true }).first(),
  ).toHaveAttribute("href", `/api/documents/${id}/file#page=2`);
  await expect(page.getByText("Year 2024", { exact: true })).toBeVisible();
  await expect(page.getByText("Year 2025", { exact: true })).toBeVisible();
  await page.getByLabel("Năm báo cáo", { exact: true }).fill("2025");
  await page
    .getByRole("button", { name: "Lưu thông tin", exact: true })
    .click();
  await expect(
    page.getByRole("alert").filter({ hasText: "Thông tin đã thay đổi" }),
  ).toBeVisible();
});

test("document list shows connection error without claiming an empty library", async ({
  page,
}) => {
  await page.route("**/api/documents?*", (route) =>
    route.fulfill({
      status: 503,
      json: { error: { message: "Backend không khả dụng" } },
    }),
  );
  await page.goto("/documents");
  await expect(
    page.getByRole("alert").filter({ hasText: "Backend không khả dụng" }),
  ).toBeVisible();
  await expect(
    page.getByText("Chưa có tài liệu nào.", { exact: true }),
  ).toHaveCount(0);
});

for (const width of [1440, 1366]) {
  test(`auto-accepted metadata is ready without a mandatory form at ${width}px`, async ({
    page,
  }) => {
    const id = "22222222-2222-4222-8222-222222222222";
    const fields = [
      "company_name",
      "stock_ticker",
      "reporting_year",
      "reporting_period",
      "reporting_scope",
    ];
    const suggestions: Record<string, Suggestion> = Object.fromEntries(
      fields.map((field) => [
        field,
        { status: "unresolved", candidates: [], issues: [] },
      ]),
    );
    for (const [field, value] of [
      ["company_name", "Synthetic Auto Company"],
      ["reporting_year", 2025],
    ] as const) {
      suggestions[field] = {
        status: "resolved",
        candidates: [
          {
            value,
            raw_text: String(value),
            sources: [{ pdf_page: 2, content_id: "sha256:synthetic" }],
          },
        ],
        issues: [],
      };
    }
    await page.route(`**/api/documents/${id}`, (route) =>
      route.fulfill({
        json: {
          id,
          filename: "synthetic-auto.pdf",
          page_count: 2,
          size_bytes: 1234,
          state: "ready",
          metadata_revision: 1,
          metadata: {
            values: {
              company_name: "Synthetic Auto Company",
              reporting_year: 2025,
              stock_ticker: null,
              reporting_period: null,
              reporting_scope: null,
            },
            suggestions,
            accepted: true,
            confirmed: false,
            acceptance_origin: "auto",
            edits: [],
            preflight: {
              analyzed_pages: [1, 2],
              stop_reason: "sufficient_evidence",
              issues: [],
            },
          },
          job: null,
        },
      }),
    );
    await page.setViewportSize({ width, height: 950 });
    await page.goto(`/documents/${id}`);
    await expect(
      page.getByRole("status").filter({ hasText: "Sẵn sàng" }),
    ).toBeVisible();
    await expect(
      page.getByRole("heading", { name: "Hệ thống đề xuất" }),
    ).toBeVisible();
    await expect(
      page.getByText("Hệ thống tự chấp nhận theo nguồn PDF", { exact: false }),
    ).toBeVisible();
    await expect(page.getByRole("textbox")).toHaveCount(0);
    await expect(page.getByText(/Gemini|gemini-/)).toHaveCount(0);
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    if (width === 1440)
      await page.screenshot({
        path: "test-results/auto-first-1440.png",
        fullPage: true,
      });
    await page.getByRole("button", { name: "Chỉnh sửa thông tin" }).click();
    await expect(page.getByLabel("Tên công ty", { exact: true })).toHaveValue(
      "Synthetic Auto Company",
    );
  });
}
