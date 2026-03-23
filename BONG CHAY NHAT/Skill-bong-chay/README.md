# NPB Podcast Multi-Agent System

Hệ thống multi-agent tự động viết script podcast YouTube về bóng chày Nhật Bản (NPB).

## Kiến trúc

```
Input: "はんしん vs よみうり"
  ↓
[Agent 1: データ収集]     Thu thập dữ liệu NPB
  ↓
[Agent 2: 戦術分析]       Phân tích chiến thuật (starter → bullpen → lineup)
  ↓
[Agent 3: 独自視点]       Tìm góc nhìn riêng mà fan chưa thấy
  ↓
[Agent 4: 台本作成]       Viết script podcast 8-15 phút
  ↓
[Agent 5: 品質検査]       Kiểm tra chất lượng TTS + quy tắc chữ viết
  ↓
Output: Script podcast tiếng Nhật hoàn chỉnh (.md)
```

## Skills đã kết hợp

| Skill | Vai trò |
|-------|---------|
| `gemini-api-dev` | Gọi Google Gemini API |
| `ai-agent-development` | Thiết kế agent architecture |
| `multi-agent-patterns` | Pipeline orchestration pattern |
| `prompt-engineer` | Tối ưu prompt cho mỗi agent |
| `python-pro` | Code Python production-ready |

## Cài đặt

```bash
cd Skill-bong-chay
pip install -r requirements.txt
```

## Thiết lập API Key

```bash
# Windows
set GEMINI_API_KEY=your-gemini-api-key

# Linux/Mac
export GEMINI_API_KEY=your-gemini-api-key
```

## Sử dụng

```bash
# Chạy với argument
python main.py "はんしん vs よみうり"

# Chạy interactive
python main.py
```

## Các format hỗ trợ

| Keyword trong input | Format |
|---------------------|--------|
| プレビュー / 予告 | 試合プレビュー (mặc định) |
| まとめ / 週間 | 週間まとめ |
| ランキング | パワーランキング |
| チーム分析 | チーム深掘り分析 |
| 選手 / スポットライト | 選手スポットライト |
| 戦術 | 戦術ブレイクダウン |
| プレーオフ / 日本シリーズ | ポストシーズン予測 |
| 初心者 / ルール | 初心者向け解説 |

## Quy tắc output (TTS-optimized)

- 100% tiếng Nhật, 0% tiếng Anh
- Tên Nhật → ひらがな (ví dụ: おおたに しょうへい)
- Tên ngoại → カタカナ (ví dụ: マイク・トラウト)
- Số → アラビア数字 (ví dụ: 2026年, 28歳)
- Câu ≤ 40 ký tự, có （間） giữa các đoạn
- Biến số liệu thành câu chuyện, không ném raw stats

## Output

Script được lưu tự động vào `output/` với format:
```
output/20260323_143000_はんしん_vs_よみうり.md
```
