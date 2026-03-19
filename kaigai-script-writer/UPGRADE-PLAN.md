# Kaigai Script Writer — Upgrade Plan v2.0

**Ngày:** 2026-03-19
**Mục tiêu:** Nâng cấp chất lượng nội dung tiếng Nhật
**Trạng thái:** Multi-Agent Review xong — APPROVED — sẵn sàng implement

---

## Understanding Summary

- **What:** Full overhaul kaigai-script-writer — workflow mới, chất lượng tiếng Nhật cao hơn đáng kể
- **Why:** Ba vấn đề cốt lõi trong output hiện tại:
  1. Văn phong dịch — câu tiếng Nhật đọc như dịch từ tiếng Việt/Anh
  2. Cảm xúc phẳng — diễn biến không có đỉnh điểm rõ ràng
  3. Thiếu biểu hiện đặc trưng Nhật (日本語らしい表現)
- **Who:** Chạy trên Claude Code + Codex + Gemini CLI (cả ba hỗ trợ subagent)
- **Không-goals:** Không tối ưu TTS production format, không tối ưu tốc độ

---

## Constraints

- **Không có RAG** — mọi kiến thức mẫu nhúng trực tiếp vào prompt
- **Full overhaul** workflow được chấp nhận
- Output format giữ nguyên: `voiceover.txt` + `metadata.md`
- Giao tiếp tiếng Việt, output tiếng Nhật

---

## Kiến trúc đã chọn: Option B — Writer + Narrator + Reviewer

### Workflow tổng thể

```
SEARCH → SUGGEST → WAIT → [WRITE PIPELINE]
                              │
                    ┌─────────▼─────────┐
                    │   ORCHESTRATOR    │
                    │  (Claude chính)   │
                    └─────────┬─────────┘
                              │ với mỗi phần (Hook→...→Kết luận)
                    ┌─────────▼─────────┐
                    │     WRITER        │
                    │  draft nội dung   │
                    │  focus: facts +   │
                    │  storyline + beats│
                    └─────────┬─────────┘
                              │
                    ┌─────────▼─────────┐
                    │NARRATOR SPECIALIST│
                    │ rewrite: văn phong│
                    │ Nhật thuần + cảm  │
                    │ xúc + biểu hiện   │
                    └─────────┬─────────┘
                              │
                    ┌─────────▼─────────┐
                    │    REVIEWER       │
                    │ score 3 chiều     │
                    │ ≥7/10 → ghi file  │
                    │ <7/10 → Narrator  │
                    │        viết lại   │
                    └─────────┬─────────┘
                              │ OK
                    ┌─────────▼─────────┐
                    │   ghi file phần   │
                    │ → phần tiếp theo  │
                    └───────────────────┘
```

### Ba agent và nhiệm vụ

| Agent | Nhiệm vụ | Không làm |
|-------|----------|-----------|
| **WRITER** | Draft content: facts, storyline, beat changes, character arc | Không lo văn phong Nhật |
| **NARRATOR SPECIALIST** | Rewrite: văn phong Nhật thuần, cảm xúc sâu, biểu hiện 日本語らしい | Không thêm/bớt nội dung |
| **REVIEWER** | Score 3 chiều, yêu cầu rewrite nếu < threshold | Không viết nội dung |

### Reviewer Rubric (3 chiều × 10 điểm)

| Chiều | Mô tả | Threshold |
|-------|-------|-----------|
| 文体 (Văn phong) | Không có dấu hiệu dịch, SOV tự nhiên, です/ます nhất quán | ≥7 |
| 感情 (Cảm xúc) | Có ít nhất 3 beat changes, đỉnh điểm rõ tại 60-85% Diễn biến | ≥7 |
| 表現 (Biểu hiện) | Dùng biểu hiện 日本語らしい, không dùng từ generic | ≥7 |

**Tổng ≥21/30 → ghi file. < 21 → Narrator viết lại (tối đa 2 vòng)**

### Reviewer — Checklist Binary (thay numeric score)

Reviewer không chấm điểm số. Dùng checklist binary — PASS/FAIL per item:

**文体チェック (Văn phong):**
- [ ] Không có câu passive không cần thiết
- [ ] Không có false agency (sự vật làm hành động của người)
- [ ] SOV order tự nhiên — không đảo ngược theo kiểu dịch
- [ ] です/ます nhất quán trong đoạn

**感情チェック (Cảm xúc):**
- [ ] Có ít nhất 3 beat changes trong Diễn biến
- [ ] Climax nằm ở 60–85% phần Diễn biến, không ở cuối
- [ ] Câu kết phần tạo cảm xúc đúng theo Emotional Arc Blueprint

**表現チェック (Biểu hiện):**
- [ ] Không có AI-tell patterns tiếng Nhật (xem Japanese Stop-Slop list)
- [ ] Dùng ít nhất 2 biểu hiện 日本語らしい thay vì từ generic
- [ ] Không có từ tiếng Anh nào trong voiceover text

**Rule:** Nếu bất kỳ item nào FAIL → Narrator viết lại với lý do cụ thể.
Loop tối đa 2 lần. Sau 2 lần vẫn FAIL → **warning inline trong conversation** + ghi file + tiếp tục.

### Status Display (bắt buộc)

```
🖊️ Writer đang draft [Tên phần]...
✅ Writer: [X] ký tự

🎙️ Narrator đang rewrite...
✅ Narrator: rewrite xong

📋 Reviewer đang kiểm tra...
✅ Reviewer: PASS — ghi file
   hoặc
⚠️ Reviewer: FAIL — [item fail + lý do] — Narrator viết lại (lần 1/2)
```

### File-based Handoff

```
XXX-slug/
├── _draft/          (intermediate — xóa sau khi merge)
│   ├── 01-hook_draft.txt      ← Writer output
│   ├── 01-hook_narrated.txt   ← Narrator output
│   └── 01-hook_review.txt     ← Reviewer checklist
├── 01-hook.txt                ← Final approved
└── ...
```

### Graceful Degradation

Nếu Agent tool không khả dụng (platform không hỗ trợ subagent):
- Fallback sang **single-agent mode**
- Claude chính tự thực hiện Writer + Narrator + Reviewer tuần tự inline
- Thông báo: `⚠️ Subagent không khả dụng — chạy single-agent mode`

---

## Điểm khác biệt so với Kaigai-skill (nguồn tham khảo)

| Yếu tố | Kaigai-skill | kaigai-script-writer v2 |
|--------|-------------|------------------------|
| RAG | Bắt buộc (27+ truyện) | Không có — dùng embedded library |
| RAG Analyst | Có | Không có |
| Writer | Có | Có |
| Narrator Specialist | Có | Có |
| Reviewer | Có | Có (rubric nhúng sẵn) |
| Loop max | Không rõ | 2 lần |
| Output format | TTS segments `[VOICE:]` | Plain text `voiceover.txt` |

---

## Japanese Stop-Slop Rules (từ stop-slop-main — adapt sang tiếng Nhật)

Narrator Specialist phải nhúng danh sách này. Đây là các AI-tell patterns tiếng Nhật cần tránh:

### Throat-Clearing tiếng Nhật (cần cắt)
- `〜ということになります` → viết thẳng vào điều đó là gì
- `〜と言えるでしょう` → khẳng định thẳng hoặc bỏ
- `〜ではないでしょうか` (dùng quá nhiều) → chỉ dùng khi thực sự muốn đặt câu hỏi
- `〜について見ていきましょう` → bắt đầu thẳng vào nội dung

### False Agency tiếng Nhật
- `歴史が動きました` → ai/cái gì tạo ra sự thay đổi? Viết cụ thể
- `注目が集まりました` → ai chú ý? Truyền thông? Fan? Ghi rõ
- `感動が広がりました` → ai cảm động? Viết nhân vật cụ thể

### AI-tell Patterns tiếng Nhật
- 5 câu liên tiếp kết bằng `〜ました` → xen kẽ `〜のです`/`〜でした`/`〜ています`
- `非常に`/`とても`/`大変` (adverb yếu) → mô tả cụ thể hơn hoặc bỏ
- `素晴らしい`/`感動的な` (adjective generic) → dùng biểu hiện cụ thể
- Binary contrast: `〜だけでなく、〜も` liên tục → đổi cấu trúc

### Biểu hiện 日本語らしい thay thế (embedded library)
| Generic | Authentic Japanese |
|---------|-------------------|
| 驚きました | 言葉を失いました / 目を見開きました |
| 感動しました | 胸を打たれました / 涙がこぼれました |
| 注目しました | 目が釘付けになりました |
| 重要でした | 〜に他なりませんでした |
| 成功しました | 見事にやり遂げました |
| 世界が注目した | 世界中の目が、一点に注がれました |
| すごかった | 〜の右に出る者はいませんでした |
| 驚いた反応 | 球場が、まるで爆発したかのような歓声に包まれました |

---

## Việc cần thiết kế tiếp (TODO)

- [x] **Writer prompt** — focus vào content, không lo văn phong
- [x] **Narrator Specialist prompt** — Japanese Stop-Slop rules + 日本語らしい表現 library
- [x] **Reviewer prompt** — binary checklist 文体・感情・表現
- [x] **Orchestrator logic** — status display, file-based handoff, loop control, graceful degradation
- [x] **Cập nhật kaigai-core.md** — WRITE PIPELINE section mới thay CHAIN OF THOUGHT
- [x] **Cập nhật kaigai-script-writer.md** — workflow v2, write pipeline table, updated key rules
- [ ] **Cập nhật sample output** — sample mới theo chất lượng mới (optional — sample hiện tại vẫn dùng được)

---

## Decision Log

| # | Quyết định | Alternatives | Lý do | Objections raised |
|---|-----------|-------------|-------|-------------------|
| 1 | Option B (3 agent) | A (Narrator only), C (persona switch) | Full overhaul ok; 3 vấn đề → 3 agent chuyên biệt | — |
| 2 | Không có RAG | RAGFlow integration | Môi trường không hỗ trợ | — |
| 3 | Japanese Stop-Slop rules thay embedded library chung | Generic expression list | stop-slop approach cụ thể hơn, maintainable hơn | Skeptic S1: circular quality |
| 4 | Checklist binary thay numeric score | 1-10 rubric | LLM scoring không deterministic; binary ổn định hơn | Skeptic S3, Constraint C3 |
| 5 | File-based handoff giữa agents | Context-pass | Tránh context bloat sau 5 sections | Constraint C2 |
| 6 | Status display bắt buộc | Silent pipeline | User cần thấy progress | User Advocate U1 |
| 7 | Warning inline khi fail-through | Warning trong file | User có thể bỏ qua warning trong file | Skeptic S4, User U4 |
| 8 | Graceful degradation single-agent | Hard fail | Multi-platform compatibility | Constraint C4 |
| 9 | Không thêm intervention point giữa WRITE | Mid-write pause | YAGNI — WAIT phase đã đủ | User U3 — REJECTED |
| 10 | Giữ output format cũ | TTS segments format | Không phải mục tiêu | — |

---

## Multi-Agent Review Summary

**Arbiter verdict: APPROVED**

| Reviewer | Objections raised | Accepted | Rejected |
|----------|-------------------|----------|---------|
| Skeptic | S1 (circular quality), S2 (ranh giới mờ), S3 (threshold), S4 (fail-through) | S1, S3, S4 | S2 partial |
| Constraint Guardian | C1 (context cost), C2 (handoff), C3 (non-deterministic), C4 (multi-platform) | C2, C3, C4 | C1 |
| User Advocate | U1 (black box), U2 (failure không actionable), U3 (intervention), U4 (warning chôn) | U1, U2, U4 | U3 |
