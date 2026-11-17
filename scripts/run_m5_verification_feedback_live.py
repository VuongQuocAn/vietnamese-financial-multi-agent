"""New questions on real JSON/EF-EG, one repair/request and no transport retest."""

import argparse
from pathlib import Path

from run_m5_coordinator_live import check_sources, prepare
from run_vfb_qwen_e2e import run
from vietnamese_financial_multi_agent.core.persistence import atomic_json

CASES = [
    dict(
        id="M5C3-BBS-01",
        group="multi_hop",
        difficulty="probe",
        document_alias="BBS_2025",
        question="BBS theo báo cáo 2025: nêu doanh thu thuần và lợi nhuận sau thuế năm 2025, dùng hai kết quả này tính lợi nhuận sau thuế chia doanh thu thuần theo phần trăm. Đồng thời nêu lưu chuyển tiền thuần từ hoạt động kinh doanh năm 2024 như một kết quả độc lập. Chỉ trình bày số liệu và phép tính, không suy nguyên nhân.",
    ),
    dict(
        id="M5C3-ADC-02",
        group="multi_hop",
        difficulty="probe",
        document_alias="ADC_2021",
        question="ADC theo báo cáo 2021: so sánh doanh thu thuần năm 2021 và năm 2020, chọn năm có doanh thu nhỏ hơn rồi truy xuất lợi nhuận sau thuế cùng năm và tính lợi nhuận sau thuế chia doanh thu thuần theo phần trăm. Riêng lưu chuyển tiền thuần từ hoạt động kinh doanh năm 2021 hãy nêu độc lập. Không suy nguyên nhân.",
    ),
    dict(
        id="M5C3-BBS-03",
        group="multi_hop",
        difficulty="probe",
        document_alias="BBS_2025",
        question="Trong báo cáo BBS 2025, giữa hai năm 2024 và 2025 hãy chọn năm có lưu chuyển tiền thuần từ hoạt động kinh doanh lớn hơn theo giá trị có dấu. Nêu doanh thu thuần cùng năm đã chọn rồi tính doanh thu thuần trừ dòng tiền kinh doanh của năm ấy. Đồng thời nêu lợi nhuận sau thuế năm 2025 độc lập với bước chọn năm. Không suy nguyên nhân.",
    ),
]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["prepare", "run"])
    parser.add_argument(
        "--output", type=Path, default=Path("artifacts/evidence/M5-COORD-03/live-v1")
    )
    parser.add_argument("--ids", nargs="+", choices=[c["id"] for c in CASES])
    parser.add_argument("--call-cap", type=int, choices=range(1, 33), default=28)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    output = (root / args.output).resolve()
    if not output.is_relative_to(root / "artifacts/evidence/M5-COORD-03"):
        parser.error("output outside M5-COORD-03")
    if args.mode == "prepare":
        prepare(root, output, args.ids, args.call_cap, cases=CASES)
        import json

        receipt = json.loads((output / "implementation.json").read_bytes())
        receipt["settings"]["max_calls_per_question"] = 16
        receipt["settings"]["max_repair_rounds"] = 1
        atomic_json(output / "implementation.json", receipt)
    else:
        try:
            run(root, output, args.ids)
        finally:
            check_sources(root, output)
