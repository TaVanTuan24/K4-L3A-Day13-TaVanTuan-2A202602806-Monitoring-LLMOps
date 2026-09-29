# Báo cáo cá nhân — K4-L3A Day 13 Monitoring & LLMOps

> Mỗi học viên hoàn thiện một file duy nhất này. Khi dẫn evidence, dùng đường dẫn tương đối, ví dụ `evidence/07-trace-waterfall.png`.

## 1. Thông tin học viên

- **Họ và tên:** (điền)
- **MSSV:** (điền)
- **Lớp:** K4-L3A
- **Repository URL:** (điền)
- **Commit SHA cuối:** (điền)
- **Challenge ID:** Không thực hiện CP3 trong task này.
- **Tên project Langfuse cá nhân:** `day13-k4-l3a-<MSSV>` (điền MSSV)

## 2. Evidence index

Điền đúng đường dẫn tới evidence thực tế. Có thể đổi tên hoặc dùng nhiều ảnh nếu cần.
Các ảnh đánh dấu `TODO` là evidence runtime người dùng phải tự chụp trên Langfuse/terminal.

| Evidence | Đường dẫn |
|---|---|
| Pytest cuối | `evidence/01-pytest.txt` |
| Log validator | `evidence/02-log-validator.txt` |
| Dashboard validator | `evidence/03-dashboard-validator.txt` |
| Structured log | `evidence/04-structured-log.png` |
| PII redaction | `evidence/05-pii-redaction.png` |
| Trace list | `evidence/06-trace-list.png` (TODO: Langfuse UI) |
| Trace waterfall | `evidence/07-trace-waterfall.png` (TODO: Langfuse UI) |
| Trace metadata | `evidence/08-trace-metadata.png` (TODO: Langfuse UI) |
| Prompt versions | `evidence/09-prompt-versions.png` (TODO: Langfuse UI) |
| Prompt rollback | `evidence/10-prompt-rollback.png` (TODO: Langfuse UI) |
| Dashboard runtime | `evidence/11-dashboard-overview.png` |
| Incident metric | `evidence/12-incident-metric.png` |
| Incident log | `evidence/13-incident-log.png` |
| Incident trace | `evidence/14-incident-trace.png` (TODO: Langfuse UI) |

## 3. Kết quả kỹ thuật

| Nội dung | Baseline | Kết quả cuối | Nhận xét |
|---|---|---|---|
| `validate_logs.py` | Chưa đạt (starter TODO) | **100/100** | 21 records, 10 correlation IDs, 0 PII leak, 0 thiếu field |
| `validate_dashboard.py` | 6/6 | **6/6** | Contract `config/dashboard.yaml` giữ nguyên |
| `pytest` | 22 passed | **34 passed** | Thêm 12 test (PII, correlation ID, tracing, dashboard) |
| Số traces hợp lệ | 0 | ≥10 (đã trigger; xác nhận UI) | `load_test.py` gửi 10 request với `tracing_enabled=true` |
| Số PII leak | — | 0 | email/phone/CCCD/credit card đều redact |
| Latency P95 / TTFT P95 | — | 1326 ms / 50 ms | first-request warmup ~1326 ms; steady-state ~151 ms |
| Retrieval success rate | — | 100 % | `tool_success=true` trên mọi `response_sent` |

## 4. Logging và PII

- **Cách tạo/nhận và truyền correlation ID:**
  Middleware `app/middleware.py` gọi `clear_contextvars()` ở đầu mỗi request để tránh context leakage,
  đọc header `x-request-id`, giữ lại khi đúng format `req-<8-hex>` (regex `^req-[0-9a-f]{8}$`),
  ngược lại sinh mới bằng `req-{uuid4().hex[:8]}`. Kết quả được bind qua
  `bind_contextvars(correlation_id=...)`, gán vào `request.state.correlation_id` và trả lại hai header
  `x-request-id` và `x-response-time-ms` (đo bằng `time.perf_counter()`). Mỗi request có context riêng.

- **Các metadata được ghi vào structured log:**
  `ts`, `level`, `event`, `service`, `correlation_id`, `user_id_hash`, `session_id`, `feature`,
  `model`, `env` (bind trong `app/main.py` trước event `request_received`, kế thừa cho
  `response_sent`/`request_failed` qua `merge_contextvars`). `model` lấy từ `agent.model`, `env` từ
  `APP_ENV`, `user_id_hash` từ `hash_user_id()` — không log raw `user_id`.

- **Cách bảo đảm PII được scrub trước khi ghi:**
  Processor `scrub_event` (trong `app/logging_config.py`) đăng ký **trước** `JsonlFileProcessor` và
  `JSONRenderer`, scrub **đệ quy** (dict/list/tuple/string) qua `app/pii.py::scrub_value`, phủ email,
  điện thoại Việt Nam, CCCD 12 số, credit card 16 số (kể cả dấu cách/`-`) thành
  `[REDACTED_EMAIL]`, `[REDACTED_PHONE_VN]`, `[REDACTED_CCCD]`, `[REDACTED_CREDIT_CARD]`.

- **Cách kiểm chứng kết quả:**
  `python scripts/validate_logs.py` báo `100/100`, `Potential PII leaks detected: 0`; log thực tế có
  `message_preview` đã redact (vd `My email is [REDACTED_EMAIL]`).

## 5. Tracing và prompt versioning

- **Cách xác nhận traces do chính tôi tạo trong project cá nhân:**
  `tracing_enabled()` trả `true` khi `.env` có public/secret key (đã xác nhận qua `/health`).
  `python scripts/load_test.py` gửi 10 request → mỗi request tạo 1 trace.
  *(Điền danh sách trace IDs sau khi mở project trên Langfuse UI.)*

- **Cấu trúc root/retrieval/generation observations:**
  Root `lab-agent-run` (loại `agent`, `capture_input=False`, `capture_output=False`) từ `@observe`.
  Trong `app/agent.py` dùng Langfuse SDK v4 `start_as_current_observation` tạo 2 child:
  - `retrieval` (loại `retriever`) quanh `retrieve(...)`, metadata: `correlation_id`, `doc_count`,
    `query_preview` (đã scrub), `feature`.
  - `generation` (loại `generation`) quanh `FakeLLM.generate(...)` với `model`, prompt
    name/version/label/source, `usage_details` (input/output tokens), `cost_details`
    (input/output/total USD) qua `update_current_generation`.
  Quan hệ: `agent ─ retrieval + generation`.

- **Cách nối trace với log:**
  `correlation_id` nằm trong metadata trace (`propagate_attributes(metadata={"correlation_id": ...})`)
  và trong `data/logs.jsonl`. Nối: lọc log → lấy `correlation_id` → mở trace cùng ID.

- **Prompt name:** `day13-chat` (từ `LANGFUSE_PROMPT_NAME`).
- **Version/label baseline:** version 1, labels `baseline` + `production`.
- **Version/label candidate:** version 2, label `candidate`.
- **Trace ID của mỗi version:** *(Chạy cùng input với `LANGFUSE_PROMPT_LABEL=baseline` và
  `candidate`, mở 2 trace và dán ID vào đây.)*
- **Cách promote và rollback `production`:**
  Đã tạo prompt v1/v2 bằng script `scripts/setup_prompts.py` (SDK, không cần UI). Chuyển label
  `production` v1 → v2 rồi rollback là thao tác UI (SDK v4 không move label an toàn). Bước UI:
  1. Langfuse → Prompts → `day13-chat` → version 2 → **Set as production** (promote).
  2. Chạy `python scripts/load_test.py`; mở trace kiểm tra `prompt_label=production`, `prompt_version=2`.
  3. Version 1 → **Set as production** (rollback); chạy lại và chụp trace.
  4. Chụp ảnh trước/sau làm evidence `10-prompt-rollback.png`.

## 6. Dashboard, SLO và alerts

- **Dashboard và sáu panel:**
  `dashboard.py` (Streamlit + pandas) đọc `data/logs.jsonl` và dựng đúng 6 panel theo
  `config/dashboard.yaml`: Latency (P50/P95/P99 + TTFT P95, threshold P95<=3000 ms),
  Traffic (request count, requests/minute), Errors & Retrieval (error rate %, breakdown,
  retrieval success %), Cost (total + cost by minute), Tokens (input/output), Quality (mean).
  Hiển thị rõ time range 60 phút, đơn vị và threshold/SLO. Chạy `streamlit run dashboard.py`.

- **SLO và lý do chọn:**
  `config/slo.yaml`: SLI `fast_successful_requests` (good = `response_sent and latency_ms <= 3000`),
  target `99.5%`. 3000 ms là ngưỡng P95 trong `dashboard.yaml`; 99.5% là mức khả dụng phổ biến cho
  API đồng bộ, đủ chặt để phát hiện tail latency nhưng không gây nhiễu alert.

- **Cách tính error budget:**
  `100% - 99.5% = 0.5%`. Với 10,000 requests (cửa sổ 28d), budget vi phạm = `10,000 * 0.5% = 50 requests`.
  Mỗi request có `latency_ms > 3000` “đốt” một phần budget; hết budget là đã vượt SLO.

- **Ba alert và runbook tương ứng:**
  - `high_latency_p95`: `latency_p95 > 3000ms`, 5m, critical (runbook `docs/alerts.md#alert-1`).
  - `high_error_rate`: `error_rate_pct > 2%`, 5m, critical (runbook `docs/alerts.md#alert-2`).
  - `low_quality_or_retrieval_degradation`: `quality_score_avg < 0.75 OR retrieval_success_rate_pct < 90%`,
    10m, warning (runbook `docs/alerts.md#alert-3`).

## 7. Điều tra challenge

> Task này chỉ hoàn thành CP1 + CP2, **không** chạy CP3 challenge chính thức.

- **Challenge ID:** Không áp dụng.
- **Khoảng thời gian điều tra:** Không áp dụng.
- **Triệu chứng từ metrics:** (practice) bật `rag_slow` thấy P95 tăng từ ~151 ms → ~2652 ms.
- **Log line và correlation ID liên quan:** (practice) `req-42f30bee` (7988 ms), `req-33df1654` (13314.8 ms).
- **Trace ID và span gây ảnh hưởng:** (practice) span `retrieval` chậm (2.5 s sleep trong `mock_rag.retrieve`).
- **Root cause:** (practice) incident `rag_slow` làm chậm bước retrieval.
- **Fix action:** Tắt `python scripts/inject_incident.py --scenario rag_slow --disable` (đã thực hiện).
- **Preventive measure:** Đặt SLO latency + alert `high_latency_p95`, giữ span retrieval riêng để khoanh vùng.

## 8. Giải thích và tự đánh giá

- **Một quyết định kỹ thuật quan trọng và lý do:**
  Scrub PII **đệ quy trên toàn bộ event** (không chỉ `payload`) và đặt processor `scrub_event` ngay
  trước renderer/file writer. Lý do: PII có thể nằm ở nested dict/list hoặc field bất kỳ; scrub tại
  điểm cuối pipeline đảm bảo cả stdout lẫn `data/logs.jsonl` đều sạch mà không phá schema.

- **Một lỗi/blocker đã gặp:**
  Langfuse SDK v4 gây latency cao ở lần đầu và khi chạy nhiều concurrency (first-request ~1.9–2.7 s,
  và HTTP latency ở `--concurrency 5` + `rag_slow` lên ~13 s do background flush/backpressure).

- **Cách tìm nguyên nhân và xử lý:**
  Đối chiếu latency đo trong agent (`result.latency_ms`, ~151 ms steady-state) với HTTP latency
  endpoint-to-end và server log; xác định phần tăng do `get_prompt` (fetch lần đầu) và flush trace,
  không phải logic app. Giữ `capture_input/output=False`, `fetch_timeout_seconds=2`,
  `cache_ttl_seconds=60` để giới hạn tác động; ghi rõ warmup thay vì cố che.

- **Cách hiểu luồng Metrics → Logs → Traces:**
  1. Metrics (dashboard) chỉ ra triệu chứng và khoảng thời gian (vd P95 tăng).
  2. Logs (`data/logs.jsonl`) lọc theo khoảng đó, lấy `correlation_id` của request bất thường.
  3. Traces (Langfuse) mở theo `correlation_id`, so sánh các span để tìm span gây chậm/lỗi.
  4. Kết luận root cause chỉ khi 3 lớp tín hiệu cùng chỉ về một nguyên nhân.

- **Vai trò của prompt version, token/cost, SLO hoặc rollback trong vận hành LLM:**
  Prompt version giúp truy vết “request này dùng prompt nào” và rollback an toàn khi có regression;
  token/cost giúp theo dõi chi phí và phát hiện spike; SLO biến chất lượng thành con số đo được và
  sinh error budget để quyết định khi nào đánh đổi tính năng hay độ ổn định.

- **Điều quan trọng nhất đã học:**
  Observability là một **chuỗi**: correlation ID là cầu nối giữa log và trace; guardrails PII phải chạy
  trước khi dữ liệu được serialize; trace có child span mới khoanh vùng được root cause.

- **Hạn chế hoặc phần chưa hoàn thành, nếu có:**
  - Evidence trace/prompt/rollback cần người dùng tự chụp trên Langfuse UI (agent không có browser/login).
  - Warmup trace latency ở request đầu tiên chưa được loại bỏ hoàn toàn (do prompt fetch).

## 9. Checklist trước khi nộp

- [ ] Kết quả và evidence thuộc commit SHA cuối.
- [ ] Tất cả ảnh/output mở được bằng đường dẫn tương đối.
- [ ] Incident evidence nối đúng metric → log → trace.
- [ ] Trace/prompt evidence thuộc project Langfuse cá nhân và ảnh không lộ key/secret.
- [ ] Repository chạy lại được theo README.
- [ ] Không có secret, API key, PII thô hoặc evidence của người khác/lớp khác.
- [ ] URL repo và commit SHA cuối đã được nộp trên LMS/Codelabs.
