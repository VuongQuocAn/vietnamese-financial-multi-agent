# Bảng tra công thức NR

## Quy ước toán hạng

- Theo đúng báo cáo, phạm vi, kỳ và cột mà câu hỏi chỉ định. Khi hỏi số so sánh trong một báo cáo, lấy cột so sánh của chính báo cáo đó.
- Mỗi dữ kiện gốc gắn với một ô hoặc fact đúng chỉ tiêu và kỳ. Kiểm bằng nhãn nguồn. Đại lượng dẫn xuất được tính từ các dữ kiện gốc: BQ(X) = (X đầu kỳ + X cuối kỳ) / 2; ΔX = X kỳ sau − X kỳ gốc. Một ô cuối kỳ chỉ chứng minh số cuối kỳ.
- DT = doanh thu thuần; LNTT/LNST = lợi nhuận trước/sau thuế; VCSH = vốn chủ sở hữu; CFO = dòng tiền thuần từ hoạt động kinh doanh. Giá vốn = giá vốn hàng bán. Vay NH/DH = vay và nợ thuê tài chính ngắn/dài hạn.
- Trong các phép tính dùng **độ lớn khoản chi**, Capex = abs(tiền chi mua sắm, xây dựng TSCĐ và tài sản dài hạn khác). Cổ tức, lãi vay, thuế và nợ gốc thực trả cũng lấy độ lớn khi dùng làm khoản chi. CFO và các dòng điều chỉnh vốn lưu động giữ dấu báo cáo.
- Quy đổi các nguồn về cùng đơn vị trước khi tính. Tỷ lệ mục tiêu dùng số thập phân; kết quả % nhân 100 đúng một lần. Giữ dấu kết quả, làm tròn theo đề ở bước cuối. Mẫu số bằng 0 thì tỷ số không xác định.

## Chọn phép tính theo điều người dùng hỏi

| Dạng hỏi | Biểu thức |
|---|---|
| Chênh lệch kỳ sau so với kỳ gốc | X₁ − X₀. Nếu hỏi theo độ lớn khoản chi/dự phòng: abs(X₁) − abs(X₀). |
| Kỳ sau bằng bao nhiêu lần kỳ gốc | X₁ / X₀. |
| Biến động bao nhiêu phần trăm | 100 × (X₁ − X₀) / X₀ với kỳ gốc dương. Nếu hỏi quy mô khoản chi, dùng độ lớn cho cả hai kỳ. Với kỳ gốc âm, cần xác định quy ước của câu hỏi. |
| Chênh bao nhiêu điểm phần trăm | 100 × (r₁ − r₀), với r₁ và r₀ ở dạng thập phân. |
| Tăng trưởng kép hằng năm | 100 × ((X cuối / X đầu)^(1/n) − 1). n = năm cuối − năm đầu; với doanh thu, cần kỳ gốc dương và tỷ số hợp lệ. |
| Dùng số cuối kỳ lệch bao nhiêu so với dùng bình quân | Tính cùng chỉ tiêu theo hai cách rồi lấy kết quả dùng cuối kỳ trừ kết quả dùng BQ. |
| Cần tăng thêm / cần giảm để đạt mục tiêu | Giải phương trình theo đại lượng cần thay đổi, giữ các đại lượng cố định theo đề. Cần tăng = mục tiêu − thực tế. Cần giảm = thực tế − mục tiêu. |
| A cao hơn B bao nhiêu tiền / nguồn còn thừa hay thiếu | A cao hơn B: A − B. Thừa/thiếu: nguồn thực có − nhu cầu. |

## Chỉ tiêu tài chính

| Chỉ tiêu | Công thức | Đầu ra |
|---|---|---|
| ROE sau thuế | 100 × LNST theo phạm vi đề hỏi / BQ(VCSH) | % |
| Vòng quay tổng tài sản | DT / BQ(tổng tài sản) | lần |
| Vòng quay hàng tồn kho | Giá vốn / BQ(tồn kho thuần) | lần |
| Số ngày thu tiền (DSO) | Số ngày × BQ(phải thu khách hàng) / doanh thu bán chịu. Nếu đề quy định: dùng 365 ngày, phải thu khách hàng ngắn hạn trước dự phòng và DT đại diện bán chịu. | ngày |
| Số ngày tồn kho | Số ngày theo đề × BQ(tồn kho thuần) / giá vốn | ngày |
| Số ngày trả tiền người bán | Số ngày theo đề × BQ(phải trả người bán) / mua chịu. Khi đề chỉ định, lấy phải trả người bán ngắn hạn và dùng giá vốn đại diện mua hàng. | ngày |
| Thanh toán bằng tiền | Tiền và tương đương tiền / nợ ngắn hạn | lần |
| Nợ phải trả trên VCSH | Tổng nợ phải trả / VCSH | lần |
| Nguồn vốn thường xuyên bao phủ tài sản dài hạn | (VCSH + nợ dài hạn) / tài sản dài hạn. Ba số dư cùng ngày. | lần |
| Bảo đảm lãi vay | (LNTT + chi phí lãi vay ghi nhận) / chi phí lãi vay ghi nhận | lần |
| Thuế suất hiệu dụng | 100 × (chi phí thuế hiện hành + chi phí thuế hoãn lại có dấu) / LNTT | % |
| Biên EBIT ước tính | 100 × (LNTT + chi phí lãi vay) / DT | % |
| Chi phí bán hàng và quản lý trên lợi nhuận gộp | 100 × (chi phí bán hàng + chi phí quản lý doanh nghiệp) / lợi nhuận gộp | % |
| CFO trên doanh thu thuần | 100 × CFO / DT | % |
| Trang trải lãi vay bằng tiền, dùng CFO trước lãi và thuế đã trả | (CFO + lãi vay thực trả + thuế TNDN thực nộp) / lãi vay thực trả | lần |
| CFO trên nợ phải trả bình quân | 100 × CFO / BQ(tổng nợ phải trả) | % |
| Cổ tức và lợi nhuận thực trả trên LNST | 100 × cổ tức và lợi nhuận thực trả cho chủ sở hữu / LNST cùng kỳ, cùng phạm vi | % |
| Capex trên tài sản bình quân | 100 × Capex / BQ(tổng tài sản) | % |
| Vốn lưu động ròng trên doanh thu | 100 × (tài sản ngắn hạn − nợ ngắn hạn) / DT | % |
| Nợ vay ròng trên VCSH | 100 × (vay NH + vay DH − tiền và tương đương tiền) / VCSH | % |
| CFO sau Capex trên doanh thu | 100 × (CFO − Capex) / DT | % |
| Tỷ trọng vay và nợ thuê ngắn hạn | 100 × vay NH / (vay NH + vay DH) | % |
| Tỷ trọng phải thu khách hàng trước dự phòng | 100 × phải thu khách hàng ngắn hạn trước dự phòng / tổng phải thu ngắn hạn trước dự phòng. Nếu tổng chỉ có số thuần, mẫu số = tổng thuần + abs(dự phòng phải thu ngắn hạn khó đòi). | % |
| Hao mòn lũy kế TSCĐ hữu hình trên nguyên giá | 100 × abs(hao mòn lũy kế) / nguyên giá cùng nhóm tài sản, cùng ngày | % |
| Hiệu suất sử dụng TSCĐ hữu hình | DT / BQ(giá trị còn lại của TSCĐ hữu hình) | lần |

## Phép tính nhiều bước

| Dạng hỏi | Bước trung gian | Kết quả cần trả |
|---|---|---|
| Biến động biên lợi nhuận gộp | r = lợi nhuận gộp / DT của từng năm. | Điểm phần trăm: 100 × Δr. Tăng tương đối khi r₀ dương: 100 × Δr / r₀. |
| Dư vay so với CFO còn lại sau Capex và cổ tức | Còn lại = CFO − Capex − cổ tức thực trả. | Khả năng trang trải (%): 100 × còn lại / dư vay theo đề. Dư vay cao hơn bao nhiêu tiền: dư vay − còn lại. |
| Đóng góp của vốn lưu động vào thay đổi CFO | Với mỗi năm, S = tổng ba dòng điều chỉnh phải thu, tồn kho và phải trả trên B03, giữ đúng dấu. | Chênh tiền: S₁ − S₀. Đóng góp (%): 100 × (S₁ − S₀) / (CFO₁ − CFO₀). |
| Tiền đầu kỳ và CFO trang trải các khoản chi | Nguồn = tiền đầu kỳ + CFO. Chi = Capex + cổ tức thực trả + nợ gốc thực trả khi đề xét ba khoản này. | Thừa/thiếu: nguồn − chi. Trang trải (%): 100 × nguồn / chi. |
| Giải phóng phải thu khi rút ngắn DSO | Vốn giải phóng = BQ(phải thu khách hàng) − doanh thu bán chịu × số ngày mục tiêu / số ngày trong năm. Dùng DT thay doanh thu bán chịu khi đề quy định. | So với Capex (%): 100 × vốn giải phóng / Capex. Nếu hỏi CFO điều chỉnh: cộng vốn giải phóng vào CFO trước khi chia. |
| Tác động riêng của biên ròng hoặc quy mô doanh thu đến LNST | m = LNST / DT của từng năm. | Giữ DT kỳ gốc: (m₁ − m₀) × DT₀. Giữ biên kỳ gốc: (DT₁ − DT₀) × m₀. |
| Doanh thu cần để trang trải chi phí bán hàng và quản lý | C = chi phí bán hàng + chi phí quản lý. m₀ = lợi nhuận gộp kỳ gốc / DT kỳ gốc. | Bù phần chi phí tăng: (C₁ − C₀) / m₀. Trang trải tổng chi phí kỳ 1: C₁ / m₀. |
| Gộp CFO sau Capex và cổ tức qua hai năm | Cộng riêng CFO, Capex và cổ tức qua cả hai năm. | Số lần: (tổng CFO − tổng Capex) / tổng cổ tức. Dư tiền: tổng CFO − tổng Capex − tổng cổ tức. |
| Thuế hiện hành ghi nhận so với tiền thuế thực nộp | Mỗi năm, G = chi phí thuế hiện hành − độ lớn tiền thuế đã nộp. | Chênh lệch thay đổi: G₁ − G₀. Tỷ lệ gộp (%): 100 × tổng tiền thuế thực nộp / tổng chi phí thuế hiện hành. |
