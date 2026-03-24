# NPB Podcast Writer — Flet Desktop App Design

**Ngày:** 2026-03-23
**Trạng thái:** APPROVED — sẵn sàng implement
**Author:** Solo developer

---

## Understanding Summary

- **What:** Desktop app (Windows .exe) bằng Flet + SQLite — UI cho pipeline Bong Chay Nhat (NPB Podcast multi-agent system)
- **Why:** Thay thế CLI bằng giao diện trực quan — nhập topic, xem tiến trình real-time, quản lý lịch sử, chỉnh sửa, cấu hình pipeline
- **Who:** User mua license từ LicenseHub, activate bằng CPU+Motherboard, offline cache 24h grace
- **Auth flow:** Nhập license key → `POST /api/licenses/activate` với machineCode → lưu token encrypted vào SQLite → verify định kỳ 4h, offline 24h grace
- **Storage:** SQLite cho tất cả (articles, pipeline logs, config encrypted, license cache)
- **UI:** Dark theme (Dark SaaS, accent orange #F97316), single-window multi-tab, sidebar icon-based
- **Export:** Markdown file + Copy clipboard
- **Distribution:** PyInstaller → .exe, auto-update

---

## Constraints

- **Pipeline > 5 phút** — phải chạy background thread, UI không block
- **SQLite không giới hạn** — pagination khi hiển thị
- **API keys encrypted** — bằng machineCode hash (CPU+Main), bind theo máy
- **License server đã deploy production** — có URL public
- **Windows only** — .exe, dùng `wmic` lấy hardware ID

---

## Kiến trúc tổng thể

```
┌─────────────────────────────────────────────────────┐
│                  NPB Podcast Writer (.exe)            │
│                                                      │
│  ┌──────────┐  ┌──────────────────────────────────┐ │
│  │ Sidebar   │  │ Content Views                    │ │
│  │ (60px)    │  │                                  │ │
│  │           │  │ Dashboard / Pipeline / History   │ │
│  │ ⌂ ▶ ☰ ✎ │  │ Editor / Settings / License      │ │
│  │ ⚙ 🔑     │  │                                  │ │
│  └──────────┘  └──────────────────────────────────┘ │
│  ┌──────────────────────────────────────────────────┐│
│  │ Status Bar                                        ││
│  └──────────────────────────────────────────────────┘│
├──────────────────────────────────────────────────────┤
│                     Services                          │
│  ┌────────────┐ ┌──────────┐ ┌───────────────────┐  │
│  │ Pipeline   │ │ License  │ │ Crypto / MachineID│  │
│  │ Runner     │ │ Service  │ │ / Updater         │  │
│  │ (thread)   │ │          │ │                   │  │
│  └─────┬──────┘ └────┬─────┘ └───────────────────┘  │
│        │              │                               │
│        ▼              ▼                               │
│  ┌──────────────────────────────────────────────────┐│
│  │              SQLite (npb_podcast.db)               ││
│  │  articles │ pipeline_runs │ agent_logs            ││
│  │  settings │ license_cache                         ││
│  └──────────────────────────────────────────────────┘│
├──────────────────────────────────────────────────────┤
│                  External Services                    │
│  ┌───────────────┐  ┌──────────────────────────┐    │
│  │ Gemini API    │  │ License Server (HTTPS)   │    │
│  │ (3 keys xoay) │  │ POST /api/licenses/...   │    │
│  └───────────────┘  └──────────────────────────┘    │
└──────────────────────────────────────────────────────┘
```

---

## Cấu trúc Project

```
BONG CHAY NHAT/
├── Skill-bong-chay/          # Pipeline hiện tại (giữ nguyên)
│   ├── main.py
│   ├── pipeline_v2.py
│   ├── agents.py
│   ├── section_writers.py
│   ├── supervisor.py
│   ├── nlm_data.py
│   ├── config.py
│   └── output/
│
└── npb-podcast-app/           # Flet app mới
    ├── DESIGN.md              # File này
    ├── main.py                # Entry point Flet
    ├── db/
    │   ├── database.py        # SQLite connection + init
    │   └── models.py          # CRUD operations
    ├── views/
    │   ├── layout.py          # Sidebar + main container
    │   ├── dashboard.py       # Tab tạo bài mới
    │   ├── pipeline.py        # Tab tiến trình real-time
    │   ├── history.py         # Tab lịch sử
    │   ├── editor.py          # Tab chỉnh sửa
    │   ├── settings.py        # Tab cấu hình
    │   └── license.py         # Tab license + first-launch
    ├── services/
    │   ├── license_service.py # Activate/verify/cache
    │   ├── pipeline_runner.py # Wrapper gọi pipeline, emit progress
    │   ├── crypto.py          # Encrypt/decrypt bằng machineCode
    │   ├── machine_id.py      # Lấy CPU+Motherboard ID
    │   └── updater.py         # Auto-update checker
    ├── theme.py               # Color tokens, styles
    ├── assets/
    │   └── icon.ico
    ├── requirements.txt
    └── build.py               # PyInstaller config → .exe
```

---

## SQLite Schema

```sql
-- Bài viết output
CREATE TABLE articles (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    topic       TEXT NOT NULL,
    format      TEXT NOT NULL,
    content     TEXT NOT NULL,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at  DATETIME
);

-- Lịch sử chạy pipeline
CREATE TABLE pipeline_runs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    article_id  INTEGER REFERENCES articles(id),
    status      TEXT NOT NULL,  -- running/completed/failed
    started_at  DATETIME,
    finished_at DATETIME,
    total_time  REAL            -- seconds
);

-- Log từng agent
CREATE TABLE agent_logs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id      INTEGER REFERENCES pipeline_runs(id),
    agent_name  TEXT NOT NULL,
    status      TEXT NOT NULL,  -- running/passed/failed/retrying
    attempt     INTEGER DEFAULT 1,
    started_at  DATETIME,
    finished_at DATETIME,
    error_msg   TEXT
);

-- Cấu hình (encrypted API keys + settings)
CREATE TABLE settings (
    key         TEXT PRIMARY KEY,
    value       TEXT NOT NULL,  -- encrypted nếu là API key
    encrypted   INTEGER DEFAULT 0
);

-- License cache
CREATE TABLE license_cache (
    id          INTEGER PRIMARY KEY,
    license_key TEXT NOT NULL,
    machine_code TEXT NOT NULL,
    status      TEXT NOT NULL,
    product     TEXT,
    plan        TEXT,
    expires_at  DATETIME,
    verified_at DATETIME,
    token_data  TEXT            -- encrypted JSON response
);
```

---

## UI Design

### Theme (Dark SaaS)

| Token | Giá trị | Mô tả |
|---|---|---|
| bg-primary | #0A0A0B | Nền chính |
| bg-card | #141416 | Nền card/panel |
| bg-elevated | #1C1C1F | Sidebar, header |
| border | #27272A | Viền mặc định |
| border-hover | #3F3F46 | Viền hover |
| text-primary | #FAFAFA | Chữ chính |
| text-secondary | #A1A1AA | Chữ phụ |
| text-muted | #71717A | Chữ mờ |
| accent | #F97316 | Orange chính |
| accent-hover | #EA580C | Orange hover |
| success | #22C55E | Thành công |
| warning | #EAB308 | Cảnh báo |
| danger | #EF4444 | Lỗi |

### Layout

- **Sidebar:** 60px width, icon-only, expand 200px khi hover
- **Sidebar bg:** #0A0A0B
- **Active tab:** left border orange #F97316 + icon sáng
- **Inactive icon:** #71717A
- **Status bar:** bottom, hiện license status + version + last run time
- **Window size:** 1200×800 default, resizable, min 900×600

### Tab 1: Dashboard

- Input field cho topic
- Format cards (grid 3×2): chọn 1, highlight orange border
- Pipeline version toggle: v1 / v2
- Button "Bắt đầu tạo" (orange) → chuyển sang Pipeline tab
- "Bài viết gần đây": 5 bài mới nhất từ SQLite

### Tab 2: Pipeline (Real-time Progress)

- Header: topic + trạng thái + timer đếm
- Progress cards cho mỗi agent/section:
  - Icon trạng thái: ✅ passed, ⟳ retrying, ⏳ waiting, ❌ failed
  - Tên agent + thời gian + attempt count [n/max]
  - Agent đang chạy: indeterminate progress bar
  - Retry: hiện lý do fail từ Supervisor
- Agent Log panel (expandable, scrollable, auto-scroll)
- Nút "Hủy" (confirm dialog) + "Hoàn tất → Mở Editor" (hiện khi xong)
- Tất cả events lưu vào pipeline_runs + agent_logs

### Tab 3: History

- Search bar: tìm theo topic (SQLite LIKE)
- Filter: status (tất cả/completed/failed) + format dropdown
- Sort: mới nhất / cũ nhất / thời gian chạy
- Danh sách cards, mỗi bài:
  - Topic + format + status + thời gian chạy + ngày tạo
  - Actions: Copy, Edit, Xóa (confirm), Run lại
  - Bài failed: Logs thay Copy
- Pagination: 20 bài/trang, SQLite LIMIT OFFSET

### Tab 4: Editor

- 3 chế độ: Edit / Preview / Split
- Edit: textarea, monospace, line numbers
- Preview: render markdown styled
- Split: 50/50 edit + preview
- Stats bar: chars, lines, ước lượng TTS (~700 chars/phút)
- Actions: Save, Copy, Export .md, Undo (revert về gốc, confirm)
- Auto-save mỗi 30 giây khi đang edit
- Shortcuts: Ctrl+S save, Ctrl+C copy

### Tab 5: Settings

- **API Keys section:**
  - 3 fields (Writer, Editor, Architect): masked •••, toggle 👁, nút Test
  - Encrypted bằng machineCode hash, lưu SQLite settings table
- **Model section:**
  - 4 dropdowns (Data, Analysis, Writer, Supervisor)
  - Options: gemini-2.5-pro, gemini-2.5-flash, gemini-2.0-flash
- **Pipeline section:**
  - Temperature slider 0.0–1.0 (default 0.8)
  - Supervisor Temperature slider (default 0.3)
  - Max Output Tokens input (default 16384)
  - Max Retries input (default 2)
- **Server section:**
  - License Server URL
  - Update Server URL
- **Storage section:**
  - DB size, article count, log count
  - Xóa logs cũ (>30 ngày, confirm)
  - Export DB (save file dialog)
- Button "Lưu cấu hình" (orange)

### Tab 6: License

- Status card: badge màu (green/red/yellow) + plan + key + expiry + last verify
- Device info: machineCode, CPU name, Mainboard name
- Actions: Verify ngay, Hủy kích hoạt (confirm → deactivate API → clear cache)
- App info: version, build date, nút Kiểm tra update

### First-Launch Screen

- Fullscreen (không sidebar), centered
- Logo/icon + tiêu đề app
- Input: license key
- Hiện machineCode + nút Copy
- Button "Kích hoạt" → loading state → success/error
- Link mua license
- Flow: activate OK → lưu encrypted → chuyển main app

---

## License Flow

1. **Lần đầu mở app** → kiểm tra `license_cache` → không có → First-Launch Screen
2. **Activate:** lấy machineCode → `POST /api/licenses/activate` → lưu encrypted vào SQLite
3. **Mỗi lần mở app:**
   - Đọc `license_cache`
   - `verified_at` < 24h → vào app (offline OK)
   - `verified_at` >= 24h → gọi `POST /api/licenses/verify`
     - OK → cập nhật `verified_at`, vào app
     - Fail + trong grace → cảnh báo, vẫn cho dùng
     - Fail + hết grace → khóa, hiện License Screen
4. **Background verify:** mỗi 4h khi app đang chạy

---

## Auto-Update Flow

1. App khởi động → `GET https://server/api/updates/npb-podcast/latest`
2. Version mới → dialog "Có bản mới vX.Y.Z — Cập nhật?"
3. User đồng ý → download .exe → chạy installer → thoát app cũ
4. User từ chối → bỏ qua (trừ `required: true` → bắt buộc)
5. Không có update → im lặng

**Update API response:**
```json
{
  "version": "1.2.0",
  "download_url": "https://server/releases/npb-podcast-1.2.0.exe",
  "changelog": "- Fix lỗi agent timeout\n- Thêm format mới",
  "required": false
}
```

---

## Machine ID & Crypto

**machine_id.py:**
- Lấy CPU ID: `wmic cpu get ProcessorId`
- Lấy Motherboard serial: `wmic baseboard get SerialNumber`
- Hash: `SHA256(cpuId + "|" + boardSerial)` → machineCode

**crypto.py:**
- Derive Fernet key từ machineCode (SHA256 → base64)
- `encrypt(data, machineCode)` → encrypted string
- `decrypt(data, machineCode)` → plain string
- Dùng cho: API keys, license token_data

---

## Decision Log

| # | Quyết định | Thay thế | Lý do chọn |
|---|---|---|---|
| 1 | Flet + SQLite desktop app | Electron, Tkinter, PyQt | Flet = Python native, hot reload, dark theme built-in, đóng .exe dễ |
| 2 | Single-window multi-tab | Wizard, Multi-window | Linh hoạt nhất, xem lịch sử trong lúc pipeline chạy |
| 3 | Sidebar icon-based (60px) | Top navbar, hamburger | Tối ưu không gian, style Dark SaaS giống LicenseHub |
| 4 | Dark theme, orange accent | Light, auto | Thống nhất style với license-manager, user chọn |
| 5 | Activate 1 lần + 24h grace | Online-only, offline-only | Cân bằng bảo mật + UX, tận dụng grace có sẵn |
| 6 | Encrypt API keys bằng machineCode | Plain text, master password | Tự động, bind theo máy, không cần nhớ password |
| 7 | Pipeline chạy background thread | asyncio, subprocess | Flet UI responsive, thread + queue emit events |
| 8 | SQLite tất cả trong 1 file | JSON files, multiple DB | 1 file dễ backup, query mạnh, ACID |
| 9 | Auto-update check khi mở app | Manual only | User có quyền từ chối, required flag cho critical |
| 10 | Export .md + clipboard | PDF, HTML, TXT | Đủ dùng, YAGNI |
| 11 | Editor 3 mode (edit/preview/split) | Edit only | Preview markdown quan trọng cho TTS script |
| 12 | Pagination 20 bài/trang | Infinite scroll | SQLite hiệu quả LIMIT OFFSET, không giới hạn tổng |

---

## Thứ tự triển khai

1. **Phase 0:** Project setup (requirements, cấu trúc thư mục, theme)
2. **Phase 1:** SQLite database + models (schema, CRUD)
3. **Phase 2:** Services (machine_id, crypto, license_service)
4. **Phase 3:** Layout + First-Launch + License tab
5. **Phase 4:** Settings tab (config pipeline, API keys encrypted)
6. **Phase 5:** Dashboard tab + Pipeline runner (background thread, progress events)
7. **Phase 6:** Pipeline tab (real-time UI)
8. **Phase 7:** History tab + Editor tab
9. **Phase 8:** Auto-updater
10. **Phase 9:** PyInstaller build → .exe
