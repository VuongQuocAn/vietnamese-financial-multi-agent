import { expect, test } from "@playwright/test";
import { renderToStaticMarkup } from "react-dom/server";
import { FinancialTable } from "../components/evidence/financial-table";

test("dashboard, navigation and truthful empty states", async ({ page }) => {
  // Empty-state presentation remains deterministic when upload tests run alongside.
  await page.route("**/api/documents?*", (route) =>
    route.fulfill({ json: { items: [], total: 0, offset: 0, limit: 20 } }),
  );
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  const failed: string[] = [];
  page.on("response", (response) => {
    if (response.status() >= 400) failed.push(response.url());
  });
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Chào mừng quay trở lại" }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Chọn tệp PDF" }),
  ).toBeEnabled();
  await expect(
    page.getByText("Chưa có tài liệu nào.", { exact: true }),
  ).toBeVisible();
  expect(
    await page
      .locator("body")
      .evaluate((element) => getComputedStyle(element).fontFamily),
  ).toContain("Be Vietnam Pro");
  expect(
    await page.evaluate(() => document.fonts.check('14px "Be Vietnam Pro"')),
  ).toBe(true);
  await page.screenshot({
    path: "test-results/dashboard-1440.png",
    fullPage: true,
  });
  await page.getByRole("button", { name: "Thu gọn thanh điều hướng" }).click();
  await expect(
    page.getByRole("button", { name: "Mở rộng thanh điều hướng" }),
  ).toHaveAttribute("aria-expanded", "false");
  await page.getByRole("button", { name: "Mở rộng thanh điều hướng" }).click();
  await page
    .getByRole("navigation")
    .getByRole("link", { name: "Tài liệu", exact: true })
    .click();
  await expect(page).toHaveURL(/\/documents$/);
  await expect(
    page.getByRole("link", { name: "Tài liệu", exact: true }),
  ).toHaveAttribute("aria-current", "page");
  await expect(
    page.getByRole("button", { name: "Chọn tệp PDF" }),
  ).toBeEnabled();
  await expect(
    page.getByText("Chưa có tài liệu nào.", { exact: true }),
  ).toBeVisible();
  await page
    .getByRole("navigation")
    .getByRole("link", { name: "Khám phá dữ liệu" })
    .click();
  await expect(
    page.getByText("Chọn một tài liệu đã xử lý để khám phá dữ liệu tài chính."),
  ).toBeVisible();
  await page.screenshot({
    path: "test-results/evidence-1440.png",
    fullPage: true,
  });
  const range = page.getByRole("slider", { name: "Độ rộng khung PDF" });
  await range.focus();
  await page.keyboard.press("ArrowRight");
  await expect(range).toHaveValue("46");
  await page.getByRole("tab", { name: /B01/ }).focus();
  await page.keyboard.press("ArrowRight");
  await expect(page.getByRole("tab", { name: /B02/ })).toHaveAttribute(
    "aria-selected",
    "true",
  );
  await page.getByRole("tab", { name: /B09/ }).click();
  await expect(
    page.getByText("Chưa có danh mục trang thuyết minh"),
  ).toBeVisible();
  await page.getByRole("tab", { name: /Evidence Graph/ }).click();
  await expect(page.getByRole("tabpanel")).toContainText("Sắp ra mắt");
  await page
    .getByRole("navigation")
    .getByRole("link", { name: "Trợ lý AI tài chính" })
    .click();
  await expect(
    page.getByRole("heading", { name: "Trợ lý AI tài chính", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText("Hỏi đáp báo cáo tài chính", { exact: true }),
  ).toBeVisible();
  await expect(page.getByRole("textbox")).toHaveCount(0);
  expect(errors).toEqual([]);
  expect(failed).toEqual([]);
});

for (const width of [1280, 390]) {
  test(`responsive routes at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    for (const route of ["/", "/documents", "/evidence", "/ai-workspace"]) {
      const response = await page.goto(route);
      expect(response?.status()).toBe(200);
      await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth,
        ),
      ).toBe(true);
      if (route === "/" || route === "/evidence")
        await page.screenshot({
          path: `test-results/${route === "/" ? "dashboard" : "evidence"}-${width}.png`,
          fullPage: true,
        });
    }
    if (width === 390) {
      await page.goto("/evidence");
      await expect(
        page.getByRole("heading", { name: "Tài liệu PDF gốc" }),
      ).not.toBeVisible();
      await page.getByRole("button", { name: "PDF gốc", exact: true }).click();
      await expect(
        page.getByRole("heading", { name: "Tài liệu PDF gốc" }),
      ).toBeVisible();
    }
  });
}

test("Next.js proxy reaches the real FastAPI health endpoint", async ({
  request,
}) => {
  const response = await request.get("/api/health");
  expect(response.status()).toBe(200);
  expect(await response.json()).toEqual({
    status: "ok",
    service: "financial-ai-api",
  });
});

test("synthetic table preserves raw values, dynamic periods and quality labels", async () => {
  // Synthetic presentation fixture, never shipped to any application route.
  const html = renderToStaticMarkup(
    <FinancialTable
      periods={[
        { key: "p1", label: "Kỳ tổng hợp A" },
        { key: "p2", label: "Kỳ tổng hợp B" },
        { key: "p3", label: "Kỳ tổng hợp C" },
      ]}
      rows={[
        {
          key: "synthetic-row",
          sourceItemCode: "01",
          rawLabel: "Chỉ tiêu tổng hợp thử nghiệm",
          statuses: ["Chưa ánh xạ"],
          cells: {
            p1: { id: "synthetic-zero", rawValue: "0" },
            p2: {
              id: "synthetic-dash",
              rawValue: "—",
              statuses: ["Không có số", "Cần xem xét"],
            },
            p3: {
              id: "synthetic-missing",
              rawValue: null,
              statuses: ["Thiếu"],
            },
          },
        },
      ]}
    />,
  );
  expect(html).toContain("Kỳ tổng hợp C");
  expect(html).toContain(">01</td>");
  expect(html).toContain('class="raw-value">0</span>');
  expect(html).toContain('class="raw-value">—</span>');
  expect(html).toContain("Chưa ánh xạ");
  expect(html).toContain("Cần xem xét");
  expect(html).toContain("Thiếu");
});
