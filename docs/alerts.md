# Alert và Runbook

Mỗi alert dựa trên triệu chứng người dùng hoặc SLO, không dựa trực tiếp vào tên implementation nội bộ.
Thứ tự điều tra chuẩn luôn là **metrics → logs → correlation_id → trace → span**.

## Alert 1 — High latency (P95)

- **Tên:** `high_latency_p95`
- **Severity:** critical
- **Duration:** 5 phút duy trì liên tục
- **Kênh thông báo:** Slack `#llm-alerts`
- **SLI/SLO liên quan:** SLI `fast_successful_requests` (good = `response_sent and latency_ms <= 3000`), SLO target 99.5%.
- **Điều kiện:** `latency_p95 > 3000ms` trong 5 phút.
- **Ảnh hưởng tới người dùng:** Phản hồi chậm rõ rệt ở nhóm request “đuôi” (tail), người dùng cảm nhận ứng dụng bị treo/lâu trả lời; có thể hết timeout ở phía client.
- **Ba bước kiểm tra đầu tiên:**
  1. Mở dashboard panel Latency, xác nhận P95/P99 tăng và khoảng thời gian bắt đầu tăng.
  2. Lọc `data/logs.jsonl` trong khoảng đó, lấy `correlation_id` của request chậm và ghi lại `latency_ms`.
  3. Mở trace có cùng `correlation_id` trên Langfuse, so sánh thời lượng `retrieval` và `generation` để tìm span chậm.
- **Mitigation tạm thời:** Nếu span `retrieval` chậm, tắt incident `python scripts/inject_incident.py --scenario rag_slow --disable` (practice) hoặc tăng timeout/giảm top-k retrieval; nếu `generation` chậm, giảm `max_tokens`/chuyển model rẻ hơn.
- **Owner:** LLM Platform On-Call.

## Alert 2 — High error rate

- **Tên:** `high_error_rate`
- **Severity:** critical
- **Duration:** 5 phút duy trì liên tục
- **Kênh thông báo:** Slack `#llm-alerts`
- **SLI/SLO liên quan:** Guardrail `error_rate_pct_max = 2%` trong `config/slo.yaml`.
- **Điều kiện:** `error_rate_pct > 2%` trong 5 phút.
- **Ảnh hưởng tới người dùng:** Một phần request bị trả lỗi 5xx, người dùng không nhận được câu trả lời; trải nghiệm gián đoạn.
- **Ba bước kiểm tra đầu tiên:**
  1. Mở dashboard panel Errors, xem `error_rate_pct` và `error_breakdown` (loại lỗi nào đang tăng).
  2. Lọc `data/logs.jsonl` event `request_failed` trong khoảng thời gian đó, lấy `correlation_id` và `error_type`.
  3. Mở trace có cùng `correlation_id`, kiểm tra span nào bị lỗi (ví dụ `retrieval` ném `Vector store timeout`).
- **Mitigation tạm thời:** Nếu là `tool_fail`, tắt `python scripts/inject_incident.py --scenario tool_fail --disable`; nếu là lỗi hạ tầng retrieval, bật fallback answer hoặc circuit breaker cho vector store.
- **Owner:** LLM Platform On-Call.

## Alert 3 — Low quality / retrieval degradation

- **Tên:** `low_quality_or_retrieval_degradation`
- **Severity:** warning
- **Duration:** 10 phút duy trì liên tục
- **Kênh thông báo:** Slack `#llm-alerts`
- **SLI/SLO liên quan:** Guardrail `quality_score_avg_min = 0.75` và `retrieval_success_rate_pct_min = 90%` trong `config/slo.yaml`.
- **Điều kiện:** `quality_score_avg < 0.75` hoặc `retrieval_success_rate_pct < 90%` trong 10 phút.
- **Ảnh hưởng tới người dùng:** Câu trả lời kém đúng/thiếu ngữ cảnh (hoặc retrieval thất bại), giảm độ tin cậy mặc dù hệ thống vẫn trả lời.
- **Ba bước kiểm tra đầu tiên:**
  1. Mở dashboard panel Quality và panel Errors → Retrieval success, xác nhận metric nào vi phạm và từ khi nào.
  2. Lọc `data/logs.jsonl` event `response_sent`, xem `quality_score` thấp và `tool_name/tool_success` tương ứng, lấy `correlation_id`.
  3. Mở trace có cùng `correlation_id`, xem `retrieval` span có `doc_count` bằng 0 hoặc output generation lệch hẳn so với context.
- **Mitigation tạm thời:** Kiểm tra corpus/index retrieval có bị missing/empty không; nếu là regression do prompt, rollback label `production` về version cũ trên Langfuse (xem `docs/PROMPT_VERSIONING.md`).
- **Owner:** LLM Platform On-Call.
