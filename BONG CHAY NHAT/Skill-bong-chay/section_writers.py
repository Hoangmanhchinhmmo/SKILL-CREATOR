"""
Section Writers — Mỗi agent viết 1 phần cụ thể của podcast.
Supervisor sẽ review từng phần, yêu cầu viết lại nếu cần.
"""

import google.generativeai as genai
from config import AGENT_KEYS, AGENT_MODELS, GEMINI_MODEL, TEMPERATURE, MAX_OUTPUT_TOKENS, TTS_RULES


def _call_gemini(system_prompt: str, user_input: str, agent_key: str) -> str:
    api_key = AGENT_KEYS.get(agent_key, "")
    if not api_key:
        raise ValueError(f"API key not configured: {agent_key}")
    model_name = AGENT_MODELS.get(agent_key, GEMINI_MODEL)
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(
        model_name=model_name,
        system_instruction=system_prompt,
        generation_config=genai.GenerationConfig(
            temperature=TEMPERATURE,
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


# === Shared TTS rules for all writers ===
WRITER_RULES = f"""
【TTS絶対ルール】
{TTS_RULES}
- マークダウン（###, **, ---, 箇条書き）は一切禁止
- 記号（■●★→＝）は一切禁止
- セクション見出しや時間指示は禁止
- 許可される唯一の区切り：（間）
- （間）を2つ以上連続で書くのは禁止
- すべて話し言葉で書く
- 最低800文字以上書くこと

【致命的禁止事項】
- 「はい、承知いたしました」「了解しました」「以下の通りです」は絶対に書かない
- 「ご指定の内容を」「ご質問にお答え」「解説します」で始めない
- AIの応答文は一切混入させない
- 最初の1文字目から、視聴者に語りかける台本を書くこと
"""


# ============================================================
# Section 1: Opening (HCRP)
# ============================================================

def write_opening(context: str) -> str:
    system = f"""あなたはポッドキャストのオープニングライターです。
30秒の冒頭部分だけを書きます。以下の4要素を必ず含めること：

【重要：AIの応答文は絶対に書かない】
「はい」「承知しました」「了解です」「以下の通り」は絶対に書かない。
最初の1文字目から、視聴者に語りかける台本を書くこと。

1. フック（最初の1文は必ず修辞疑問文。試合の本質を鋭く突く）
   良い例：「なぜ、昨年のBクラス同士の開幕戦が、セリーグを占う最重要な一戦なのか。」
   良い例：「なぜ、好調のはんしんが、この試合だけは危ないのか。」
   悪い例：「開幕戦の勝利で弾みをつけるのはどちらでしょうか。」← 弱すぎる
   → フックは「意外性」「逆説」「常識への挑戦」を含むこと
   → フックの直後に、答えの方向を示す1〜2文を続ける

2. チャンネル挨拶（フックの直後。短く統一）
   「みなさん、チャンネルへようこそ。
   このチャンネルでは、データと戦術で、プロ野球を深く読み解いています。」
   → この2文だけ。長くしない。

3. 視聴維持フック
   「今日の分析を聞けば〜」「最後に驚く予測も〜」

4. ロードマップ
   「今日は3つの視点で読み解きます。まず〜。次に〜。そして〜。」
   → 3つの具体的な内容を予告する

{WRITER_RULES}"""

    return _call_gemini(system, f"以下の試合情報でオープニングを書いてください：\n{context}", "script_writer")


# ============================================================
# Section 2: 先発投手の徹底比較
# ============================================================

def write_pitching_analysis(data: str, analysis: str) -> str:
    system = f"""あなたはNPB投手分析の専門家です。
両チームの先発投手を徹底比較するセクションだけを書きます。

【必ず含める内容】
- 両先発の名前（ひらがな）
- 球種の特徴（ストレートの球速帯、変化球の種類）
- 制球力（四球の傾向）
- 左打者/右打者との相性
- 直近の調子（良い点、課題）
- 立ち上がりの傾向
- 相手打線との過去の対戦
- 2人の対照的な特徴をまとめる結論

1500文字以上で詳しく書くこと。
選手名を必ず挙げ、「投手」とだけ書くのは禁止。

{WRITER_RULES}"""

    prompt = f"以下のデータと分析をもとに、先発投手比較セクションを書いてください：\n\n【データ】\n{data}\n\n【分析】\n{analysis}"
    return _call_gemini(system, prompt, "tactical_analyst")


# ============================================================
# Section 3: 打線の力関係
# ============================================================

def write_batting_analysis(data: str, analysis: str) -> str:
    system = f"""あなたはNPB打撃分析の専門家です。
両チームの打線を比較するセクションだけを書きます。

【必ず含める内容】
- 両チームの主力打者名（ひらがな/カタカナ）
- 1〜2番の出塁能力
- クリーンアップ（3〜5番）の特徴と破壊力
- 下位打線の厚み
- 得点パターン（序盤型か終盤型か、一発依存かつなぎか）
- 機動力（盗塁、足の速さ）
- 勝負所での強さ
- 外国人打者の貢献と適応状況
- 両打線の対照的な特徴をまとめる結論

1500文字以上で詳しく書くこと。

{WRITER_RULES}"""

    prompt = f"以下のデータと分析をもとに、打線比較セクションを書いてください：\n\n【データ】\n{data}\n\n【分析】\n{analysis}"
    return _call_gemini(system, prompt, "script_writer")


# ============================================================
# Section 4: 救援陣・守備・外国人選手
# ============================================================

def write_bullpen_defense(data: str, analysis: str) -> str:
    system = f"""あなたはNPBの救援投手と守備の専門家です。
救援陣、守備力、外国人選手を分析するセクションを書きます。

【必ず含める内容】
■ 救援陣比較：
- 勝利の方程式（7回→8回→9回、投手名を明記）
- セットアップと抑えの特徴
- 弱点やリスク
- 両チームの救援陣のどちらが上か

■ 守備力比較：
- 内野守備の堅さ（二遊間の名前）
- 外野守備の範囲
- 捕手のリード力と盗塁阻止
- バッテリーの相性

■ 外国人選手：
- 登録外国人の名前（カタカナ）
- 貢献度と弱点

1500文字以上で詳しく書くこと。

{WRITER_RULES}"""

    prompt = f"以下のデータと分析をもとに、救援陣・守備・外国人セクションを書いてください：\n\n【データ】\n{data}\n\n【分析】\n{analysis}"
    return _call_gemini(system, prompt, "tactical_analyst")


# ============================================================
# Section 5: 独自の視点
# ============================================================

def write_unique_perspective(data: str, analysis: str) -> str:
    system = f"""あなたはNPBの名コラムニストです。
他の誰も語っていない、深い独自の視点を展開するセクションを書きます。

【重要：AIの応答文は絶対に書かない】
「はい」「承知しました」「了解です」は絶対に書かない。
「ここで、ひとつ大事な話をします。」で始めること。

【深さの基準 — v1.5 benchmark】
以下のような「哲学レベルの分析」を目指す：
ベンチマーク例：
「この開幕戦でぶつかるのは、単に2つのチームではない。
 "負けない野球"を突き詰める哲学と、
 "打ち勝つ野球"へと生まれ変わろうとする哲学。
 この2つの異なる再建方針が、どちらが正しいのかを証明する最初の戦いなのだ。」

→ このレベルの深さを必ず出すこと。
→ 表面的な戦術論ではなく、「なぜこのチームはこう戦うのか」という哲学に踏み込む。

以下の角度から1つだけ選んで深掘り：
1. 哲学の衝突：両チームのチーム作りの思想が根本的にどう違うか
2. 監督の賭け：この試合の采配に込められた、シーズン全体への布石
3. 心理戦争：Bクラスの悔しさ、ファンの期待、選手の重圧がどう作用するか
4. 世代交代：ベテランと若手の力関係が、この1試合でどう表れるか
5. 歴史の教訓：過去の類似した状況で何が起きたか、そこから何を学ぶか

必ず以下の構成で書く：
- 導入：「ここで、ひとつ大事な話をします。」
- 問題提起：多くの人が見落としているポイント
- 深掘り：なぜそうなのか、具体的に説明
- 対比：2つの考え方をぶつける
- 結論：1文で強く締める（「〜なのだ。」「〜の戦いである。」）

1500文字以上で書くこと。

{WRITER_RULES}"""

    prompt = f"以下のデータと分析をもとに、独自の視点セクションを書いてください：\n\n【データ】\n{data}\n\n【分析】\n{analysis}"
    return _call_gemini(system, prompt, "unique_perspective")


# ============================================================
# Section 6: 予測 + 締め
# ============================================================

def write_prediction_ending(data: str, analysis: str, perspective: str) -> str:
    system = f"""あなたはNPB予測の専門家です。
試合の予測と、ポッドキャストの締めくくりを書きます。

【予測セクション — 必ず含める】
- 勝敗予測（どちらが勝つか明言する）
- 予想スコア（例：「3対1」）
- 根拠3つ（具体的に）
- リスク要因（予測が外れるシナリオ）
- 自信度（言葉で：「かなり自信あり」「五分五分」など）

【締めセクション — 必ず含める】
- 視聴者への問いかけ（議論を促す質問）
- コメント促進
- チャンネル登録の自然な呼びかけ
- 印象に残る最後の1文

800文字以上で書くこと。

{WRITER_RULES}"""

    prompt = f"""以下のデータ、分析、視点をもとに、予測と締めを書いてください：

【データ】
{data}

【分析】
{analysis}

【独自の視点】
{perspective}"""
    return _call_gemini(system, prompt, "script_writer")
