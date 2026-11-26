# Nối bằng chứng Multi-Hop

| Dạng hỏi | Cách nối nguồn | Final cần nêu |
|---|---|---|
| Xếp hạng rồi hỏi thuộc tính | Lọc đúng nhóm, kỳ và chỉ tiêu. Loại dòng tổng khi xếp hạng các thành phần. Tra thuộc tính theo tên bên được chọn. | Đối tượng và thuộc tính. Giữ các bên đồng hạng. |
| Cùng đối tượng qua nhiều nguồn | Ghép theo tên, chi nhánh, mã hợp đồng hoặc bên đứng tên. | Đúng vai trò và chiều quan hệ: ai vay của ai, tài sản nào bảo đảm khoản nào. |
| Thỏa hai điều kiện | Lọc từng danh sách theo cùng kỳ và phạm vi, rồi so chủ thể. Nếu hỏi “cùng đứng đầu”, xếp hạng từng danh sách trước. | Bên thỏa cả hai điều kiện. |
| So biến động hoặc dấu | Tăng/giảm cần hai mốc. Âm/dương cần giá trị trong kỳ. Kiểm cột trước/sau điều chỉnh nếu có hồi tố. | Dấu hoặc chiều của từng chỉ tiêu và kết quả so sánh. |
| Phân biệt hai khoản mục | Đọc nhãn, nhóm, cột và thuyết minh. Phân biệt số dư với phát sinh, chi phí với tiền đã trả, giá gốc với giá trị hợp lý. | Tên nhóm hoặc bản chất từng khoản. Hai số bằng nhau chưa đủ kết luận cùng bản chất. |
| Tra chú thích hoặc điều khoản | Theo ký hiệu từ dòng đến đúng chú thích. Tách điều khoản chung và riêng. | Điều khoản áp dụng cho đúng bên: thời hạn, lãi suất hoặc bảo đảm theo câu hỏi. |
| Theo sự kiện qua thời gian | Ghép cùng sự kiện theo ngày báo cáo, công bố hoặc hiệu lực. | Trạng thái từng mốc: đề xuất, phê duyệt hay đã thực hiện. |
| Đối chiếu nhiều báo cáo | Ghép đúng bên, kỳ, phạm vi và vai trò đối ứng, như phải thu bên bán với phải trả bên mua. | Kết quả từng bên hoặc từng kỳ, khớp hay chênh lệch. |

## Phối hợp

- **Coordinator** ghi các ý phải trả và quan hệ cần chứng minh. Giữ mở câu hỏi có/không. Tra song song các vế độc lập.
- **Evidence** giữ dữ kiện và nguồn đã thấy. Tra vế còn thiếu bằng tên đối tượng + thuộc tính + kỳ. Một nguồn có thể chứng minh nhiều vế.
- **Reasoning** nối dữ kiện, dùng Calculator khi cần tính. Nếu thiếu vế quyết định hoặc chưa đủ nhóm để xếp hạng, nêu phần thiếu.
- **Verifier** kiểm từng ý trong Final. Đủ nguồn nhưng thiếu ý → trả Reasoning bổ sung. Thiếu nguồn → trả Evidence kèm dữ kiện đã biết. Chỉ kết luận “không có” khi nguồn bao quát đủ phạm vi.
- Mỗi kết luận dẫn báo cáo + trang/bảng. Backend giữ địa chỉ nguồn chi tiết.
