"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import {
  ChartNoAxesCombined,
  Files,
  FolderOpen,
  LayoutDashboard,
  PanelLeftClose,
  PanelLeftOpen,
  ScanSearch,
  Sparkles,
} from "lucide-react";

const navigation = [
  { href: "/", label: "Tổng quan", icon: LayoutDashboard },
  { href: "/documents", label: "Tài liệu", icon: Files },
  { href: "/evidence", label: "Khám phá dữ liệu", icon: ScanSearch },
  { href: "/ai-workspace", label: "Trợ lý AI tài chính", icon: Sparkles },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [collapsed, setCollapsed] = useState(false);
  const isActive = (href: string) =>
    pathname === href || (href !== "/" && pathname.startsWith(`${href}/`));
  const current = navigation.find((item) => isActive(item.href));
  return (
    <div className={`app-shell ${collapsed ? "is-collapsed" : ""}`}>
      <a className="skip-link" href="#main-content">
        Đến nội dung chính
      </a>
      <aside className="sidebar">
        <div className="brand-row">
          <Link
            href="/"
            className="brand"
            aria-label="Financial AI — Tổng quan"
          >
            <span className="brand-icon">
              <ChartNoAxesCombined size={21} />
            </span>
            <span className="sidebar-label">Financial AI</span>
          </Link>
          <button
            className="icon-button collapse-button"
            onClick={() => setCollapsed(!collapsed)}
            aria-label={
              collapsed
                ? "Mở rộng thanh điều hướng"
                : "Thu gọn thanh điều hướng"
            }
            aria-expanded={!collapsed}
          >
            {collapsed ? (
              <PanelLeftOpen size={18} />
            ) : (
              <PanelLeftClose size={18} />
            )}
          </button>
        </div>
        <p className="nav-caption sidebar-label">Không gian làm việc</p>
        <nav aria-label="Điều hướng chính">
          {navigation.map(({ href, label, icon: Icon }) => (
            <Link
              key={href}
              href={href}
              className={`nav-link ${isActive(href) ? "active" : ""}`}
              aria-current={isActive(href) ? "page" : undefined}
              title={label}
            >
              <Icon size={19} />
              <span className="sidebar-label">{label}</span>
            </Link>
          ))}
        </nav>
        <div className="sidebar-footer">
          <span className="local-dot" />
          <span className="sidebar-label">Phiên bản local · Web Demo V1</span>
        </div>
      </aside>
      <div className="workspace">
        <header className="topbar">
          <div className="header-context">
            <FolderOpen size={19} />
            <span>Không gian phân tích</span>
            <span className="header-divider">/</span>
            <span className="muted">{current?.label}</span>
          </div>
          <span className="local-label">Bản xem trước V1</span>
        </header>
        <main id="main-content" tabIndex={-1}>
          {children}
        </main>
        <footer className="workspace-footer">
          Financial AI Workspace{" "}
          <span>Khám phá dữ liệu · Truy nguyên nguồn dẫn</span>
        </footer>
      </div>
    </div>
  );
}
