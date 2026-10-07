# 「4階、異常なし。」の声を Gemini TTS で事前に作る（ゲーム実行中に API は呼ばない）
#
# APIキー: 環境変数 GEMINI_API_KEY、なければ --env で指定した .env から読む（このリポジトリには置かない）
#   python tools/gen_voices.py --env "E:/Claude code/ItsukiFable/yt-experiment/.env"
#   python tools/gen_voices.py --only w_away1 --env ...      ← 1本だけ作り直す
#
# 出力: --raw に 24kHz WAV、voice/ にゲーム用の MP3（ffmpeg が必要）
import argparse, base64, json, os, re, subprocess, sys, time, urllib.request, urllib.error, wave

MODEL = "gemini-3.8-flash-tts"
ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/interactions"
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# 無線：警備会社の詰所にいる上司。疲れていて、小声で、淡々と
RADIO = ("Charon", "深夜の警備会社の無線です。詰所にいる疲れた中年男性が、小声で淡々と話します。"
                   "感情はほとんど出さず、ところどころ言いよどみます。ゆっくり、読点で間を取ってください。")
# それ：耳元のささやき。息が多く、抑揚がない
WHISPER = ("Enceladus", "耳元で、息を多く混ぜてささやきます。とても近い距離です。感情も抑揚もなく、"
                        "ゆっくり、一語ずつ置くように話してください。少しだけ笑っているようにも聞こえます。")
# 前任者たち：声色を変えて同じ言葉を重ねる
GHOSTS = [("Algenib", "かすれた低い声で、力なくつぶやきます。"),
          ("Achernar", "小さな声で、遠くからつぶやくように話します。"),
          ("Gacrux", "疲れきった声で、ゆっくりつぶやきます。"),
          ("Umbriel", "抑揚のない声で、ぼそっとつぶやきます。")]

LINES = {
    "r_greet":     (RADIO,   "お疲れさまです。異常があれば、報告を。"),
    "r_again":     (RADIO,   "……あれ。またあなたですか。"),
    "r_9th":       (RADIO,   "お疲れさまです。……9人目の方ですね。"),
    "r_empty":     (RADIO,   "4階は今日、誰もいないはずです。"),
    "r_saw":       (RADIO,   "……いま、何か映りました？"),
    "r_noreport":  (RADIO,   "報告、一件も届いてないんですけど。"),
    "r_noreport9": (RADIO,   "報告、届いてません。前の8人のも。"),
    "r_broken":    (RADIO,   "4階のカメラ、先月から壊れてるんですよ。"),
    "r_where":     (RADIO,   "じゃあ、今見てるのは、どこの映像ですか。"),
    "r_dontturn":  (RADIO,   "振り返らないでください。"),
    "r_arrived":   (RADIO,   "交代の人が、もう、そこに。"),
    "r_nomore":    (RADIO,   "交代の人は、もう来ません。"),
    "r_youare9":   (RADIO,   "あなたが、9人目です。"),
    "w_away1":     (WHISPER, "目を、離しましたね？"),
    "w_away2":     (WHISPER, "また、目を、離しましたね。"),
    "w_welcome":   (WHISPER, "……おかえりなさい。"),
    "w_watching":  (WHISPER, "……ずっと、見ていましたよ。"),
}
# 場面ごとの言い換え（毎回ランダムに選ぶ）。0番は上の r_empty などが担当
VARIANTS = {
    "r_b": ["4階のテナント、先月で全部退去してます。", "そのフロア、もう電気も止めてあるはずなんですけど。"],
    "r_c": ["……今、そっちで物音、しませんでした？", "……画面、少し暗くなってません？"],
    "r_d": ["報告ボタン、押してます？　こっち、何も来てなくて。", "さっきから、報告が、全部空っぽで届くんです。"],
    "r_e": ["そのカメラ、配線、切ってあるはずなんですけど。", "4階のカメラは、もう撤去したはずです。"],
    "r_f": ["……その映像、どこから来てるんですか。", "じゃあ、あなたは、何を見てるんですか。"],
    "r_g": ["動かないでください。", "画面から、目を離さないでください。"],
    "r_h": ["……あなたの後ろの人、誰ですか。", "交代の人、もう着いてますよね。"],
    "r_x": ["……すみません、ノイズがひどくて。", "何かあったら、すぐ言ってくださいね。", "前の担当の人も、この時間に連絡が途切れたんです。"],
}
for k, texts in VARIANTS.items():
    for i, t in enumerate(texts, 1):
        LINES[f"{k}{i}"] = (RADIO, t)

# 何度も遊んだ人だけに聞こえる無線（3回目・4回目・5回目以降・警備室）
REPEAT = {
    "r_p3":  "……3回目ですね。前の2回のこと、覚えてます？",
    "r_p4":  "……何回目ですか、これ。もう、来ないほうがいいですよ。",
    "r_p5a": "あなた、ずっとここにいるんじゃないですか。",
    "r_p5b": "……交代の記録、全部あなたの名前になってるんですけど。",
    "r_p5c": "もう、帰れないんですよ。",
    "r_rp":  "……前の回も、その人、そこにいましたよ。",
}
for k, t in REPEAT.items():
    LINES[k] = (RADIO, t)

# 1〜8人目：冒頭で番号を呼ばれ、最後に9人目までの残りを告げられる
for n in range(1, 9):
    LINES[f"r_pos{n}"] = (RADIO, f"お疲れさまです。……{n}人目の方ですね。")
    LINES[f"r_left{n}"] = (RADIO, "……次の人で、9人目です。" if n == 8 else f"……あと、{9 - n}人。")
for i, (v, st) in enumerate(GHOSTS):
    LINES[f"g_kotai{i}"] = ((v, st), "交代して。……交代して。")


def find_key(env_path):
    if os.environ.get("GEMINI_API_KEY"):
        return os.environ["GEMINI_API_KEY"]
    if env_path and os.path.isfile(env_path):
        for line in open(env_path, encoding="utf-8-sig", errors="replace"):
            m = re.match(r"\s*(?:GEMINI_API_KEY|GOOGLE_API_KEY)\s*=\s*(.+)$", line)
            if m:
                return m.group(1).strip().strip('"').strip("'")
    return None


def synth(text, voice, style, key):
    body = {
        "model": MODEL,
        "input": [{"type": "user_input", "content": [{
            "type": "text", "text": text,
            "annotations": [{"type": "speech_metadata", "style": style}]}]}],
        "response_format": {"type": "audio"},
        "generation_config": {"speech_config": [{"voice": voice}]},
    }
    req = urllib.request.Request(ENDPOINT, data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json", "x-goog-api-key": key})
    with urllib.request.urlopen(req, timeout=180) as r:
        res = json.load(r)
    datas = []
    def dig(o):
        if isinstance(o, dict):
            if o.get("type") == "audio" and isinstance(o.get("data"), str):
                datas.append(o["data"])
            for v in o.values(): dig(v)
        elif isinstance(o, list):
            for v in o: dig(v)
    dig(res)
    if not datas:
        raise RuntimeError("音声が応答にありません: " + json.dumps(res, ensure_ascii=False)[:300])
    return base64.b64decode(datas[-1])


def save_wav(blob, path):
    if blob[:4] == b"RIFF":                      # ヘッダ付き WAV
        open(path, "wb").write(blob)
    else:                                        # 生の PCM（24kHz/16bit/モノラル）
        w = wave.open(path, "wb"); w.setnchannels(1); w.setsampwidth(2); w.setframerate(24000)
        w.writeframes(blob); w.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--env")
    ap.add_argument("--only")
    ap.add_argument("--prefix", help="この接頭辞の行だけ作る（例: r_pos,r_left）")
    ap.add_argument("--raw", default=os.path.join(ROOT, "work", "voice_raw"))
    a = ap.parse_args()
    key = find_key(a.env)
    if not key:
        sys.exit("APIキーが見つかりません")
    os.makedirs(a.raw, exist_ok=True); os.makedirs(os.path.join(ROOT, "voice"), exist_ok=True)
    names = [a.only] if a.only else [n for n in LINES if not a.prefix or n.startswith(tuple(a.prefix.split(",")))]
    for name in names:
        (voice, style), text = LINES[name]
        raw = os.path.join(a.raw, name + ".wav")
        for attempt in range(4):
            try:
                save_wav(synth(text, voice, style, key), raw); break
            except urllib.error.HTTPError as e:
                msg = e.read().decode(errors="replace")[:300]
                print(f"  {name}: HTTP {e.code} {msg}")
                if e.code in (429, 500, 503): time.sleep(20 * (attempt + 1)); continue
                sys.exit(1)
        else:
            sys.exit(f"{name}: 生成に失敗")
        mp3 = os.path.join(ROOT, "voice", name + ".mp3")
        # 先頭と末尾の無音を詰めて、モノラル 64kbps の MP3 に
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", raw, "-af",
                        "silenceremove=start_periods=1:start_threshold=-50dB,areverse,"
                        "silenceremove=start_periods=1:start_threshold=-50dB,areverse,"
                        "apad=pad_dur=0.15,loudnorm=I=-18:TP=-2",
                        "-ac", "1", "-ar", "24000", "-b:a", "64k", mp3], check=True)
        print(f"  {name:<12} {voice:<10} {text}")
        time.sleep(4)


if __name__ == "__main__":
    main()
