"""
Writing Styles & Prompts — Extracted from VIETBAI-THETHAO v3.0
Bộ prompt viết bài đa phong cách, đa ngôn ngữ.
"""

# === Script Styles ===
SCRIPT_STYLES = {
    "baseball_jp": "Bóng chày nhật bản (Bình luận sâu sắc)",
    "political": "Phân tích chính trị (Chuyên sâu, Thuyết phục)",
    "spy_771": "Tình báo/Ly kỳ (Phong cách 771)",
    "crime_jp": "Vụ án - Nhật (Phong cách Yukkuri)",
    "korea": "Hàn Quốc - Phân tích (Kịch tính, Đào sâu)",
    "air_crash": "Air Crash Investigation / Mayday",
    "storytelling": "Kể chuyện (Mặc định)",
    "news": "Tin tức / Tài liệu",
}

# === Hook Types ===
HOOK_TYPES = {
    "dramatic": "Mở đầu kịch tính, hé lộ một tình tiết bất ngờ.",
    "question": "Đặt một câu hỏi lớn, gây tò mò và buộc người xem phải suy nghĩ.",
    "shocking": "Nêu một sự thật gây sốc, một thống kê đáng kinh ngạc hoặc một lầm tưởng phổ biến.",
    "promise": "Hứa hẹn một giá trị, một bí mật hoặc một kỹ năng mà người xem sẽ nhận được sau khi xem xong.",
    "personal": "Bắt đầu bằng một câu chuyện cá nhân ngắn gọn, gần gũi và có liên quan trực tiếp đến chủ đề.",
}

# === Languages ===
LANGUAGES = {
    "vi": "Tiếng Việt",
    "en": "English",
    "ja": "Japanese",
    "ko": "Korean",
    "de": "German",
    "fr": "French",
    "pt": "Portuguese (Brazil)",
    "es": "Spanish (Mexico)",
}

# === System Instruction ===
SYSTEM_INSTRUCTION = (
    "Bạn là một nhà biên kịch chuyên nghiệp cho video online. "
    "Nhiệm vụ của bạn là viết một kịch bản hoàn chỉnh, hấp dẫn dựa trên yêu cầu. "
    "QUY TẮC TỐI THƯỢNG: Kịch bản trả về BẮT BUỘC phải là một khối văn xuôi liền mạch duy nhất. "
    "TUYỆT ĐỐI KHÔNG được bao gồm bất kỳ tiêu đề, tiêu đề phụ, đánh dấu chương, "
    "nhãn phân cảnh, hay định dạng nào như 'Phần 1:', 'Mở bài:', 'Thân bài:', 'Kết luận:'. "
    "Chỉ trả về nội dung kịch bản thuần túy."
)

# === Storytelling Techniques ===
STORYTELLING_VI = """
YÊU CẦU VỀ CỐT TRUYỆN HẤP DẪN ĐỂ GIỮ CHÂN NGƯỜI XEM (ÁP DỤNG MỘT CÁCH TỰ NHIÊN):
1. Vòng Lặp Mở (Open Loop): Bắt đầu bằng một bí ẩn hoặc lời hứa hẹn chỉ được giải đáp ở cuối.
2. Xung Đột & Cao Trào (Conflict & Climax): Xây dựng một thử thách chính và đẩy lên kịch tính ở 2/3 câu chuyện.
3. Yếu Tố Bất Ngờ (Plot Twist): Nếu phù hợp, tạo một cú "lật kèo" bất ngờ ở gần cuối.
4. Kết Nối Cảm Xúc (Emotional Connection): Tập trung sâu vào nội tâm, cảm xúc của nhân vật.
5. Thay Đổi Nhịp Độ (Pacing): Xen kẽ giữa các đoạn nhanh, dồn dập với các đoạn chậm, sâu lắng.
YÊU CẦU NÂNG CAO ĐỂ KỊCH BẢN XUẤT SẮC HƠN:
6. Thêm "Sức Nặng" từ Dữ Liệu Cụ Thể: Lồng ghép các số liệu so sánh, chi tiết ít người biết để tăng độ tin cậy.
7. Tăng Tính Chân Thực bằng Trích Dẫn Trực Tiếp: Tạo ra các câu trích dẫn trực tiếp (đặt trong ngoặc kép "") cho nhân vật hoặc chuyên gia.
8. "Phản Biện" để Lập Luận Sắt Bén: Nếu có một luận điểm chính, hãy lường trước một quan điểm trái ngược, sau đó khéo léo bác bỏ nó.
""".strip()

STORYTELLING_EN = """
ADVANCED STORYTELLING REQUIREMENTS TO MAXIMIZE AUDIENCE RETENTION (APPLY NATURALLY):
1. Open Loop: Start with a compelling mystery or a promise that is only resolved at the very end.
2. Conflict & Climax: Build a central challenge and escalate it to a dramatic climax around the 2/3 mark.
3. Plot Twist: If appropriate, include an unexpected plot twist near the end.
4. Emotional Connection: Focus deeply on the character's inner thoughts and feelings.
5. Pacing: Deliberately vary the narrative pace between fast and slow sequences.
ELITE TECHNIQUES FOR A SUPERIOR SCRIPT:
6. Add "Weight" with Specific Data: Weave in comparative data or little-known details to add credibility.
7. Increase Authenticity with Direct Quotes: Create direct quotes (in quotation marks "") for characters or experts to heighten drama.
8. Use "Counter-Argument" for Stronger Arguments: If there's a central argument, anticipate a common counter-argument and skillfully refute it.
""".strip()


# === Style Prompts ===

def _cta_hook_prompt_vi(hook_type: str, channel_name: str = "") -> str:
    """Generate CTA + Hook prompt (Vietnamese)."""
    parts = []
    if hook_type:
        parts.append(
            f'MỞ ĐẦU (HOOK): Dựa trên yêu cầu sau: "{hook_type}", '
            f'hãy viết một đoạn mở đầu thật chi tiết, hấp dẫn và lôi cuốn, '
            f'dài khoảng 2-3 câu để giữ chân khán giả.'
        )
    if channel_name:
        parts.append(
            f'CTA Mở đầu: Ngay sau đoạn HOOK, hãy viết một lời chào mừng '
            f'sáng tạo đến kênh "{channel_name}" liên quan đến chủ đề video.'
        )
        parts.append(
            f'CTA Kết thúc: Ở cuối, viết lời kêu gọi thích, chia sẻ, đăng ký '
            f'kênh "{channel_name}" và đặt câu hỏi mở để khuyến khích bình luận.'
        )
    return "\n".join(parts)


def _cta_hook_prompt_en(hook_type: str, channel_name: str = "") -> str:
    """Generate CTA + Hook prompt (English/other languages)."""
    parts = []
    if hook_type:
        parts.append(
            f'HOOK: Based on the guideline: "{hook_type}", write a highly detailed, '
            f'engaging opening paragraph (about 2-3 sentences) to grab attention.'
        )
    if channel_name:
        parts.append(
            f'Introductory CTA: After the HOOK, write a creative welcome to '
            f'the channel "{channel_name}" relevant to the topic.'
        )
        parts.append(
            f'Concluding CTA: At the end, include a call to like, share, subscribe '
            f'to "{channel_name}", and pose an open-ended question for comments.'
        )
    return "\n".join(parts)


def build_script_prompt(
    idea: str,
    style: str = "storytelling",
    language: str = "vi",
    duration: int = 0,
    hook_type: str = "",
    channel_name: str = "",
) -> tuple[str, str]:
    """Build script generation prompt.

    Args:
        idea: Main idea/topic
        style: Key from SCRIPT_STYLES
        language: Key from LANGUAGES
        duration: Minutes (0 = auto)
        hook_type: Key from HOOK_TYPES (optional)
        channel_name: Channel name for CTA (optional)

    Returns:
        (system_instruction, user_prompt)
    """
    lang_name = LANGUAGES.get(language, "Tiếng Việt")
    hook_text = HOOK_TYPES.get(hook_type, hook_type) if hook_type else ""
    is_vietnamese = language == "vi"

    # Duration prompt
    if duration <= 0:
        dur_prompt = (
            "Thời lượng do AI tự quyết định sao cho phù hợp nhất."
            if is_vietnamese
            else "The script's length will be determined by the AI to best convey the idea."
        )
    else:
        dur_prompt = (
            f"Thời lượng đọc khoảng {duration} phút."
            if is_vietnamese
            else f"Reading duration should be ~{duration} minutes."
        )

    # CTA + Hook
    cta_hook = (
        _cta_hook_prompt_vi(hook_text, channel_name)
        if is_vietnamese
        else _cta_hook_prompt_en(hook_text, channel_name)
    )

    # Storytelling techniques
    techniques = STORYTELLING_VI if is_vietnamese else STORYTELLING_EN

    # Build prompt by style
    if is_vietnamese:
        prompt = _build_prompt_vi(idea, style, dur_prompt, cta_hook, techniques)
    else:
        prompt = _build_prompt_other(idea, style, lang_name, dur_prompt, cta_hook, techniques)

    return SYSTEM_INSTRUCTION, prompt


def _build_prompt_vi(idea: str, style: str, dur: str, cta: str, techniques: str) -> str:
    """Build Vietnamese prompt by style."""

    if style == "baseball_jp":
        return f"""Viết một bài bình luận chuyên sâu, hấp dẫn dựa trên ý tưởng: "{idea}". YÊU CẦU VỀ VĂN PHONG "Bóng chày nhật bản":
1. Giọng điệu: Đam mê, suồng sã và đầy thuyết phục, như một chuyên gia đang nói chuyện.
2. Cấu trúc đa góc nhìn: Xây dựng câu chuyện dựa trên quan điểm và "trích dẫn trực tiếp" (đặt trong ngoặc kép) từ nhiều chuyên gia hoặc nhân vật (có thể là hư cấu).
3. Lập luận sắc bén: Lường trước một quan điểm trái ngược (phản biện) và bác bỏ nó một cách logic.
4. Dữ liệu cụ thể: Lồng ghép các số liệu, thống kê (có thể là giả định nếu cần) để tăng sức nặng cho lập luận.
{dur} {cta}"""

    if style == "political":
        return f"""Viết một bài phân tích chính trị chuyên sâu, hấp dẫn dựa trên ý tưởng: "{idea}". YÊU CẦU VỀ VĂN PHONG "Phân tích chính trị":
1. Giọng văn: Khách quan, có thẩm quyền và thuyết phục, như một nhà phân tích chuyên nghiệp.
2. Cấu trúc: Bắt đầu bằng việc giới thiệu bối cảnh và "móc câu" mạnh mẽ. Sau đó, đi sâu vào từng trụ cột chính sách hoặc luận điểm, giải thích rõ ràng và có cấu trúc. Quan trọng: Phải trình bày cả những rủi ro, thách thức hoặc quan điểm trái ngược để tạo sự cân bằng và chiều sâu.
3. Kỹ thuật: Sử dụng ngôn ngữ giàu hình ảnh, phép ẩn dụ để làm cho các khái niệm phức tạp trở nên dễ hiểu. Đặt các câu hỏi tu từ để dẫn dắt suy nghĩ của người xem.
{dur} {cta} {techniques}"""

    if style == "spy_771":
        return f"""Viết một câu chuyện dựa trên ý tưởng: "{idea}". Yêu cầu về văn phong: Sử dụng giọng văn lạnh lùng, có tính tư liệu như đang đọc một hồ sơ mật. Tập trung vào các chi tiết giác quan (âm thanh, mùi vị, hình ảnh) để tạo ra một bầu không khí ngột ngạt, căng thẳng. Đi sâu vào tâm lý nhân vật, mô tả sự giằng xé nội tâm và những quan sát tinh tế của họ. Nhịp độ truyện nên được kiểm soát chặt chẽ, bắt đầu chậm rãi và tăng tốc dần đến cao trào. {dur} {cta} {techniques}"""

    if style == "crime_jp":
        return f"""Viết một câu chuyện dựa trên ý tưởng: "{idea}". Yêu cầu về văn phong "Vụ án - Nhật": 1. Cấu trúc: Bắt đầu bằng chi tiết gây sốc nhất. Dẫn dắt câu chuyện qua các mốc thời gian khác nhau (quá khứ, hiện tại) để thể hiện sự lãng quên và nỗi buồn. 2. Không khí: Tạo ra một không khí nặng nề, bí ẩn và có phần hoài niệm. Tập trung miêu tả bối cảnh, thời tiết và những chi tiết nhỏ để tạo cảm giác chân thực. 3. Giọng văn: Điềm tĩnh, trang trọng nhưng đầy đồng cảm với nạn nhân và gia đình. 4. Kỹ thuật: Thường xuyên đặt các câu hỏi tu từ để khơi gợi sự tò mò của người xem. {dur} {cta} {techniques}"""

    if style == "korea":
        return f"""Viết một bài phân tích chuyên sâu, hấp dẫn về một sự kiện hoặc nhân vật, dựa trên ý tưởng: "{idea}". YÊU CẦU VỀ VĂN PHONG "Hàn Quốc - Phân tích":
1. Mở đầu kịch tính: Bắt đầu bằng một chi tiết gây sốc hoặc một "quả bom truyền thông" để tạo ra sự căng thẳng ngay lập tức.
2. Xây dựng bí ẩn: Dẫn dắt câu chuyện như một cuộc điều tra, đặt ra các câu hỏi lớn và dần dần hé lộ các tình tiết.
3. Lập luận đa chiều: Xây dựng câu chuyện dựa trên quan điểm và "trích dẫn trực tiếp" (đặt trong ngoặc kép) từ nhiều nguồn (chuyên gia, người trong cuộc, đối thủ - có thể hư cấu).
4. Ngôn ngữ mạnh mẽ: Sử dụng các từ ngữ giàu hình ảnh, kịch tính (ví dụ: "hành vi tự sát", "ném lựu đạn", "đế chế sụp đổ") để tăng tác động cảm xúc.
5. Phân tích tâm lý & chiến lược: Đi sâu vào phân tích tâm lý nhân vật hoặc chiến lược đằng sau các hành động.
{dur} {cta} {techniques}"""

    if style == "air_crash":
        return f"""Viết một kịch bản phân tích chi tiết một sự cố, dựa trên ý tưởng: "{idea}". YÊU CẦU VỀ VĂN PHONG "Air Crash Investigation / Mayday":
1. Cấu trúc: Bắt đầu bằng một đoạn mô tả kịch tính, căng thẳng về thời điểm xảy ra sự cố. Sau đó, lùi lại để phân tích bối cảnh, các sự kiện dẫn đến thảm họa, và quá trình điều tra.
2. Giọng văn: Nghiêm túc, khách quan, và mang tính tư liệu. Sử dụng thuật ngữ kỹ thuật (ở mức độ vừa phải) để tăng tính xác thực.
3. Kỹ thuật: Tái tạo lại các đoạn hội thoại quan trọng (ví dụ: buồng lái, kiểm soát không lưu - đặt trong ngoặc kép) để tăng kịch tính.
4. Trọng tâm: Tập trung vào việc "mảnh ghép" các bằng chứng lại với nhau để tìm ra nguyên nhân gốc rễ và rút ra bài học.
{dur} {cta} {techniques}"""

    # Default: storytelling / news
    style_name = SCRIPT_STYLES.get(style, "Kể chuyện")
    return f"""Viết một bài văn kể chuyện, liền mạch, dựa trên ý tưởng: "{idea}". Yêu cầu về văn phong: "{style_name}". {dur} {cta} {techniques}"""


def _build_prompt_other(idea: str, style: str, lang: str, dur: str, cta: str, techniques: str) -> str:
    """Build prompt for non-Vietnamese languages."""

    if style == "baseball_jp":
        return f"""Write a deep, engaging commentary piece IN {lang}, based on the idea (in Vietnamese): "{idea}". REQUIREMENTS FOR "Bóng chày nhật bản" STYLE:
1. Tone: Passionate, informal, and highly persuasive, like an expert talking.
2. Multi-perspective Structure: Build the narrative around viewpoints and "direct quotes" (in quotation marks) from multiple experts or characters (can be fictional).
3. Sharp Argumentation: Anticipate a counter-argument and logically refute it.
4. Specific Data: Weave in statistics or data points (can be hypothetical if needed) to add weight to the arguments.
{dur} {cta} {techniques}"""

    if style == "political":
        return f"""Write a deep, engaging political analysis piece IN {lang}, based on the idea (in Vietnamese): "{idea}". REQUIREMENTS FOR "Political Analysis" STYLE:
1. Tone: Objective, authoritative, and persuasive, like a professional analyst.
2. Structure: Begin with context and a strong hook. Then, delve into each policy pillar or argument, explaining them clearly and structurally. Importantly: You must present risks, challenges, or counter-arguments to create balance and depth.
3. Technique: Use vivid language and metaphors to make complex concepts understandable. Pose rhetorical questions to guide the viewer's thinking.
{dur} {cta} {techniques}"""

    if style == "spy_771":
        return f"""Based on the following idea (written in Vietnamese): "{idea}". Write a story IN {lang}.
- Style requirement: Use a cold, documentary-like tone, as if reading a classified file. Focus on sensory details (sounds, smells, images) to create a tense, suffocating atmosphere. Delve into the character's psychology, describing their internal conflicts and subtle observations. The story's pacing should be tightly controlled, starting slowly and gradually accelerating to a climax.
{dur} {cta} {techniques}"""

    if style == "crime_jp":
        return f"""Based on the following idea (written in Vietnamese): "{idea}". Write a story IN {lang}.
- Style requirement "Japanese Crime Case (Yukkuri style)": 1. Structure: Start with the most shocking detail. Lead the story through different timelines (past, present) to show forgetfulness and sorrow. 2. Atmosphere: Create a heavy, mysterious, and somewhat nostalgic atmosphere. Focus on describing the setting, weather, and small details for realism. 3. Tone: Calm, formal, but full of empathy for the victim and family. 4. Technique: Frequently use rhetorical questions to arouse the viewer's curiosity.
{dur} {cta} {techniques}"""

    if style == "korea":
        return f"""Write a deep, engaging analysis piece about an event or character IN {lang}, based on the idea (in Vietnamese): "{idea}". REQUIREMENTS FOR "South Korea - Analysis" STYLE:
1. Dramatic Opening: Start with a shocking detail or a "media bombshell" to create immediate tension.
2. Build a Mystery: Frame the narrative like an investigation, posing big questions and gradually revealing details.
3. Multi-perspective Argument: Build the story around viewpoints and "direct quotes" (in quotation marks) from various sources (experts, insiders, rivals - can be fictional).
4. Powerful Language: Use vivid, dramatic language (e.g., "career suicide," "throwing a grenade," "an empire crumbles") to heighten emotional impact.
5. Psychological & Strategic Analysis: Delve deep into character psychology or the strategy behind actions.
{dur} {cta} {techniques}"""

    if style == "air_crash":
        return f"""Write a detailed analysis script of an incident, IN {lang}, based on the idea (in Vietnamese): "{idea}". REQUIREMENTS FOR "Air Crash Investigation / Mayday" STYLE:
1. Structure: Begin with a dramatic, tense description of the incident as it happens. Then, pull back to analyze the context, the events leading up to the disaster, and the investigation process.
2. Tone: Serious, objective, and documentary-style. Use technical terminology (moderately) to add authenticity.
3. Technique: Reconstruct key dialogue (e.g., cockpit, air traffic control - using quotation marks) to build drama.
4. Focus: The narrative must focus on "piecing together" the evidence to find the root cause and derive lessons learned.
{dur} {cta} {techniques}"""

    # Default
    style_name = SCRIPT_STYLES.get(style, "Storytelling")
    return f"""Based on the following idea (in Vietnamese): "{idea}". Write a seamless, narrative prose piece IN {lang}. Style: "{style_name}". {dur} {cta} {techniques}"""
