# Flet Desktop App — Build & Design Guide

**Mục đích:** Tài liệu toàn diện để tái sử dụng khi xây dựng app desktop mới bằng Flet + SQLite + License (be.4mmo.top).

**Rút ra từ:** NPB Podcast Writer — tất cả bug đã fix, bài học đã học.

---

## Mục lục

1. [Kiến trúc tổng thể](#1-kiến-trúc-tổng-thể)
2. [Cấu trúc project](#2-cấu-trúc-project)
3. [Flet 0.82+ API Changes](#3-flet-082-api-changes)
4. [SQLite — Lưu ở đâu](#4-sqlite--lưu-ở-đâu)
5. [License System](#5-license-system)
6. [Machine ID](#6-machine-id)
7. [Encrypt/Decrypt](#7-encryptdecrypt)
8. [Theme Dark SaaS](#8-theme-dark-saas)
9. [Background Threads & Real-time UI](#9-background-threads--real-time-ui)
10. [Build .exe](#10-build-exe)
11. [Checklist trước khi ship](#11-checklist-trước-khi-ship)
12. [Bugs đã gặp & cách fix](#12-bugs-đã-gặp--cách-fix)

---

## 1. Kiến trúc tổng thể

```
┌──────────────────────────────────────────┐
│           Flet Desktop App (.exe)         │
│                                          │
│  views/         UI tabs (Flet widgets)   │
│  services/      Business logic           │
│  db/            SQLite persistence       │
│  theme.py       Color tokens + helpers   │
│  main.py        Entry point              │
├──────────────────────────────────────────┤
│              External Services            │
│  License Server (be.4mmo.top/api)        │
│  Any API (Gemini, OpenAI, etc.)          │
└──────────────────────────────────────────┘
```

**Nguyên tắc:**
- `views/` chỉ chứa UI logic — gọi `services/` cho business logic
- `services/` không import Flet — tách biệt hoàn toàn
- `db/` là layer duy nhất truy cập SQLite
- `theme.py` là nơi duy nhất định nghĩa màu sắc và UI helpers

---

## 2. Cấu trúc project

```
my-app/
├── main.py                # Entry point
├── theme.py               # Colors, helpers (show_snackbar, show_dialog, etc.)
├── build.py               # Build script
├── requirements.txt       # flet, cryptography, requests
│
├── db/
│   ├── __init__.py
│   ├── database.py        # Connection, init schema, get_db_path()
│   └── models.py          # CRUD functions
│
├── views/
│   ├── __init__.py
│   ├── layout.py          # Sidebar + content + status bar
│   ├── dashboard.py       # Tab 1
│   ├── settings.py        # Tab N
│   └── license.py         # License tab + first-launch
│
├── services/
│   ├── __init__.py
│   ├── license_service.py # Activate/verify/cache
│   ├── machine_id.py      # CPU+Board hash
│   ├── crypto.py          # Fernet encrypt/decrypt
│   └── updater.py         # Auto-update
│
└── assets/
    └── icon.ico
```

---

## 3. Flet 0.82+ API Changes

Flet 0.80+ thay đổi nhiều API. Đây là danh sách đầy đủ:

### 3.1. `page.open()` KHÔNG TỒN TẠI

```python
# SAI — sẽ crash
page.open(ft.SnackBar(...))
page.open(dialog)

# ĐÚNG — dùng overlay
def show_snackbar(page, message, duration=2000, bgcolor=None):
    sb = ft.SnackBar(content=ft.Text(message), duration=duration)
    if bgcolor:
        sb.bgcolor = bgcolor
    page.overlay.append(sb)
    sb.open = True
    page.update()

def show_dialog(page, dialog):
    page.overlay.append(dialog)
    dialog.open = True
    page.update()

def close_dialog(page, dialog):
    dialog.open = False
    page.update()
```

### 3.2. Button `text` -> `content`

```python
# SAI
ft.ElevatedButton(text="Click me")
ft.TextButton("Click me", on_click=handler)

# ĐÚNG
ft.ElevatedButton(content=ft.Text("Click me"))
ft.TextButton(content=ft.Text("Click me"), on_click=handler)
```

### 3.3. `self.page` là reserved property

```python
# SAI — ft.Column, ft.Container đã có property `page`
class MyView(ft.Column):
    def __init__(self, page):
        self.page = page  # ERROR: no setter

# ĐÚNG
class MyView(ft.Column):
    def __init__(self, page):
        self._page = page  # Dùng underscore prefix
```

### 3.4. `ft.alignment.center` không tồn tại

```python
# SAI
alignment=ft.alignment.center

# ĐÚNG
alignment=ft.Alignment(0, 0)
```

### 3.5. Dropdown `on_change` -> `on_select`

```python
# SAI
ft.Dropdown(on_change=handler)

# ĐÚNG
ft.Dropdown(on_select=handler)
# Lưu ý: RadioGroup, TextField, Slider vẫn dùng on_change
```

### 3.6. ColorScheme thay đổi

```python
# SAI — removed fields
ft.ColorScheme(background=..., on_background=..., surface_variant=...)

# ĐÚNG
ft.ColorScheme(
    surface=BG_PRIMARY,
    surface_container=BG_CARD,
    surface_container_high=BG_ELEVATED,
    # Không có background, on_background, surface_variant
)
```

### 3.7. `ft.app()` deprecated

```python
# SAI
ft.app(target=main)

# ĐÚNG
ft.run(main)
```

---

## 4. SQLite — Lưu ở đâu

**BUG NGHIÊM TRỌNG:** PyInstaller onefile extract vào temp folder mỗi lần chạy. Nếu DB nằm cùng thư mục `__file__`, nó sẽ bị xóa khi app đóng.

```python
# SAI — DB trong temp, mất khi đóng app
_db_path = os.path.join(os.path.dirname(__file__), "app.db")

# ĐÚNG — DB trong %APPDATA%, persistent vĩnh viễn
import os, sys

APP_DATA_DIR = "My-App-Name"  # Thay bằng tên app

def get_db_path():
    appdata = os.environ.get("APPDATA")
    if appdata:
        data_dir = os.path.join(appdata, APP_DATA_DIR)
    else:
        data_dir = os.path.join(os.path.expanduser("~"), f".{APP_DATA_DIR}")
    os.makedirs(data_dir, exist_ok=True)
    return os.path.join(data_dir, "app.db")
```

**Vị trí thực tế:** `C:\Users\<user>\AppData\Roaming\My-App-Name\app.db`

---

## 5. License System

### 5.1. API Endpoints (be.4mmo.top)

| Endpoint | Method | Mục đích |
|---|---|---|
| `/api/auth/login` | POST | Login admin (JWT) |
| `/api/licenses/activate` | POST | Activate key + machineCode |
| `/api/licenses/verify` | POST | Verify key + machineCode |
| `/api/licenses/deactivate` | POST | Deactivate device |
| `/api/licenses/admin/all` | GET | List all (admin) |
| `/api/licenses/admin/:id/extend` | PUT | Gia hạn (admin) |
| `/api/licenses/admin/:id/revoke` | PUT | Thu hồi (admin) |
| `/api/licenses/admin/:id/suspend` | PUT | Tạm ngưng (admin) |
| `/api/licenses/admin/:id/reset-devices` | PUT | Reset devices (admin) |

### 5.2. Flow khi mở app

```
Mở app
  → Loading spinner "Đang kiểm tra license..."
  → Gọi POST /api/licenses/verify (LUÔN LUÔN, không skip)
    → valid: true, graceMode: false → Vào app
    → valid: true, graceMode: true  → Block! Device bị reset → First-Launch
    → valid: false                  → Clear cache → First-Launch
    → Không có mạng + cache < 24h   → Cho vào (offline grace)
    → Không có mạng + cache >= 24h  → Block
```

### 5.3. Bài học quan trọng

```python
# 1. LUÔN verify mỗi lần mở app — không skip dù vừa verify
# SAI: skip nếu verified gần đây
if elapsed < 4h: return valid  # User revoke trên server nhưng app vẫn chạy!

# ĐÚNG: luôn verify
result = verify()  # Gọi server mỗi lần

# 2. graceMode = true KHÔNG phải hợp lệ — nghĩa là device bị reset
if data.get("graceMode"):
    clear_cache()
    return invalid  # Bắt activate lại

# 3. Khi verify fail do revoke/suspend → xóa cache ngay
if "revoked" in reason or "suspended" in reason or "not activated" in reason:
    clear_license_cache()
```

### 5.4. Activate phải chạy background thread

```python
# SAI — block UI thread, app freeze, user tưởng không kết nối được
def _on_activate(self, e):
    result = license_service.activate(key)  # Block 5-15 giây!

# ĐÚNG — chạy background, UI responsive
def _on_activate(self, e):
    self.loading.visible = True
    self._page.update()

    def _do():
        result = license_service.activate(key)
        def _ui():
            self.loading.visible = False
            # update UI...
            self._page.update()
        self._page.run_thread(_ui)

    threading.Thread(target=_do, daemon=True).start()
```

---

## 6. Machine ID

**Tương thích Win10 + Win11** (wmic deprecated trên Win11):

```python
def _get_value(ps_query, wmic_query):
    """PowerShell trước, fallback wmic."""
    # PowerShell (Win11+)
    result = _run_powershell(ps_query)
    if result and result != "UNKNOWN":
        return result
    # wmic fallback (Win10)
    return _run_wmic(wmic_query)

def get_cpu_id():
    return _get_value(
        "(Get-CimInstance Win32_Processor).ProcessorId",
        "wmic cpu get ProcessorId",
    )

def get_board_serial():
    return _get_value(
        "(Get-CimInstance Win32_BaseBoard).SerialNumber",
        "wmic baseboard get SerialNumber",
    )
```

**CHU Y:** PowerShell trả multiple lines cho multi-socket CPU → chỉ lấy dòng đầu:

```python
first_line = output.split("\n")[0].strip()
```

---

## 7. Encrypt/Decrypt

Dùng `cryptography.Fernet` với key derive từ machineCode:

```python
from cryptography.fernet import Fernet
import hashlib, base64

def _derive_key(machine_code):
    digest = hashlib.sha256(machine_code.encode()).digest()
    return base64.urlsafe_b64encode(digest)

def encrypt(data, machine_code):
    return Fernet(_derive_key(machine_code)).encrypt(data.encode()).decode()

def decrypt(data, machine_code):
    try:
        return Fernet(_derive_key(machine_code)).decrypt(data.encode()).decode()
    except:
        return ""  # Sai máy hoặc data corrupt
```

**Dùng cho:** API keys, license token, admin JWT token.

---

## 8. Theme Dark SaaS

```python
# Color tokens (style giống Vercel/Linear)
BG_PRIMARY    = "#0A0A0B"   # Nền chính
BG_CARD       = "#141416"   # Card
BG_ELEVATED   = "#1C1C1F"   # Sidebar, header
BORDER        = "#27272A"
TEXT_PRIMARY   = "#FAFAFA"
TEXT_SECONDARY = "#A1A1AA"
TEXT_MUTED     = "#71717A"
ACCENT         = "#F97316"   # Orange
SUCCESS        = "#22C55E"
WARNING        = "#EAB308"
DANGER         = "#EF4444"
INFO           = "#3B82F6"
```

---

## 9. Background Threads & Real-time UI

### 9.1. Quy tắc vàng

```python
# Callback từ background thread PHẢI dùng page.run_thread()
runner = PipelineRunner(
    on_progress=lambda *a: page.run_thread(self._on_progress, *a),
    on_complete=lambda *a: page.run_thread(self._on_complete, *a),
)

# KHÔNG gọi page.update() trực tiếp từ background thread
# (có thể hoạt động nhưng không thread-safe)
```

### 9.2. Live timer

```python
def _start_timer(self):
    def _tick():
        while self._running:
            elapsed = time.time() - self._start
            self.timer.value = f"{int(elapsed//60):02d}:{int(elapsed%60):02d}"
            self._safe_update()
            time.sleep(1)
    threading.Thread(target=_tick, daemon=True).start()
```

### 9.3. Auto-refresh khi chuyển tab

```python
# layout.py — gọi refresh() khi switch tab
def _on_nav_click(self, index):
    self.content_area.content = self.views[index]
    view = self.views[index]
    if hasattr(view, "refresh"):
        view.refresh()  # Reload data từ DB
```

---

## 10. Build .exe

### 10.1. Dùng `flet pack` (KHUYẾN NGHỊ)

```bash
flet pack main.py \
  --name My-App \
  --distpath dist \
  --add-data "../data-folder;data-folder" \
  --product-name "My App" \
  --company-name "Company" \
  --file-version "1.0.0.0" \
  --product-version "1.0.0.0" \
  --copyright "Copyright 2026" \
  -y
```

**Tại sao `flet pack`:**
- Tự bundle Flutter runtime (flet.exe, DLLs, data/)
- Tự xử lý icons.json, cupertino_icons.json
- Không cần config phức tạp

### 10.2. KHÔNG dùng Nuitka cho Flet

Nuitka compile Python -> C nhưng **KHÔNG** xử lý được:
- `flet_desktop/app/` (Flutter runtime — flet.exe, DLLs)
- `icons.json` (Flet material icons)
- Onefile extract path khác với PyInstaller

Kết quả: exe build thành công nhưng **không chạy được** do thiếu Flutter runtime.

### 10.3. build.py template

```python
import subprocess, sys, os

APP_NAME = "My-App"

def build():
    cmd = [
        sys.executable, "-m", "flet", "pack",
        "main.py",
        "--name", APP_NAME,
        "--distpath", "dist",
        "--product-name", "My App",
        "--company-name", "Company",
        "--file-version", "1.0.0.0",
        "--product-version", "1.0.0.0",
        "--copyright", "Copyright 2026",
        "-y",
    ]
    # Add data folders
    cmd.extend(["--add-data", f"../data;data"])
    # Add icon
    if os.path.exists("assets/icon.ico"):
        cmd.extend(["-i", "assets/icon.ico"])

    subprocess.run(cmd, check=True)

if __name__ == "__main__":
    build()
```

### 10.4. Output

```
dist/My-App.exe  (~110 MB)
- Bao gồm: Python runtime + Flet + Flutter + tất cả dependencies
- User chỉ cần download 1 file, chạy ngay
- Không cần cài Python, không cần cài gì thêm
```

---

## 11. Checklist trước khi ship

```
[ ] DB lưu ở %APPDATA%, không phải cùng thư mục exe
[ ] License verify LUÔN gọi server khi mở app
[ ] graceMode = true → block, yêu cầu re-activate
[ ] Tất cả HTTP requests chạy background thread (không block UI)
[ ] page.open() đã thay bằng show_snackbar/show_dialog
[ ] self.page đã đổi thành self._page trong views
[ ] Button dùng content=ft.Text() không phải text=
[ ] Dropdown dùng on_select không phải on_change
[ ] Machine ID dùng PowerShell + fallback wmic
[ ] PowerShell output lấy first line only
[ ] Build bằng flet pack, KHÔNG dùng Nuitka
[ ] Company metadata trong build (giảm antivirus false positive)
[ ] Test exe chạy được trên máy không có Python
[ ] Test activate → đóng app → mở lại → không bị activate lại
[ ] Test revoke trên server → mở app → bị block
[ ] Server URLs hardcode trong code, không cho user sửa (bảo mật)
```

---

## 12. Bugs đã gặp & cách fix

### Bug 1: App freeze khi activate
**Nguyên nhân:** `requests.post()` block UI thread 5-15 giây
**Fix:** Chạy HTTP requests trong `threading.Thread` + `page.run_thread()` cho UI callback

### Bug 2: License bị revoke nhưng app vẫn chạy
**Nguyên nhân:** Skip verify nếu `verified_at` < 4h
**Fix:** LUÔN verify với server mỗi lần mở app, không skip

### Bug 3: graceMode cho phép dùng sau reset device
**Nguyên nhân:** Server trả `valid: true, graceMode: true` — app coi là hợp lệ
**Fix:** `graceMode: true` = device bị reset → clear cache → block

### Bug 4: DB mất khi đóng app (exe)
**Nguyên nhân:** PyInstaller onefile extract vào temp → DB tạo trong temp → xóa khi đóng
**Fix:** DB lưu ở `%APPDATA%/App-Name/`

### Bug 5: Pipeline không update realtime
**Nguyên nhân:** Callbacks từ background thread gọi `page.update()` không thread-safe
**Fix:** Wrap callbacks bằng `page.run_thread()`

### Bug 6: `wmic` không hoạt động trên Win11
**Nguyên nhân:** Microsoft deprecated `wmic` từ Win11
**Fix:** Dùng PowerShell `Get-CimInstance` trước, fallback `wmic`

### Bug 7: PowerShell trả multi-line cho multi-CPU
**Nguyên nhân:** `(Get-CimInstance Win32_Processor).ProcessorId` trả 2 dòng cho 2 socket
**Fix:** Chỉ lấy `output.split("\n")[0].strip()`

### Bug 8: Nuitka exe không chạy — thiếu flet.exe
**Nguyên nhân:** Nuitka không bundle Flutter runtime (`flet_desktop/app/`)
**Fix:** Dùng `flet pack` thay vì Nuitka

### Bug 9: Exe bị antivirus block
**Nguyên nhân:** Unsigned exe + onefile extract behavior giống malware
**Fix:** Thêm company metadata + code signing certificate ($200/năm)

### Bug 10: Settings lưu URL cũ, override default mới
**Nguyên nhân:** Code ưu tiên giá trị trong DB hơn default
**Fix:** Filter out placeholder URLs: `if "yourdomain" not in url`

---

## Template nhanh cho app mới

1. Copy cấu trúc project ở mục 2
2. Thay `APP_DATA_DIR` trong `db/database.py`
3. Thay `productSlug` trong `license_service.py`
4. Thay `APP_NAME` trong `build.py`
5. Thiết kế views mới
6. `flet pack` để build

**Thời gian ước tính:** 2-4 giờ cho skeleton app có license + dark theme + build exe.
