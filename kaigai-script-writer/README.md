# Kaigai Script Writer / 海外の反応スクリプトライター

**Skill tạo script YouTube tiếng Nhật theo phong cách "海外の反応" cho CLI tools**

A CLI skill that creates viral Japanese YouTube voice-over scripts in "海外の反応" (overseas reactions) style.

---

## Tổng quan / Overview

**VI:** Skill này giúp bạn tìm chủ đề viral, gợi ý topic, và viết script voice over tiếng Nhật tối ưu cho TTS. Hỗ trợ nhiều lĩnh vực: thể thao, công nghệ, văn hóa, ẩm thực... Giao tiếp bằng tiếng Việt, output bằng tiếng Nhật.

**EN:** This skill helps you find viral topics, suggest content ideas, and write Japanese voice-over scripts optimized for TTS. Supports multiple niches: sports, technology, culture, food... Communication in Vietnamese, output in Japanese.

---

## Tính năng / Features

- Configurable niche (MLB, bóng đá, công nghệ, văn hóa Nhật...)
- Web search tự động (nếu CLI hỗ trợ) hoặc nhận input thủ công
- Đề xuất topic theo format chuẩn với đánh giá viral potential
- Viết full script hoặc từng phần (tùy chọn)
- Output ra file: `metadata.md` + `voiceover.txt`
- Mỗi bài viết một thư mục riêng, đánh số tự động (`001-slug/`, `002-slug/`...)
- Hỗ trợ 3 CLI: Claude Code, Codex CLI, Gemini CLI

---

## Cài đặt / Installation

### 1. Clone repo

```bash
git clone https://github.com/YOUR_USERNAME/kaigai-script-writer.git
```

### 2. Cài cho CLI bạn dùng / Install for your CLI

#### Claude Code

Skill phải nằm trong thư mục con `~/.claude/skills/<tên>/SKILL.md`:

```bash
# Tạo thư mục skill + copy core reference
mkdir -p ~/.claude/skills/kaigai-script-writer
cp kaigai-script-writer/claude-code/kaigai-script-writer.md ~/.claude/skills/kaigai-script-writer/SKILL.md
```

**Quan trọng:** Sau khi copy, sửa đường dẫn core trong SKILL.md thành absolute path:
```
Read and apply ALL instructions from the core logic file: `<đường-dẫn-tuyệt-đối>/kaigai-script-writer/core/kaigai-core.md`
```

Hoặc symlink:
```bash
mkdir -p ~/.claude/skills/kaigai-script-writer
ln -s $(pwd)/kaigai-script-writer/claude-code/kaigai-script-writer.md ~/.claude/skills/kaigai-script-writer/SKILL.md
```

Gọi skill: `/kaigai-script-writer` hoặc Claude tự nhận diện qua context.

#### Codex CLI (OpenAI)

Skill nằm trong `~/.codex/skills/<tên>/SKILL.md` (tương tự Claude Code):

```bash
mkdir -p ~/.codex/skills/kaigai-script-writer
cp kaigai-script-writer/codex-cli/agents.md ~/.codex/skills/kaigai-script-writer/SKILL.md
```

Hoặc cài vào project cụ thể:
```bash
cp kaigai-script-writer/codex-cli/agents.md ./AGENTS.md
```

#### Gemini CLI (Google)

Copy vào thư mục global `~/.gemini/`:

```bash
cp kaigai-script-writer/gemini-cli/GEMINI.md ~/.gemini/GEMINI.md
```

Hoặc cài vào project cụ thể:
```bash
cp kaigai-script-writer/gemini-cli/GEMINI.md ./GEMINI.md
```

**Lưu ý:** Copy vào global sẽ ghi đè file GEMINI.md hiện có. Nếu bạn đã có instruction riêng, hãy dùng project-level thay vì global.

---

## Cách dùng / Usage

### Bước 1: Chọn lĩnh vực / Choose niche

Khi bắt đầu, skill sẽ hỏi bạn muốn tạo nội dung về lĩnh vực nào. Mặc định: MLB/Ohtani.

### Bước 2: Tìm chủ đề / Find topics

Yêu cầu skill tìm chủ đề viral. Skill sẽ search (nếu CLI hỗ trợ) hoặc hỏi bạn cung cấp thông tin.

```
Tìm cho tôi 3-5 chủ đề viral nhất tuần này về Ohtani
```

### Bước 3: Chọn topic / Select topic

Skill sẽ đề xuất danh sách topic. Bạn chọn 1 topic.

```
Tôi chọn topic 2
```

### Bước 4: Nhận script / Get script

Skill viết từng phần vào file riêng, sau đó merge thành script hoàn chỉnh:

```
./001-ohtani-homerun/
├── 01-hook.txt          # Hook section
├── 02-context.txt       # Bối cảnh section
├── 03-development.txt   # Diễn biến section
├── 04-reactions.txt     # Phản ứng quốc tế section
├── 05-conclusion.txt    # Kết luận section
├── bak/                 # Backup các bản bị UNDER/OVER (nếu có)
│   └── 01-hook_v1.txt
├── voiceover.txt        # Full merged script (TTS-ready)
└── metadata.md          # Titles, thumbnails, structure
```

---

## Cấu trúc output / Output Structure

```
./XXX-slug/
├── 01-hook.txt          # Section files (written during WRITE phase)
├── 02-context.txt
├── 03-development.txt
├── 04-reactions.txt
├── 05-conclusion.txt
├── bak/                 # Only created if sections need rewriting
├── voiceover.txt        # Merged final script, TTS-optimized
└── metadata.md          # Title options, thumbnail text, character count table
```

- Mỗi section file: plain text thuần, viết + verify riêng từng phần
- `bak/`: backup bản bị UNDER/OVER, đặt tên `{tên}_v{n}.txt`
- `voiceover.txt`: merge từ 5 file phần, cách nhau 2 dòng trống
- `metadata.md`: Markdown với 5 title options, 5 thumbnail text, bảng character count
- Tất cả file phần và bak/ được giữ lại sau merge

### Script Structure

| Phần | Ký tự |
|------|-------|
| Hook | 400–600 |
| Bối cảnh | 700–1000 |
| Diễn biến | 2500–3500 |
| Phản ứng quốc tế | 1200–1500 |
| Kết luận | 400–600 |
| **Tổng** | **5,000–7,000** |

---

## Cấu trúc repo / Repo Structure

```
kaigai-script-writer/
├── README.md                              # Tài liệu này
├── core/
│   └── kaigai-core.md                     # Core logic (single source of truth)
├── claude-code/
│   └── kaigai-script-writer.md            # Claude Code skill wrapper
├── codex-cli/
│   └── agents.md                          # Codex CLI wrapper (full embed)
├── gemini-cli/
│   └── GEMINI.md                          # Gemini CLI wrapper (full embed)
└── examples/
    └── 001-sample-output/                 # Ví dụ output
        ├── metadata.md
        └── voiceover.txt
```

---

## Cập nhật / Update

```bash
cd kaigai-script-writer
git pull
```

Sau khi pull, copy lại wrapper files cho CLI bạn dùng (xem phần Installation).

**Lưu ý:** Codex CLI và Gemini CLI wrapper chứa full logic (không reference file ngoài), nên cần copy lại sau mỗi lần update.

---

## License

MIT
