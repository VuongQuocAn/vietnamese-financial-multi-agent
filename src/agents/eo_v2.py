"""Adaptive evidence obligations from a natural question to a verified Final."""

import re
from copy import deepcopy
from decimal import Decimal, DecimalException, DivisionByZero
from pathlib import Path

from ..accounting.item_mapping import ITEM_CATALOG
from ..core.llm_contracts import GenerationParameters, LLMRequest, Message, OutputSpec
from ..evidence.json_catalog import resolve_pointer
from ..evidence.search import normalize_search, rank_search_candidates
from ..tools.eo_v2_evidence import (
    NUMBER,
    calculate,
    citation_key,
    dump,
    number,
    quantities,
    result_unit,
    source_ids,
)

MODEL = "gpt-4o-mini"
CONTEXT_CHARS = 36_000


def record_schema(**properties):
    return dict(
        type="object", properties=properties, required=list(properties), additionalProperties=False
    )


def array_schema(items):
    return dict(type="array", items=items)


STRING = dict(type="string")
INT = dict(type="integer")
ROUTE = dict(type="string", enum=["SH", "MH", "NR"])
REQUIREMENT = record_schema(description=STRING, filings=array_schema(STRING), section=STRING)
PLAN = record_schema(
    route=ROUTE,
    filings=array_schema(STRING),
    obligations=array_schema(
        record_schema(
            goal=STRING,
            needs=array_schema(STRING),
            requirements=array_schema(REQUIREMENT),
            result=dict(type="string", enum=["calculation", "evidence"]),
            result_unit=STRING,
            formula=STRING,
        )
    ),
)
LINK = record_schema(value=STRING, source=STRING)
NEED = record_schema(
    eo=INT,
    agent=dict(type="string", enum=["evidence", "reasoning"]),
    query=STRING,
    reason=STRING,
    link=LINK,
)
PROPOSAL = record_schema(
    claims=array_schema(
        record_schema(
            eo=INT,
            kind=dict(type="string", enum=["lookup", "answer", "calculation"]),
            answer=STRING,
            sources=array_schema(STRING),
            operands=array_schema(
                record_schema(
                    name=STRING,
                    source=STRING,
                    indicator=STRING,
                    period=STRING,
                    value=STRING,
                )
            ),
            expression=STRING,
            unit=STRING,
            decimals=INT,
        )
    ),
    missing=array_schema(NEED),
)
CALCULATION = record_schema(
    eo=INT,
    operands=array_schema(
        record_schema(
            name=STRING, source=STRING, indicator=STRING, period=STRING, group=STRING, filing=STRING
        )
    ),
    expression=STRING,
    revision=STRING,
    unit=STRING,
    decimals=INT,
)
NUMERICAL_PROPOSAL = record_schema(claims=array_schema(CALCULATION), missing=array_schema(NEED))
MIXED_PROPOSAL = record_schema(
    claims=array_schema(dict(anyOf=[PROPOSAL["properties"]["claims"]["items"], CALCULATION])),
    missing=array_schema(NEED),
)
MH_ANSWER = record_schema(answer=STRING, sources=array_schema(INT))
MH_PROPOSAL = record_schema(claims=array_schema(MH_ANSWER), missing=array_schema(NEED))
MH_EVIDENCE_JOIN = record_schema(
    legs=array_schema(
        record_schema(
            eo=INT,
            requirement=STRING,
            query=STRING,
            link_value=STRING,
            link_choice=INT,
        )
    ),
    prerequisite_pending=dict(type="boolean"),
)

MH_MIXED_PROPOSAL = record_schema(
    claims=array_schema(dict(anyOf=[MH_ANSWER, CALCULATION])), missing=array_schema(NEED)
)
ASSESSMENT = record_schema(
    checks=array_schema(
        record_schema(
            eo=INT,
            requirement=INT,
            claims=array_schema(INT),
            status=dict(type="string", enum=["supported", "missing", "incorrect", "irrelevant"]),
            basis=STRING,
        )
    ),
    missing=array_schema(NEED),
)

MH_ASSESSMENT = record_schema(
    checks=array_schema(
        record_schema(
            claim=INT,
            status=dict(type="string", enum=["supported", "missing", "incorrect", "irrelevant"]),
            basis=STRING,
            requirements=array_schema(INT),
            sources=array_schema(INT),
        )
    ),
    completion=array_schema(
        record_schema(
            eo=INT, status=dict(type="string", enum=["complete", "incomplete"]), basis=STRING
        )
    ),
    missing=array_schema(NEED),
)

DIRECT_NR_PROPOSAL = record_schema(
    expression=STRING,
    unit=STRING,
    decimals=INT,
    roles=array_schema(record_schema(code=STRING, purpose=STRING)),
    missing=array_schema(record_schema(query=STRING, reason=STRING)),
)
DIRECT_NR_VERDICT = record_schema(
    status=dict(type="string", enum=["supported", "incorrect", "missing"]),
    basis=STRING,
    query=STRING,
)


COORDINATOR = """Bạn là Coordinator QA báo cáo tài chính. Chọn route từ nguyên câu hỏi:
SH = tra cứu trực tiếp một chỉ tiêu/đối tượng/đoạn; MH = nối nhiều nguồn, xác định quan hệ
hoặc so sánh nhiều đối tượng; NR = cần tính giá trị bằng biểu thức số học. SH mặc định một EO,
không tách các cụm tên của một chỉ tiêu gộp theo chữ và/dấu phẩy. MH/NR mặc định một EO toàn
câu; chỉ tách EO khi kết luận có ý nghĩa độc lập cần kiểm riêng. Không tách từng toán hạng
hay từng kỳ của cùng phép tính. Giữ nguyên các điều kiện câu hỏi, mỗi need là cụm tìm kiếm
ngắn theo tên hàng/bảng/đối tượng cần đọc. MH tìm đủ dữ kiện nối; nếu cần biết đối tượng
trước thì bắt đầu ở nguồn xác định đối tượng. NR cần các nhãn nghiệp vụ của từng thành phần
và kỳ, ưu tiên bảng chứa nhiều toán hạng. Với calculation, formula là công thức
nghiệp vụ dự kiến bằng tên đại lượng (phân biệt kỳ, tổng/thành phần, mẫu số, dấu,
đơn vị và điều kiện so sánh). Chưa chọn ô nguồn và không đoán số. Nếu evidence,
formula rỗng. Công thức phải trả đúng đại lượng được hỏi, không chỉ trung gian.
Chọn người phát hành báo cáo và năm/phạm vi từ options; không nhầm đối tác là người lập.
Giữ filing fixed nếu có. result=calculation cho kết quả số cần phép tính, evidence cho kết luận khác.
NR hỏi một kết quả chỉ tạo một EO calculation có requirements mô tả đầy đủ kết quả; không tách làm tròn, bước trung gian hay lặp mục tiêu thành EO riêng.
result_unit là đơn vị kết quả tính được hỏi rõ trong câu gốc (VND, lần, %, ngày...), rỗng nếu không chỉ định. Không chép đơn vị toán hạng vào tỷ số.
requirements là các kết luận bắt buộc của nguyên câu hỏi, không phải truy vấn.
SH chỉ một requirement toàn chỉ tiêu, kể cả tên hàng ghép. MH ưu tiên một requirement
diễn tả chính quan hệ cần chứng minh, cùng thực thể và điều kiện của từng kỳ; không
liệt kê bốn số thay cho quan hệ. Chỉ tách các kết luận độc lập thực sự được hỏi.
Một phép tính
là một kết quả kèm toàn bộ thành phần/kỳ/dấu/đơn vị; không tách toán hạng thành đáp án.
Quan hệ giữa các vế là một yêu cầu thực sự, không chỉ liệt kê dữ kiện. Không bỏ điều kiện
so sánh, phạm vi hoặc mốc kỳ. Mỗi requirement có description, filings là alias của
chính BÁO CÁO được yêu cầu (phân biệt năm của filing và năm của cột so sánh;
không mở báo cáo năm trước chỉ để lấy cột so sánh của báo cáo năm được hỏi),
section là tên báo cáo/bảng được chỉ định nguyên văn trong câu hỏi, rỗng nếu không chỉ định.
Không suy đoán locator. Các requirements của các EO phải bao phủ đầy đủ câu hỏi.
Riêng NR, trước khi lập công thức hãy xác định NGUỒN được chỉ định trong nguyên câu hỏi:
1. Đọc cụm chỉ báo cáo của người lập và năm báo cáo, rồi chọn alias theo options.fiscal_year.
Ví dụ: "Theo BCTC năm N ... tại cuối năm N-1" → filing năm N, cột so sánh N-1 trong filing N.
Nếu chỉ định một BCTC, cả filings và requirements.filings CHỈ chứa alias báo cáo đó,
kể cả khi hỏi biến động giữa hai năm. Không chọn năm của đại lượng làm năm filing.
2. Trong goal ghi nguyên cụm chỉ nguồn và kỳ cần đọc trước mô tả phép tính.
Nếu chỉ định B01/B02/B03 hoặc tên báo cáo/bảng tương đương, giữ đúng trong section;
needs chứa tên dòng cần tìm trong bảng đó (ví dụ dòng điều chỉnh dòng tiền, không phải số dư).
Nếu không chỉ định bảng, section có thể rỗng; không giới hạn nguồn tương đương hợp lệ.
Chỉ chọn nhiều filing nếu câu hỏi thực sự yêu cầu nhiều báo cáo. Giữ nguyên câu hỏi.
filings là danh sách báo cáo cần đọc, không phải danh sách kỳ của toán hạng.
Mỗi needs ghi ngắn đại lượng nghiệp vụ và kỳ/cột cần tìm (gồm tổng hay thành phần, đầu/cuối,
dòng tiền hay số dư). formula diễn đạt liên hệ giữa đầy đủ đại lượng đó, kể cả bình quân và dấu.
Nếu hỏi một số cần phép tính, route NR kể cả khi các đại lượng từ nhiều bảng.
Riêng MH: mô tả yêu cầu trung lập, không giả định câu trả lời có/không hoặc chiều tăng/giảm.
Đặt các ý độc lập thành requirements riêng trong một EO bằng chứng; nếu câu hỏi đòi quan hệ,
ghi chính quan hệ cần chứng minh cùng điều kiện chọn đối tượng. Không tách các lựa chọn
trái nhau thành hai mệnh đề khẳng định: yêu cầu chọn khả năng đúng và xác định đối tượng.
Nếu hỏi tên doanh nghiệp/bộ phận, phân loại, ai đứng đầu, có/không hay mối quan hệ, kết quả là
văn bản evidence dù cần so sánh số liệu. Chỉ result=calculation nếu câu thực sự yêu cầu một giá
trị số được tính; nếu cần cả tính số lẫn giải thích thì tách hai loại EO. Không gọi Calculator
để thay việc xếp hạng, đọc tên hay chọn giữa hai khả năng. Dùng hướng dẫn phù hợp nếu được cấp.
MH: thứ tự needs là dữ kiện tiền đề trước, thuộc tính cần nối sau. Khi chưa biết tên thực thể,
need đầu chỉ tìm bảng/danh sách/sự kiện xác định thực thể (không thay bằng tổng), need sau mô tả
đúng khoản mục cần đọc cho thực thể đó. Nếu hỏi hướng biến động, thứ hạng hoặc tên đối tượng,
không chuyển thành phép tính max, tỷ trọng hay tỷ lệ không được hỏi. Nếu hỏi hai báo cáo cụ thể,
chọn cả hai alias báo cáo đó; phân biệt kỳ so sánh và năm phát hành.
"""

COLAB_SYSTEM = "Bạn là trợ lý phân tích báo cáo tài chính của các công ty Việt Nam. Chỉ trả lời dựa trên các đoạn trích báo cáo được cung cấp."
SINGLE_GUIDE = '- Chỉ dùng thông tin trong các đoạn trích. Chú ý đúng công ty, đúng năm tài chính, đúng cột số liệu (cột cuối năm/năm nay; không lấy cột đầu năm/năm trước trừ khi câu hỏi hỏi).\n- Với số liệu: chép đúng nguyên văn con số trong bảng (giữ dấu chấm ngăn cách hàng nghìn), không làm tròn, kèm đúng đơn vị ghi trên bảng (VND, nghìn đồng, triệu đồng, người, năm, ...).\n- Ngày tháng: dạng dd/mm/yyyy.\n- Trả lời ngắn gọn nhất có thể.\n- Nếu đoạn trích không có thông tin: trả lời "KHÔNG TÌM THẤY".'
MULTI_GUIDE = '- Câu hỏi cần kết hợp thông tin từ nhiều đoạn trích (và có thể nhiều báo cáo/năm khác nhau): xác định đối tượng ở đoạn này rồi tra số liệu hoặc thông tin liên quan ở đoạn kia.\n- Chỉ dùng thông tin trong các đoạn trích. Chú ý đúng công ty, đúng năm tài chính, đúng cột số liệu (cuối năm/năm nay; không lấy cột đầu năm/năm trước trừ khi câu hỏi hỏi).\n- Trả lời đầy đủ nhưng ngắn gọn, 1-3 câu: nêu rõ tên đối tượng được chọn và các con số/ngày tháng liên quan, chép đúng nguyên văn số liệu trong bảng (giữ dấu chấm ngăn cách hàng nghìn, không làm tròn) kèm đơn vị.\n- Nếu đoạn trích không đủ thông tin: trả lời "KHÔNG TÌM THẤY".'
CALC_GUIDE = "- Xác định các số liệu cần dùng (đúng công ty, đúng năm, đúng cột, đúng chỉ tiêu); chép nhãn chỉ tiêu, kỳ/cột và giá trị nguyên văn từ bảng đã đọc; backend gắn địa chỉ nguồn.\n- KHÔNG tự tính kết quả. Chỉ viết biểu thức theo đúng quy tắc trong câu hỏi (dấu, kỳ gốc, nhân 100 nếu hỏi phần trăm, 365 ngày, bình quân đầu/cuối kỳ...) bằng tên biến. Biểu thức chỉ dùng + - * / ** ( ), hàm abs() và tên biến."
CONTRACT = """
Đầu vào có câu hỏi gốc, obligations và các nguồn thực sự được cấp. Mỗi claim là
một kết luận có ý nghĩa độc lập cần trả cho người dùng. Chọn EO id đã cấp.
- lookup: một ô số trực tiếp, sources chứa đúng một ID ô hoặc F; backend đọc
giá trị và đơn vị. answer có thể ghi câu đáp ngắn để lưu candidate, không dùng số để đoán ID.
- answer: kết luận văn bản/quan hệ, answer ngắn gọn tự đứng được; sources là
các ID đoạn, hàng hoặc ô thực sự chứng minh từng vế. Khi nối nhiều đối tượng,
nêu riêng tên từng đối tượng, giá trị/thời điểm và quan hệ; chọn nguồn của từng bên,
không chỉ tên bảng chung. Chỉ dùng cả bảng T khi tất cả hàng đã được cấp.
- calculation: mỗi toán hạng có name (tên biến nghiệp vụ), indicator (chép nhãn
dòng), period (chép tiêu đề cột hoặc kỳ đầy đủ), value (chép giá trị gốc gồm dấu),
source (ID bảng T hoặc fact F thực sự được cấp, có thể rỗng nếu nhãn/kỳ duy nhất).
Không cần tự viết ID ô R/C. Không thêm prefix filing vào ID. Backend xác định
tọa độ duy nhất từ nhãn và kỳ trong nguồn đã đọc rồi kiểm value khớp; nếu nhiều
bảng có cùng nhãn/kỳ, chỉ rõ bảng. expression dùng tên biến, unit, decimals;
sources và answer rỗng, không nhẩm kết quả. Dùng + - * / ** (), abs và hằng số
có căn cứ, giữ dấu nguồn và từng thành phần. Calculator tạo đáp số duy nhất.
Một câu MH cũng có thể cần calculation. Không phát hành toán hạng riêng như đáp án.
Với trường không dùng: string rỗng, array rỗng, decimals=0.
Nếu thiếu bằng chứng, không đoán. Trả missing cho EO với agent=evidence,
query cụm tìm cụ thể, reason mô tả chính xác dữ kiện còn thiếu. Nếu đã xác định đối tượng nối,
link.value chép nguyên tên/dữ kiện nguồn, link.source là ID đã cấp chứa nó;
truy vấn tiếp theo sẽ dùng giá trị đó. Nếu không có link, hai trường rỗng.
Nếu chỉ chứng minh được một vế độc lập, trả claim vế đó cùng missing phần còn thiếu.
Khi recovery, chỉ giải phần chưa xác minh; giữ nguyên vế đã verified.
"""
REASONING_PROMPTS = {
    "SH": COLAB_SYSTEM + "\n" + SINGLE_GUIDE + "\n" + CONTRACT,
    "MH": COLAB_SYSTEM
    + "\n"
    + MULTI_GUIDE
    + "\n"
    + CONTRACT
    + "\nNếu mới biết đối tượng từ một nguồn, nhưng thiếu nguồn khác để kết luận quan hệ, trả missing agent=evidence; query chứa tên đối tượng và dữ kiện thứ hai cần tìm, link.value và link.source ghi đúng tên và ID đã thấy. Không suy từ số tổng sang đối tác.",
    "NR": COLAB_SYSTEM + "\n" + CALC_GUIDE + "\n" + CONTRACT,
}
NUMERICAL_PROMPT = (
    COLAB_SYSTEM
    + """
Đọc nguyên câu hỏi, xác định đúng đại lượng, công thức, toàn bộ thành phần/kỳ/dấu/đơn vị.
Chọn từng dữ kiện gốc bằng indicator (nhãn chỉ tiêu cần dùng) và period (kỳ/cột cần dùng).
source có thể là ID ô/fact đã thấy, hoặc ID bảng để giới hạn, hoặc rỗng để tìm theo nhãn/kỳ.
 group và filing chỉ điền khi cần phân biệt nhiều nguồn, mặc định rỗng. Không chép số hay tọa độ.
Kể cả chọn ID, indicator và period phải diễn tả dữ kiện CẦN cho công thức, không đổi chúng theo ô sai.
Dùng nhãn thực tế hoặc nhãn tương đương rõ ràng; không đánh đồng tổng/thành phần, gộp/thuần,
đầu/cuối kỳ hoặc bình quân. Nếu cần bình quân, khai hai toán hạng gốc riêng.
EO.formula là đề xuất nghiệp vụ, không phải đáp án bắt buộc. Đối chiếu với nguyên câu hỏi.
operands ánh xạ name (snake_case có kỳ khi cần) đến selector ở trên.
Nếu có đoạn bảng tra công thức, chỉ dùng mẫu phù hợp với câu hỏi, tự lập công thức nếu không phù hợp.
expression viết MỘT công thức bằng các name đã khai, không viết ID nguồn lại
trong biểu thức. Dùng + - * / ** (), abs(), hằng số được câu hỏi cho phép.
Nếu sửa EO.formula, revision ghi ngắn phép tính đã sửa và lý do, nếu không để rỗng.
Phân biệt đại lượng đích với trung gian; biểu thức phải đủ tất cả thành phần,
đúng kỳ, đúng dấu nguồn và chuyển độ lớn nếu câu hỏi yêu cầu. Đại lượng suy ra
được viết trong expression từ các toán hạng gốc, không khai một ô trung gian giả.
Một EO tính một kết quả: một claim cho đúng EO đang active, đầy đủ tất cả thành
phần, kỳ; đại lượng suy ra viết trong expression. Không lập claim cho mỗi toán
hạng. Không tự tính số cuối. Dùng result_unit được hỏi và decimals đúng yêu cầu;
chia hai khoản tiền là tỷ số, nếu hỏi % thì quy đổi ×100, nếu hỏi lần thì không.
Nếu thiếu toán hạng, trả missing agent=evidence, query nêu đúng tên chỉ tiêu,
kỳ và báo cáo cần tìm, reason cụ thể, không tạo phép tính thiếu thành phần.
Nếu đã có dữ kiện nối, link.value và link.source chép nguyên giá trị và ID đã
đọc, nếu không thì cả hai rỗng. Khi recovery sửa đúng lỗi được nêu, dùng lại
nguồn đã thấy và nguồn mới nếu có. Không chỉ chép lại phản hồi lỗi làm missing.
"""
)


VERIFICATION = """
Bạn là Verifier. Nguyên câu hỏi là chuẩn. Chỉ kiểm đúng candidate và tool_answer
đã được đưa tới bạn; không phải gõ lại ID, không chọn thay nguồn. Kiểm từng
claim với địa chỉ nguồn đã pin, nhãn dòng/cột, kỳ, đơn vị, issuer và đối tượng.
Một địa chỉ tồn tại vẫn có thể sai hàng/cột hoặc sai đối tượng. Với lookup,
đối chiếu ý nghĩa ô được chọn với đúng chỉ tiêu người dùng hỏi.
Với quan hệ, không suy số dư nghĩa vụ từ chi phí, không gán số tổng cho đối tác. Nếu thiếu nguồn thứ hai, yêu cầu Evidence tra cứu bằng đúng tên đối tượng đã xác định và ID chứa tên đó.
Với quan hệ, kiểm từng đối tượng và nguồn tương ứng, kiểm cả chiều liên hệ và
các vế. Không chấp nhận chỉ vì có hai địa chỉ hoặc cùng một thuật ngữ.
Với phép tính, trước tiên xác định tất cả thành phần, kỳ, dấu, mẫu số và
đơn vị mà NGUYÊN CÂU HỎI yêu cầu. Sau đó đọc proof.expression và từng tên biến
cùng label/column/period/unit/value/citation thật. Nêu trong basis các thành phần và kỳ
đã dùng so với yêu cầu; nếu thiếu/sai, chỉ đích danh phần thiếu/sai. Decimal chỉ xác nhận
số học chứ không chứng tỏ công thức giải đúng bài. Không supported nếu thiếu thành phần/kỳ
hoặc sai dấu, công thức, đơn vị hay đối tượng. Không tính lại một đáp số thay tool.
Nếu target có một EO/claim/proof, đây là đối tượng duy nhất đang kiểm; vẫn đánh status theo đầy đủ câu hỏi, không tự tính lại, claims có thể rỗng.
Mỗi requirement do Coordinator ghi có chỉ số 1-based trong EO. Đánh đúng MỘT
check cho mỗi requirement chưa verified: eo, requirement, claims (các index đã
cấp của claim thực sự chứng minh ý này; rỗng nếu chưa có), status và basis.
Đọc câu hỏi nguyên gốc, đối chiếu mọi điều kiện của requirement; nếu thiếu một
điều kiện của câu hỏi mà plan chưa ghi, không supported một kết luận thiếu/sai.
basis phải nêu cụ thể quan sát thực tế (đúng báo cáo, dòng, cột, kỳ, quan hệ hoặc
thành phần của proof) và vì sao đáp ứng; không chỉ lặp lại candidate.
Chỉ supported nếu toàn bộ claim được liên kết đều đúng và có nguồn đủ, kể cả
các phát biểu bổ sung trong câu; nếu một claim chứa quan hệ sai/thiếu, đánh sai
hoặc thiếu chứ không xác nhận từng số rời. Khi câu cần nối hai nguồn, kiểm điều
kiện chọn thực thể và quan hệ giữa các nguồn. Đừng xác nhận đúng số từ sai báo
cáo; nếu câu chỉ định filing, cột so sánh của chính báo cáo đó khác báo cáo năm trước.
Không chép lại ID nguồn, không có phiếu complete; backend tổng hợp các ý đã
verified từ các check. Các ý đã verified giữ nguyên; chỉ kiểm các ý còn mở.

Nếu có lỗi, trả missing: eo, agent=reasoning khi nguồn đủ nhưng chọn sai ô,
công thức hoặc quan hệ; agent=evidence khi cần nguồn mới. reason phải cụ thể;
query cụm tra cứu khi evidence, rỗng nếu reasoning. Nếu đã có dữ kiện nối,
link.value chép đúng tên/dữ kiện và link.source ID nguồn đã pin; nếu không có,
hai trường link rỗng. Một vế độc lập đúng vẫn có thể supported, nhưng không
được xem là đủ câu nếu vế khác thiếu. Không dùng Gold hoặc giả định ngoài nguồn.
"""


MH_EVIDENCE_PROMPT = """
Bạn lập truy vấn bằng chứng cho EO MH, không viết đáp án hay phán found/missing.
Dùng nguyên câu hỏi, reading_plan của Coordinator và đoạn MH_EVIDENCE_GUIDE đã cấp.
reading_plan là các bước đọc nguồn, KHÔNG phải nghĩa vụ phát hành độc lập. Giữ điều kiện lọc, vai trò,
kỳ và filing của từng bước; câu hỏi gốc ưu tiên nếu kế hoạch thiếu điều kiện. Với “A hay B” chỉ tìm
nguồn phân biệt hai khả năng, không tìm bằng chứng chứng minh cả hai.
Với mỗi vế độc lập cần chứng minh, lập query thực thi: tên đối tượng/thuộc tính/dòng hoặc bảng cần tra,
đúng kỳ và alias filing từ danh sách. Một query có thể bao phủ nhiều vế nếu cùng dòng/đoạn thực sự trả lời.
Mỗi leg gồm eo, requirement (dữ kiện cần đọc), query (luôn là cụm tra cứu, không phải câu trả lời),
link_value và link_choice. Chỉ lập query khi dữ kiện thật sự cần thêm; nếu nguồn đã có đủ thì legs=[].
query là cụm tra cứu thuộc tính/kỳ/alias + tên đã xác định, không sao chép đoạn dài, số tổng,
mã nguồn, câu SQL hay locator. Giữ riêng query khác kỳ hoặc thuộc tính dù requirement giống nhau.
Khi đối tượng đã nêu trong câu hỏi, dùng trực tiếp tên đó trong query; link_value="", link_choice=0.
Khi đối tượng chưa được nêu và vế sau phụ thuộc nó, làm bước lọc/xếp hạng từ reading_plan trước.
Đọc đúng các hàng/cột và điều kiện khi xác định tên, sau đó chuyển chính tên đọc được cùng
link_choice chứa nó để tìm thuộc tính của cùng đối tượng. Nếu nguồn thuộc tính đã có, dùng ngay.
Nếu chưa đọc được tiền đề, query tìm dòng/đoạn xác định nó; prerequisite_pending=true.
Nếu có dẫn chiếu, tiêu đề hay ký hiệu thực từ nguồn đã cấp, có thể dùng đó làm link_value để mở vùng nguồn.
Khi đã có dữ kiện nối từ nguồn, ghi đúng nguyên văn link_value và số lựa chọn [#n] chứa nó vào link_choice.
Backend kiểm link_value trong nguồn được cấp. Không đặt tên báo cáo/alias hoặc tọa độ làm dữ kiện nối.
Nếu không cần link, hai trường là "" và 0. Không đoán tên. Nếu phải đọc theo hai báo cáo, query riêng từng alias.
Ở lượt nối tiếp, dùng dữ kiện đã đọc thật từ nguồn mới để tìm thuộc tính còn cần; không lặp tìm tiền đề.
Nếu nguồn mới đã chứa cả thuộc tính cần nối, không cần thêm query (legs=[]). Không bịa nguồn hoặc kết luận.
"""


MH_REASONING = (
    COLAB_SYSTEM
    + """
Đọc câu hỏi gốc, reading_plan và yêu cầu EO rồi trả từng ý bằng claim văn bản {answer,sources}.
reading_plan chỉ là gợi ý đọc theo bước, không phải số claim buộc sinh. Khi bước sau cần một tên/dữ kiện
từ bước trước, đối chiếu tên và điều kiện lọc trong nguồn tiền đề với nguồn thuộc tính; không đoán.
Khi so sánh, đọc đúng hai kỳ/đối tượng/khoản mục và chỉ kết luận khả năng được chứng minh.
Backend tự nối các claim văn bản với EO bằng chứng; KHÔNG chép eo hay requirement vào claim.
Mỗi claim là khẳng định tự đứng được, kèm nguồn thực sự chứng minh đúng đối tượng, kỳ và vai trò.
Trả lời trực tiếp quan hệ/điều kiện chính của câu hỏi TRƯỚC, rồi nêu dữ kiện chứng minh. Ví dụ khi hỏi có tăng không, nếu đã có hai kỳ thì phải kết luận tăng, giảm hay không đổi, không dừng ở việc chép số. Khi hỏi cùng một đối tượng, khẳng định quan hệ trên chính đối tượng đó. Tách các ý độc lập để giữ được phần đã biết.
Nếu hỏi A hay B, xác định đối tượng trước rồi đối chiếu cả hai khả năng; không khẳng định cả hai.
Nếu hỏi bên/bộ phận đứng đầu, trả tên thực thể và điều kiện xếp hạng; không thay đáp án bằng tỷ số.
Dùng nguồn duy nhất nếu đã đủ. Nếu cần nối nguồn, giữ nguồn đầu và nguồn tiếp theo.
Đọc NGUỒN THEO VẾ trước; so từng lựa chọn với câu hỏi gốc, rồi mở context rộng nếu chưa đủ.
Nhóm chỉ gợi ý, không phải verdict: không mặc định hàng đầu là đáp án. Khi nối hai vế, chọn cả nguồn xác định đối tượng và nguồn thuộc tính của chính đối tượng đó.
Nếu đã có bổ sung, đọc các dòng mới và nối với nguồn đầu. Chưa thấy trong đoạn được cấp
không có nghĩa báo cáo không công bố; không khẳng định sự vắng mặt nếu không có nguồn chứng minh.
Nếu thiếu vế, chỉ trả phần có căn cứ và missing chính xác; không biến số tổng thành tên thực thể.
sources là mảng SỐ NGUYÊN duy nhất từ [#n] ngay cạnh đoạn/dòng đã đọc. Cùng mã có cùng nguồn trong mọi nhóm và context rộng. Không chép trang, nhãn hay locator. Mỗi claim nối quan hệ chọn đúng các lựa chọn trực tiếp chứng minh từng vế, kể cả nguồn ở nhóm khác; không liệt kê toàn bộ mã hay mã không dùng. Mã toán hạng chỉ dùng trong Calculator.
Nếu thiếu điều kiện, giữ các claim đã có căn cứ; missing ghi EO đang active, agent=evidence,
query thuộc tính còn thiếu + kỳ + báo cáo + tên/dữ kiện nối nếu đã biết. link.value chép nguyên tên/dữ kiện vừa xác định từ nguồn; link.source để rỗng, backend kiểm dữ kiện trong nguồn đã cấp. Không dùng số giao dịch làm số dư nghĩa vụ.
Nếu đủ nguồn nhưng nối sai, agent=reasoning, reason chỉ rõ nguồn và quan hệ cần sửa. Khi có phản hồi Verifier, chỉ bổ sung/sửa ý được chỉ ra bằng đúng nguồn đã thấy, không chép lại các claim đã verified. Nếu nguồn chưa đủ, nói thiếu, không đoán; không yêu cầu thêm retrieval nếu đã khóa nguồn. nếu cần nối chú thích, đối chiếu đúng ký hiệu và khoản mục trong cùng báo cáo.
Đọc guide được cấp như gợi ý cách nối, bỏ mẫu không phù hợp; câu hỏi quyết định.
Với EO calculation trong luồng hỗn hợp, dùng contract Calculator tương ứng, không thay tên bằng số.
"""
)

MH_VERIFICATION = """
Kiểm nguyên câu hỏi, EO và từng claim. sources trong payload là mã [#n] đã bind, nội dung nguồn chỉ xuất hiện một lần trong context_visible; đọc các mã đó và các dòng liên quan khác để đối chiếu. Không chép lại cả danh sách nguồn.
Không yêu cầu kết luận hoặc dữ kiện ngoài phạm vi câu hỏi; chỉ kiểm những đối tượng và quan hệ được hỏi. Nếu bác, basis phải chỉ rõ đối tượng, kỳ, dòng hoặc quan hệ mâu thuẫn/thiếu. Không tự viết câu trả lời mới. Với mỗi index claim trả đúng một
check: claim, status, basis ngắn, requirements (chỉ số yêu cầu EO thực sự được chứng minh, KHÔNG phải mã nguồn),
sources (mảng số nguyên [#n], để [] nếu nguồn đã gắn đủ; chỉ thay bằng các mã thực sự chứng minh nếu cần sửa citation, không lặp lựa chọn không dùng). Không xác nhận câu chỉ vì nguồn chứa một từ hoặc có hai con số.
Kiểm đối tượng, báo cáo, kỳ, nhãn dòng/cột, vai trò và chiều quan hệ. Khi A hay B, xác định đúng
đối tượng có đặc điểm được hỏi trước rồi kiểm lý do/phân loại, không gán đặc điểm của đối tượng khác.
Khi xếp hạng, kiểm các đối tượng cùng nhóm (không tính dòng tổng) và tên trả lời. Khi so hai
kỳ, kiểm cùng thực thể và dấu/chiều. Với proof Calculator, kiểm expression, các nguồn và đơn vị
trả đúng câu hỏi; số đúng chưa chứng minh phép tính đúng.
status=supported chỉ khi toàn bộ phát biểu trong claim được chứng minh. Claim độc lập đúng
vẫn supported dù toàn câu thiếu vế; requirements=[] nếu claim chưa đủ bất kỳ yêu cầu hoàn chỉnh.
Chỉ đánh dấu requirement khi các claim supported, kể cả phần verified trước đó, cùng chứng minh
đầy đủ ý/quan hệ, không chỉ các dữ kiện rời. Một claim có thể chứng minh nhiều yêu cầu; đừng
đánh dấu nếu kết luận quan hệ chưa được viết. Nếu thiếu/sai một vế hay cả kết luận nối, trả
missing với eo, agent=reasoning nếu context đủ: reason chỉ ra vế phải sửa, mã [#n] đã thấy, dòng/cột/kỳ hoặc giá trị cần đối chiếu và điều chưa kết luận (không tự viết đáp án). Nếu các nguồn đã có nhưng ứng viên chỉ liệt kê số, chọn sai đối tượng hay nguồn, không chuyển sang Evidence. agent=evidence chỉ nếu đã xét context mà thiếu dữ kiện thật, query thuộc tính/kỳ và link.value của dữ kiện đã xác định
để tìm tiếp. Giữ các ý độc lập đã supported. Không chặn cả candidate vì một vế chưa rõ nguồn.
Đối chiếu từng yêu cầu của nguyên câu hỏi với TOÀN BỘ các claim supported, kể cả claim
retained từ lượt trước. Trả completion cho từng EO active: complete chỉ khi toàn bộ vế và
quan hệ đã được chứng minh; basis nói rõ chúng là gì. Thiếu một ý thì incomplete, basis nêu
chính xác ý thiếu. Không dựa riêng vào requirements hay số claim supported.
Đọc missing của Reasoning: nếu là thiếu thật, giữ yêu cầu truy tiếp, nếu nguồn đã có thì
chỉ rõ nguồn/dòng cho Reasoning sửa; không bỏ qua vì claim khác supported. Kiểm số dư khác
giao dịch, công ty cho vay khác công ty đi vay, và chú thích phải thuộc đúng dòng có ký hiệu.
Nếu cần Evidence, query cụ thể thuộc tính, kỳ, báo cáo và link.value đúng dữ kiện đã pin;
link.source để rỗng, backend kiểm tên trong context. Nếu chưa biết đối tượng, tra nguồn
xác định đối tượng trước. Nếu nguồn cũ đủ, không tìm thêm. Trong lượt sửa, claim retained đã được duyệt: không cần trả check lại nếu không có mâu thuẫn. Nếu retained đúng nội dung nhưng citation sai, có thể trả supported với các mã chứng minh đúng để thay citation. Chỉ bác retained khi đối chiếu nguồn chứng minh nó sai/không liên quan; nêu basis cụ thể, không bác vì lượt sửa thiếu ý khác. Kiểm các claim mới và completion trên cả retained đúng + claim mới supported. Nếu đã đủ mọi ý, missing=[].
Không Gold, không tạo claim mới, không suy nguồn ngoài context.
"""

DIRECT_NR_REASONING = (
    COLAB_SYSTEM
    + """
Đọc nguyên câu hỏi trước EO; xác định rõ báo cáo được chỉ định và kỳ số liệu riêng biệt.
Chọn mã từ dòng thật: kiểm filing, tiêu đề bảng, nhãn, kỳ/cột, đại lượng, dấu và đơn vị.
Nếu cùng kỳ xuất hiện ở hai filing, dùng đúng filing câu hỏi chỉ định; không thay bằng cùng số
ở báo cáo khác. Nếu cần dòng biến động/điều chỉnh trên báo cáo lưu chuyển tiền tệ, không dùng
số dư trên bảng cân đối. Đọc bảng ưu tiên trước, nhưng chấp nhận nguồn tương đương khi câu hỏi cho phép. Ví dụ expression=(T1R2C4+T1R2C5)/2; dùng trực tiếp mã có trong
LỰA CHỌN TOÁN HẠNG. Không khai operands, không chép nhãn/kỳ/số hay viết tên biến mới.
Không tự tính số cuối, không dùng literal số tài chính thay mã. Dùng + - * / ** (), abs()
và hằng số có căn cứ như 2, 100, 365. Trả expression, unit kết quả cần hỏi, decimals.
roles: với mỗi mã thực sự dùng, ghi một purpose ngắn: đại lượng mà mã phải chứng minh và kỳ
được yêu cầu (ví dụ VCSH đầu kỳ, tiền thuế thực nộp năm trước), không chép số/nhãn/địa chỉ ô.
Trước khi chốt, đối chiếu purpose với chính dòng/cột của mã: tổng sau dự phòng khác thành phần
trước dự phòng; số phải nộp khác số đã nộp; bình quân cần đủ đầu/cuối; LNST trong kỳ khác số dư
LNST chưa phân phối; dòng tổng lưu chuyển tiền khác dòng thu/chi riêng. Câu hỏi quyết định vai trò.
EO.formula là gợi ý, có thể sửa theo câu hỏi. Bảng tra cũng chỉ là tham khảo; phải dùng đủ
thành phần/kỳ. Bình quân và thay đổi cần các số gốc, không gán một ô cuối kỳ làm bình quân.
Nếu scale_basis=raw_source_unresolved, scale 1 chỉ giữ số gốc, chưa xác định đơn vị/scale.
Không suy đơn vị VND; chỉ dùng số như vậy khi phép tính không cần quy đổi hoặc nguồn đủ căn cứ.
Nếu thiếu một dòng quyết định sau khi kiểm các mã đã cấp, không thay bằng đại lượng gần giống.
Báo missing gồm query ngắn chỉ tiêu + kỳ/cột + alias filing + bảng cần tìm và lý do;
expression rỗng nếu không đủ các đại lượng để lập phép tính. Nếu expression vẫn hợp lệ, đừng
báo thiếu chỉ vì phản hồi lượt trước; verifier sẽ kiểm proof theo câu hỏi.
Nếu đủ dữ kiện, missing=[]; không báo thiếu chỉ vì mã đã cung cấp chưa có kỳ chuẩn hóa.
Khi recovery, sửa cụ thể dựa trên proof/feedback trước và các mã đang cấp, không lặp lời giải sai.
"""
)

DIRECT_NR_VERIFICATION = """
Bạn kiểm chứng một proof số học. Câu hỏi gốc là yêu cầu, EO chỉ là kế hoạch có thể sai.
Trước khi duyệt, đối chiếu NGUỒN của từng toán hạng với câu hỏi: năm filing (khác năm cột),
bảng/trang, chỉ tiêu/dòng thực tế, kỳ/cột, dấu và đơn vị. Không suy nguồn từ tên EO hoặc số cuối.
Nếu yêu cầu một BCTC cụ thể, cột so sánh phải thuộc filing đó; hai báo cáo có thể ghi cùng năm
nhưng khác số. Nếu câu hỏi yêu cầu B03, số dư B01 không chứng minh dòng điều chỉnh B03.
Đọc EO.needs và formula để xác định các vai trò theo câu hỏi (không mặc định EO đúng).
Với từng mã: intended_role là ý định của Reasoning, không phải bằng chứng; so với nhãn/cột
thực tế, nearby_rows nếu có, và expression. Phải phân biệt tổng thuần với dòng thành phần,
số đã nộp với số phải nộp, lưu chuyển tiền thuần với riêng dòng thu/chi và bình quân với một số dư.
Đừng gọi dòng sai bằng tên vai trò đúng. Kiểm đủ thành phần/kỳ/dấu/mẫu số và đơn vị kết quả.
Nếu missing cùng expression, kiểm bằng chứng thực: supported nếu phép tính đã đủ, không duyệt
đại lượng thay thế khi còn thiếu dữ kiện quyết định.
Không tính lại Calculator. Chấp nhận nguồn tương đương nếu câu hỏi không giới hạn bảng và
nhãn, kỳ, đơn vị thật chứng minh được. Nếu metadata kỳ rỗng, đọc tiêu đề và cột gốc;
scale_basis=raw_source_unresolved nghĩa là đơn vị/scale chưa chuẩn hóa, chỉ duyệt nếu nguồn
xác định được hoặc phép tính bất biến với scale. Không mặc định VND.
Trả supported chỉ khi đủ căn cứ: basis nêu ngắn các dòng/kỳ/filing quyết định, query rỗng.
Nếu proof dùng dòng/filing/kỳ sai hoặc công thức thiếu/sai, trả incorrect, basis nêu mâu thuẫn
cụ thể giữa yêu cầu và dòng đã chọn; query ngắn mô tả nguồn đúng cần dùng nếu cần.
Nếu không thể chứng minh vì proof thiếu dữ kiện, trả missing, basis và query chỉ rõ dòng/kỳ/filing/bảng.
Bạn chỉ thấy các toán hạng của proof, KHÔNG biết toàn bộ mã Reasoning đã được cấp. Không kết luận
rằng Evidence không có nguồn thay thế. Reasoning sẽ kiểm lại các mã trước khi tìm thêm.
Không Gold, không chép ID từng ô/EO/proof. Không bác proof chỉ vì candidate từng báo thiếu.
"""


def display_value(value, unit):
    text = f"{Decimal(value):,f}".translate(str.maketrans(".,", ",."))
    return f"{text} {unit}".strip()


class EvidenceObligationAgent:
    def __init__(self, gateway, workspace, question, request_id, filing=None, formula_guide=True):
        self.gateway, self.workspace = gateway, workspace
        self.question, self.request_id = question, request_id
        self.resolution = workspace.resolver.shortlist(question, filing)
        self.obligations, self.proofs = {}, {}
        self.events, self.candidates, self.context = [], [], []
        self.visible, self.searched = set(), set()
        self.calls = self.recovery_rounds = 0
        self.route = None
        self.handoffs = []
        self.choices = {}
        self.verifier_target = None
        self.formula_guide = formula_guide
        self.evidence_before_answer = {}
        self.mh_choices = {}

    def call(self, role, prompt, content, schema=None):
        self.calls += 1
        response = self.gateway.generate(
            LLMRequest(
                contract_version="llm_gateway_v1",
                request_id=f"{self.request_id}-{self.calls}-{role}",
                model={"provider": "openai", "model": MODEL},
                messages=[
                    Message(role="system", content=prompt),
                    Message(role="user", content=content),
                ],
                generation=GenerationParameters(temperature=0, max_output_tokens=1500),
                output_spec=OutputSpec(format="json", json_schema=schema)
                if schema
                else OutputSpec(format="text"),
            )
        )
        self.events.append(
            dict(
                event="model",
                role=role,
                status=response.status,
                issue=response.error.code if response.error else None,
            )
        )
        if response.status != "success":
            return {} if schema else ""
        return response.output.payload if schema else response.output.text

    def mh_guide(self, queries):
        rows = {
            i: line
            for i, line in enumerate(
                Path(__file__)
                .with_name("MH_EVIDENCE_GUIDE.md")
                .read_text(encoding="utf-8-sig")
                .splitlines()
            )
            if line.startswith("| ") and not line.startswith(("| Dạng hỏi", "| ---"))
        }
        hits = rank_search_candidates(rows, queries, top_k=2)[:2]
        return "\n".join(rows[i] for i in hits)

    def initialize(self):
        fixed, options = self.resolution["selected"], self.resolution["options"]
        if not options:
            return
        proposal = self.call(
            "coordinator",
            COORDINATOR
            + "\nMẫu nối nguồn tham khảo CHỈ nếu route MH (câu hỏi quyết định):\n"
            + self.mh_guide([self.question]),
            dump(
                dict(
                    question=self.question,
                    fixed=fixed,
                    options={k: options[k] for k in fixed} if fixed else options,
                )
            ),
            PLAN,
        )
        self.route = proposal.get("route")
        if self.route not in {"SH", "MH", "NR"}:
            return
        goals = proposal.get("obligations") or []
        if self.route == "MH" and goals and all(g.get("result") == "calculation" for g in goals):
            self.events.append(dict(event="calculation_route", coordinator_route="MH", route="NR"))
            self.route = "NR"
        selected = fixed or [alias for alias in proposal.get("filings", []) if alias in options]
        reason = "metadata_match" if fixed else "coordinator"
        if not selected and proposal.get("obligations"):
            selected = self.workspace.resolver.from_plan(self.resolution, proposal["obligations"])
            reason = "plan_issuer" if selected else "coordinator_resolution"
            if not selected:
                resolution = self.call(
                    "coordinator",
                    "Chọn filing từ options theo người lập báo cáo và năm được hỏi. "
                    "Chỉ trả alias cần đọc trong filings, giữ route hiện tại và đặt obligations rỗng.",
                    dump(
                        dict(
                            question=self.question,
                            obligations=proposal["obligations"],
                            route=self.route,
                            options=options,
                        )
                    ),
                    PLAN,
                )
                selected = [alias for alias in resolution.get("filings", []) if alias in options]
        self.workspace.select(selected)
        requested = set(self.resolution["scope_hints"])
        if len(requested) == 1 and not self.resolution["override"]:
            selected = [
                alias
                for alias, info in self.workspace.filings_context().items()
                if info["source_scope"] not in {"separate", "consolidated"}
                or info["source_scope"] in requested
            ]
            self.workspace.select(selected)
        selected = self.workspace.active
        self.resolution.update(selected=selected, reason=reason)
        self.events.append(dict(event="filing_selection", filing=selected, reason=reason))
        if not selected:
            return
        goals = proposal.get("obligations") or []
        if not goals or (self.route != "NR" and any(not g.get("requirements") for g in goals)):
            self.events.append(
                dict(
                    event="plan_requirements_missing",
                    reason="Không có EO hoặc thiếu nghĩa vụ bằng chứng.",
                )
            )
            return
        if self.route in {"SH", "NR"}:
            units = {g.get("result_unit", "") for g in goals} - {""}
            goals = [
                dict(
                    goal=self.question,
                    needs=list(dict.fromkeys(n for g in goals for n in g["needs"])),
                    requirements=[req for g in goals for req in g.get("requirements", [])],
                    result="calculation" if self.route == "NR" else "evidence",
                    result_unit=next(iter(units)) if len(units) == 1 else "",
                    formula=" · ".join(
                        dict.fromkeys(g.get("formula", "") for g in goals if g.get("formula"))
                    ),
                )
            ]
        if self.route in {"SH", "NR"} and len(goals) == 1:
            parts = goals[0]["requirements"]
            if not parts:
                self.events.append(
                    dict(
                        event="plan_requirements_missing",
                        reason="EO hợp nhất không có nghĩa vụ bằng chứng.",
                        needs=goals[0]["needs"],
                    )
                )
                return
            sections = list(dict.fromkeys(r["section"] for r in parts if r["section"]))
            goals[0]["requirements"] = [
                dict(
                    description=self.question,
                    # NR source scope comes from the one resolved filing list; operand periods
                    # live in needs/formula, not a second contradictory list of filings.
                    filings=list(selected)
                    if self.route == "NR"
                    else list(dict.fromkeys(f for r in parts for f in r["filings"])),
                    section=sections[0] if len(sections) == 1 else "",
                )
            ]
        if self.route == "MH":
            evidence = [g for g in goals if g.get("result", "evidence") == "evidence"]
            if evidence:
                calculations = [g for g in goals if g.get("result") == "calculation"]
                parts = list(
                    {dump(req): req for g in evidence for req in g["requirements"]}.values()
                )
                if not calculations:
                    # Original question is the neutral full relation; don't turn A-or-B into two mandatory assertions.
                    parts = [dict(description=self.question, filings=list(selected), section="")]
                goals = [
                    dict(
                        goal=self.question
                        if not calculations
                        else " · ".join(g["goal"] for g in evidence),
                        needs=list(dict.fromkeys(n for g in evidence for n in g["needs"])),
                        requirements=parts,
                        reading_plan=[
                            {field: g[field] for field in ("goal", "needs", "requirements")}
                            for g in evidence
                        ],
                        result="evidence",
                        result_unit="",
                        formula="",
                    ),
                    *calculations,
                ]
        self.events.append(dict(event="route", route=self.route, plan=goals))
        for index, goal in enumerate(goals[:3], 1):
            self.obligations[index] = dict(
                id=index,
                goal=self.question if len(goals) == 1 else goal["goal"],
                result=goal.get("result", "evidence"),
                result_unit=goal.get("result_unit", ""),
                formula=goal.get("formula", ""),
                needs=list(dict.fromkeys(goal["needs"][:6])),
                requirements=goal["requirements"],
                verified_requirements=[],
                retrieved=[],
                delivered=[],
                status="open",
                reason="",
                support=[],
                proof=None,
                verified_claims=[],
                **({"reading_plan": goal["reading_plan"]} if goal.get("reading_plan") else {}),
            )

    def acquire(self, demands, phase, budget, seeded=None):
        groups = []
        if self.route == "NR" and phase == "initial":
            key = demands[0][0]
            section = self.obligations[key]["requirements"][0]["section"]
            if section:
                query = " ".join([section, *self.obligations[key]["needs"]])
                for source in self.workspace.section_tables(section, query):
                    body, shown = self.workspace.render(
                        source, query, min(budget, 8000), self.visible
                    )
                    if not shown or len(body) > budget:
                        continue
                    new = [item for item in shown if item not in self.visible]
                    if not new:
                        continue
                    self.context.append(body)
                    self.visible.update(new)
                    self.obligations[key]["retrieved"].append(source)
                    self.obligations[key]["delivered"].extend(new)
                    self.events.append(
                        dict(
                            event="context",
                            eo=key,
                            query=query,
                            evidence=new,
                            phase=phase,
                            priority="section",
                        )
                    )
                    budget -= len(body) + 2
        for key, query in demands:
            normalized = normalize_search(query)
            if not normalized or (phase == "initial" and (key, normalized) in self.searched):
                continue
            self.searched.add((key, normalized))
            requested = (
                [
                    self.workspace.base_id(source)
                    for source in source_ids(query)
                    if self.workspace.base_id(source) in self.workspace.entries
                    and not self.workspace.was_shown(source, self.visible)
                ]
                if phase != "initial"
                else []
            )
            aliases = [
                alias
                for alias in self.workspace.active
                if phase == "before_answer"
                and re.search(rf"(?<!\w){re.escape(alias)}(?!\w)", query)
            ]
            ids = list(dict.fromkeys(requested)) or self.workspace.search(
                query[:500], **({"alias": aliases[0]} if len(aliases) == 1 else {})
            )
            if seeded and (key, query) in seeded:
                seeds = seeded[key, query]
                ids = list(dict.fromkeys([*ids[:2], *seeds, *ids[2:]]))
            self.obligations[key]["retrieved"].extend(ids)
            self.events.append(
                dict(event="retrieval", eo=key, query=query, evidence=ids, phase=phase)
            )
            unopened = (
                [item for item in ids if item not in self.visible] if phase != "initial" else ids
            )
            docs = [item for item in unopened if not item.startswith("F")]
            facts = [item for item in unopened if item.startswith("F")]
            groups.append((key, query, [*(docs if phase != "initial" else docs[:4]), *facts[:1]]))
        added = []
        for rank in range(max((len(ids) for _, _, ids in groups), default=0)):
            for key, query, ids in groups:
                if rank >= len(ids):
                    continue
                source = ids[rank]
                if source in self.visible:
                    self.obligations[key]["delivered"].append(source)
                    continue
                limit = min(budget, max(3500, 9000 - 750 * len(groups)))
                if limit < 450:
                    continue
                body, shown = self.workspace.render(source, query, limit, self.visible)
                if len(body) > limit or not (
                    new := [item for item in shown if item not in self.visible]
                ):
                    continue
                self.visible.update(new)
                self.obligations[key]["delivered"].extend(new)
                self.events.append(
                    dict(
                        event="context",
                        eo=key,
                        query=query,
                        evidence=new,
                        phase=phase,
                        linked_paragraphs=[
                            i for i in new if source.startswith("T") and i.startswith("D")
                        ],
                    )
                )
                added.append(body)
                budget -= len(body) + 2
        self.context.extend(added)
        return bool(added)

    def context_message(self, active, grouped=False):
        return (
            dump(
                dict(
                    question=self.question,
                    filings=self.workspace.filings_context(),
                    obligations=[
                        {
                            field: self.obligations[key].get(field, "evidence")
                            for field in (
                                "id",
                                "goal",
                                "needs",
                                "result",
                                "result_unit",
                                "formula",
                                "requirements",
                                "verified_requirements",
                            )
                        }
                        | (
                            {"reading_plan": self.obligations[key]["reading_plan"]}
                            if self.obligations[key].get("reading_plan")
                            else {}
                        )
                        for key in active
                    ],
                    active=active,
                    route=self.route,
                    verified={
                        k: (
                            [
                                dict(answer=c["answer"], sources=self.mh_choice_refs(c))
                                for c in e["verified_claims"]
                            ]
                            if self.route == "MH"
                            else e.get("verified_claims", [])
                        )
                        for k, e in self.obligations.items()
                        if e.get("verified_claims")
                    },
                    handoffs=self.handoffs,
                )
            )
            + (self.mh_claim_context(active) if grouped and self.route == "MH" else "")
            + (
                "\n\nCác nguồn của báo cáo (context rộng):\n"
                if grouped and self.route == "MH"
                else "\n\nCác nguồn của báo cáo:\n"
            )
            + "\n\n".join(self.mh_context() if self.route == "MH" else self.context)
        )

    def guide_excerpt(self, calculations):
        """Retrieve a small excerpt, not a deterministic formula decision."""
        lines = (
            Path(__file__)
            .with_name("NR_FORMULA_GUIDE.md")
            .read_text(encoding="utf-8-sig")
            .splitlines()
        )
        rows = {
            i: line
            for i, line in enumerate(lines)
            if line.startswith("| ")
            and not line.startswith("| ---")
            and not line.startswith(("| Dạng hỏi |", "| Chỉ tiêu |"))
        }
        queries = [
            self.question,
            *[self.obligations[e].get("formula", "") for e in sorted(calculations)],
        ]
        hits = rank_search_candidates(rows, queries, top_k=2)[:3]
        if not hits:
            return ""
        conventions = {i: line for i, line in enumerate(lines) if line.startswith("- ")}
        base = list(conventions)[:2]
        related = rank_search_candidates(conventions, [*queries, *[rows[i] for i in hits]], top_k=2)
        return "\n".join(
            [
                *(conventions[i] for i in dict.fromkeys([*base, *related[:2]])),
                *(rows[i] for i in hits),
            ]
        )

    def mh_guide_for(self, active):
        return self.mh_guide(
            [
                self.question,
                *[
                    q
                    for e in active
                    for q in (
                        self.obligations[e]["goal"],
                        *self.obligations[e]["needs"],
                        *(r["description"] for r in self.obligations[e]["requirements"]),
                        *(
                            r["description"]
                            for g in self.obligations[e].get("reading_plan", [])
                            for r in g["requirements"]
                        ),
                    )
                ],
            ]
        )

    def mh_context(self):
        """Number the actual displayed chunks/rows; internal IDs stay bound to their coordinates."""
        reverse = {ref: index for index, ref in self.mh_choices.items()}

        def mark(match):
            ref = match[0].strip("[]")
            if self.workspace.base_id(
                ref
            ) not in self.workspace.entries or not self.workspace.was_shown(ref, self.visible):
                return "Bảng trích" if not match[0].startswith("[") else ""
            if ref not in reverse:
                index = len(self.mh_choices) + 1
                reverse[ref] = index
                self.mh_choices[index] = ref
            return f"[#{reverse[ref]}]"

        pattern = r"(?m)^[TDF]\d+(?= \|)|\[(?:T\d+R\d+|[DF]\d+)\]"
        return [
            re.sub(r"\[T\d+R\d+C\d+\] ", "", re.sub(pattern, mark, chunk)) for chunk in self.context
        ]

    def mh_choice_refs(self, item):
        reverse = {ref: n for n, ref in self.mh_choices.items()}
        return list(
            dict.fromkeys(reverse[c["id"]] for c in item["citations"] if c["id"] in reverse)
        )

    def mh_claim_context(self, active):
        """Group only already rendered evidence; broad context stays intact."""
        chunks = self.mh_context()
        choices = {
            i: {int(n) for n in re.findall(r"\[#(\d+)\]", body)} for i, body in enumerate(chunks)
        }
        refs = {i: {self.mh_choices[n] for n in ns} for i, ns in choices.items()}
        context_events = [e for e in self.events if e["event"] == "context"]
        initial = {k for e in context_events if e["phase"] == "initial" for k in e["evidence"]}
        legs = [
            leg
            for check in self.evidence_before_answer.get("checks", [])
            for leg in check.get("decision", {}).get("legs", [])
            if leg["eo"] in active or len(active) == 1
        ]
        # The recovery query also belongs to its requested leg, not a new evidence source.
        legs.extend(
            dict(
                requirement=h["reason"],
                query=h["query"],
                link_value=h["value"],
                link_choice=next(
                    (n for n, ref in self.mh_choices.items() if ref == h["source"]["id"]), 0
                ),
            )
            for h in self.handoffs
            if h.get("phase") == "verification" and h["eo"] in active
        )
        legs.extend(
            dict(requirement=e["query"], query=e["query"], link_value="", link_choice=0)
            for e in self.events
            if e["event"] == "retrieval"
            and e["phase"] == "verification"
            and e["eo"] in active
            and not any(leg["query"] == e["query"] for leg in legs)
        )
        legs.extend(
            dict(requirement=r["description"], query=r["description"], link_value="", link_choice=0)
            for key in active
            if not self.obligations[key].get("reading_plan")
            for r in self.obligations[key]["requirements"]
        )
        legs.extend(
            dict(
                requirement=r["description"],
                query=" ".join([r["description"], r["section"], *r["filings"]]),
                filings=r["filings"],
                link_value="",
                link_choice=0,
            )
            for key in active
            for g in self.obligations[key].get("reading_plan", [])
            for r in g["requirements"]
        )
        groups = []
        for leg in legs:
            requirement, query = leg["requirement"], leg["query"]
            if not requirement.strip() or any(
                g["requirement"] == requirement
                and g["query"] == query
                and g.get("filings", []) == leg.get("filings", [])
                for g in groups
            ):
                continue
            related = {
                k
                for e in context_events
                if e["phase"] != "initial"
                and normalize_search(query)
                and normalize_search(query) in normalize_search(e["query"])
                for k in e["evidence"]
            }

            def intersects(i, keys):
                return any(ref in keys or self.workspace.base_id(ref) in keys for ref in refs[i])

            texts = {i: body for i, body in enumerate(chunks) if choices[i]}
            filings = leg.get("filings", [])
            scoped = {
                i: body
                for i, body in texts.items()
                if any(
                    self.workspace.entries[self.workspace.base_id(ref)]["view"]["filing"] in filings
                    for ref in refs[i]
                )
            }
            if scoped:
                texts = scoped
            queries = [query, requirement]
            old = {i: body for i, body in texts.items() if intersects(i, initial)}
            new = {i: body for i, body in texts.items() if intersects(i, related)}
            if not new and not related:
                new = {i: body for i, body in texts.items() if not intersects(i, initial)}
            link = next(
                (
                    h
                    for h in self.handoffs
                    if h["value"] == leg["link_value"] and h["reason"] == requirement
                ),
                None,
            )
            anchor_choice = next(
                (n for n, ref in self.mh_choices.items() if link and ref == link["source"]["id"]),
                0,
            )
            anchor = [i for i, ns in choices.items() if anchor_choice in ns][:1]
            picked = list(
                dict.fromkeys(
                    [
                        *anchor,
                        *rank_search_candidates(new, queries, top_k=2)[:2],
                        *rank_search_candidates(old or texts, queries, top_k=2)[:2],
                    ]
                )
            )[:4]
            options = []
            for i in picked:
                body = chunks[i]
                lines = body.splitlines()
                # Keep table title, surrounding notes and column headers; rank actual displayed
                # rows for this short view. The unabridged table is still below.
                row_lines = {
                    j: line
                    for j, line in enumerate(lines)
                    if (m := re.match(r"^\[#(\d+)\]", line))
                    and re.fullmatch(r"T\d+R\d+", self.mh_choices[int(m[1])])
                }
                if len(row_lines) > 8:
                    hit = rank_search_candidates(row_lines, queries, top_k=5)[:5]
                    keep = set(hit)
                    if anchor_choice:
                        keep.update(
                            j
                            for j, line in row_lines.items()
                            if line.startswith(f"[#{anchor_choice}]")
                        )
                    body = (
                        "\n".join(
                            line for j, line in enumerate(lines) if j not in row_lines or j in keep
                        )
                        + "\n(Chỉ trích một số hàng; đọc bảng đầy đủ trong context rộng để so sánh/xếp hạng.)"
                    )
                options.append(body)
            groups.append(
                dict(
                    requirement=requirement,
                    query=query,
                    filings=filings,
                    link_value=link["value"] if link else "",
                    link_choice=anchor_choice,
                    options=options,
                )
            )
        self.events.append(dict(event="mh_claim_groups", groups=groups))
        return (
            "\n\nNGUỒN THEO VẾ (gợi ý đọc, không phải đáp án; cùng mã # với context rộng):\n"
            + "\n\n".join(
                f"Vế: {g['requirement']}\nTruy vấn/thuộc tính: {g['query']}\n"
                + (f"Phạm vi báo cáo: {', '.join(g['filings'])}\n" if g["filings"] else "")
                + (
                    f"Dữ kiện nối cần đối chiếu [#{g['link_choice']}]: {g['link_value']}\n"
                    if g["link_choice"] and g["link_value"]
                    else ""
                )
                + "\n\n".join(g["options"])
                for g in groups
            )
        )

    def mh_evidence_preflight(self, active):
        """Execute the guide-directed queries, with at most one dependent substep."""
        state = self.evidence_before_answer
        guide = self.mh_guide_for(active)
        checks = state["checks"]
        for step in range(2):
            content = self.context_message(active)
            content += "\n\nHƯỚNG DẪN NỐI DỮ KIỆN (tham khảo):\n" + guide
            content += "\nCác alias báo cáo khả dụng: " + dump(list(self.resolution["options"]))
            if checks:
                content += "\nĐã truy tiền đề: " + dump(
                    dict(
                        plan=checks[-1]["decision"],
                        executed_queries=checks[-1]["executed_queries"],
                        new_choices=[
                            n
                            for n, ref in self.mh_choices.items()
                            if ref in checks[-1]["added_sources"]
                            or self.workspace.base_id(ref) in checks[-1]["added_sources"]
                        ],
                    )
                )
                content += "\nChọn dữ kiện mới thật để truy vế phụ thuộc; không lặp tiền đề."
            decision = self.call("evidence_join", MH_EVIDENCE_PROMPT, content, MH_EVIDENCE_JOIN)
            actions = {}
            for leg in decision.get("legs", []):
                key = active[0] if len(active) == 1 else leg["eo"]
                query, value = leg["query"].strip(), leg["link_value"].strip()
                ref = self.mh_choices.get(leg["link_choice"], "")
                # Question literals and filing aliases are search scope, not source-derived links.
                if value in self.resolution["options"] or (
                    value and not ref and normalize_search(value) in normalize_search(self.question)
                ):
                    self.events.append(dict(event="handoff_scope_only", value=value, query=query))
                    value, ref = "", ""
                if key not in active or not query or (step and not value):
                    self.events.append(dict(event="join_query_rejected", leg=leg, step=step + 1))
                    continue
                actions.setdefault(key, dict(actions=[]))["actions"].append(
                    dict(
                        eo=key,
                        agent="evidence",
                        query=query,
                        reason=leg["requirement"],
                        link=dict(value=value, source=ref),
                    )
                )
            event = dict(
                step=step + 1,
                guide=guide,
                decision=decision,
                actions=actions,
                visible_before=sorted(self.visible),
                added_sources=[],
                executed_queries=[],
            )
            checks.append(event)
            if not actions:
                break
            before = self.visible.copy()
            start = len(self.events)
            self.recover(actions, phase="before_answer", budget=8500)
            event["added_sources"] = sorted(self.visible - before)
            event["executed_queries"] = [
                e["query"]
                for e in self.events[start:]
                if e["event"] == "retrieval" and e["phase"] == "before_answer"
            ]
            if event["executed_queries"]:
                state["supplement_used"] = True
            if not (decision.get("prerequisite_pending") and event["added_sources"]):
                break
        return "Truy vấn bằng chứng đã thực thi theo từng vế: " + dump(
            [q for c in checks for q in c["executed_queries"]]
        )

    def reasoning(self, active, feedback=""):
        calculations = {e for e in active if self.obligations[e]["result"] == "calculation"}
        prompt, schema = REASONING_PROMPTS[self.route], PROPOSAL
        mh = self.route == "MH"
        if mh:
            prompt, schema = MH_REASONING, MH_PROPOSAL
        if self.route == "NR":
            prompt, schema = DIRECT_NR_REASONING, DIRECT_NR_PROPOSAL
        elif calculations and calculations == set(active):
            prompt, schema = NUMERICAL_PROMPT, NUMERICAL_PROPOSAL
        elif calculations:
            prompt += (
                "\n"
                + NUMERICAL_PROMPT
                + "\nDùng dạng Numerical không có kind cho EO calculation; giữ answer/sources cho EO evidence."
            )
            schema = MH_MIXED_PROPOSAL if mh else MIXED_PROPOSAL
        content = self.context_message(active, grouped=mh)
        mh_guide = self.mh_guide_for(active) if mh else ""
        if mh_guide:
            content += "\n\nHƯỚNG DẪN NỐI DỮ KIỆN (tham khảo):\n" + mh_guide
        if mh:
            self.events.append(
                dict(
                    event="mh_guide_selection",
                    active=active,
                    excerpt=mh_guide,
                    status="selected" if mh_guide else "no_matching_row",
                )
            )
        if calculations:
            if self.route == "NR":
                for ref, operand in self.workspace.direct_operand_choices(self.visible).items():
                    self.choices.setdefault(ref, operand)
            else:
                self.choices = self.workspace.operand_choices(self.visible)
            # IDs already appear in the displayed tables; metadata here makes them selectable.
            content += "\n\nLỰA CHỌN TOÁN HẠNG (ID | filing/trang | nhóm/nhãn | kỳ/cột | giá trị | đơn vị/scale):\n"
            content += "\n".join(
                f"{ref} | {o['filing']}/{o['page']} | {o.get('group') or ''} / {o['label']} | "
                f"{o['period']} / {o['column']} | {o['raw']} | {o['unit']}/{o['scale']}"
                + (f" | {o['scale_basis']}" if self.route == "NR" else "")
                for ref, o in self.choices.items()
            )
        guide = self.guide_excerpt(calculations) if calculations and self.formula_guide else ""
        if guide:
            content += "\n\nBẢNG TRA CÔNG THỨC (mẫu tham khảo, không phải đáp án):\n" + guide
        if feedback:
            content += "\n\nCần xử lý: " + feedback
            if (calculations or mh) and self.candidates:
                previous = self.candidates[-1]
                content += "\nCandidate và verdict lượt trước (sửa lỗi, không chép lại): " + dump(
                    dict(
                        claims=previous["claims"],
                        assessment=previous.get("assessment"),
                        proofs=[
                            self.proofs[b["proof"]]
                            for b in previous.get("bound", [])
                            if b.get("proof")
                        ],
                    )
                )
        wire = self.call("reasoning", prompt, content, schema)
        proposal = dict(wire)
        if schema is DIRECT_NR_PROPOSAL and wire:
            eo = active[0]
            proposal = dict(
                claims=[
                    dict(
                        eo=eo,
                        kind="calculation",
                        answer="",
                        sources=[],
                        operands=[],
                        expression=wire["expression"],
                        unit=wire["unit"],
                        decimals=wire["decimals"],
                        roles=wire.get("roles", []),
                    )
                ]
                if wire["expression"].strip()
                else [],
                missing=[
                    dict(
                        eo=eo,
                        agent="evidence",
                        query=n["query"],
                        reason=n["reason"],
                        link=dict(value="", source=""),
                    )
                    for n in wire["missing"]
                ],
            )
        elif schema is not PROPOSAL and wire:
            proposal["claims"] = [
                c
                if "kind" in c
                else dict(
                    c,
                    eo=next(e for e in active if self.obligations[e]["result"] == "evidence"),
                    kind="answer",
                    operands=[],
                    expression="",
                    unit="",
                    decimals=0,
                )
                if mh and "answer" in c
                else dict(
                    c,
                    kind="calculation",
                    answer="",
                    sources=[],
                    operands=c["operands"],
                )
                for c in wire["claims"]
            ]
        if mh and len(active) == 1:
            for need in proposal.get("missing", []):
                need["eo"] = active[0]
        self.candidates.append(
            dict(
                raw=dump(wire),
                active=active,
                operand_choices=dict(self.choices) if calculations else {},
                guide_excerpt=guide,
                mh_guide_excerpt=mh_guide,
                claims=proposal.get("claims", []),
                missing=proposal.get("missing", []),
            )
        )
        self.events.append(dict(event="candidate", active=active, index=len(self.candidates) - 1))
        return proposal

    def source(self, key):
        if not self.workspace.was_shown(key, self.visible):
            raise ValueError(f"Nguồn {key} chưa được cấp.")
        citation = self.workspace.citation(key, self.workspace.entries)
        filing = self.workspace.filings[citation["filing"]]
        view = self.workspace.entries[self.workspace.base_id(key)]["view"]
        details = dict(
            citation=citation,
            issuer=filing.details["company_name"],
            scope=filing.details["source_scope"],
            title=view.get("title"),
        )
        pointer = citation["pointer"]
        if "/rows/" in pointer and "rows" not in view:
            page = filing.catalog.json_sources[citation["page_sha256"]]
            table_pointer, row_pointer = pointer.split("/rows/", 1)
            table = resolve_pointer(page, table_pointer)
            row_index, _, col_index = row_pointer.partition("/")
            details["title"] = table.get("title")
            details["columns"] = table["columns"]
            details["row"] = table["rows"][int(row_index)]
            if col_index:
                details["column"] = table["columns"][int(col_index)]
        if "rows" in view:
            match = re.fullmatch(r"T[0-9]+R([0-9]+)(?:C([0-9]+))?", key)
            details["columns"] = view["columns"]
            details["preceding_text"] = view["preceding_text"]
            if match:
                details["row"] = view["rows"]["R" + match[1]]
                if match[2]:
                    details["column"] = view["columns"][int(match[2]) - 1]
        if key.startswith("F") or re.fullmatch(r"T[0-9]+R[0-9]+C[0-9]+", key):
            try:
                details["operand"] = self.workspace.operand(key, self.workspace.entries)
            except ValueError as err:
                details["operand_issue"] = str(err)
        return details

    @staticmethod
    def indicator_key(label):
        # Presentation ordinals are not part of the accounting label.
        return re.sub(r"^(?:[ivxlcdm]+|[a-z]|\d+)\s+", "", normalize_search(str(label))).strip()

    @staticmethod
    def period_matches(requested, header, actual):
        wanted = normalize_search(str(requested))
        if not wanted:
            return False
        # Exact displayed header or precise metadata period. A year-only
        # request can match two dates; caller rejects ambiguity before value check.
        h = normalize_search(str(header))
        p = normalize_search(str(actual))
        if wanted == p:
            return True
        date = re.fullmatch(r"(?:tai ngay |ngay )?(\d{1,2}) (\d{1,2}) (\d{4})", wanted)
        if date:
            return p == f"{date[3]} {int(date[2]):02d} {int(date[1]):02d}"
        if re.fullmatch(r"(?:nam )?(?:19|20)\d{2}", wanted):
            year = wanted[-4:]
            return bool(re.search(rf"(?<!\d){year}(?!\d)", p or h))
        return wanted == h or bool(wanted and f" {wanted} " in f" {h} ")

    def bind_operand(self, spec):
        """Resolve explicit source or label/period against already shown evidence."""
        if "group" not in spec:
            return self.bind_legacy_operand(spec)
        selector, label, period = (spec[k].strip() for k in ("source", "indicator", "period"))
        group, filing = spec["group"].strip(), spec["filing"].strip()
        if not label or not period:
            raise ValueError(f"{spec['name']}: cần chỉ tiêu và kỳ/cột được yêu cầu.")
        wanted = self.indicator_key(label)
        exact = bool(re.fullmatch(r"F[0-9]+|T[0-9]+R[0-9]+C[0-9]+", selector))
        coordinates, errors, alternatives = {}, [], []

        def match_label(actual, title=""):
            actual_key = self.indicator_key(actual)
            # A total row in a named note inherits its table indicator, not the components.
            if title:
                title_key = self.indicator_key(title)
                totals = {"tong cong", "cong", "tong"}
                if actual_key in totals or any(
                    actual_key == f"{title_key} {total}" for total in totals
                ):
                    if wanted in {title_key, actual_key, *totals}:
                        return True
            if actual_key == wanted:
                return True

            def aliases(key):
                return {
                    rule.canonical_item_id
                    for rule in ITEM_CATALOG
                    if not rule.requires_source_code
                    and key in {self.indicator_key(a) for a in rule.aliases}
                }

            a, b = aliases(actual_key), aliases(wanted)
            return len(a) == 1 and a == b

        def consider(ref, cell=None):
            if not self.workspace.was_shown(ref, self.visible):
                if exact:
                    errors.append(f"{ref}: chưa cấp nguồn này")
                return
            try:
                src = self.source(ref)
                op = src.get("operand")
                if not op:
                    raise ValueError(src.get("operand_issue", "không phải ô số"))
            except ValueError as err:
                errors.append(f"{ref}: {err}")
                return
            actual_group = (cell or {}).get("group") or self.choices.get(ref, {}).get("group") or ""
            if (
                not match_label(op["label"], src.get("title"))
                or not self.period_matches(period, op["column"], op["period"])
                or (filing and src["citation"]["filing"] != filing)
                or (
                    group
                    and self.indicator_key(group)
                    not in {
                        self.indicator_key(actual_group),
                        self.indicator_key(src.get("title") or ""),
                    }
                )
            ):
                if exact:
                    errors.append(
                        f"{ref}: yêu cầu '{label}', '{period}', '{group}', '{filing}' nhưng nguồn là '{op['label']}', kỳ '{op['period']}', cột '{op['column']}', nhóm '{actual_group}', filing '{src['citation']['filing']}'"
                    )
                return
            coordinates.setdefault(citation_key(src["citation"]), src)
            alternatives.append(
                f"{ref} | {src['citation']['filing']}/trang {src['citation']['page']} | {actual_group}/{op['label']} | {op['period']}/{op['column']} | {op['raw']}"
            )

        if exact:
            base = self.workspace.base_id(selector)
            cell = None
            if base != selector and base in self.workspace.entries:
                view = self.workspace.entries[base]["view"]
                match = re.fullmatch(r"T\d+R(\d+)C(\d+)", selector)
                cell = self.workspace.table_cells(base).get(
                    view["pointer"] + f"/rows/{int(match[1]) - 1}/{int(match[2]) - 1}"
                )
            consider(selector, cell)
        else:
            for base, entry in self.workspace.entries.items():
                view = entry["view"]
                if (selector and selector != base) or (filing and view["filing"] != filing):
                    continue
                if base.startswith("F") and match_label(view.get("label", "")):
                    consider(base)
                if "rows" not in view or not any(
                    self.workspace.was_shown(base + row, self.visible) for row in view["rows"]
                ):
                    continue
                cells = self.workspace.table_cells(base)
                # Include exact EF-EG facts even when table projection omits a cell.
                columns = view["columns"]
                labels = [normalize_search(str(c)) for c in columns]
                label_col = next(
                    (i for i, c in enumerate(labels) if c in {"chi tieu", "tai san", "nguon von"}),
                    1 if labels and labels[0] in {"stt", "so tt"} else 0,
                )
                for row_id, row in view["rows"].items():
                    if not self.workspace.was_shown(base + row_id, self.visible):
                        continue
                    for col, raw in enumerate(row, 1):
                        if (
                            col > len(columns)
                            or col - 1 == label_col
                            or labels[col - 1] in {"ma so", "ms", "tm", "thuyet minh", "stt"}
                            or self.financial_cell(raw)[0] != "number"
                        ):
                            continue
                        pos = view["pointer"] + f"/rows/{int(row_id[1:]) - 1}/{col - 1}"
                        cell = cells.get(pos, {})
                        raw_label = cell.get("label") or (
                            row[label_col] if len(row) > label_col else ""
                        )
                        if not match_label(raw_label, view.get("title")):
                            continue
                        if cell.get("period") and not self.period_matches(
                            period, columns[col - 1], cell["period"]
                        ):
                            continue
                        consider(base + row_id + f"C{col}", cell)
        if len(coordinates) != 1:
            detail = "; ".join(dict.fromkeys(alternatives if coordinates else errors))[:1800]
            issue = (
                "đã có các lựa chọn, hãy chọn đúng bảng/kỳ/filing"
                if coordinates
                else "đã có ô nhưng chưa khớp hoặc chưa phân giải metadata"
                if errors
                else "chưa tìm thấy chỉ tiêu/kỳ trong nguồn đã cấp"
            )
            self.events.append(
                dict(
                    event="operand_unresolved",
                    selection=spec,
                    issue=issue,
                    alternatives=alternatives,
                    errors=errors,
                )
            )
            raise ValueError(f"{spec['name']}: {label} | {period}: {issue}. {detail}")
        found = next(iter(coordinates.values()))
        self.events.append(
            dict(
                event="operand_bound",
                name=spec["name"],
                selection=spec,
                citation=found["citation"],
                period=found["operand"]["period"],
            )
        )
        return found

    def bind_legacy_operand(self, spec):
        """Resolve a model-selected label/period, then validate its copied value."""
        if "indicator" not in spec:
            ref = spec["source"]
            selected = self.choices.get(ref)
            found = self.source(ref)
            op = found.get("operand")
            if not op or (
                selected is not None
                and any(
                    str(op[k]) != str(selected[k]) for k in ("value", "scale", "unit", "period")
                )
            ):
                raise ValueError(f"{ref}: metadata toán hạng không khớp nguồn đã pin.")
            self.events.append(
                dict(
                    event="operand_bound",
                    name=spec["name"],
                    selection=spec,
                    citation=found["citation"],
                    period=op["period"],
                )
            )
            return found
        selector = spec.get("source", "").strip()
        label = spec.get("indicator", "").strip()
        period = spec.get("period", "").strip()
        raw = spec.get("value", "").strip()
        if not label or not period or not raw:
            raise ValueError(f"Biến {spec['name']} cần nhãn chỉ tiêu, kỳ/cột và giá trị gốc.")
        wanted = self.indicator_key(label)
        if not wanted:
            raise ValueError("Nhãn chỉ tiêu rỗng.")
        if selector:
            base = self.workspace.base_id(selector)
            if base not in self.workspace.entries:
                raise ValueError(f"Nguồn {selector} chưa được cấp; dùng ID bảng hoặc fact thật.")
            entries = [(base, self.workspace.entries[base])]
        else:
            entries = list(self.workspace.entries.items())
        coordinates = {}
        errors = []

        def consider(key):
            if not self.workspace.was_shown(key, self.visible):
                return
            try:
                src = self.source(key)
            except ValueError as err:
                errors.append(str(err))
                return
            op = src.get("operand")
            if not op:
                errors.append(f"{key}: {src.get('operand_issue', 'không phải ô số')}")
                return
            if self.indicator_key(op["label"]) != wanted or not self.period_matches(
                period, op.get("column", ""), op.get("period", "")
            ):
                return
            coordinates.setdefault(citation_key(src["citation"]), src)

        for base, entry in entries:
            view = entry["view"]
            if base.startswith("F"):
                if self.indicator_key(view.get("label", "")) == wanted and self.period_matches(
                    period, view.get("column", ""), view.get("period", "")
                ):
                    consider(base)
                continue
            if not base.startswith("T") or "rows" not in view:
                continue
            if selector and re.fullmatch(r"T\d+R\d+C\d+", selector):
                consider(selector)
                continue
            for row_id, row in view["rows"].items():
                if selector and selector != base and selector != base + row_id:
                    continue
                if (
                    not row
                    or self.indicator_key(row[0]) != wanted
                    or not self.workspace.was_shown(base + row_id, self.visible)
                ):
                    continue
                for col, (header, value) in enumerate(zip(view["columns"], row, strict=False), 1):
                    if (
                        col == 1
                        or normalize_search(str(header)) in {"ma so", "ms", "tm", "thuyet minh"}
                        or self.financial_cell(value)[0] != "number"
                    ):
                        continue
                    # Resolve period metadata for numeric cells only; exact
                    # header matching is checked again against the actual operand.
                    key = base + row_id + f"C{col}"
                    consider(key)
        if len(coordinates) != 1:
            detail = "; ".join(errors[:3])
            raise ValueError(
                f"Biến {spec['name']}: nhãn '{label}', kỳ '{period}' xác định {len(coordinates)} tọa độ đã cấp; "
                "hãy chỉ rõ bảng hoặc kỳ/cột, không chọn theo số trùng."
                + (f" Chi tiết: {detail}" if detail else "")
            )
        found = next(iter(coordinates.values()))
        kind, expected = self.financial_cell(raw)
        actual_kind, actual = self.financial_cell(found["operand"]["raw"])
        if kind != "number" or actual_kind != "number" or expected != actual:
            raise ValueError(
                f"Biến {spec['name']} chép giá trị {raw} nhưng nguồn {found['citation']['id']} "
                f"nhãn '{found['operand']['label']}', cột '{found['operand']['column']}' có {found['operand']['raw']}."
            )
        self.events.append(
            dict(
                event="operand_bound",
                name=spec["name"],
                selection=spec,
                citation=found["citation"],
                period=found["operand"]["period"],
            )
        )
        return found

    def mh_sources(self, refs):
        sources, unresolved = {}, []
        legacy = [r for r in refs if isinstance(r, str)]
        choices = [r for r in refs if not isinstance(r, str)]
        for ref in dict.fromkeys(choices):
            try:
                source = self.source(self.mh_choices[ref])
                sources[citation_key(source["citation"])] = source
            except (ValueError, KeyError, IndexError):
                unresolved.append(ref)
        for ref in dict.fromkeys(self.workspace.group_locators(legacy)):
            try:
                matches = self.workspace.resolve(ref, self.visible)
                if not matches:
                    unresolved.append(ref)
                    continue
                for match in matches:
                    source = self.source(match["id"])
                    sources[citation_key(source["citation"])] = source
            except (ValueError, KeyError, IndexError):
                unresolved.append(ref)
        return list(sources.values()), unresolved

    def check_claim(self, claim):
        item = dict(claim=claim, answer="", citations=[], proof=None, issue="", sources=[])
        kind = claim["kind"]
        before_events = len(self.events)
        try:
            if kind == "calculation":
                if self.route == "NR":
                    if not claim["unit"].strip() or not claim["expression"].strip():
                        raise ValueError("Thiếu biểu thức hoặc đơn vị kết quả.")

                    def operand(code):
                        if code not in self.choices:
                            raise ValueError(f"Mã {code} chưa được cấp trong lựa chọn toán hạng.")
                        return self.choices[code]

                    proof = calculate(
                        claim["expression"], operand, self.question, claim["decimals"]
                    )
                    mapping = {code: op["citation"]["id"] for code, op in proof["operands"].items()}
                    resolved = {
                        code: dict(
                            citation=op["citation"],
                            title=op.get("title"),
                            row=op.get("row"),
                            columns=op.get("columns"),
                            column=op.get("column"),
                            operand=op,
                        )
                        for code, op in proof["operands"].items()
                    }
                    unit = claim["unit"].strip()
                else:
                    # Explicit variable-to-source links. Never infer addresses from literals.
                    selections = {v["name"]: v for v in claim["operands"]}
                    if len(selections) != len(claim["operands"]) or not selections:
                        raise ValueError("Tên biến thiếu hoặc trùng.")
                    if not claim["unit"].strip() or not claim["expression"].strip():
                        raise ValueError("Thiếu biểu thức hoặc đơn vị.")
                    if claim["answer"].strip() or claim["sources"]:
                        raise ValueError(
                            "Calculation chỉ dùng operands, expression, unit, decimals."
                        )
                    resolved = {name: self.bind_operand(spec) for name, spec in selections.items()}
                    mapping = {name: src["citation"]["id"] for name, src in resolved.items()}

                    def operand(name):
                        if name not in resolved:
                            raise ValueError(f"Biến {name} chưa được gắn nguồn.")
                        if "operand" not in resolved[name]:
                            raise ValueError(
                                f"Nguồn {mapping[name]}: {resolved[name].get('operand_issue', 'không phải ô số')}"
                            )
                        return resolved[name]["operand"]

                    proof = calculate(
                        claim["expression"], operand, self.question, claim["decimals"]
                    )
                    if set(proof["operands"]) != set(mapping):
                        raise ValueError("Có biến đã khai nhưng không dùng trong biểu thức.")
                    unit = result_unit(
                        claim["expression"],
                        proof["operands"],
                        claim["unit"],
                        self.obligations.get(claim["eo"], {}).get("result_unit", ""),
                    )
                key = f"P{len(self.proofs) + 1}"
                citations = list(
                    {
                        citation_key(op["citation"]): op["citation"]
                        for op in proof["operands"].values()
                    }.values()
                )
                proof.update(
                    id=key,
                    eo=claim["eo"],
                    unit=unit,
                    proposed_unit=claim["unit"],
                    display=display_value(proof["value"], unit),
                    citations=citations,
                    operand_sources=mapping,
                )
                self.proofs[key] = proof
                item.update(
                    proof=key,
                    citations=citations,
                    sources=list(resolved.values()),
                    answer=proof["display"],
                )
                self.events.append(
                    dict(event="calculator", eo=claim["eo"], proof=key, success=True)
                )
            else:
                if self.route == "MH" and kind == "answer":
                    sources, unresolved = self.mh_sources(claim["sources"])
                    item.update(
                        answer=claim["answer"].strip(),
                        sources=sources,
                        citations=[src["citation"] for src in sources],
                    )
                    if unresolved or not sources or not item["answer"]:
                        item["issue"] = (
                            "Nguồn cần làm rõ: " + dump(unresolved)
                            if unresolved
                            else "Thiếu nguồn hoặc kết luận."
                        )
                    return item
                if not claim["sources"] or claim["operands"] or claim["expression"]:
                    raise ValueError("Thiếu nguồn hoặc trường tính toán không phù hợp.")
                refs = list(dict.fromkeys(claim["sources"]))
                sources = [self.source(key) for key in refs]
                item["sources"] = sources
                item["citations"] = list(
                    {citation_key(s["citation"]): s["citation"] for s in sources}.values()
                )
                if kind == "lookup":
                    if len(sources) != 1 or not re.fullmatch(
                        r"F[0-9]+|T[0-9]+R[0-9]+C[0-9]+", claim["sources"][0]
                    ):
                        raise ValueError("Lookup cần một ô/fact chính xác.")
                    if "operand" in sources[0]:
                        op = sources[0]["operand"]
                        item["answer"] = display_value(
                            Decimal(op["value"]) * Decimal(op["scale"]), op["unit"]
                        )
                    elif claim["answer"].strip() and isinstance(
                        sources[0]["citation"]["source_value"], str
                    ):
                        # No guessed period/unit: verifier reads selected cell and surrounding labels.
                        item["answer"] = claim["answer"].strip()
                    else:
                        raise ValueError("Ô chưa đọc được giá trị; cần kiểm lại nguồn.")
                elif kind == "answer" and claim["answer"].strip():
                    item["answer"] = claim["answer"].strip()
                else:
                    raise ValueError("Thiếu kết luận.")
        except (ValueError, KeyError, SyntaxError, IndexError, DecimalException) as err:
            item["issue"] = (
                "Chia cho 0."
                if self.route == "NR" and isinstance(err, DivisionByZero)
                else str(err)
            )
            if kind == "calculation":
                unresolved = next(
                    (
                        e
                        for e in reversed(self.events[before_events:])
                        if e["event"] == "operand_unresolved"
                    ),
                    None,
                )
                if unresolved and unresolved["issue"].startswith("chưa tìm thấy"):
                    spec = unresolved["selection"]
                    item["binding_need"] = dict(
                        eo=claim["eo"],
                        agent="evidence",
                        query=" ".join(
                            filter(
                                None,
                                [spec["indicator"], spec["period"], spec["group"], spec["filing"]],
                            )
                        ),
                        reason=unresolved["issue"],
                        link=dict(value="", source=""),
                    )
                self.events.append(
                    dict(event="calculator", eo=claim["eo"], success=False, issue=str(err))
                )
        return item

    def nr_verification_payload(self, key, proof_id, claim, missing):
        eo, proof = self.obligations[key], self.proofs[proof_id]
        fields = (
            "filing",
            "page",
            "title",
            "group",
            "label",
            "row",
            "columns",
            "column",
            "period",
            "raw",
            "unit",
            "scale",
            "scale_basis",
            "preceding_text",
        )
        roles = {r["code"]: r["purpose"] for r in claim.get("roles", [])}
        operands = {}
        for code, op in proof["operands"].items():
            row = {k: op.get(k) for k in fields}
            row["intended_role"] = roles.get(code, "")
            # Preserve adjacent *shown* rows only; don't infer their business meaning.
            match = re.fullmatch(r"(T\d+)R(\d+)C\d+", code)
            if match:
                table, index = match[1], int(match[2])
                rows = self.workspace.entries[table]["view"]["rows"]
                row["nearby_rows"] = [
                    rows[r]
                    for r in (f"R{index - 1}", f"R{index + 1}")
                    if r in rows and self.workspace.was_shown(table + r, self.visible)
                ]
            operands[code] = row
        return dict(
            question=self.question,
            eo=dict(
                needs=eo["needs"],
                formula=eo["formula"],
                result_unit=eo["result_unit"],
                requirements=[
                    {k: req[k] for k in ("filings", "section")} for req in eo["requirements"]
                ],
            ),
            proof={
                **{k: proof[k] for k in ("expression", "value", "unit", "display")},
                "operands": operands,
            },
            candidate_missing=[{k: n[k] for k in ("query", "reason")} for n in missing],
        )

    def verify(self, proposal, active):
        claims = [c for c in proposal.get("claims", []) if c["eo"] in active]
        bound = [self.check_claim(c) for c in claims]
        if self.route == "MH":
            # Recheck retained claims with revisions, so a corrected claim can supersede an old one.
            for key in active:
                for item in self.obligations[key]["verified_claims"]:
                    same = next(
                        (
                            b
                            for b in bound
                            if b["answer"] == item["answer"] and b["citations"] == item["citations"]
                        ),
                        None,
                    )
                    if same is None:
                        bound.append(dict(item, retained=True))
                    else:
                        same["retained"] = True
        self.candidates[-1]["bound"] = bound
        self.candidates[-1]["answer"] = "\n".join(
            i["answer"] or i["claim"]["answer"] for i in bound
        )
        valid = [(i, b) for i, b in enumerate(bound, 1) if not b["issue"]]
        assessment = {}
        self.verifier_target = (
            dict(eo=active[0], claim=valid[0][0], proof=valid[0][1]["proof"])
            if len(active) == len(bound) == len(valid) == 1 and valid[0][1]["proof"]
            else None
        )
        if self.verifier_target:
            self.events.append(dict(event="verifier_target", **self.verifier_target))
        if self.route == "NR":
            if self.verifier_target:
                assessment = self.call(
                    "verification",
                    DIRECT_NR_VERIFICATION,
                    dump(
                        self.nr_verification_payload(
                            active[0],
                            self.verifier_target["proof"],
                            valid[0][1]["claim"],
                            proposal.get("missing", []),
                        )
                    ),
                    DIRECT_NR_VERDICT,
                )
            self.candidates[-1]["assessment"] = assessment
            return self.aggregate_nr(active[0], proposal, assessment, bound)
        if self.route == "MH":
            if bound or proposal.get("missing"):
                assessment = self.call(
                    "verification",
                    MH_VERIFICATION,
                    dump(
                        dict(
                            question=self.question,
                            route=self.route,
                            obligations=[
                                {
                                    k: self.obligations[e].get(k, "")
                                    for k in (
                                        "id",
                                        "goal",
                                        "result",
                                        "result_unit",
                                        "formula",
                                        "needs",
                                        "requirements",
                                        "verified_requirements",
                                    )
                                }
                                for e in active
                            ],
                            claims=[
                                dict(
                                    index=i,
                                    claim=b["claim"],
                                    tool_answer=b["answer"],
                                    sources=self.mh_choice_refs(b),
                                    issue=b["issue"],
                                    proof=self.proofs.get(b["proof"]),
                                    retained=b.get("retained", False),
                                )
                                for i, b in enumerate(bound, 1)
                            ],
                            missing=proposal.get("missing", []),
                            context_visible=self.mh_context(),
                            unopened=self.unopened(active),
                        )
                    ),
                    MH_ASSESSMENT,
                )
            self.candidates[-1]["assessment"] = assessment
            return self.aggregate_mh(active, proposal, assessment, bound)
        if valid:
            assessment = self.call(
                "verification",
                VERIFICATION,
                dump(
                    dict(
                        question=self.question,
                        route=self.route,
                        obligations=[
                            {
                                k: self.obligations[e].get(k, "")
                                for k in (
                                    "id",
                                    "goal",
                                    "result",
                                    "result_unit",
                                    "formula",
                                    "needs",
                                    "requirements",
                                    "verified_requirements",
                                )
                            }
                            for e in active
                        ],
                        claims=[
                            dict(
                                index=i,
                                claim=b["claim"],
                                tool_answer=b["answer"],
                                sources=b["sources"],
                                proof=self.proofs.get(b["proof"]),
                            )
                            for i, b in valid
                        ],
                        available_choices=[],
                        target=self.verifier_target,
                        missing=proposal.get("missing", []),
                        verified={
                            k: e.get("verified_claims", [])
                            for k, e in self.obligations.items()
                            if e.get("verified_claims")
                        },
                        unopened=self.unopened(active),
                    )
                ),
                ASSESSMENT,
            )
        self.candidates[-1]["assessment"] = assessment
        return self.aggregate(active, proposal, assessment, bound)

    def unopened(self, active):
        return {
            key: [
                dict(
                    id=i,
                    filing=v["filing"],
                    page=v["page"],
                    label=v.get("label") or v.get("title") or v.get("text", "")[:120],
                )
                for i in dict.fromkeys(self.obligations[key]["retrieved"])
                if i in self.workspace.entries and i not in self.visible
                for v in [self.workspace.entries[i]["view"]]
            ][:25]
            for key in active
        }

    @staticmethod
    def headings(source):
        """Exact normalized metadata labels, not a semantic classifier."""
        return {
            normalize_search(line)
            for text in [source.get("title") or "", *source.get("preceding_text", [])]
            for line in text.splitlines()
            if len(normalize_search(line).split()) >= 3
        }

    def proof_issue(self, item):
        proof = self.proofs.get(item.get("proof"))
        if not proof:
            return "Thiếu proof Calculator."
        try:
            operands = proof["operands"]
            replay = calculate(
                proof["expression"], operands.__getitem__, self.question, proof["decimals"]
            )
            if any(replay[k] != proof[k] for k in ("exact", "value", "operands")):
                return "Proof Calculator không replay được."
            if proof["display"] != item["answer"] or proof["display"] != display_value(
                proof["value"], proof["unit"]
            ):
                return "Câu trả lời không phải giá trị proof."
            if {citation_key(v["citation"]) for v in operands.values()} != {
                citation_key(c) for c in item["citations"]
            }:
                return "Citation không khớp toán hạng proof."
            if any(
                not v.get("label") or not v.get("period") or not v.get("unit")
                for v in operands.values()
            ):
                return "Proof thiếu nhãn, kỳ hoặc đơn vị."
        except (KeyError, ValueError, DecimalException, SyntaxError) as err:
            return f"Proof không hợp lệ: {err}"
        return ""

    def scope_issue(self, requirement, items):
        citations = [c for item in items for c in item["citations"]]
        if not citations:
            return "Thiếu nguồn đã pin."
        filings = set(requirement.get("filings", []))
        if filings and any(c["filing"] not in filings for c in citations):
            return "Nguồn nằm ngoài filing được yêu cầu: " + ", ".join(sorted(filings))
        if self.route == "MH":
            # Filing and source pins stay deterministic. The Verifier sees actual table
            # headings, rows and full context; a global title cannot constrain each vế.
            return ""
        # Filing scope is metadata, not the heading of a component table.
        requested = set(self.resolution.get("scope_hints", []))
        actual = {
            info.get("source_scope") or info.get("statement_scope")
            for c in citations
            for info in [self.workspace.filings[c["filing"]].details]
        }
        known = actual & {"consolidated", "separate"}
        if len(requested) == 1 and known - requested:
            return "Nguồn sai phạm vi riêng/hợp nhất của filing được yêu cầu."
        scope_titles = {
            f"{label} {scope}"
            for label in ("bao cao", "bao cao tai chinh", "bctc")
            for scope in ("rieng", "hop nhat")
        }
        # Only a source name actually stated by the user is a release constraint.
        # Names proposed for retrieval are not authoritative.
        question = " " + normalize_search(self.question) + " "
        displayed = set()
        for key, entry in self.workspace.entries.items():
            if key in self.visible or any(v.startswith(key + "R") for v in self.visible):
                displayed.update(self.headings(entry["view"]))
        named = {h for h in displayed if f" {h} " in question}
        section = normalize_search(requirement.get("section", ""))
        if section and f" {section} " in question:
            named.add(section.removeprefix("bang "))
        if len(requested) == 1 and actual == requested:
            named -= scope_titles
        if named:
            selected = set().union(
                *(self.headings(src) for item in items for src in item["sources"])
            )
            selected = {h.removeprefix("bang ") for h in selected}
            named = {h.removeprefix("bang ") for h in named}
            if not any(n == h or f" {n} " in f" {h} " for n in named for h in selected):
                return "Nguồn không khớp tên báo cáo/bảng được chỉ định: " + " / ".join(
                    sorted(named)
                )
        return ""

    @staticmethod
    def financial_cell(raw):
        """Keep a dash, empty cell, and numeric zero distinct."""
        text = str(raw).strip()
        if text in {"-", "–", "—", "−"}:
            return "dash", None
        if not text:
            return "empty", None
        negative = text.startswith("(") and text.endswith(")")
        token = text.strip("()")
        if NUMBER.fullmatch(token):
            try:
                value = number(token)
                return "number", -abs(value) if negative else value
            except DecimalException:
                pass
        return "other", None

    @staticmethod
    def activity_label(label, measure):
        """Canonical accounting row identity, not a list of activities."""
        text = normalize_search(label)
        if not text.startswith(measure + " "):
            return ""
        text = text.removeprefix(measure + " ")
        if measure == "doanh thu":
            text = text.removeprefix("ban ")
        else:
            text = text.removeprefix("hang ban cua ").removeprefix("cua ")
            text = text.removesuffix(" da ban")
        return text.strip()

    def financial_relation(self, item):
        """Evaluate the explicit dash/inequality conditions of the original question.

        Deliberately limited to revenue/COGS rows and explicitly stated operators.
        The LLM still selects the activity and cites the tables; no search for a
        replacement activity or inference from an unmentioned value.
        """
        question = normalize_search(self.question)
        # Only directly stated operators, not a router or general question interpreter.
        dash = (
            "doanh thu" in question
            and "gia von" in question
            and "nam truoc" in question
            and "dau gach" in question
        )
        comparisons = re.findall(
            r"\bdoanh thu (thap hon|nho hon|cao hon|lon hon) gia von nam (\d{4})\b",
            question,
        )
        if not dash and not comparisons:
            return dict(status="not_applicable")
        if item["issue"] or item.get("proof"):
            return dict(status="unresolved", reason=item["issue"] or "Cần claim quan hệ từ bảng.")
        answer = " " + normalize_search(item["answer"]) + " "
        rows = {"doanh thu": {}, "gia von": {}}
        for src in item["sources"]:
            cite = src["citation"]
            raw = cite["source_value"]
            table_rows = (
                raw.get("rows", [])
                if isinstance(raw, dict)
                else [src["row"]]
                if src.get("row")
                else []
            )
            columns = raw.get("columns", []) if isinstance(raw, dict) else src.get("columns", [])
            for row in table_rows:
                if not row:
                    continue
                for measure in rows:
                    obj = self.activity_label(str(row[0]), measure)
                    if obj and f" {obj} " in answer:
                        rows[measure].setdefault(obj, []).append(
                            dict(row=row, columns=columns, citation=cite)
                        )
        shared = set(rows["doanh thu"]) & set(rows["gia von"])
        if len(shared) != 1:
            return dict(
                status="unresolved",
                reason="Chưa xác định duy nhất cùng đối tượng trong hai bảng doanh thu và giá vốn đã dẫn; cần đối chiếu nhãn dòng.",
            )
        obj = next(iter(shared))
        pair = [rows[name][obj] for name in ("doanh thu", "gia von")]
        if any(len(x) != 1 for x in pair):
            return dict(
                status="unresolved",
                reason="Có nhiều dòng cùng đối tượng trong nguồn đã dẫn; cần xác định đúng dòng.",
            )
        revenue, cost = (x[0] for x in pair)
        if revenue["citation"]["filing"] != cost["citation"]["filing"]:
            return dict(
                status="unresolved",
                reason="Hai dòng đối tượng thuộc các filing khác nhau; cần xác định phạm vi so sánh.",
            )
        filing = revenue["citation"]["filing"]
        year = self.workspace.filings_context().get(filing, {}).get("fiscal_year")

        def cell(record, period):
            matches = []
            for idx, column in enumerate(record["columns"]):
                label = normalize_search(str(column))
                years = re.findall(r"\b(?:19|20)\d{2}\b", label)
                value = (
                    int(years[0])
                    if len(years) == 1
                    else (
                        year
                        if "nam nay" in label
                        else year - 1
                        if "nam truoc" in label and year
                        else None
                    )
                )
                if value == period and idx < len(record["row"]):
                    raw = record["row"][idx]
                    kind, n = self.financial_cell(raw)
                    matches.append(
                        dict(
                            source=record["citation"]["id"],
                            filing=filing,
                            row=record["row"][0],
                            column=column,
                            period=period,
                            raw=raw,
                            kind=kind,
                            number=str(n) if n is not None else None,
                        )
                    )
            if len(matches) != 1:
                raise ValueError(
                    f"Chưa xác định duy nhất cột {period} của dòng {record['row'][0]}."
                )
            return matches[0]

        observations = []
        try:
            if dash:
                if not year:
                    raise ValueError("Thiếu kỳ filing để xác định cột năm trước.")
                previous = cell(revenue, year - 1)
                current = cell(revenue, year)
                c = cell(cost, year)
                observations.extend([previous, current, c])
                if previous["kind"] != "dash":
                    raw = previous["raw"] if previous["kind"] != "empty" else "(ô trống)"
                    return dict(
                        status="conflict",
                        observations=observations,
                        reason=f"Điều kiện câu hỏi: doanh thu năm trước phải ghi dấu gạch ngang. "
                        f"Đối tượng đã chọn '{previous['row']}', nguồn {previous['source']}, "
                        f"cột '{previous['column']}' (năm {previous['period']}) thực tế là {raw}, "
                        "không phải dấu gạch. Hãy đối chiếu lại đối tượng từ các bảng đã cấp.",
                    )
                if current["kind"] != "number" or c["kind"] != "number":
                    return dict(
                        status="conflict",
                        observations=observations,
                        reason=f"Điều kiện doanh thu năm nay ghi số và có giá vốn riêng chưa thỏa: "
                        f"{current['row']} = {current['raw']}, {c['row']} = {c['raw']}, năm {year}.",
                    )
            for op, when in comparisons:
                r, c = cell(revenue, int(when)), cell(cost, int(when))
                observations.extend([r, c])
                if r["kind"] != "number" or c["kind"] != "number":
                    return dict(
                        status="unresolved",
                        observations=observations,
                        reason=f"Cần hai số cùng đối tượng và kỳ {when}; nguồn có {r['raw']} và {c['raw']}.",
                    )
                # Match currency units from the pinned table headers; do not compare unlike units.
                if not all("vnd" in normalize_search(str(x["column"])) for x in (r, c)):
                    return dict(
                        status="unresolved",
                        observations=observations,
                        reason="Chưa xác định hai cột so sánh cùng đơn vị VND.",
                    )
                x, y = Decimal(r["number"]), Decimal(c["number"])
                actual = x < y if op in {"thap hon", "nho hon"} else x > y
                if not actual:
                    return dict(
                        status="conflict",
                        observations=observations,
                        reason=f"Điều kiện câu hỏi doanh thu {'nhỏ hơn' if op in {'thap hon', 'nho hon'} else 'lớn hơn'} giá vốn năm {when} không thỏa: "
                        f"{r['source']} {r['row']} = {r['raw']}; {c['source']} {c['row']} = {c['raw']}. Hãy kiểm lại cùng đối tượng.",
                    )
            # Ground explicit currency values in the exact rows/periods just observed.
            values = {Decimal(x["number"]) for x in observations if x["number"] is not None}
            stated = {n for n, u in quantities(item["answer"]) if u == "vnd"}
            if stated - values:
                return dict(
                    status="conflict",
                    observations=observations,
                    reason="Số tiền trong candidate không khớp các dòng/kỳ đối tượng đã đối chiếu: "
                    + ", ".join(str(n) for n in sorted(stated - values)),
                )
        except ValueError as err:
            return dict(status="unresolved", observations=observations, reason=str(err))
        return dict(
            status="pass",
            observations=observations,
            conditions="prior_dash_and_cost" if dash else "explicit_decimal_comparisons",
        )

    def historical_single_issue(self, eo, bound, verdict):
        """Legacy verdicts have no requirement coverage: admit only pinned scalar/proof evidence.

        This is a narrow compatibility path for historical records, never used by a new plan.
        A multi-claim or multi-source narrative cannot establish relationship coverage.
        """
        if len(bound) != 1:
            return "Cần live để xác nhận độ bao phủ từng ý/quan hệ (verdict lịch sử không có coverage)."
        item = bound[0]
        if (
            item["issue"]
            or verdict.get("status") != "supported"
            or not verdict.get("basis", "").strip()
        ):
            return item["issue"] or verdict.get("basis") or "Thiếu verdict supported có căn cứ."
        if not item["citations"]:
            return "Thiếu nguồn pin."
        if item.get("proof"):
            issue = self.proof_issue(item)
            if issue:
                return issue
            proof = self.proofs[item["proof"]]
            if len({c["filing"] for c in item["citations"]}) != 1:
                return "Cần live để xác định phạm vi filing của từng toán hạng; proof lịch sử dùng nhiều báo cáo."
            # Historical basis must actually discuss every bound amount, not just assert supported.
            observed = {n for n, _ in quantities(verdict["basis"])}
            if any(
                Decimal(v["value"]) * Decimal(v["scale"]) not in observed
                for v in proof["operands"].values()
            ):
                return "Cần live để xác nhận đủ các toán hạng trong verdict lịch sử."
            return ""
        if eo["result"] == "calculation" or len(item["citations"]) != 1:
            return (
                "Cần live để xác nhận quan hệ/nguồn của từng ý; verdict lịch sử không có coverage."
            )
        issue = self.scope_issue({}, [item])
        if issue:
            return issue
        # One explicitly unit-bearing value, uniquely present in the already-selected source.
        # Do not invent/refine a citation by searching for a matching number elsewhere.
        amounts = [(n, u) for n, u in quantities(item["answer"]) if u]
        if len(amounts) != 1:
            return "Cần live để xác nhận các ý không phải một giá trị đơn duy nhất."
        value = amounts[0][0]
        raw = item["citations"][0]["source_value"]
        cells = (
            [x for row in raw.get("rows", []) for x in row]
            if isinstance(raw, dict)
            else raw
            if isinstance(raw, list)
            else [raw]
        )
        matches = 0
        for cell in cells:
            token = str(cell).strip()
            negative = token.startswith("(") and token.endswith(")")
            token = token.strip("()")
            if NUMBER.fullmatch(token):
                try:
                    n = number(token)
                    if (-abs(n) if negative else n) == value:
                        matches += 1
                except DecimalException:
                    pass
        if matches != 1:
            return "Cần live để xác định duy nhất giá trị trong nguồn đã chọn."
        return ""

    def aggregate_nr(self, key, proposal, verdict, bound):
        eo = self.obligations[key]
        target = self.verifier_target
        item = bound[target["claim"] - 1] if target else None
        accepted = bool(
            item and item.get("proof") == target["proof"] and verdict.get("status") == "supported"
        )
        actions = []
        reason = (
            ""
            if accepted
            else verdict.get("basis", "")
            or " · ".join(b["issue"] for b in bound if b["issue"])
            or "Chưa có proof được Verifier duyệt."
        )
        if not accepted:
            if not target and proposal.get("missing"):
                actions.extend(proposal["missing"])
            if not actions:
                actions.append(
                    dict(
                        eo=key,
                        agent="reasoning",
                        query=verdict.get("query", ""),
                        reason=reason,
                        link=dict(value="", source=""),
                    )
                )
        coverage = list(range(1, len(eo["requirements"]) + 1)) if accepted else []
        eo.update(
            status="verified" if accepted else "insufficient",
            reason=reason,
            verified_requirements=coverage,
            verified_claims=[item] if accepted else [],
            conclusion=item["answer"] if accepted else "",
            support=item["citations"] if accepted else [],
            proof=item["proof"] if accepted else None,
        )
        self.events.append(
            dict(
                event="verification",
                eo=key,
                status=eo["status"],
                target=target,
                verdict=verdict,
                issue=reason,
                missing=actions,
                coverage=coverage,
                required=list(range(1, len(eo["requirements"]) + 1)),
                candidate_missing_overridden=bool(accepted and proposal.get("missing")),
            )
        )
        return {} if accepted else {key: dict(reason=reason, actions=actions, retained=[])}

    def aggregate_mh(self, active, proposal, assessment, bound):
        pending = {}
        for key in active:
            eo = self.obligations[key]
            required = set(range(1, len(eo["requirements"]) + 1))
            accepted = []
            covered = set()
            checks, issues = [], []
            candidates = {i: b for i, b in enumerate(bound, 1) if b["claim"]["eo"] == key}
            for i, item in candidates.items():
                votes = [v for v in assessment.get("checks", []) if v["claim"] == i]
                vote = votes[0] if len(votes) == 1 else {}
                if item.get("retained") and not (
                    vote.get("status") in {"incorrect", "irrelevant"}
                    and vote.get("basis", "").strip()
                ):
                    disposition = "retained_verified"
                    if (
                        vote.get("status") == "supported"
                        and vote.get("basis", "").strip()
                        and vote.get("sources")
                        and item["claim"]["kind"] == "answer"
                    ):
                        sources, unresolved = self.mh_sources(vote["sources"])
                        if sources and not unresolved:
                            item = dict(
                                item, sources=sources, citations=[s["citation"] for s in sources]
                            )
                            disposition = "retained_rebound"
                    if not any(
                        c["answer"] == item["answer"] and c["citations"] == item["citations"]
                        for c in accepted
                    ):
                        accepted.append(item)
                    covered.update(required & set(vote.get("requirements", [])))
                    checks.append(dict(index=i, verdict=vote, disposition=disposition))
                    continue
                issue = ""
                if vote.get("status") == "irrelevant":
                    checks.append(dict(index=i, verdict=vote, disposition="irrelevant"))
                    continue
                if vote.get("status") != "supported" or not vote.get("basis", "").strip():
                    issue = vote.get("basis") or item["issue"] or "Thiếu verdict cho claim."
                elif item["claim"]["kind"] == "calculation":
                    issue = item["issue"] or self.proof_issue(item)
                elif not item["answer"]:
                    issue = "Thiếu kết luận."
                elif vote.get("sources"):
                    sources, unresolved = self.mh_sources(vote["sources"])
                    if unresolved or not sources:
                        issue = "Verifier chưa xác định được nguồn: " + dump(unresolved)
                    else:
                        item = dict(
                            item,
                            sources=sources,
                            citations=[s["citation"] for s in sources],
                            issue="",
                        )
                elif not item["citations"] or not item["answer"]:
                    issue = item["issue"] or "Thiếu chứng cứ đã pin."
                if issue:
                    # A rejected retained assertion is removed, not an unresolved obligation
                    # when the revised, verified claims independently cover the whole question.
                    if not (item.get("retained") and vote.get("status") == "incorrect"):
                        issues.append(issue)
                else:
                    covered.update(required & set(vote["requirements"]))
                    if not any(
                        c["answer"] == item["answer"] and c["citations"] == item["citations"]
                        for c in accepted
                    ):
                        accepted.append(item)
                checks.append(
                    dict(
                        index=i,
                        verdict=vote,
                        disposition="open" if issue else "verified",
                        issue=issue,
                    )
                )
            completions = [v for v in assessment.get("completion", []) if v["eo"] == key]
            completion = completions[0] if len(completions) == 1 else {}
            complete = completion.get("status") == "complete" and bool(
                completion.get("basis", "").strip()
            )
            needs = [n for n in assessment.get("missing", []) if n["eo"] == key or len(active) == 1]
            # A concrete verifier action overrides the candidate's hypothesis. Otherwise carry
            # forward the candidate's actionable missing evidence unless completion was confirmed.
            if not needs and (not complete or issues):
                needs = [
                    n for n in proposal.get("missing", []) if n["eo"] == key or len(active) == 1
                ]
            needs = [dict(n, eo=key) for n in needs]
            if complete and not issues and not needs and accepted:
                covered = required.copy()
            elif completion:
                covered.clear()
                issues.append(completion.get("basis") or "Verifier chưa xác nhận đủ câu hỏi.")
            elif required - covered:
                # Legacy raw verdict replay: do not fabricate completion from support.
                issues.extend(
                    eo["requirements"][r - 1]["description"] + ": chưa chứng minh đủ."
                    for r in sorted(required - covered)
                )
            if not accepted and not issues:
                issues.append("Chưa có claim đã xác minh.")
            if eo["result"] == "calculation" and not any(i.get("proof") for i in accepted):
                covered.clear()
                issues.append("Thiếu proof Calculator đã xác minh.")
            issues.extend(n["reason"] or n["query"] for n in needs)
            if issues and not needs:
                needs = [
                    dict(
                        eo=key,
                        agent="reasoning",
                        query="",
                        reason=" · ".join(dict.fromkeys(issues)),
                        link=dict(value="", source=""),
                    )
                ]
            status = (
                "verified"
                if accepted and required <= covered and not issues
                else "partial"
                if accepted
                else "insufficient"
            )
            eo.update(
                status=status,
                reason=" · ".join(dict.fromkeys(issues)),
                verified_requirements=sorted(covered),
                verified_claims=accepted,
                conclusion="\n".join(i["answer"] for i in accepted),
                support=list(
                    {citation_key(c): c for i in accepted for c in i["citations"]}.values()
                ),
                proof=next((i["proof"] for i in accepted if i["proof"]), None),
            )
            self.events.append(
                dict(
                    event="verification",
                    eo=key,
                    status=status,
                    checks=checks,
                    issue=eo["reason"],
                    missing=needs,
                    completion=completion,
                    coverage=sorted(covered),
                    required=sorted(required),
                )
            )
            if status != "verified":
                pending[key] = dict(
                    reason=eo["reason"], actions=needs, retained=[i["answer"] for i in accepted]
                )
        return pending

    def aggregate(self, active, proposal, assessment, bound):
        pending = {}
        for key in active:
            eo = self.obligations[key]
            candidates = {i: item for i, item in enumerate(bound, 1) if item["claim"]["eo"] == key}
            accepted = list(eo["verified_claims"])
            covered = set(eo.get("verified_requirements", []))
            trace, issues = [], []
            requirements = eo.get("requirements")
            if requirements is None:
                # Preserve original verdict verbatim; no manufactured coverage for historical traces.
                checks = assessment.get("checks", [])
                verdicts = [v for v in checks if v.get("claim") == next(iter(candidates), 0)]
                verdict = verdicts[0] if len(verdicts) == 1 else {}
                issue = self.historical_single_issue(eo, list(candidates.values()), verdict)
                if issue:
                    issues.append(issue)
                elif not proposal.get("missing") and not assessment.get("missing"):
                    accepted = list(candidates.values())
                    covered = {1}
                else:
                    issues.append("Có dữ kiện còn thiếu trong trace lịch sử.")
                required = {1}
                trace = [
                    dict(
                        index=i,
                        claim=item["claim"],
                        tool=item,
                        verdicts=[v for v in checks if v.get("claim") == i],
                        disposition="verified" if covered else "open",
                        issue=issue,
                    )
                    for i, item in candidates.items()
                ]
            else:
                required = set(range(1, len(requirements) + 1))
                checks = assessment.get("checks", [])
                proposals = {}
                invalid = set()
                source_checks = {
                    i: self.financial_relation(item)
                    for i, item in candidates.items()
                    if not item["issue"]
                }
                for i, result in source_checks.items():
                    if result["status"] != "not_applicable":
                        self.events.append(
                            dict(event="source_condition_check", eo=key, claim=i, **result)
                        )
                    if result["status"] in {"conflict", "unresolved"}:
                        invalid.add(i)
                        issues.append(result["reason"])
                # A whole relation may prove several required ideas even if a
                # supported verdict mentioned only one index. No explicit
                # contradictory/missing verdict is overridden.
                supported = {
                    i
                    for v in checks
                    if v.get("eo") == key
                    and v.get("status") == "supported"
                    and v.get("basis", "").strip()
                    for i in v.get("claims", [])
                }
                relation = [
                    i
                    for i, result in source_checks.items()
                    if result["status"] == "pass" and i in supported
                ]
                for req in sorted(required - covered):
                    verdicts = [
                        v for v in checks if v.get("eo") == key and v.get("requirement") == req
                    ]
                    verdict = verdicts[0] if len(verdicts) == 1 else {}
                    indices = set(verdict.get("claims", []))
                    target = self.verifier_target
                    if (
                        not indices
                        and target
                        and target["eo"] == key
                        and len(verdicts) == 1
                        and verdict.get("status") == "supported"
                        and target["claim"] in candidates
                        and candidates[target["claim"]].get("proof") == target["proof"]
                    ):
                        indices = {target["claim"]}
                        self.events.append(
                            dict(event="verdict_bound_to_target", requirement=req, **target)
                        )
                    if (
                        self.route == "MH"
                        and not indices
                        and len(verdicts) == 1
                        and verdict.get("status") == "supported"
                        and verdict.get("basis", "").strip()
                    ):
                        tagged = [
                            i
                            for i, item in candidates.items()
                            if item["claim"].get("requirement") == req and not item["issue"]
                        ]
                        if len(tagged) == 1:
                            indices = set(tagged)
                            self.events.append(
                                dict(
                                    event="verdict_bound_to_requirement",
                                    eo=key,
                                    requirement=req,
                                    claim=tagged[0],
                                )
                            )
                    items = [candidates[i] for i in indices if i in candidates]
                    issue = ""
                    # Actual table predicate checks can cover a missing index
                    # only for the one whole-answer claim, not arbitrary extra claims.
                    independently_covered = (
                        not verdicts and len(candidates) == 1 and len(relation) == 1
                    )
                    if independently_covered:
                        indices = set(relation)
                        items = [candidates[i] for i in indices]
                        issue = self.scope_issue(requirements[req - 1], items)
                    elif verdict.get("mismatch", "").strip():
                        issue = verdict["mismatch"]
                    elif "required_formula" in verdict and not verdict["required_formula"].strip():
                        issue = "Verifier chưa xác định công thức yêu cầu."
                    elif (
                        len(verdicts) != 1
                        or verdict.get("status") != "supported"
                        or not verdict.get("basis", "").strip()
                    ):
                        issue = verdict.get("basis") or "Thiếu verdict duy nhất có căn cứ."
                    elif (
                        not indices
                        or indices - set(candidates)
                        or any(i["issue"] for i in items)
                        or (
                            self.route == "MH"
                            and any(i["claim"].get("requirement", req) != req for i in items)
                        )
                    ):
                        issue = "Claim thiếu nguồn hợp lệ hoặc không thuộc EO."
                    else:
                        issue = self.scope_issue(requirements[req - 1], items)
                        if not issue:
                            for item in items:
                                if item.get("proof"):
                                    issue = self.proof_issue(item)
                                elif eo["result"] == "calculation":
                                    issue = "Yêu cầu kết quả tính có proof."
                                if issue:
                                    break
                    conflict = next(
                        (
                            source_checks[i]["reason"]
                            for i in indices
                            if i in source_checks
                            and source_checks[i]["status"] in {"conflict", "unresolved"}
                        ),
                        "",
                    )
                    issue = conflict or issue
                    if issue:
                        invalid.update(indices)
                        issues.append(requirements[req - 1]["description"] + ": " + issue)
                    else:
                        proposals[req] = indices
                    trace.append(
                        dict(
                            requirement=req,
                            verdicts=verdicts,
                            claim_indices=sorted(indices),
                            issue=issue,
                            independent_source_coverage=independently_covered and not issue,
                        )
                    )
                # A compound claim touched by a failed requirement is not independently releasable.
                # Propagate through any jointly-supported requirement to avoid releasing half a relation.
                while True:
                    affected = {req for req, idx in proposals.items() if idx & invalid}
                    if not affected:
                        break
                    for req in affected:
                        invalid.update(proposals.pop(req))
                for req, indices in proposals.items():
                    covered.add(req)
                    for i in sorted(indices):
                        item = candidates[i]
                        if not any(
                            c["answer"] == item["answer"] and c["citations"] == item["citations"]
                            for c in accepted
                        ):
                            accepted.append(item)
                for req in sorted(required - covered):
                    label = requirements[req - 1]["description"]
                    if not any(i.startswith(label + ":") for i in issues):
                        issues.append(label + ": chưa có bằng chứng đã xác minh cho toàn ý.")
                if eo["result"] == "calculation" and required - covered:
                    accepted = []
                    covered = set()
            if not required or required - covered or not accepted:
                if not issues:
                    issues.append("Chưa có kết luận được kiểm cho đủ các ý.")
            binding_issues = [item["issue"] for item in candidates.values() if item["issue"]]
            if binding_issues:
                issues.extend(binding_issues)
            # Explicit missing controls recovery, never stands in for coverage.
            needs = [
                n
                for n in [
                    *assessment.get("missing", []),
                    *proposal.get("missing", []),
                    *[i["binding_need"] for i in candidates.values() if i.get("binding_need")],
                ]
                if n["eo"] == key
            ]
            if self.route == "MH" and requirements is not None:
                judged = {
                    v["requirement"] for v in assessment.get("checks", []) if v.get("eo") == key
                }
                if required <= (covered | judged):
                    # Verifier has the actual context and can distinguish missing source vs missing answer.
                    needs = [n for n in assessment.get("missing", []) if n["eo"] == key] + [
                        i["binding_need"] for i in candidates.values() if i.get("binding_need")
                    ]
            direct_conflicts = (
                [r["reason"] for r in source_checks.values() if r["status"] == "conflict"]
                if requirements is not None
                else []
            )
            if direct_conflicts:
                needs = [
                    dict(
                        eo=key,
                        agent="reasoning",
                        query="",
                        reason=" · ".join(dict.fromkeys(direct_conflicts)),
                        link=dict(value="", source=""),
                    )
                ]
            elif binding_issues:
                needs = [n for n in needs if n["agent"] == "evidence" and n["query"].strip()] + [
                    dict(
                        eo=key,
                        agent="reasoning",
                        query="",
                        reason=" · ".join(dict.fromkeys(binding_issues)),
                        link=dict(value="", source=""),
                    )
                ]
            if needs:
                issues += [n["reason"] or n["query"] for n in needs]
            if eo["result"] == "calculation" and (
                issues or not any(i.get("proof") for i in accepted)
            ):
                accepted = []
                covered = set()
                if not issues:
                    issues.append("Thiếu proof đã xác minh.")
            if issues and not needs:
                needs = [
                    dict(
                        eo=key,
                        agent="reasoning",
                        query="",
                        reason=" · ".join(issues),
                        link=dict(value="", source=""),
                    )
                ]
            status = (
                "verified"
                if not issues and required <= covered and accepted
                else "partial"
                if accepted
                else "insufficient"
            )
            eo.update(
                status=status,
                reason=" · ".join(dict.fromkeys(issues)),
                verified_requirements=sorted(covered),
                verified_claims=accepted,
                conclusion="\n".join(i["answer"] for i in accepted),
                support=list(
                    {citation_key(c): c for i in accepted for c in i["citations"]}.values()
                ),
                proof=next((i["proof"] for i in accepted if i["proof"]), None),
            )
            self.events.append(
                dict(
                    event="verification",
                    eo=key,
                    status=status,
                    checks=trace,
                    issue=eo["reason"],
                    missing=needs,
                    coverage=sorted(covered),
                    required=sorted(required),
                    historical=requirements is None,
                )
            )
            if status != "verified":
                pending[key] = dict(
                    reason=eo["reason"], actions=needs, retained=[i["answer"] for i in accepted]
                )
        return pending

    def recover(self, pending, phase="verification", budget=10_000):
        demands, seeded = [], {}
        for key, plan in pending.items():
            for action in plan["actions"]:
                if action["agent"] != "evidence":
                    continue
                query, link = action["query"], action["link"]
                if self.route == "MH" and not query.strip():
                    query = action["reason"]
                if not query.strip():
                    continue
                aliases = []
                if self.route == "NR" or (
                    phase == "before_answer" and not self.resolution["override"]
                ):
                    # Aliases are metadata identifiers supplied by Reasoning, not inferred years.
                    aliases = [
                        alias
                        for alias in self.resolution["options"]
                        if re.search(rf"(?<!\w){re.escape(alias)}(?!\w)", query)
                    ]
                    self.workspace.select([*self.workspace.active, *aliases])
                if link["value"] or link["source"]:
                    try:
                        link_ref = link["source"]
                        matching = []

                        def matches_value(raw, link=link):
                            value = normalize_search(link["value"])
                            if self.route == "MH" and not value:
                                return bool(link["value"].strip()) and link["value"] in raw
                            return bool(link["value"].strip()) and value in normalize_search(raw)

                        if self.route == "MH" and not self.workspace.was_shown(
                            link_ref, self.visible
                        ):
                            matches = self.workspace.resolve(link_ref, self.visible)
                            matching = [
                                c for c in matches if matches_value(dump(c["source_value"]))
                            ]
                            if len(matching) == 1:
                                link_ref = matching[0]["id"]
                            elif not link_ref.strip() and link["value"].strip():
                                # Validate the supplied entity/marker against actual displayed data.
                                # Multiple witnesses are valid for query construction, not a unique graph seed.
                                matching = [
                                    self.workspace.citation(ref, self.workspace.entries)
                                    for ref in sorted(self.visible)
                                    if matches_value(
                                        dump(
                                            self.workspace.citation(ref, self.workspace.entries)[
                                                "source_value"
                                            ]
                                        )
                                    )
                                ]
                                if matching:
                                    link_ref = matching[0]["id"]
                        src = self.source(link_ref)
                        raw = dump(src["citation"]["source_value"])
                        if not matches_value(raw):
                            raise ValueError("Dữ kiện nối không có trong nguồn đã pin.")
                        if not matches_value(query):
                            query = link["value"] + " " + query
                        handoff = dict(
                            eo=key,
                            value=link["value"],
                            source=src["citation"],
                            query=query,
                            reason=action["reason"],
                            phase=phase,
                        )
                        if self.route == "MH":
                            base = self.workspace.base_id(link_ref)
                            filing = self.workspace.filings[src["citation"]["filing"]]
                            try:
                                graph = (
                                    self.workspace.traverse(filing, base)
                                    if link["source"] or len(matching) == 1
                                    else []
                                )
                            except (ValueError, KeyError) as err:
                                graph = []
                                self.events.append(
                                    dict(
                                        event="graph_handoff_issue", source=link_ref, issue=str(err)
                                    )
                                )
                            # Prefer actual discovered sources that match the missing attribute, not arbitrary graph neighbors.
                            texts = {
                                i: dump(self.workspace.entries[i]["view"])
                                for i in graph
                                if i in self.workspace.entries
                                and not self.workspace.was_shown(i, self.visible)
                            }
                            graph = rank_search_candidates(texts, [query], top_k=3) if texts else []
                            handoff["graph_candidates"] = graph
                            if (
                                phase == "before_answer"
                                and (link["source"] or len(matching) == 1)
                                and (not aliases or src["citation"]["filing"] in aliases)
                            ):
                                # A pinned heading, note marker, or entity can point to adjoining
                                # tables/paragraphs. Search actual page neighbours, not a guessed target.
                                neighbours = self.workspace.open_page(
                                    link_ref, self.workspace.entries, radius=1
                                )
                                nearby = {
                                    i: dump(self.workspace.entries[i]["view"])
                                    for i in neighbours
                                    if not self.workspace.was_shown(i, self.visible)
                                }
                                local = (
                                    rank_search_candidates(nearby, [query], top_k=4)
                                    if nearby
                                    else []
                                )
                                # OCR may split a marked note into short consecutive paragraphs;
                                # proximity preserves those even when lexical ranking favors long tables.
                                anchor = int(src["citation"]["pointer"].split("/")[2])
                                adjacent = sorted(
                                    (
                                        i
                                        for i in nearby
                                        if self.workspace.entries[i]["view"]["page"]
                                        == src["citation"]["page"]
                                    ),
                                    key=lambda i: abs(
                                        int(
                                            self.workspace.entries[i]["view"]["pointer"].split("/")[
                                                2
                                            ]
                                        )
                                        - anchor
                                    ),
                                )[:3]
                                handoff["page_candidates"] = list(
                                    dict.fromkeys([*adjacent, *local])
                                )
                                seeded[key, query] = list(
                                    dict.fromkeys([*adjacent, *local, *graph])
                                )
                            else:
                                seeded[key, query] = graph
                        self.handoffs.append(handoff)
                        self.events.append(dict(event="handoff", **handoff))
                    except (ValueError, KeyError) as err:
                        self.events.append(
                            dict(event="handoff_rejected", eo=key, issue=str(err), action=action)
                        )
                        if phase == "before_answer":
                            # Don't search by a model-invented link; preserve the missing leg instead.
                            continue
                        # Legacy recovery searches the requested topic when the optional link is malformed.
                demands.append((key, query))
        if demands:
            if self.route == "MH":
                return self.acquire(demands, phase, budget, seeded=seeded)
            else:
                return self.acquire(demands, phase, budget)

    def prepare(self):
        self.initialize()
        if not self.obligations:
            return
        active = list(self.obligations)
        needs = [(e["id"], n) for e in self.obligations.values() for n in e["needs"]]
        self.acquire([*needs, (active[0], self.question)], "initial", CONTEXT_CHARS)

    def run(self):
        self.prepare()
        return self.run_prepared()

    def run_prepared(self):
        if not self.obligations:
            return self.snapshot()
        active = list(self.obligations)
        self.evidence_before_answer = dict(
            initial_context=list(self.context),
            initial_visible=sorted(self.visible),
            checks=[],
            supplement_used=False,
        )
        feedback = self.mh_evidence_preflight(active) if self.route == "MH" else ""
        self.evidence_before_answer.update(
            answer_context=list(self.context),
            answer_visible=sorted(self.visible),
            answer_payload_context=self.mh_context() if self.route == "MH" else list(self.context),
        )
        return self.run_answer(active, feedback)

    def run_answer(self, active, feedback="", allow_retrieval=True):
        """Run actual answer, verification and bounded repair with already prepared evidence."""
        proposal = self.reasoning(active, feedback)
        pending = self.verify(proposal, active)
        if self.route == "MH":
            search_allowed = allow_retrieval and not self.evidence_before_answer["supplement_used"]
            actions = [a for p in pending.values() for a in p["actions"]]
            reasoning_needed = any(a["agent"] == "reasoning" for a in actions)
            evidence_needed = any(a["agent"] == "evidence" for a in actions)
            repair = bool(pending and (reasoning_needed or (search_allowed and evidence_needed)))
            self.events.append(
                dict(
                    event="mh_repair_decision",
                    triggered=repair,
                    pending=pending,
                    search_allowed=search_allowed,
                    reasoning_needed=reasoning_needed,
                    evidence_needed=evidence_needed,
                    reason=(
                        "no_pending"
                        if not pending
                        else "repair_requested"
                        if repair
                        else "evidence_missing_search_not_available"
                    ),
                )
            )
            if not repair:
                return self.snapshot()
            self.recovery_rounds = 1
            prior = deepcopy(self.obligations)
            prev_sources, prev_proofs = self.visible.copy(), set(self.proofs)
            if search_allowed and evidence_needed:
                self.recover(pending)
            revised = self.reasoning(
                list(pending),
                dump(dict(pending=pending, retrieval_allowed=search_allowed and evidence_needed)),
            )
            if revised:
                self.verify(revised, list(pending))
                if not self.candidates[-1].get("assessment"):
                    self.obligations = prior
                    self.events.append(dict(event="mh_repair_failed", reason="no_valid_verdict"))
            else:
                self.events.append(dict(event="mh_repair_failed", reason="no_valid_revision"))
            self.events.append(
                dict(
                    event="recovery_result",
                    added_sources=sorted(self.visible - prev_sources),
                    added_proofs=sorted(set(self.proofs) - prev_proofs),
                    verified=[k for k in pending if self.obligations[k]["status"] == "verified"],
                )
            )
            return self.snapshot()
        if pending and not self.evidence_before_answer["supplement_used"]:
            self.recovery_rounds = 1
            self.events.append(dict(event="recovery", targets=pending))
            prev_sources, prev_proofs = self.visible.copy(), set(self.proofs)
            self.recover(pending)
            revised = self.reasoning(list(pending), dump(dict(pending=pending)))
            remaining = self.verify(revised, list(pending)) if revised else pending
            if (
                self.route == "NR"
                and remaining
                and revised.get("missing")
                and any(a["agent"] == "reasoning" for p in pending.values() for a in p["actions"])
            ):
                # A supported proof already returned no remaining obligation. Otherwise give
                # Evidence one opportunity, even when the revised candidate had an expression.
                self.events.append(dict(event="recovery_context_gap", missing=revised["missing"]))
                self.recover(
                    {
                        key: dict(actions=[n for n in revised["missing"] if n["eo"] == key])
                        for key in remaining
                    }
                )
                revised = self.reasoning(
                    list(remaining), dump(dict(pending=remaining, missing=revised["missing"]))
                )
                if revised:
                    self.verify(revised, list(remaining))
            self.events.append(
                dict(
                    event="recovery_result",
                    added_sources=sorted(self.visible - prev_sources),
                    added_proofs=sorted(set(self.proofs) - prev_proofs),
                    verified=[k for k in pending if self.obligations[k]["status"] == "verified"],
                )
            )
        return self.snapshot()

    def snapshot(self):
        claims = [c for eo in self.obligations.values() for c in eo.get("verified_claims", [])]
        pending = [
            eo["reason"] or eo["goal"]
            for eo in self.obligations.values()
            if eo["status"] != "verified"
        ]
        citations = list({citation_key(c): c for i in claims for c in i["citations"]}.values())
        index = {citation_key(c): i for i, c in enumerate(citations, 1)}
        answers = []
        for claim in claims:
            text = re.sub(
                r"\[([^\[\]\n]+)\]", lambda m: "" if source_ids(m[1]) else m[0], claim["answer"]
            ).strip()
            tags = "".join(
                f"[{i}]" for i in dict.fromkeys(index[citation_key(c)] for c in claim["citations"])
            )
            answers.append(f"{text} {tags}")
        answer = "\n".join(dict.fromkeys(answers))
        if self.route in {"MH", "NR"} and answer:
            labels = {}
            for claim in claims:
                for src in claim["sources"]:
                    c = src["citation"]
                    labels[citation_key(c)] = f"{c['filing']}, trang {c['page']}" + (
                        f", {src['title']}" if src.get("title") else ""
                    )
            answer += "\nNguồn: " + "; ".join(
                f"[{i}] {labels[citation_key(c)]}" for i, c in enumerate(citations, 1)
            )
        if answer and pending:
            answer += "\nChưa đủ căn cứ cho phần sau: " + " · ".join(pending)
        return dict(
            route=self.route,
            handoffs=self.handoffs,
            status=("partial" if pending else "complete") if claims else "blocked",
            answer=answer,
            citations=citations,
            published_proofs=list(dict.fromkeys(i["proof"] for i in claims if i["proof"])),
            calculator_proofs=list(self.proofs.values()),
            obligations=list(self.obligations.values()),
            candidates=self.candidates,
            events=self.events,
            tool_traces=self.workspace.traces,
            evidence_index={
                key: dict(origin=entry["origin"], **entry["view"])
                for key, entry in self.workspace.entries.items()
            },
            recovery_rounds=self.recovery_rounds,
            evidence_before_answer=self.evidence_before_answer,
            mh_source_choices=self.mh_choices,
            document_resolution=dict(self.resolution, documents=self.workspace.filings_context()),
        )
