"""
Supervisor Agent — Giám sát chất lượng từng phần podcast.

Nhận output từ mỗi Section Writer, đánh giá theo checklist,
nếu FAIL → yêu cầu viết lại (tối đa 2 lần).
Nếu PASS → chuyển sang phần tiếp theo.
Hỗ trợ route qua 9router khi ROUTER_URL được cấu hình.
"""

import logging
import requests
import google.generativeai as genai
from config import (
    AGENT_KEYS, GEMINI_MODEL_SUPERVISOR, SUPERVISOR_TEMPERATURE, MAX_OUTPUT_TOKENS,
    TTS_RULES, ROUTER_URL, ROUTER_API_KEY,
)

_log = logging.getLogger(__name__)

SUPERVISOR_SYSTEM = f"""あなたはNPBポッドキャスト台本の品質審査官です。
台本の各セクションを審査し、PASSかFAILを判定します。

【審査基準】
1. 選手名が具体的に挙がっているか
2. 分析に根拠があるか
3. 800文字以上か
4. 英語やマークダウンが含まれていないか
5. 日本人名がひらがな、外国人名がカタカナか
6. 話し言葉で書かれているか
7. メタ応答（「承知しました」等）が混入していないか

【出力フォーマット — 簡潔に】

問題なければ：
判定：PASS

軽微な修正が必要な場合：
判定：PASS
修正点：（修正箇所だけ簡潔に列挙。元テキスト全体は出力しない）

不合格の場合：
判定：FAIL
理由：（2〜3行）
改善指示：（何を足すか具体的に）

【重要】
- PASSの場合、元テキスト全体を出力しないこと（トークン節約）
- 修正箇所だけ「○○→△△」形式で書く
"""


def _call_supervisor(system_prompt: str, user_input: str) -> str:
    """Gọi Supervisor — qua 9router nếu ROUTER_URL được set.
    Supervisor chỉ cần review + output lại section, nên max_tokens=8192 là đủ."""
    if ROUTER_URL:
        url = f"{ROUTER_URL}/v1/chat/completions"
        model = GEMINI_MODEL_SUPERVISOR
        headers = {"Content-Type": "application/json"}
        if ROUTER_API_KEY:
            headers["Authorization"] = f"Bearer {ROUTER_API_KEY}"
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_input},
            ],
            "temperature": SUPERVISOR_TEMPERATURE,
            "max_tokens": min(MAX_OUTPUT_TOKENS, 8192),
            "stream": False,
        }
        _log.info(f"9router supervisor: POST {url} model={model}")
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=120)
            resp.raise_for_status()
            data = resp.json()
            choices = data.get("choices", [])
            if choices:
                return choices[0].get("message", {}).get("content", "")
        except requests.exceptions.Timeout:
            _log.warning(f"9router supervisor: TIMEOUT after 120s")
        except Exception as e:
            _log.warning(f"9router supervisor: error — {e}")
        return ""

    # Direct Gemini SDK
    api_key = AGENT_KEYS.get("quality_checker", "")
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(
        model_name=GEMINI_MODEL_SUPERVISOR,
        system_instruction=system_prompt,
        generation_config=genai.GenerationConfig(
            temperature=SUPERVISOR_TEMPERATURE,
            max_output_tokens=MAX_OUTPUT_TOKENS,
        ),
    )
    response = model.generate_content(user_input)
    try:
        return response.text
    except ValueError:
        if response.candidates:
            parts = response.candidates[0].content.parts
            if parts:
                return parts[0].text
        return ""


def review_section(section_text: str, section_name: str) -> dict:
    """1つのセクションを審査する。

    Returns:
        dict with keys:
        - passed: bool
        - text: str (修正済みテキスト or 元テキスト)
        - reason: str (FAILの理由)
        - instruction: str (改善指示)
    """
    prompt = f"""以下の「{section_name}」セクションを審査してください。

{section_text}"""

    result_text = _call_supervisor(SUPERVISOR_SYSTEM, prompt)
    if not result_text:
        # Response rỗng (timeout/safety filter) → auto PASS với元テキスト
        return {"passed": True, "text": section_text, "reason": "", "instruction": ""}

    # Parse response
    passed = "PASS" in result_text.upper().split("\n")[0] if result_text.strip() else False

    if passed:
        # PASS — luôn dùng元テキスト (supervisor không output lại full text nữa)
        return {"passed": True, "text": section_text, "reason": "", "instruction": ""}
    else:
        reason = ""
        instruction = ""
        for sep_r in ("理由：", "理由:"):
            if sep_r in result_text:
                parts = result_text.split(sep_r, 1)[1]
                for sep_i in ("改善指示：", "改善指示:"):
                    if sep_i in parts:
                        reason, instruction = parts.split(sep_i, 1)
                        break
                else:
                    reason = parts
                break

        return {
            "passed": False,
            "text": section_text,
            "reason": reason.strip(),
            "instruction": instruction.strip(),
        }
