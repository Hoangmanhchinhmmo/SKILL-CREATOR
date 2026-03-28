"""
Translator Runner — 3-agent pipeline for story conversion.
Agents: Analyzer → Translator → Reviewer
Converts Vietnamese/Korean content to fully localized Japanese.
"""

import sys
import os
import re
import json
import threading
import datetime
import time
import concurrent.futures

from db.models import (
    get_setting, update_translation, update_translation_segment,
    get_translation_segments,
)
from services.machine_id import get_machine_code
from services.crypto import decrypt

# Reuse Skill-bong-chay path setup from pipeline_runner
from services.pipeline_runner import SKILL_DIR, _inject_settings_to_env


# ─── Conversion rules (embedded in prompts) ───

CONVERSION_RULES_JA = """
【変換ルール — 厳守】
1. これは「翻訳」ではなく「コンテンツ変換」です。文体は完全に日本語ネイティブであること。
2. 外国の要素がある場合 → マッピング表に従ってすべて日本に変換する
   - ベトナム・韓国・中国の登場人物 → 日本人に変換、マッピング表の日本名を使用
   - 外国の地名 → マッピング表の日本の地名を使用
   - 外国の文化要素 → マッピング表の日本の対応要素を使用
   ※ マッピング表にない要素は、論理的に日本の対応する要素に変換する
3. 欧米が舞台の場合 → 背景はそのまま維持し、言語のみ日本語に変換
4. 日本の固有名詞（人名・地名・組織名）→ ひらがなで表記
   例: きむら しゅんすけ、とうきょう、こくどこうつうしょう
5. 外国の固有名詞（欧米の人名・地名）→ カタカナで表記
   例: ボーイング、CNN、グアム、アメリカ、アジア
6. 年代・日時・年齢・人数・金額・単位 → アラビア数字で表記
   例: 1986年、28歳、15人、1000円
7. 英語は一切使用しない — すべて日本語に変換
8. CTAやチャンネル名がある場合 → 「{channel_name}」に置き換え
9. TTS最適化: 文は短く明確に、同音異義語を避ける、自然な読み上げを意識
10. マッピング表の人物名・地名を必ず使用する — 独自に別の名前を作らないこと
"""

CONVERSION_RULES_SIMPLE = """
【CONVERSION RULES — STRICT】
1. This is CONTENT CONVERSION, not translation. The output must read as native Japanese.
2. Korean elements → Convert ALL to Japan (culture, geography, history — logically mapped)
3. Non-Korean settings → Keep the setting, convert language only
4. Japanese proper nouns (names, places) → Write in HIRAGANA
5. Foreign proper nouns → Write in KATAKANA
6. Numbers (dates, ages, counts, money, units) → Use Arabic numerals
7. NO English words allowed — convert everything to Japanese
8. CTA/channel names → Replace with "{channel_name}"
9. Optimize for TTS: short clear sentences, avoid homophones
"""

# ─── Default segment size ───
DEFAULT_SEGMENT_SIZE = 3000  # characters per segment


def split_text_into_segments(text: str, max_size: int = DEFAULT_SEGMENT_SIZE) -> list[str]:
    """Split text into segments at natural boundaries.
    Strategy: paragraphs → single newlines → sentences → hard cut.
    Works for all input types including YouTube subtitles (single-line text).
    """
    if len(text) <= max_size:
        return [text]

    # Step 1: Split into atomic units (smallest meaningful chunks)
    # Try double newline first, then single newline, then sentences
    paragraphs = re.split(r"\n\s*\n", text)

    # If only 1 big block (e.g. YouTube subtitles), split by single newline
    if len(paragraphs) <= 2 and any(len(p) > max_size for p in paragraphs):
        paragraphs = text.split("\n")

    # If still 1 big block (no newlines at all), split by sentences
    if len(paragraphs) <= 2 and any(len(p) > max_size for p in paragraphs):
        # Korean/Japanese/Vietnamese sentence endings + Western punctuation
        paragraphs = re.split(r"(?<=[。！？\.!\?\.\n다요])\s*", text)

    segments = []
    current = ""

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        if len(current) + len(para) + 2 <= max_size:
            current = (current + "\n" + para) if current else para
        else:
            if current:
                segments.append(current.strip())

            # If single chunk is still too long, hard split
            if len(para) > max_size:
                while len(para) > max_size:
                    # Find best cut point near max_size
                    cut = max_size
                    # Try to cut at sentence boundary
                    for pattern in [r"[。！？\.!\?]", r"[,，、;；]", r"\s"]:
                        match = None
                        for m in re.finditer(pattern, para[:max_size]):
                            match = m
                        if match and match.end() > max_size * 0.5:
                            cut = match.end()
                            break
                    segments.append(para[:cut].strip())
                    para = para[cut:].strip()
                current = para
            else:
                current = para

    if current.strip():
        segments.append(current.strip())

    # Filter out tiny segments (< 20 chars) by merging with neighbors
    if len(segments) > 1:
        merged = []
        for seg in segments:
            if merged and len(seg) < 20:
                merged[-1] = merged[-1] + "\n" + seg
            else:
                merged.append(seg)
        segments = merged

    return segments if segments else [text]


class TranslatorRunner:
    """Runs the 3-agent translation pipeline with progress callbacks."""

    def __init__(self, on_progress=None, on_segment_done=None,
                 on_complete=None, on_error=None, on_log=None):
        """
        Callbacks:
            on_progress(agent_name, status, segment_index, message)
            on_segment_done(segment_index, result_text)
            on_complete(translation_id)
            on_error(message)
            on_log(timestamp, agent, message)
        """
        self.on_progress = on_progress or (lambda *a: None)
        self.on_segment_done = on_segment_done or (lambda *a: None)
        self.on_complete = on_complete or (lambda *a: None)
        self.on_error = on_error or (lambda *a: None)
        self.on_log = on_log or (lambda *a: None)
        self._thread = None
        self._cancelled = False
        self.translation_id = None
        self._counter_lock = threading.Lock()
        self._pre_analysis = None

    def start(self, translation_id: int, config: dict, fast_mode: bool = False,
              pre_analysis: dict = None):
        """Start translation pipeline in background thread.

        Args:
            pre_analysis: If provided, skip Analyzer and use this mapping directly.
                          Comes from user-confirmed tab_analysis.
        """
        self._cancelled = False
        self.translation_id = translation_id
        self._pre_analysis = pre_analysis
        self._thread = threading.Thread(
            target=self._run, args=(translation_id, config, fast_mode), daemon=True,
        )
        self._thread.start()

    def cancel(self):
        self._cancelled = True

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def _log(self, agent: str, message: str):
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        self.on_log(ts, agent, message)

    def _increment_completed(self):
        """Thread-safe increment of completed_segments counter."""
        with self._counter_lock:
            from db.models import get_translation
            t = get_translation(self.translation_id)
            if t:
                update_translation(self.translation_id,
                                   completed_segments=t["completed_segments"] + 1)

    def _run(self, translation_id: int, config: dict, fast_mode: bool):
        """Main pipeline execution."""
        start_time = time.time()
        _inject_settings_to_env()

        # Override model env vars with translator-specific models from config
        model_analyzer = config.get("model_analyzer", "gemini-2.5-flash")
        model_translator = config.get("model_translator", "gemini-2.5-pro")
        model_reviewer = config.get("model_reviewer", "gemini-2.5-flash")

        # Analyzer uses data_collector key → GEMINI_MODEL_DATA
        os.environ["GEMINI_MODEL_DATA"] = model_analyzer
        # Translator uses script_writer key → GEMINI_MODEL_WRITER
        os.environ["GEMINI_MODEL_WRITER"] = model_translator
        # Reviewer uses quality_checker key → GEMINI_MODEL_SUPERVISOR
        os.environ["GEMINI_MODEL_SUPERVISOR"] = model_reviewer

        self._log("System", f"Models: Analyzer={model_analyzer}, Translator={model_translator}, Reviewer={model_reviewer}")

        update_translation(translation_id, status="translating")

        try:
            # Get Gemini caller
            import importlib
            if "config" in sys.modules:
                importlib.reload(sys.modules["config"])
            if "agents" in sys.modules:
                importlib.reload(sys.modules["agents"])
            from agents import _call_gemini

            # Get segments
            segments = get_translation_segments(translation_id)
            if not segments:
                raise ValueError("Không có đoạn nào để dịch")

            total = len(segments)
            self._log("System", f"Bắt đầu chuyển đổi {total} đoạn")

            # ── Agent 1: Analyzer (runs ONCE for entire story) ──
            if self._pre_analysis:
                # Use user-confirmed mapping from tab_analysis
                analysis = self._pre_analysis
                self.on_progress("Analyzer", "passed", -1, "Sử dụng mapping đã xác nhận")
                self._log("Analyzer", f"✅ Dùng mapping đã xác nhận: {len(analysis.get('mapping', {}).get('names', {}))} tên")
            else:
                self.on_progress("Analyzer", "running", -1, "Phân tích toàn bộ truyện...")
                self._log("Analyzer", "Đang phân tích truyện...")

                full_source = "\n\n".join(seg["source_text"] for seg in segments)
                analysis = self._run_analyzer(full_source, config, _call_gemini)

                self.on_progress("Analyzer", "passed", -1, "Hoàn tất phân tích")
                self._log("Analyzer", f"✅ Mapping: {len(analysis.get('mapping', {}))} items")

            # Save mapping
            update_translation(translation_id, mapping_json=json.dumps(analysis, ensure_ascii=False))

            if self._cancelled:
                update_translation(translation_id, status="cancelled")
                self.on_error("Đã hủy")
                return

            # ── Agent 2 & 3: Translator + Reviewer per segment ──
            max_retries = int(config.get("max_retries", 2))
            channel_name = config.get("channel_name", "にほんのチカラ・【海外の反応】")

            speed_mode = config.get("speed_mode", "safe")
            # Backward compat
            if speed_mode not in ("safe", "balanced", "fast", "turbo"):
                speed_mode = "balanced" if fast_mode else "safe"

            batch_map = {"safe": 1, "balanced": 3, "fast": 5, "turbo": 10}
            batch_size = batch_map.get(speed_mode, 1)

            if batch_size <= 1 or total <= 1:
                self._log("System", "Mode: Tuần tự")
                self._run_sequential(segments, analysis, config, channel_name,
                                     max_retries, _call_gemini)
            else:
                self._log("System", f"Mode: {speed_mode} (batch {batch_size})")
                self._run_parallel(segments, analysis, config, channel_name,
                                   max_retries, _call_gemini, batch_size=batch_size)

            if self._cancelled:
                update_translation(translation_id, status="cancelled")
                self.on_error("Đã hủy")
                return

            # Assemble final result
            final_segments = get_translation_segments(translation_id)
            result_parts = []
            for seg in final_segments:
                if seg["result_text"]:
                    result_parts.append(seg["result_text"])

            full_result = "\n\n".join(result_parts)
            elapsed = time.time() - start_time

            update_translation(
                translation_id,
                result_text=full_result,
                status="done",
                completed_segments=len(result_parts),
            )

            self._log("System", f"✅ Hoàn tất trong {elapsed:.0f}s")
            self.on_complete(translation_id)

        except Exception as e:
            update_translation(translation_id, status="failed")
            self._log("System", f"❌ Lỗi: {e}")
            self.on_error(f"Pipeline lỗi: {str(e)}")

    def _run_sequential(self, segments, analysis, config, channel_name, max_retries, call_fn):
        """Translate segments one by one with full story context accumulation."""
        story_context = ""  # Running summary of story so far
        prev_tail = ""      # Last 500 chars of previous translated segment

        for i, seg in enumerate(segments):
            if self._cancelled:
                return
            result = self._translate_segment(
                i, seg, analysis, config, channel_name,
                max_retries, call_fn, len(segments),
                story_context=story_context,
                prev_tail=prev_tail,
            )
            if result:
                prev_tail = result[-500:]
                # Generate running summary after each segment (except last)
                if i < len(segments) - 1:
                    self._log("Context", f"Đoạn {i+1} — Đang tóm tắt bối cảnh...")
                    new_summary = self._summarize_segment(result, story_context, call_fn)
                    if new_summary:
                        story_context = new_summary
                        self._log("Context", f"Đoạn {i+1} — Bối cảnh: {story_context[:80]}...")

    def _run_parallel(self, segments, analysis, config, channel_name, max_retries, call_fn,
                      batch_size: int = 3):
        """Translate segments in batched parallel with story context between batches.
        Within each batch, segments run in parallel sharing the same context.
        Between batches, a summary is generated to carry context forward.
        """
        total = len(segments)
        story_context = ""
        prev_tail = ""

        for batch_start in range(0, total, batch_size):
            if self._cancelled:
                return

            batch_end = min(batch_start + batch_size, total)
            batch = list(range(batch_start, batch_end))

            self._log("System", f"Batch {batch_start//batch_size + 1}: đoạn {batch[0]+1}-{batch[-1]+1}")

            results = {}
            max_workers = min(batch_size, len(batch))
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {}
                for i in batch:
                    if self._cancelled:
                        return
                    future = executor.submit(
                        self._translate_segment, i, segments[i], analysis, config,
                        channel_name, max_retries, call_fn, total,
                        story_context=story_context,
                        prev_tail=prev_tail,
                    )
                    futures[future] = i

                for future in concurrent.futures.as_completed(futures):
                    if self._cancelled:
                        executor.shutdown(wait=False, cancel_futures=True)
                        return
                    try:
                        result = future.result()
                        if result:
                            results[futures[future]] = result
                    except Exception as e:
                        self._log("System", f"❌ Segment {futures[future]+1} lỗi: {e}")

            # After batch: use last segment result for tail, summarize all batch results
            last_idx = batch[-1]
            if last_idx in results:
                prev_tail = results[last_idx][-500:]

            # Summarize this batch for context carry-forward
            if batch_end < total and results:
                # Combine batch results in order for summary
                batch_text = "\n".join(results[i] for i in sorted(results.keys()))
                self._log("Context", f"Batch tóm tắt bối cảnh...")
                new_summary = self._summarize_segment(batch_text, story_context, call_fn)
                if new_summary:
                    story_context = new_summary
                    self._log("Context", f"Bối cảnh: {story_context[:80]}...")

    def _translate_segment(self, index: int, segment: dict, analysis: dict,
                           config: dict, channel_name: str, max_retries: int,
                           call_fn, total: int,
                           story_context: str = "", prev_tail: str = ""):
        """Translate + Review a single segment. Returns final translated text."""
        seg_id = segment["id"]
        source = segment["source_text"]
        label = f"Đoạn {index+1}/{total}"

        # ── Translator ──
        self.on_progress("Translator", "running", index, f"{label} — Đang chuyển đổi...")
        update_translation_segment(seg_id, status="translating")
        self._log("Translator", f"{label} — Bắt đầu chuyển đổi")

        translated = self._run_translator(source, analysis, config, channel_name, call_fn,
                                          story_context=story_context, prev_tail=prev_tail)

        if self._cancelled:
            return translated

        # ── Reviewer ──
        for attempt in range(max_retries + 1):
            if self._cancelled:
                return translated

            self.on_progress("Reviewer", "running", index, f"{label} — Kiểm tra lần {attempt+1}...")
            self._log("Reviewer", f"{label} — Kiểm tra lần {attempt+1}")

            review = self._run_reviewer(source, translated, analysis, channel_name, call_fn)

            if review["passed"]:
                final_text = review.get("corrected_text", translated)
                update_translation_segment(seg_id, result_text=final_text, status="done")
                self.on_progress("Reviewer", "passed", index, f"{label} ✅")
                self._log("Reviewer", f"{label} ✅ Passed")

                self._increment_completed()
                self.on_segment_done(index, final_text)
                return final_text

            # Retry
            if attempt < max_retries:
                feedback = review.get("feedback", "")
                self.on_progress("Translator", "retrying", index, f"{label} — Sửa lỗi: {feedback[:50]}")
                self._log("Translator", f"{label} — Retry: {feedback[:80]}")
                translated = self._run_translator_with_feedback(
                    source, translated, feedback, analysis, config, channel_name, call_fn,
                    story_context=story_context, prev_tail=prev_tail,
                )

        # Max retries exhausted — accept what we have
        update_translation_segment(seg_id, result_text=translated, status="done")
        self.on_progress("Reviewer", "passed", index, f"{label} ✅ (max retries)")
        self._log("Reviewer", f"{label} ✅ Accepted after max retries")

        self._increment_completed()
        self.on_segment_done(index, translated)
        return translated

    # ─── Agent implementations ───

    def _summarize_segment(self, translated_text: str, prev_summary: str, call_fn) -> str:
        """Generate a running story context summary after translating a segment.
        Uses a lightweight model (data_collector/flash) for speed.
        Returns updated summary combining previous context + new events."""

        prev_section = ""
        if prev_summary:
            prev_section = f"""【これまでの物語の状況】
{prev_summary}

"""

        prompt = f"""{prev_section}【今回変換したセグメント】
{translated_text[:2000]}

【タスク】
上記の内容を基に、物語の現在の状況を簡潔にまとめてください（5-8行以内）。
以下の情報を含めてください：
1. 登場人物とその現在の状況・感情
2. 重要な出来事（何が起きたか）
3. 場面設定（今どこにいるか）
4. 人物間の関係性の変化
5. 使用した特殊な表現・方言・ニックネーム

前回のまとめがある場合は、新しい情報を統合して更新してください。
古い情報は削除せず、現在も有効な情報は保持してください。

簡潔な日本語のまとめのみを返してください。"""

        system = "あなたは物語の要約専門家です。変換済みテキストから物語の状況を簡潔にまとめます。"
        try:
            result = call_fn(system, prompt, "data_collector")
            summary = result.strip() if result else prev_summary
            # Hard cap: keep summary under 1500 chars to avoid prompt bloat
            if len(summary) > 1500:
                summary = summary[:1500]
            return summary
        except Exception:
            return prev_summary  # If summary fails, keep previous context

    def _run_analyzer(self, full_text: str, config: dict, call_fn) -> dict:
        """Agent 1: Analyze full source text, detect ALL foreign elements, create mapping."""
        genre = config.get("genre", "")
        audience = config.get("audience", "")
        setting = config.get("setting", "")

        # Send full text (up to 50000 chars to stay within model limits)
        analysis_text = full_text[:50000]

        prompt = f"""以下のテキスト全体を分析してください。すべての登場人物・地名・組織を漏れなく抽出してください。

【テキスト全文】
{analysis_text}

【分析タスク】
1. 原文の言語を特定（vi=ベトナム語、ko=韓国語、en=英語、zh=中国語、other=その他）
2. すべての登場人物の名前を抽出し、日本語名（ひらがな）に変換
   - ベトナム人名 → 日本人名（例: Nguyễn Minh → みなみ しゅん）
   - 韓国人名 → 日本人名（例: 김민수 → きむら みのる）
   - 中国人名 → 日本人名（例: 李明 → あかり めい）
   - 英語圏の名前 → カタカナ（例: John Smith → ジョン・スミス）
   - ニックネーム・あだ名も含める
3. すべての地名を抽出し、日本の対応地名に変換
   - 首都 → 東京、大都市 → 大阪/名古屋、港町 → 横浜/神戸 など論理的に対応
4. 文化的要素（食べ物、祭り、習慣、学校制度など）を日本の対応要素に変換
5. 組織名（会社、学校、政府機関など）を日本の対応組織に変換
6. 物語の背景設定を特定（舞台はどの国か）
7. テキストの雰囲気とトーンを分析

ジャンル: {genre}
対象読者: {audience}
設定: {setting}

【重要】
- テキスト全体を読み、後半に登場するキャラクターも漏れなく抽出すること
- 同一人物の別称（フルネーム、姓のみ、名のみ、あだ名）はすべてマッピングに含めること
- 日本人名はひらがなで表記（例: たなか ゆうき）
- 外国人名（欧米など）はカタカナで表記（例: マイケル）
- 各マッピング項目に「ベトナム語での意味説明」を必ず付与すること（ユーザーが確認するため）

【出力形式 — JSON】
{{
  "source_lang": "vi|ko|en|zh|other",
  "has_foreign_elements": true/false,
  "is_foreign_setting": true/false,
  "original_setting_country": "元の舞台の国",
  "tone": "描写",
  "mapping": {{
    "names": {{"元の名前": {{"ja": "日本語名（ひらがな）", "vi": "Nghĩa tiếng Việt và lý do chọn tên này"}}}},
    "places": {{"元の地名": {{"ja": "日本の地名", "vi": "Nghĩa tiếng Việt, tương đương với gì"}}}},
    "culture": {{"元の文化要素": {{"ja": "日本の対応要素", "vi": "Giải thích tiếng Việt"}}}},
    "organizations": {{"元の組織名": {{"ja": "日本の対応組織", "vi": "Giải thích tiếng Việt"}}}}
  }},
  "characters_summary": [
    {{"original_name": "元の名前", "japanese_name": "日本語名", "role": "主人公/友人/敵など", "role_vi": "Vai trò bằng tiếng Việt", "first_appearance": "最初に登場する箇所の概要"}}
  ],
  "notes": "追加の変換メモ"
}}

JSONのみ返してください。"""

        system = "あなたはテキスト分析と文化的ローカライゼーションの専門家です。ベトナム語・韓国語・中国語・英語などの多言語コンテンツを分析し、すべての登場人物・地名・文化要素を漏れなく抽出して、日本語への変換マッピングを作成します。"
        result = call_fn(system, prompt, "data_collector")

        # Parse JSON from response
        try:
            # Try to extract JSON from response
            json_match = re.search(r"\{[\s\S]*\}", result)
            if json_match:
                return json.loads(json_match.group())
        except (json.JSONDecodeError, AttributeError):
            pass

        # Fallback — raise error so user knows analysis failed
        raise ValueError(
            "Analyzer không thể phân tích văn bản. "
            "Vui lòng thử lại hoặc kiểm tra API key/model."
        )

    def _run_translator(self, source_text: str, analysis: dict, config: dict,
                        channel_name: str, call_fn,
                        story_context: str = "", prev_tail: str = "") -> str:
        """Agent 2: Convert content to Japanese with full story context."""
        keigo = config.get("keigo", "casual")
        narrator = config.get("narrator", "neutral")
        style = config.get("style", "podcast")
        mapping_str = json.dumps(analysis.get("mapping", {}), ensure_ascii=False, indent=2)

        keigo_map = {
            "casual": "だ/である体（カジュアル）",
            "polite": "です/ます体（丁寧）",
            "formal": "敬語（フォーマル）",
        }
        narrator_map = {
            "male": "男性的（僕/俺）",
            "female": "女性的（私/あたし）",
            "neutral": "中性的（私）",
        }
        style_map = {
            "podcast": "ポッドキャスト台本（間の指示あり、TTS最適化）",
            "story": "小説/物語（純粋な散文）",
            "light_novel": "ライトノベルスタイル",
        }

        rules = CONVERSION_RULES_JA.replace("{channel_name}", channel_name)

        # Build story context section (running summary of story so far)
        context_section = ""
        if story_context:
            context_section += f"""
【物語の現在の状況（前のセグメントまでの要約）】
{story_context}
"""
        if prev_tail:
            context_section += f"""
【前のセグメントの末尾（文体を引き継いでください）】
{prev_tail}
"""

        prompt = f"""{rules}

【変換マッピング（Analyzerの結果）— 必ずこのマッピングに従ってください】
{mapping_str}

【スタイル設定】
- 文体: {keigo_map.get(keigo, keigo)}
- 語り手: {narrator_map.get(narrator, narrator)}
- 出力形式: {style_map.get(style, style)}
{context_section}
【原文】
{source_text}

【重要な指示】
- マッピング表の人物名・地名を必ず使用すること（独自に変換しない）
- 前のセグメントとの文体・語り口・人物の呼び方を一貫させること
- 物語の状況要約がある場合、登場人物の状態や感情の連続性を維持すること
変換後のテキストのみを返してください。メタコメントや説明は不要です。"""

        system = "あなたはプロの日本語コンテンツライターです。外国語のコンテンツを、ネイティブの日本語として自然に読める形に変換します。翻訳ではなく、文化的に適応したコンテンツ変換を行います。"
        result = call_fn(system, prompt, "script_writer")
        return result.strip() if result else ""

    def _run_translator_with_feedback(self, source_text: str, previous_translation: str,
                                      feedback: str, analysis: dict, config: dict,
                                      channel_name: str, call_fn,
                                      story_context: str = "", prev_tail: str = "") -> str:
        """Agent 2 retry: Fix translation based on reviewer feedback, preserving context."""
        rules = CONVERSION_RULES_JA.replace("{channel_name}", channel_name)
        mapping_str = json.dumps(analysis.get("mapping", {}), ensure_ascii=False, indent=2)

        # Preserve story context in retry
        context_section = ""
        if story_context:
            context_section += f"""
【物語の現在の状況】
{story_context}
"""
        if prev_tail:
            context_section += f"""
【前のセグメントの末尾】
{prev_tail}
"""

        prompt = f"""{rules}

【変換マッピング】
{mapping_str}
{context_section}
【原文】
{source_text}

【前回の変換結果】
{previous_translation}

【レビューアーのフィードバック — 修正必須】
{feedback}

上記のフィードバックに基づいて、変換結果を修正してください。
マッピング表の人物名・地名を必ず使用し、前のセグメントとの一貫性を維持してください。
修正後のテキストのみを返してください。"""

        system = "あなたはプロの日本語コンテンツライターです。レビューフィードバックに基づいてテキストを修正します。"
        result = call_fn(system, prompt, "script_writer")
        return result.strip() if result else previous_translation

    def _run_reviewer(self, source_text: str, translated_text: str,
                      analysis: dict, channel_name: str, call_fn) -> dict:
        """Agent 3: Review translated content for compliance."""
        mapping_str = json.dumps(analysis.get("mapping", {}), ensure_ascii=False, indent=2)

        prompt = f"""以下の変換結果を厳密にチェックしてください。

【変換マッピング】
{mapping_str}

【原文（参考）】
{source_text[:1500]}

【変換結果（チェック対象）】
{translated_text}

【チェック項目】
1. 韓国の要素が残っていないか（人名、地名、文化、歴史）
2. 英語が残っていないか
3. 日本の固有名詞がひらがなで書かれているか
4. 外国の固有名詞がカタカナで書かれているか
5. 数字がアラビア数字で書かれているか
6. マッピングが一貫して適用されているか
7. CTAのチャンネル名が「{channel_name}」になっているか
8. TTS向けに自然な文章か（文が長すぎないか、同音異義語がないか）
9. 文体がネイティブの日本語として自然か

【出力形式 — JSON】
{{
  "passed": true/false,
  "issues": ["問題1", "問題2"],
  "feedback": "修正が必要な場合の具体的な指示",
  "corrected_text": "軽微な修正の場合、修正済みテキスト（大きな問題がある場合は空文字）"
}}

JSONのみ返してください。"""

        system = "あなたは品質管理の専門家です。日本語コンテンツの変換品質を厳密にチェックします。"
        result = call_fn(system, prompt, "quality_checker")

        try:
            json_match = re.search(r"\{[\s\S]*\}", result)
            if json_match:
                review = json.loads(json_match.group())
                return {
                    "passed": review.get("passed", True),
                    "issues": review.get("issues", []),
                    "feedback": review.get("feedback", ""),
                    "corrected_text": review.get("corrected_text", ""),
                }
        except (json.JSONDecodeError, AttributeError):
            pass

        # If we can't parse, assume passed
        return {"passed": True, "issues": [], "feedback": "", "corrected_text": ""}
