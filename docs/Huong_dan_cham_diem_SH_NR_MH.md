# Hướng dẫn chấm điểm câu hỏi SH, NR và MH

Chấm câu trả lời cuối cùng theo đáp án chuẩn (Gold). Điểm của mỗi nhóm là trung bình điểm từng câu trong nhóm, tính bằng $S=\frac{1}{N}\sum_{i=1}^{N}s_i$. Câu không trả lời nhận 0 và vẫn tính vào $N$.

**Các cột nên có trong bảng điểm**

| Loại câu | Nội dung | Bằng chứng trong câu trả lời | Khi có phép tính |
|---|---|---|---|
| SH | Đúng theo loại đáp án | Ý đúng có nguồn | — |
| NR | Đúng trị số, đúng đơn vị | Ý đúng có nguồn | Final đúng có proof đúng nghiệp vụ |
| MH | Full, Claim-F1 | Ý đúng có nguồn, Grounded FULL | — |

## 1. SH · Tra cứu một bước

**Chấm bằng Exact Match theo loại đáp án.** Với số, so giá trị sau khi quy về cùng thang đo. Với ngày, so ngày, tháng và năm. Với tên hoặc mã, so sau khi chuẩn hóa cách viết và chấp nhận các tên tương đương đã quy định trong Gold. Gọi $n$ là phép chuẩn hóa tương ứng.

$$
s_i^{SH}=\mathbf{1}\big[n(\text{đáp án})=n(\text{Gold})\big].
$$

Cách chấm dựa trên Exact Match của TAT-QA và cách so sánh đáp án theo kiểu dữ liệu của WikiTableQuestions. [TAT-QA, ACL-IJCNLP 2021](https://aclanthology.org/2021.acl-long.254/) · [WikiTableQuestions, ACL-IJCNLP 2015](https://aclanthology.org/P15-1142/)

## 2. NR · Suy luận số học

**Chấm bằng độ chính xác của trị số cuối.** Gọi $v_i$ là kết quả trả lời và $g_i$ là giá trị Gold. Áp dụng cùng quy ước biểu diễn số và chỉ làm tròn khi đề hoặc Gold quy định.

$$
s_i^{NR}=\mathbf{1}[v_i=g_i].
$$

Có thể báo thêm **đúng đơn vị** và **trong dung sai một đơn vị làm tròn**. Chẳng hạn, với Gold **13,74%**, đáp án **13,75%** sai ở điểm chính nhưng đạt dung sai **0,01 điểm phần trăm**. Dung sai này là quy ước phụ của DACNTT.

FinQA phân biệt chấm **kết quả thực thi** với chấm **chương trình tính**. DACNTT áp dụng nguyên tắc đó để chấm trị số cuối cho cả hệ thống chỉ trả văn bản. [FinQA, EMNLP 2021](https://aclanthology.org/2021.emnlp-main.300/)

## 3. MH · Suy luận nhiều bước

**Điểm chính là Full.** Câu đạt 1 khi trả lời đủ mọi ý Gold và không có khẳng định sai làm thay đổi đáp án. Các trường hợp còn lại nhận 0. Nếu đề hỏi *ngân hàng nào cấp khoản vay nào*, mỗi ý cần đúng cả cặp ngân hàng và khoản vay.

**Điểm từng phần là F1 theo ý.** Chốt các ý bắt buộc trong Gold trước khi chấm. Chấp nhận cách diễn đạt tương đương và chỉ đếm mỗi ý một lần.

$$
P=\frac{\text{số ý trong câu trả lời được Gold xác nhận}}{\text{tổng số ý trong câu trả lời}},\qquad
R=\frac{\text{số ý Gold được trả lời đúng}}{\text{tổng số ý bắt buộc trong Gold}}.
$$

$$
F1=\frac{2PR}{P+R}.
$$

Khi câu trả lời rỗng hoặc $P+R=0$, lấy F1 bằng 0. Báo riêng tỷ lệ Full và F1 trung bình theo câu. Cách tính precision, recall và F1 theo từng nhận định dựa trên RAGChecker. [RAGChecker, NeurIPS 2024, mục 3.3.1](https://proceedings.neurips.cc/paper_files/paper/2024/hash/27245589131d17368cccdfa990cbf16e-Abstract.html)

## 4. Chấm bằng chứng cho SH, NR và MH

Mỗi **claim** là một nhận định có thể kiểm chứng. Một câu SH thường có một claim. Với MH, mỗi quan hệ được hỏi là một claim. Với NR, có thể dùng các dòng trong bảng và phép tính để chứng minh kết quả. Citation mức **báo cáo + trang/bảng** được chấp nhận nếu xác định rõ chỉ tiêu, đối tượng và kỳ. Dẫn dòng doanh thu gộp để trả lời doanh thu thuần vẫn sai nguồn dù hai dòng có cùng số.

| Chỉ số | Cách tính cho một câu |
|---|---|
| **Claim có nguồn** | Số claim trong Final được các nguồn đi kèm chứng minh ÷ tổng số claim trong Final |
| **Ý đúng có nguồn** | Số ý Gold vừa được trả lời đúng, vừa có nguồn đi kèm chứng minh ÷ tổng số ý Gold bắt buộc |
| **Grounded FULL** | 1 khi Final đúng đủ và mọi khẳng định thực chất đều có nguồn chứng minh. Với NR cần đúng đơn vị. Nếu lượt đánh giá yêu cầu proof, proof đúng nghiệp vụ phải đi tới Final. Các trường hợp còn lại nhận 0 |

**Ví dụ MH.** Gold yêu cầu ba cặp ngân hàng–khoản vay. Final nêu đúng hai cặp và chỉ dẫn được nguồn cho một cặp. Câu này đạt **Claim-F1 = 0,80**, **claim có nguồn = 1/2**, **ý đúng có nguồn = 1/3** và **Grounded FULL = 0**. Bảng điểm cho thấy hệ thống vừa thiếu một quan hệ, vừa thiếu căn cứ cho một quan hệ đã trả lời đúng.

Cột *claim có nguồn* vận dụng citation recall của ALCE ở mức nhận định. *Ý đúng có nguồn* và *Grounded FULL* là quy ước DACNTT để xét đồng thời nội dung và bằng chứng. [ALCE, EMNLP 2023](https://aclanthology.org/2023.emnlp-main.398/)

**Khi chấm RAG.** Nếu RAG chỉ xuất văn bản nhưng đã lưu context, có thể báo **tỷ lệ claim được context hỗ trợ** = số claim có căn cứ trong context ÷ tổng số claim trong Final. Chỉ số này vẫn tính được khi Final thiếu citation. Nếu lượt chạy không yêu cầu hoặc không lưu citation, ghi **N/A** ở các cột chấm citation. Nếu đã yêu cầu dẫn nguồn mà câu trả lời bỏ nguồn, ý đó nhận 0 điểm nguồn. Với nhóm có chấm nguồn, Final rỗng nhận 0 ở các chỉ số trên. [RAGChecker, NeurIPS 2024](https://proceedings.neurips.cc/paper_files/paper/2024/hash/27245589131d17368cccdfa990cbf16e-Abstract.html)

**Khi có proof hoặc trace EO.** Với NR, báo thêm **số câu có Final đúng kèm proof đúng nghiệp vụ ÷ tổng số câu NR**. Proof phải dùng đúng công thức, toán hạng, kỳ, đơn vị và nguồn. Với EO, có thể báo **số yêu cầu Gold được chứng minh và thể hiện đúng ở Final ÷ tổng số yêu cầu Gold**. Chỉ tính khi trace cho thấy EO bao phủ yêu cầu và bằng chứng thực sự được dùng. Đối chiếu với Gold để chấm, kể cả vế Coordinator bỏ sót. Đây là hai chỉ số chẩn đoán của DACNTT. Cách xem xét riêng bằng chứng tài chính và bước suy luận số học tham khảo FinLFQA. [FinLFQA, Findings of EMNLP 2025](https://aclanthology.org/2025.findings-emnlp.908/)
