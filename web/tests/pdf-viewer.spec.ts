import { expect, test } from "@playwright/test";
import { execFileSync } from "node:child_process";
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

test("PDF scan viewer renders, synchronizes URL and navigates partial inventory", async ({
  page,
  request,
}) => {
  const folder = mkdtempSync(join(tmpdir(), "w05-scan-"));
  let bytes: Buffer;
  try {
    const file = join(folder, "scan.pdf");
    execFileSync(
      process.env.PYTHON ??
        (process.platform === "win32"
          ? "../.venv/Scripts/python.exe"
          : "python"),
      [
        "-c",
        "import sys; from PIL import Image,ImageDraw; pages=[Image.new('RGB',(480,640),'white') for _ in range(3)]; [(ImageDraw.Draw(im).text((30,40),f'SYNTHETIC SCAN PAGE {i+1}',fill='black')) for i,im in enumerate(pages)]; pages[0].save(sys.argv[1],format='PDF',save_all=True,append_images=pages[1:])",
        file,
      ],
    );
    bytes = readFileSync(file);
  } finally {
    rmSync(folder, { recursive: true });
  }
  const upload = await request.post("/api/documents", {
    multipart: {
      file: {
        name: "synthetic-viewer.pdf",
        mimeType: "application/pdf",
        buffer: bytes,
      },
    },
  });
  expect(upload.status()).toBe(201);
  const doc = await upload.json();
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  const range = await request.get(`/api/documents/${doc.id}/file`, {
    headers: { Range: "bytes=0-31" },
  });
  expect(range.status()).toBe(206);
  expect(range.headers()["content-type"]).toContain("application/pdf");
  expect(range.headers()["content-range"]).toMatch(/^bytes 0-31\//);
  expect((await range.body()).length).toBe(32);
  await page.goto(`/evidence/${doc.id}?page=2`);
  const canvas = page.locator('.react-pdf__Page[data-page-number="2"] canvas');
  await expect(canvas).toBeVisible();
  await expect(
    page.getByText("Chưa có danh mục trích xuất.", { exact: false }),
  ).toBeVisible();
  const before = await canvas.evaluate((c: HTMLCanvasElement) => c.toDataURL());
  await page.getByRole("button", { name: "Trang sau", exact: true }).click();
  await expect(page).toHaveURL(/page=3$/);
  await expect(
    page.locator('.react-pdf__Page[data-page-number="3"] canvas'),
  ).toBeVisible();
  expect(
    await page
      .locator("canvas")
      .evaluate((c: HTMLCanvasElement) => c.toDataURL()),
  ).not.toBe(before);
  const input = page.getByLabel("Số trang PDF");
  await input.fill("999");
  await input.press("Enter");
  await expect(input).toHaveValue("3");
  await page.getByRole("button", { name: "Phóng to", exact: true }).click();
  await expect(page.getByLabel("Mức phóng to")).toHaveText("125%");
  await page.getByRole("button", { name: "Vừa chiều rộng" }).click();
  await expect(page.getByLabel("Mức phóng to")).toHaveText("100%");
  await page.getByRole("button", { name: "Mở rộng", exact: true }).click();
  await expect(page.locator(".pdf-expanded")).toBeVisible();
  await page.getByLabel("Trình xem PDF", { exact: true }).press("Home");
  await expect(page).toHaveURL(/page=1$/);
  await page.getByLabel("Trình xem PDF", { exact: true }).press("Escape");
  await expect(page.locator(".pdf-expanded")).toHaveCount(0);
  // Read-only browser fixtures exercise partial/uncertain inventory; no AI calls.
  await page.route(`**/api/documents/${doc.id}`, (route) =>
    route.fulfill({
      json: {
        ...doc,
        state: "partial",
        job: { id: "fixture-attempt", operation: "extract" },
      },
    }),
  );
  await page.route(`**/api/documents/${doc.id}/inventory?*`, (route) =>
    route.fulfill({
      json: {
        pages: [
          {
            pdf_page: 2,
            statement_type: "B02",
            classification: "financial_statement",
            uncertainty: null,
          },
          {
            pdf_page: 3,
            statement_type: null,
            classification: "uncertain",
            uncertainty: "ambiguous",
          },
        ],
      },
    }),
  );
  await page.reload();
  await page.getByRole("button", { name: "Trang 2", exact: true }).click();
  await expect(page).toHaveURL(/page=2$/);
  await expect(
    page.locator('.react-pdf__Page[data-page-number="2"] canvas'),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Trang 3", exact: true }),
  ).toBeVisible();
  await page.route(`**/api/documents/${doc.id}/file`, (route) =>
    route.fulfill({ status: 404 }),
  );
  await page.reload();
  await expect(
    page.getByRole("alert").filter({ hasText: "Không tải được PDF" }),
  ).toBeVisible();
  await expect(page.getByRole("link", { name: "Mở PDF gốc" })).toHaveAttribute(
    "href",
    `/api/documents/${doc.id}/file`,
  );
  expect(errors).toEqual([]);
});

test("BBS stored PDF source pages and inventory (read only)", async ({
  page,
}) => {
  test.skip(
    !process.env.W05_REAL_DOCUMENT_ID,
    "NOT RUN: BBS storage not configured",
  );
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto(`/evidence/${process.env.W05_REAL_DOCUMENT_ID}?page=7`);
  await expect(
    page.locator('.react-pdf__Page[data-page-number="7"] canvas'),
  ).toBeVisible();
  await expect(page.getByLabel("Số trang PDF")).toHaveValue("7");
  for (const number of [
    5,
    6,
    7,
    8,
    ...Array.from({ length: 16 }, (_, i) => i + 9),
  ]) {
    await page
      .getByRole("button", { name: `Trang ${number}`, exact: true })
      .click();
    await expect(page).toHaveURL(new RegExp(`page=${number}$`));
    const canvas = page.locator(
      `.react-pdf__Page[data-page-number="${number}"] canvas`,
    );
    await expect(canvas).toBeVisible();
    const data = await canvas.evaluate((c: HTMLCanvasElement) => c.toDataURL());
    writeFileSync(
      `test-results/w05-bbs-page-${number}.png`,
      Buffer.from(data.split(",")[1], "base64"),
    );
  }
  await page.getByRole("button", { name: "Phóng to", exact: true }).click();
  await expect(page.getByLabel("Mức phóng to")).toHaveText("125%");
  await page.screenshot({ path: "test-results/w05-bbs-zoom.png" });
  expect(errors).toEqual([]);
});
