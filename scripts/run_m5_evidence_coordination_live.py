"""Two new bounded real-JSON probes; no benchmark, Gold, OCR or PDF input."""

import argparse
from pathlib import Path

from run_m5_coordinator_live import check_sources, prepare
from run_vfb_qwen_e2e import run

CASES = [
    dict(
        id="M5C2-JOIN-03",
        group="multi_hop",
        difficulty="probe",
        document_alias="BBS_2025",
        question="BBS trong hai năm 2024 và 2025 của báo cáo 2025: chọn năm có lưu chuyển tiền thuần từ hoạt động kinh doanh nhỏ hơn theo giá trị có dấu. Dùng năm vừa chọn để truy xuất doanh thu thuần cùng năm, rồi tính dòng tiền kinh doanh chia doanh thu thuần của năm đó theo phần trăm. Không suy nguyên nhân.",
    ),
    dict(
        id="M5C2-SEL-01",
        group="multi_hop",
        difficulty="probe",
        document_alias="BBS_2025",
        question="Trong hai năm 2024 và 2025 trình bày ở báo cáo BBS 2025, năm nào có doanh thu thuần cao hơn? Dùng kết quả chọn năm đó để truy xuất lưu chuyển tiền thuần từ hoạt động kinh doanh cùng năm, rồi tính dòng tiền kinh doanh chia doanh thu thuần của năm đã chọn theo phần trăm. Không suy nguyên nhân.",
    ),
    dict(
        id="M5C2-SEL-02",
        group="multi_hop",
        difficulty="probe",
        document_alias="ADC_2021",
        question="Trong hai năm 2020 và 2021 trình bày ở báo cáo ADC 2021, chọn năm có lưu chuyển tiền thuần từ hoạt động kinh doanh lớn hơn theo giá trị có dấu. Sau khi chọn mới tra lợi nhuận sau thuế của cùng năm và tính dòng tiền kinh doanh trừ lợi nhuận sau thuế. Không suy nguyên nhân.",
    ),
]

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["prepare", "run"])
    parser.add_argument(
        "--output", type=Path, default=Path("artifacts/evidence/M5-COORD-02/live-v1")
    )
    parser.add_argument("--ids", nargs="+", choices=[c["id"] for c in CASES])
    parser.add_argument("--call-cap", type=int, choices=range(1, 25), default=18)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    output = (root / args.output).resolve()
    if not output.is_relative_to(root / "artifacts/evidence/M5-COORD-02"):
        parser.error("output outside M5-COORD-02")
    if args.mode == "prepare":
        prepare(root, output, args.ids, args.call_cap, cases=CASES)
    else:
        try:
            run(root, output, args.ids)
        finally:
            check_sources(root, output)
