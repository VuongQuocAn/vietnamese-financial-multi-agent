"use client";

import { useState, type ReactNode } from "react";
import { GripVertical, PanelLeft, PanelRight } from "lucide-react";

export function EvidenceLayout({
  pdf,
  children,
}: {
  pdf: ReactNode;
  children: ReactNode;
}) {
  const [split, setSplit] = useState(45);
  const [mobilePane, setMobilePane] = useState("evidence");
  return (
    <>
      <div className="explorer-controls">
        <div className="mobile-pane-buttons" aria-label="Chọn khung xem">
          <button
            className="button secondary"
            aria-pressed={mobilePane === "pdf"}
            onClick={() => setMobilePane("pdf")}
          >
            <PanelLeft size={16} />
            PDF gốc
          </button>
          <button
            className="button secondary"
            aria-pressed={mobilePane === "evidence"}
            onClick={() => setMobilePane("evidence")}
          >
            <PanelRight size={16} />
            Bằng chứng
          </button>
        </div>
        <label className="resize-control">
          Độ rộng PDF{" "}
          <input
            aria-label="Độ rộng khung PDF"
            type="range"
            min={30}
            max={65}
            value={split}
            onChange={(event) => setSplit(Number(event.target.value))}
          />
          <span>{split}%</span>
        </label>
      </div>
      <div
        className={`evidence-layout show-${mobilePane}`}
        style={{
          gridTemplateColumns: `minmax(0, ${split}fr) 16px minmax(0, ${100 - split}fr)`,
        }}
      >
        <div className="pdf-panel">{pdf}</div>
        <div className="splitter-decoration" aria-hidden="true">
          <GripVertical size={15} />
        </div>
        {children}
      </div>
    </>
  );
}
