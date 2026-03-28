# Dich Truyen - Chuyen Doi Noi Dung Viet/Han → Nhat

## Goal
Them tab "Dich Truyen" vao NPB Podcast Writer — chuyen doi triet de noi dung truyen tu tieng Viet/Han sang tieng Nhat, toi uu cho TTS podcast. Khong phai dich thuan tuy ma la chuyen doi van hoa, dia ly, lich su mot cach logic.

## Architecture

### Pipeline: 3 Agents
- **Analyzer** (gemini-2.5-flash): Detect ngon ngu, detect yeu to Han Quoc, tao mapping (ten nguoi/dia danh/van hoa), chia doan
- **Translator** (gemini-2.5-pro): Chuyen doi noi dung theo mapping + config user (kinh ngu, giong ke, style)
- **Reviewer** (gemini-2.5-flash): Kiem tra con yeu to Han/tieng Anh khong, kiem tra quy tac viet (hiragana/katakana/so), retry toi da 2 lan

### UI: Tab 4 voi 4 Sub-tabs
- **Nhap lieu**: Paste text / Import file (.txt/.md) / YouTube URL (yt-dlp subtitle) / Web crawl
- **Cau hinh**: The loai, doi tuong, boi canh, kinh ngu, giong ke, style output, fast mode, CTA
- **Tien trinh**: Review diem cat doan + pipeline real-time progress + preview tung doan
- **Ket qua**: Editor split (goc vs Nhat) + lich su dich

### Quy Tac Chuyen Doi (CRITICAL)
- Boi canh Han Quoc → chuyen TOAN BO sang Nhat Ban (van hoa, dia ly, lich su)
- Boi canh khac → giu nguyen, chi chuyen ngon ngu
- Nhan vat Han → nguoi Nhat, ten Nhat
- Ten Nhat + dia danh Nhat → **hiragana** (vd: きむら しゅんすけ, とうきょう)
- Ten nuoc ngoai → **katakana** (vd: アメリカ, ボーイング)
- So lieu → so A Rap (vd: 1986年, 28歳, 15人, 1000円)
- Loai bo 100% tieng Anh
- CTA ten kenh → にほんのチカラ・【海外の反応】
- Van phong phai rat Nhat Ban, toi uu TTS

### Database: 2 bang moi (SQLite hien tai)
- `translations`: project dich (title, source_text, result_text, config_json, status)
- `translation_segments`: tung doan (source_text, result_text, status, segment_index)

### Files

| File | Loai | Mo ta |
|------|------|-------|
| `views/translator/__init__.py` | MOI | TranslatorView + TranslatorState |
| `views/translator/tab_input.py` | MOI | 4 nguon input: paste/file/youtube/web |
| `views/translator/tab_config.py` | MOI | 6 tuy chon + fast mode + CTA |
| `views/translator/tab_progress.py` | MOI | Review diem cat + pipeline progress |
| `views/translator/tab_result.py` | MOI | Editor split + lich su |
| `services/translator_runner.py` | MOI | Pipeline 3 agents + chia doan + retry |
| `services/input_handler.py` | MOI | Xu ly 4 nguon input |
| `services/ytdlp_manager.py` | MOI | Download/update yt-dlp + extract subtitle |
| `views/layout.py` | SUA | Them divider + tab Dich Truyen (index 4) |
| `db/database.py` | SUA | Them 2 bang moi vao schema init |
| `db/models.py` | SUA | Them CRUD cho translations + segments |
| `requirements.txt` | SUA | Them beautifulsoup4, lxml |

## Tasks

- [x] Task 1: Database — Them 2 bang (`translations`, `translation_segments`) vao `database.py` schema init + CRUD functions vao `models.py` → Verify: app khoi dong, 2 bang duoc tao trong SQLite
- [x] Task 2: `services/input_handler.py` — Xu ly 4 nguon input (paste/file/youtube/web), return `InputResult` dataclass → Verify: unit test paste text + doc file .txt thanh cong
- [x] Task 3: `services/ytdlp_manager.py` — Auto download yt-dlp.exe, check update tu GitHub releases, extract subtitle tu YouTube URL → Verify: nhap URL YouTube, nhan duoc subtitle text
- [x] Task 4: `services/translator_runner.py` — Pipeline 3 agents (Analyzer→Translator→Reviewer), chia doan, retry logic, tuan tu + fast mode → Verify: nhap text ngan tieng Viet, nhan output tieng Nhat da chuyen doi
- [x] Task 5: `views/translator/__init__.py` — TranslatorView chinh voi sub-tab bar + TranslatorState shared state → Verify: tab hien thi, chuyen sub-tab hoat dong
- [x] Task 6: `views/translator/tab_input.py` — UI 4 nguon nhap lieu + preview + nut "Tiep tuc" → Verify: paste text hien preview, nhap YouTube URL tai subtitle
- [x] Task 7: `views/translator/tab_config.py` — UI 6 dropdown config + fast mode toggle + CTA input → Verify: chon config, data luu vao TranslatorState
- [x] Task 8: `views/translator/tab_progress.py` — UI review diem cat (gop/tach doan) + pipeline progress real-time + preview tung doan → Verify: hien danh sach doan, khi dich thay progress update
- [x] Task 9: `views/translator/tab_result.py` — Editor 3 mode (edit/preview/split) + sync scroll + copy/export + lich su dich → Verify: split mode hien 2 cot goc vs Nhat, copy hoat dong
- [x] Task 10: `views/layout.py` — Them divider + SidebarButton tab 4 (TRANSLATE icon) + re-index Settings(5) License(6) → Verify: sidebar hien tab moi voi divider, click chuyen tab dung
- [x] Task 11: `requirements.txt` — Them `beautifulsoup4>=4.12.0` va `lxml>=5.0.0` → Verify: `pip install -r requirements.txt` thanh cong
- [x] Task 12: Integration test — Chay full flow: paste truyen ngan tieng Viet → config → chia doan → dich → xem ket qua trong editor → Verify: output tieng Nhat, khong con tieng Anh, ten hiragana, so A Rap

## Done When
- [ ] Tab "Dich Truyen" hien trong sidebar voi divider
- [ ] 4 sub-tabs hoat dong: Nhap lieu → Cau hinh → Tien trinh → Ket qua
- [ ] 4 nguon input hoat dong (paste/file/youtube/web)
- [ ] yt-dlp auto-update khi mo tab
- [ ] Pipeline 3 agents chuyen doi noi dung (khong phai dich)
- [ ] Ket qua: ten Nhat = hiragana, ten nuoc ngoai = katakana, so = A Rap, 0% tieng Anh
- [ ] Editor split so sanh goc vs Nhat
- [ ] Lich su dich luu va truy cap duoc

## Decision Log

| # | Quyet dinh | Ly do |
|---|-----------|-------|
| 1 | Input: Paste + File + YouTube + Web | Linh hoat, YouTube la nguon truyen pho bien |
| 2 | 3 agents (Analyzer→Translator→Reviewer) | Can bang chat luong vs toc do |
| 3 | Auto chia doan + user review diem cat | Tu dong tien, user kiem soat logic |
| 4 | DB hien tai (bang moi) + editor rieng | Tan dung DB, tach biet UX |
| 5 | Config day du (kinh ngu + giong ke + style) | Tieng Nhat can kiem soat chi tiet |
| 6 | YouTube: subtitle only (yt-dlp) | Nhanh, khong ton API |
| 7 | yt-dlp auto-update silent khi mo tab | Khong phien user |
| 8 | Khong gioi han kich thuoc, app tu chia | User khong can lo |
| 9 | Tuan tu mac dinh + Fast mode option | Thay ket qua dan + option nhanh |
| 10 | UI Sub-tabs (Approach B) | Tach concerns, de maintain |
| 11 | Chuyen doi triet de, KHONG dich | Yeu cau cot loi: Han→Nhat logic van hoa |

## Notes
- Analyzer chay 1 lan duy nhat cho toan bo truyen → mapping nhat quan
- Translator + Reviewer chay per-segment
- Fast mode: Translator + Reviewer song song nhieu doan (Analyzer van chay 1 lan)
- yt-dlp.exe luu tai `%APPDATA%/NPB-Podcast-Writer/yt-dlp.exe`
- Web crawl dung requests + BeautifulSoup (khong headless browser)
- Dung chung Gemini API keys + license system hien tai
