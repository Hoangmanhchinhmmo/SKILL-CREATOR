"""
Supervisor Agent — Giám sát chất lượng từng phần podcast.

Nhận output từ mỗi Section Writer, đánh giá theo checklist,
nếu FAIL → yêu cầu viết lại (tối đa 2 lần).
Nếu PASS → chuyển sang phần tiếp theo.
"""

import google.generativeai as genai
from config import AGENT_KEYS, GEMINI_MODEL_SUPERVISOR, SUPERVISOR_TEMPERATURE, TTS_RULES

SUPERVISOR_SYSTEM = f"""あなたは、NPBポッドキャスト台本の品質審査官です。
台本の各セクションを個別に審査し、合格（PASS）か不合格（FAIL）を判定します。

【審査基準 — すべて満たす必要あり】

1. 深さ：選手名が具体的に挙がっているか（「投手」ではなく名前で）
2. 根拠：分析に理由があるか（「強い」だけでなく「なぜ強いか」）
3. 長さ：セクションが十分な長さか（最低800文字以上）
4. TTS：英語が含まれていないか、マークダウンがないか
5. 名前：日本人名がひらがな、外国人名がカタカナか
6. 数字：アラビア数字で書かれているか
7. 文体：話し言葉で自然に読めるか（書き言葉や箇条書きは禁止）
8. （間）：段落の切れ目に入っているか
9. 面白さ：対比、繰り返し、問いかけなど、聞いていて退屈しない工夫があるか

【致命的エラー — 見つけたら必ずFAILまたは削除修正】

10. メタ応答の混入禁止：
    「はい、承知いたしました」「了解しました」「以下の通りです」
    「ご指定の内容を」「ご質問にお答えします」
    → このようなAIの応答文が台本に混入していたら、必ず削除する
    → これは視聴者に聞かせる台本であり、AIへの指示応答ではない

11. （間）の連続禁止：
    （間）が2つ以上連続していたら、1つだけ残して削除する

12. 冒頭チェック：
    セクションの最初の文が、AIへの応答文（「はい」「承知」「了解」）で
    始まっていたら、その文を削除し、本文から始めるよう修正する

【出力フォーマット — 必ずこの形式で返答】

判定：PASS または FAIL

PASS の場合：
判定：PASS
修正済み：
（修正済みのテキストをそのまま出力。軽微な修正があればここで直す）

FAIL の場合：
判定：FAIL
理由：（不合格の理由を2〜3行で）
改善指示：（具体的に何を書き足すべきか）

【重要】
- PASSでも、軽微な修正（TTS表記、読点追加など）は自動で直して「修正済み」に出力する
- FAILの場合は、改善指示を具体的に書く（「もっと詳しく」は禁止。何を足すか明記する）
"""


def review_section(section_text: str, section_name: str) -> dict:
    """1つのセクションを審査する。

    Returns:
        dict with keys:
        - passed: bool
        - text: str (修正済みテキスト or 元テキスト)
        - reason: str (FAILの理由)
        - instruction: str (改善指示)
    """
    api_key = AGENT_KEYS.get("quality_checker", "")
    genai.configure(api_key=api_key)

    model = genai.GenerativeModel(
        model_name=GEMINI_MODEL_SUPERVISOR,
        system_instruction=SUPERVISOR_SYSTEM,
        generation_config=genai.GenerationConfig(
            temperature=SUPERVISOR_TEMPERATURE,
            max_output_tokens=4096,
        ),
    )

    prompt = f"""以下の「{section_name}」セクションを審査してください。

{section_text}"""

    response = model.generate_content(prompt)
    try:
        result_text = response.text
    except ValueError:
        # Response rỗng (safety filter hoặc max tokens) → auto PASS
        return {"passed": True, "text": section_text, "reason": "", "instruction": ""}

    # Parse response
    passed = "判定：PASS" in result_text or "判定: PASS" in result_text

    if passed:
        # Extract 修正済み text
        if "修正済み：" in result_text:
            revised = result_text.split("修正済み：", 1)[1].strip()
        elif "修正済み:" in result_text:
            revised = result_text.split("修正済み:", 1)[1].strip()
        else:
            revised = section_text
        return {"passed": True, "text": revised, "reason": "", "instruction": ""}
    else:
        reason = ""
        instruction = ""
        if "理由：" in result_text:
            parts = result_text.split("理由：", 1)[1]
            if "改善指示：" in parts:
                reason, instruction = parts.split("改善指示：", 1)
            elif "改善指示:" in parts:
                reason, instruction = parts.split("改善指示:", 1)
            else:
                reason = parts
        elif "理由:" in result_text:
            parts = result_text.split("理由:", 1)[1]
            if "改善指示:" in parts:
                reason, instruction = parts.split("改善指示:", 1)
            else:
                reason = parts

        return {
            "passed": False,
            "text": section_text,
            "reason": reason.strip(),
            "instruction": instruction.strip(),
        }
