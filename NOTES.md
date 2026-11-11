# Ghi chú phân tích · Day 04

Họ và tên: Trương Đặng Minh Khuê
MSSV: 2A202603785

## 1. Case được chọn

- ID case: H6 (H1 cũng bị cùng lỗi)
- Câu trả lời của agent: agent báo trạng thái Actions là operational, rồi liệt kê 3 update của h02n9572mx9y. Một update dẫn link tới incident xr3myzj7ms51 ("combined summary"), nhưng agent không đọc incident đó, nên không trả lời được câu "incident gộp có nêu nguyên nhân hay chỉ mô tả ảnh hưởng"
- Điểm ở lần chạy 1: 55 (H1: 60)

## 2. Bằng chứng trong trace

Dán đoạn trace chứng minh lỗi và nêu nguyên nhân có thể xảy ra.

```text
{'event': 'model', 'step': 1, 'finish': 'tool_calls', 'tool_calls': 2}
{'event': 'tool', 'step': 1, 'name': 'get_status', 'arguments': '{"provider": "github", "component": "actions"}'}
{'event': 'tool', 'step': 1, 'name': 'get_incident_details', 'arguments': '{"provider": "github", "incident_id": "h02n9572mx9y"}'}
   -> result.updates[0].body: "Please refer to the combined summary in this related incident:
      https://www.githubstatus.com/incidents/xr3myzj7ms51"
{'event': 'model', 'step': 2, 'finish': 'stop', 'tool_calls': 0}
{'event': 'final', 'step': 2}
```

grade.mechanical: violations = ['Cần tool calls ở ít nhất 2 model steps khác nhau.'], score_cap = 60

Nguyên nhân có thể là:

- Model gọi cả 2 tool song song trong step 1, vì câu hỏi đã cho sẵn ID. Đến step 2, model thấy link sang xr3myzj7ms51 nhưng vẫn chọn trả lời luôn.
- SYSTEM_PROMPT không có câu nào dặn đọc tiếp incident được dẫn link. Loop cũng không kiểm tra điều này.
- Lỗi nằm ở phần Reason (prompt), cộng thêm việc loop thiếu kiểm tra. Không phải do giới hạn dữ liệu: incident xr3myzj7ms51 có trong snapshot.

## 3. Thay đổi đã thực hiện

- Sửa gì, ở đâu (tất cả trong agent.py, cộng thêm test mới):
  - SYSTEM_PROMPT: thêm hướng dẫn "Nếu update của một incident dẫn tới incident khác (link /incidents/<id>), hãy gọi get_incident_details cho incident đó trước khi trả lời."
  - Thêm linked-incident gate trong run_agent:
    - Sau mỗi lần get_incident_details thành công, \_find_linked_ids() dùng regex /incidents/<id> để tìm incident được dẫn link trong các update.
    - Khi model trả lời cuối mà còn incident được dẫn link chưa đọc: ghi event validation_unread_linked_incident vào trace, thêm lời nhắc (LINKED_REMINDER), rồi gọi model lại.
    - Mỗi incident chỉ được nhắc 1 lần (reminded_ids).
  - Lấy lại evidence gate (yêu cầu kiểm tra nguồn trong tests/test_validation.py): câu trả lời phải chứa ít nhất một URL của incident đã đọc thành công. Nếu không, ghi event validation_missing_source và nhắc model.
  - Test mới tests/test_linked.py gồm 3 test:
    - có nhắc, rồi model đọc tiếp, rồi completed, và chỉ có 1 event final;
    - chỉ nhắc 1 lần;
    - incident không có link thì không nhắc.
- Vì sao chọn thay đổi này:
  - Bằng chứng khách quan: grade.mechanical do code chấm báo vi phạm, không chỉ là nhận xét của judge. Cùng một lỗi xuất hiện ở 2 case (H6, H1).
  - Sửa ở 2 lớp: prompt tác động vào phần Reason, còn gate trong loop đảm bảo bằng code. Lý do: model không phải lúc nào cũng làm theo prompt.
  - Gate chỉ nhắc 1 lần (gate mềm) để không đốt hết max_steps. Hết max_steps là case bị 0 điểm.
  - Thứ tự gate: linked gate chạy trước evidence gate, vì đọc thêm incident có thể sinh thêm URL nguồn.
  - Quan sát khi chạy thử từng case (--case): ở cả H6 và H1, model vẫn trả lời sớm ở step 2 dù prompt đã có hướng dẫn. Chính gate trong loop mới kéo model đọc tiếp ở step 3. Kết quả: H6 55 → 100, H1 60 → 75.

## 4. So sánh hai lần chạy

| Chỉ số                | `eval_before.json`                      | `eval_after.json`                       |
| --------------------- | --------------------------------------- | --------------------------------------- |
| Điểm tổng             | 81.14                                   | 80.68                                   |
| Điểm case đã chọn     | H6: 55 (H1: 60)                         | H6: 80 (H1: 80)                         |
| Số model calls        | 49                                      | 53                                      |
| Token, chi phí nếu có | 40,210 token, ~$0.0100 (chỉ tính agent) | 51,101 token, ~$0.0120 (chỉ tính agent) |

- Lỗi đã giải quyết:
  - H6 và H1 không còn vi phạm "Cần tool calls ở ít nhất 2 model steps".
  - Trace có event validation_unread_linked_incident ở step 2. Model đọc xr3myzj7ms51 ở step 3 rồi trả lời ở step 4.
  - Gate chỉ chạy ở 2 case này. Model calls tăng 49 → 53 (+4, tức 2 step cho mỗi case).
- Lỗi còn lại hoặc mới xuất hiện:
  - Mới, nghi do prompt: H2 100 → 50. Model bỏ get_status, vi phạm "Chưa gọi tool cần thiết: get_status". Lặp lại ở cả 2 lần chạy after. Giả thuyết là câu thêm vào prompt khiến model ưu tiên get_incident_details.
  - Còn lại:
    - kết luận vượt bằng chứng hoặc không nêu giới hạn (A5 = 55, H8 = 55);
    - H1 vẫn thiếu phân tích ảnh hưởng của incident Cloudflare.
  - H7 tăng 60 → 80 dù không có gate chạy, nên không tính là cải tiến của mình.
- Nhận xét:
  - Điểm tổng gần như không đổi (−0.46), vì phần tăng ở H1/H6 bị nhiễu và H2 bù trừ.
  - Muốn đánh giá cải tiến phải so từng case và đọc trace, không chỉ nhìn điểm tổng.

## 5. Giới hạn

- Điểm judge:
  - Judge là openai/gpt-4o-mini, cùng model với agent, nên có thể thiên vị khi tự chấm.
  - Judge là LLM nên có thể chấm sai. Ví dụ E5 (60 điểm): agent đã nêu "components rỗng không đủ để khẳng định", nhưng judge vẫn chấm thấp phần giới hạn.
  - Điểm judge không so sánh được giữa các cấu hình model khác nhau.
- Snapshot:
  - Dữ liệu cố định, lưu ngày 09/11/2026. Không phản ánh tình trạng thực tế hiện tại.
  - Chỉ chứa 50 incident gần nhất mỗi provider.
  - Gate dựa vào regex /incidents/<id>, nên chỉ bắt được link đúng dạng này. Incident được nhắc bằng tên hoặc link rút gọn (stspg.io) thì không bắt được.
- Chạy một lần mỗi phiên bản:
  - LLM có tính ngẫu nhiên. Chạy lại cùng code có thể lệch vài điểm, nên chênh lệch nhỏ ở các case khác có thể chỉ là nhiễu, không phải do cải tiến.
  - Muốn kết luận chắc chắn cần chạy nhiều lần, rồi so sánh trung bình và độ lệch.
- Cải tiến:
  - completed và URL có mặt trong câu trả lời chỉ chứng minh agent đã dẫn nguồn, không chứng minh mọi nhận định đều đúng.
  - Gate tốn thêm model calls: thêm 2 step cho mỗi case có link.
