"""Range une déclaration IA de Steam par usage : code, visuels, audio, texte, IA pendant le jeu.

Les morceaux de phrase négatifs (« no AI-generated art », « all music was made by real people »)
sont écartés avant de chercher les mots-clés. overrides.json corrige à la main les cas mal rangés.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent

RULES = {
    "code": r"\bcod(e|es|ing|ed)\b|programm|copilot|\bcursor\b|claude|codex|debug|boilerplate|refactor|"
            r"software development|unit test|代码|编程|コード|プログラ",
    "visuals": r"\bart\b|artwork|image|illustrat|textur|\bicons?\b|visual|graphic|sprite|portrait|"
               r"background|\b2d\b|\b3d\b|concept art|capsule|picture|poster|upscal|animation|\bvideo|cutscene|"
               r"drawing|painting|thumbnail|\bui\b|\bgui\b|logo|3d models?|modell?ing|avatar|photo|midjourney|"
               r"stable diffusion|dall|firefly|nano banana|character-face|美术|图片|图像|イラスト|画像|立绘",
    "audio": r"voice|\bvo\b|\btts\b|text[- ]to[- ]speech|music|sound|audio|narrat|\bsongs?\b|suno|elevenlabs|vocal|"
             r"dubbing|soundtrack|\bsfx\b|配音|音乐|语音|音声|ボイス",
    "text": r"translat|locali[sz]|writing|\btexts?\b(?![- ]to[- ]speech)|dialog|story|stories|descriptions?|proofread|"
            r"gramma|\blore\b|narrative|chatgpt|\bllm\b|\bgpt\b|copy ?edit|wording|翻译|文本|翻訳|テキスト",
    "live": r"real[- ]time|live[- ]generated|during gameplay|at runtime|players? can (generate|create|chat|talk)|"
            r"respond(s|ing)? (uniquely )?to (the |your )?(player|choices)|player input|conversation|chat with|"
            r"ai[- ](driven|powered) npc|dynamically generated|generated (live|on the fly|dynamically)|"
            r"large language model|\bllm\b|dlss|neural rendering|while (you )?play|as you play|实时|リアルタイム",
    "marketing": r"store page|promotional|marketing|capsule|trailer|steam page|advertis|library (artwork|images?)",
}
RULES = {k: re.compile(v, re.I) for k, v in RULES.items()}
NEG = re.compile(r"\b(no|not|never|none|nothing|without|neither|nor)\b|n't\b", re.I)
HUMAN = re.compile(r"^\W*all\b.*\b(by|from)\b|\b(entirely|solely|exclusively) by\b|"
                   r"\b(made|created|composed|performed|written|drawn|recorded|crafted|designed|programmed)\b.*"
                   r"\bby (real|human|professional|our|me\b|the dev)", re.I)
MENTIONS_AI = re.compile(r"\bAI\b|generat|\bLLM\b|GPT|machine", re.I)
SPLIT = re.compile(r"(?<=[.!?。])\s+|\n+|;|,? but |, however|\bwhile\b", re.I)
OVERRIDES = ROOT / "overrides.json"


def positive(text):
    return " . ".join(p for p in SPLIT.split(text) if p and not NEG.search(p)
                      and not (HUMAN.search(p) and not MENTIONS_AI.search(p)))


def classify(text, appid=None):
    t = positive(text)
    flags = {k: bool(r.search(t)) for k, r in RULES.items()}
    if appid and OVERRIDES.exists():
        flags.update(json.loads(OVERRIDES.read_text()).get(str(appid), {}))
    return flags


def category(f):
    if f["code"] and f["visuals"]:
        return "code+visuels"
    if f["code"]:
        return "code"
    if f["visuals"]:
        return "visuels"
    if f["audio"] or f["text"] or f["live"]:
        return "autre"
    return "non précisé"
