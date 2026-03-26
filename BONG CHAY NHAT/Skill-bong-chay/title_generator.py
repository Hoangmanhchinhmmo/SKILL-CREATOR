"""
Title Generator — Sinh tiêu đề hấp dẫn dựa trên nội dung bài viết.
Dựa trên công thức TIEUDE.JP.MD, tối ưu cho:
- Tránh vi phạm policy (không lừa đảo, không khẳng định sai sự thật)
- Dùng quan điểm cá nhân, câu hỏi tu từ, honest hooks
- Vẫn đảm bảo clickbait cao, SEO tốt
Dùng chung cho v1, v2, v3 và các version tương lai.
"""

TITLE_SYSTEM = (
    "あなたはYouTubeタイトルとSEOの専門家です。"
    "視聴者のクリック率を最大化しながら、誠実で信頼性のあるタイトルを作成します。"
    "虚偽の主張や誤解を招く表現は絶対に使用しません。"
)

TITLE_PROMPT_TEMPLATE = """以下の記事内容に基づいて、魅力的なタイトルを5つ提案してください。

【記事内容の要約（最初の1000文字）】
{content_preview}

【タイトルの公式（10パターンから選んで使用）】

1. 修辞疑問型（最も安全＆高CTR）:
   「なぜ○○は○○できたのか？」「○○の本当の実力とは？」
   → 答えを約束せず、考えさせる。虚偽にならない。

2. 個人的見解型:
   「○○を見て確信した — ○○は本物だ」「私が○○を推す理由」
   → 「私の意見」として書くため、事実誤認にならない。

3. データ分析型:
   「数字が語る○○の凄さ — ○○のデータを徹底解剖」
   → 具体的な数字に基づく。誇張しない。

4. 対比・比較型:
   「○○ vs ○○ — 明暗を分けた○○」「○○と○○、何が違うのか」
   → 比較は事実。結論は記事で述べる。

5. ストーリー型:
   「○○の軌跡 — ○○から○○へ」「知られざる○○の裏側」
   → 物語の予告。嘘ではなくフレーミング。

6. 発見・気づき型:
   「○○を分析して気づいた意外な事実」「見落としがちな○○のポイント」
   → 「気づいた」「見落としがち」は主観。安全。

7. 展望・予測型（主観として明示）:
   「○○はこうなると思う — 理由は3つ」「来季の○○を大胆予測」
   → 「思う」「予測」で主観を明示。

8. 深掘り解説型:
   「○○を徹底解説 — なぜ今注目すべきか」「○○の全貌が明らかに」
   → 解説・分析は誠実なコンテンツ。

9. ファン共感型:
   「○○ファンなら絶対共感する○○」「○○を応援する全ての人へ」
   → 感情に訴えるが嘘ではない。

10. ハイライト・まとめ型:
    「○○の注目ポイント○選」「今週の○○を振り返る」
    → 事実のまとめ。安全かつSEO強い。

【絶対禁止ルール — 守らないとタイトルが却下される】
❌ 「～が判明！」「衝撃の真実」→ 事実と異なる可能性
❌ 「誰も知らない」「世界が震えた」→ 誇大表現
❌ 「～を暴露」「極秘情報」→ 虚偽のスクープ感
❌ 断定的な未来予測（「○○は必ず～する」）
❌ 他者を中傷・侮辱する表現

【必須ルール】
✅ 記事の言語と同じ言語でタイトルを書く
✅ 80〜100文字で書く（短すぎ禁止）
✅ 具体的な選手名・チーム名を含める（SEO）
✅ 5つとも異なるパターンを使う
✅ 番号付きリストで出力（1. 2. 3. 4. 5.）
✅ タイトルだけ出力。説明不要。

【良い例】
1. なぜ戸郷翔征のスライダーは打てないのか？ — データが示す進化の全貌
2. 巨人vs阪神を見て確信した、今季のセリーグは予想以上に面白くなる
3. 数字が語る大谷翔平の異次元 — 同世代と比較して見えた本当の凄さ
4. おかわりジュニア中村勇斗の軌跡 — 父の背中を追い続けた少年の甲子園
5. 今週のNPBを振り返る — 見逃せない5つの注目ポイント"""


def build_title_prompt(content: str) -> tuple[str, str]:
    """Build title generation prompt from article content.

    Args:
        content: Full article text

    Returns:
        (system_instruction, user_prompt)
    """
    preview = content[:1000] if len(content) > 1000 else content
    prompt = TITLE_PROMPT_TEMPLATE.format(content_preview=preview)
    return TITLE_SYSTEM, prompt


def parse_titles(raw_text: str) -> list[str]:
    """Parse numbered list of titles from AI response.

    Args:
        raw_text: AI response like "1. Title one\n2. Title two\n..."

    Returns:
        List of title strings (max 5)
    """
    import re
    titles = []
    for line in raw_text.strip().split("\n"):
        line = line.strip()
        match = re.match(r"^\d+[\.\)、]\s*(.+)", line)
        if match:
            title = match.group(1).strip().strip('"').strip("「").strip("」")
            if title:
                titles.append(title)
    return titles[:5]
