"""LG K-EXAONE 2.5 API client for generating ACE-Step compatible song lyrics."""
import json
import os
import re
import socket
import urllib.error
import urllib.request

EXAONE_DEFAULT_API_URL = "https://api.exaone.ai/v1/chat/completions"
EXAONE_DEFAULT_MODEL = "k-exaone_v2.5"
DEFAULT_REQUEST_TIMEOUT = 600
DEFAULT_MAX_TOKENS = 8192

SYSTEM_PROMPT_KO = """당신은 AI 음악 생성 모델 'ACE-Step' 전용 전문 작사가이자 프롬프트 엔지니어입니다.
사용자가 제공하는 [곡 기획 정보]를 분석하여 최상의 가창력을 발휘할 수 있는 '영문 스타일 프롬프트'와 '한국어 노래 가사'를 작성하세요.

[핵심 작사 지침]:
1. **곡 구조 및 흐름**:
   - 2~3분 분량의 완성도 높은 대중가요 구조([Verse 1], [Chorus], [Verse 2], [Chorus], [Outro] 또는 [Bridge])로 작성하세요.
   - 가창 호흡에 알맞은 자연스럽고 감성적인 노랫말로 완성하세요.
   - `[Verse 1]`, `[Chorus]` 등의 곡 구조 태그는 단독 줄로 배치하세요.
2. **가사 표기**:
   - `displayLyrics`: 화면 표시 및 기본 등록을 위한 표준 한글 맞춤법(정음) 가사 (곡 구조 태그 포함)
   - `lyrics`: 보컬 엔진용 가사. 맨 첫 줄에 반드시 `[ko]` 태그를 넣고, 구조 태그와 함께 소리 나는 자연스러운 발음(연음 등)을 반영하여 작성하세요.
3. **영문 스타일 프롬프트(stylePrompt)**:
   - 곡의 장르, 메인 악기 구성, 분위기/감정, 보컬 음색/성별, 템포(BPM)를 쉼표로 구분된 영문 키워드 태그로 작성하세요.

반드시 다음 필드를 포함하는 순수한 단일 JSON 객체로만 응답하세요:
{
  "title": "어울리는 한국어 곡 제목",
  "stylePrompt": "ACE-Step용 영문 스타일 프롬프트",
  "displayLyrics": "표준 한글 맞춤법(정음) 가사",
  "lyrics": "[ko]\\n보컬 엔진용 발음(G2P) 가사",
  "summary": "곡 구성 및 작사 의도 한 줄 요약"
}"""

SYSTEM_PROMPT_EN = """You are a professional songwriter and prompt engineer specialized in the AI music generation model 'ACE-Step'.
Analyze the user's song planning request to write a creative English song title, natural singable English lyrics, and ACE-Step style tags.

[Key Lyric Writing Guidelines]:
1. **Song Structure & Flow**:
   - Write a complete 2~3 minute pop song structure: [Verse 1], [Chorus], [Verse 2], [Chorus], [Bridge], [Outro].
   - Place structure tags like `[Verse 1]`, `[Chorus]` on their own single line.
   - Write natural, singable, and poetic English lyrics with strong rhythm and rhyme (6~10 words/syllables per line).
2. **Lyrics Fields**:
   - `displayLyrics`: Standard English lyrics with structure tags for display.
   - `lyrics`: Vocal engine English lyrics starting with `[en]` on the very first line, followed by structure tags and singable lyrics.
3. **Style Prompt (stylePrompt)**:
   - English comma-separated tags specifying genre, main instrumentation, mood/emotion, vocal timbre/gender, and tempo (BPM).
4. **Summary**:
   - A short one-line summary of the song's concept and narrative in Korean (한국어로 작성).

Respond ONLY with a single valid JSON object with the following fields:
{
  "title": "Creative English Song Title",
  "stylePrompt": "ACE-Step English style prompt tags, e.g. pop, acoustic guitar, emotional female vocal, 105 BPM",
  "displayLyrics": "Standard English lyrics with structure tags",
  "lyrics": "[en]\\nVocal engine lyrics starting with [en] tag",
  "summary": "곡 구성 및 작사 의도 한 줄 요약 (한국어)"
}"""

SYSTEM_PROMPT = SYSTEM_PROMPT_KO


def get_system_prompt(language="ko"):
    return SYSTEM_PROMPT_EN if str(language).lower() == "en" else SYSTEM_PROMPT_KO


def get_api_endpoint():
    return os.environ.get("EXAONE_API_URL", EXAONE_DEFAULT_API_URL).strip()


def get_model_name():
    return os.environ.get("EXAONE_MODEL", EXAONE_DEFAULT_MODEL).strip()


def get_timeout_seconds(custom_timeout=None):
    """Return timeout in seconds, or None if timeout is disabled (unlimited / 0).

    Precedence: custom_timeout -> EXAONE_TIMEOUT env var -> DEFAULT_REQUEST_TIMEOUT (600s).
    """
    raw = custom_timeout
    if raw is None or raw == "":
        raw = os.environ.get("EXAONE_TIMEOUT")
    if raw is None or raw == "":
        return DEFAULT_REQUEST_TIMEOUT

    if isinstance(raw, str):
        raw_clean = raw.strip().lower()
        if raw_clean in ("0", "none", "unlimited", "infinite", "off", "false", "no-limit"):
            return None
        try:
            val = int(raw_clean)
        except (ValueError, TypeError):
            return DEFAULT_REQUEST_TIMEOUT
    elif isinstance(raw, (int, float)):
        val = int(raw)
    else:
        return DEFAULT_REQUEST_TIMEOUT

    if val <= 0:
        return None
    return max(10, val)


def clean_think_tags(text):
    """Remove reasoning process tags like <think>...</think> if present."""
    if not text:
        return ""
    return re.sub(r"<think>[\s\S]*?</think>", "", text).strip()


REASONING_LEAK_PATTERNS_KO = [
    r"\b(?:maybe|displaylyrics|structure tags|conversions|avoid tricky|need g2p|let's design|let's draft|too long|shorten|syllables|in json|valid json)\b",
    r"(?:count\s*[:：]|\bwe need\b|\bcan output\b|\bmultiline strings\b)",
]

REASONING_LEAK_PATTERNS_EN = [
    r"\b(?:displaylyrics|structure tags|conversions|avoid tricky|need g2p|let's design|let's draft|syllables|in json|valid json)\b",
    r"(?:count\s*[:：]|\bwe need to\b|\bcan output\b|\bmultiline strings\b)",
]

REASONING_LEAK_PATTERNS = REASONING_LEAK_PATTERNS_KO


def _is_reasoning_line(line, language="ko"):
    """Check if a line is internal model reasoning or thought leak rather than song lyrics."""
    if not line:
        return False
    # Syllable counter patterns: e.g. "Count: ..." or "word(1) word(2)..."
    if re.search(r"\bcount\s*[:：]", line, re.IGNORECASE) or re.search(r"[\uac00-\ud7a3a-zA-Z]\s*\(\d+\)", line):
        return True
    # Meta reasoning headers
    if re.match(r"^\s*(?:Theme|Title|DisplayLyrics|Need|We need|Let's draft|Let's design|Notes?|Plan)\s*[:：]", line, re.IGNORECASE):
        return True
    if str(language).lower() == "en":
        patterns = REASONING_LEAK_PATTERNS_EN
    else:
        # If the line contains 5+ Korean characters, it's a song line!
        korean_chars = len(re.findall(r"[\uac00-\ud7a3]", line))
        if korean_chars >= 5:
            return False
        patterns = REASONING_LEAK_PATTERNS_KO
    t_lower = line.lower()
    return any(re.search(pat, t_lower) for pat in patterns)


def _contains_reasoning_leak(text, language="ko"):
    if not text:
        return False
    t_lower = text.lower()
    patterns = REASONING_LEAK_PATTERNS_EN if str(language).lower() == "en" else REASONING_LEAK_PATTERNS_KO
    for pat in patterns:
        if re.search(pat, t_lower):
            return True
    return False


def sanitize_title(title, default_topic="", language="ko"):
    """Clean and validate song title to prevent prompt/reasoning leakage."""
    is_en = str(language).lower() == "en"
    default_name = "New Song" if is_en else "새로운 노래"
    if not title or not isinstance(title, str):
        return default_topic or default_name
    t = clean_think_tags(title).strip().strip('"').strip("'")
    t = t.split("\n")[0].strip()

    # Match quoted title at beginning: e.g. "가을의 온기" or "Autumn Breeze" maybe...
    q_match = re.match(r'^["\']?([^"\'\n\r]{2,50})["\']?\s*(?:maybe|DisplayLyrics|\.|$)', t, re.IGNORECASE)
    if q_match:
        cand = q_match.group(1).strip().strip('"\'.,')
        if cand and len(re.findall(r"[\uac00-\ud7a3a-zA-Z0-9]", cand)) >= 2:
            if not _contains_reasoning_leak(cand, language=language):
                return cand

    if _contains_reasoning_leak(t, language=language):
        pattern = r"^([a-zA-Z0-9\s',\-!]{2,40})" if is_en else r"^([\uac00-\ud7a3\s0-9]{2,30})"
        match = re.match(pattern, t)
        if match:
            cand = match.group(1).strip().strip('"\'.,')
            if cand:
                return cand
        return default_topic or default_name

    cand = t.strip('"\'.,')
    if len(cand) > 50:
        cand = cand[:50].strip()
    return cand or (default_topic or default_name)


def sanitize_lyrics(lyrics, fallback_display="", language="ko"):
    """Clean and validate vocal engine lyrics, ensuring [ko] or [en] tag and stripping reasoning leakage."""
    is_en = str(language).lower() == "en"
    target_tag = "[en]" if is_en else "[ko]"
    min_chars = 15 if is_en else 5
    char_pattern = r"[a-zA-Z]" if is_en else r"[\uac00-\ud7a3]"

    if not lyrics or not isinstance(lyrics, str):
        lyrics = fallback_display or ""
    text = clean_think_tags(lyrics).strip()

    # Match target tag as standalone tag or line start
    m_tag = re.search(r"(?m)^\s*\[" + ("en" if is_en else "ko") + r"\]", text, re.IGNORECASE)
    if m_tag:
        text = text[m_tag.start():].strip()
    else:
        # Check if there is an [Intro] or [Verse] or [Chorus] after English reasoning
        for marker in (r"(?m)^\s*\[Intro", r"(?m)^\s*\[Verse", r"(?m)^\s*\[Chorus"):
            m = re.search(marker, text, re.IGNORECASE)
            if m:
                before = text[:m.start()].strip()
                if before and len(re.findall(char_pattern, before)) < 3:
                    text = text[m.start():].strip()
                break

    # Clean and normalize language tag (strip any leading [ko] or [en])
    text = re.sub(r"^(?:\[(?:ko|en)\]\s*)+", "", text, flags=re.IGNORECASE).strip()
    text = target_tag + "\n" + text
    text = re.sub(r"^\[(?:ko|en)\]\s*\[", target_tag + "\n[", text, flags=re.IGNORECASE)

    # Filter out pure reasoning / syllable-counter lines
    lines = text.split("\n")
    cleaned_lines = []
    for line in lines:
        if not _is_reasoning_line(line, language=language):
            cleaned_lines.append(line)
    text = "\n".join(cleaned_lines).strip()
    if not text.lower().startswith(target_tag.lower()):
        text = target_tag + "\n" + text

    # Validate that lyrics actually contain sufficient language content
    content_chars = len(re.findall(char_pattern, text))
    if content_chars < min_chars:
        if fallback_display:
            fb_text = clean_think_tags(fallback_display).strip()
            fb_lines = [l for l in fb_text.split("\n") if not _is_reasoning_line(l, language=language)]
            fb_text = "\n".join(fb_lines).strip()
            fb_text = re.sub(r"^(?:\[(?:ko|en)\]\s*)+", "", fb_text, flags=re.IGNORECASE).strip()
            if len(re.findall(char_pattern, fb_text)) >= min_chars:
                return target_tag + "\n" + fb_text

        err_msg = "생성된 가사에 영문 내용이 부족합니다. 다시 시도해 주세요." if is_en else "생성된 가사에 한국어 내용이 부족합니다. 다시 시도해 주세요."
        raise ValueError(err_msg)

    return text


def sanitize_display_lyrics(display_lyrics, fallback_lyrics="", language="ko"):
    """Clean display/standard lyrics, stripping [ko]/[en] tags and internal thoughts."""
    is_en = str(language).lower() == "en"
    min_chars = 15 if is_en else 5
    char_pattern = r"[a-zA-Z]" if is_en else r"[\uac00-\ud7a3]"

    if not display_lyrics or not isinstance(display_lyrics, str):
        display_lyrics = fallback_lyrics or ""
    text = clean_think_tags(display_lyrics).strip()

    # Strip [ko] or [en] if present in standard display lyrics
    text = re.sub(r"^(?:\[(?:ko|en)\]\s*)+", "", text, flags=re.IGNORECASE).strip()

    # Strip English thought preamble if present before song structure markers
    for marker in (r"(?m)^\s*\[Intro", r"(?m)^\s*\[Verse", r"(?m)^\s*\[Chorus"):
        m = re.search(marker, text, re.IGNORECASE)
        if m and m.start() > 0:
            before = text[:m.start()].strip()
            if before and len(re.findall(char_pattern, before)) < 3:
                text = text[m.start():].strip()
            break

    lines = text.split("\n")
    cleaned_lines = [line for line in lines if not _is_reasoning_line(line, language=language)]
    text = "\n".join(cleaned_lines).strip()

    content_chars = len(re.findall(char_pattern, text))
    if content_chars < min_chars:
        if fallback_lyrics:
            fb_text = clean_think_tags(fallback_lyrics).strip()
            fb_text = re.sub(r"^(?:\[(?:ko|en)\]\s*)+", "", fb_text, flags=re.IGNORECASE).strip()
            fb_lines = [l for l in fb_text.split("\n") if not _is_reasoning_line(l, language=language)]
            fb_text = "\n".join(fb_lines).strip()
            if len(re.findall(char_pattern, fb_text)) >= min_chars:
                return fb_text
        err_msg = "생성된 영문 가사에 내용이 부족합니다. 다시 시도해 주세요." if is_en else "생성된 정음 가사에 한국어 내용이 부족합니다. 다시 시도해 주세요."
        raise ValueError(err_msg)

    return text


def _get_field(data, *keys):
    """Safely extract the first non-empty string value matching any candidate key."""
    if not isinstance(data, dict):
        return ""
    # Check if there is a nested wrapper like data["song"] or data["result"]
    for wrapper in ("song", "result", "response", "data"):
        sub = data.get(wrapper)
        if isinstance(sub, dict):
            val = _get_field(sub, *keys)
            if val:
                return val

    for k in keys:
        val = data.get(k)
        if val is not None and str(val).strip():
            return str(val).strip()
    return ""


def extract_json_fields_regex(text):
    """Extract individual JSON fields using regex when strict parsing fails."""
    fields = {}

    for key in ("title", "곡제목", "제목", "songTitle"):
        m = re.search(r'"' + key + r'"\s*:\s*"((?:\\.|[^"\\])*)"', text)
        if m:
            fields["title"] = m.group(1).replace('\\"', '"').replace("\\n", " ").strip()
            break

    for key in ("stylePrompt", "style_prompt", "style", "스타일프롬프트", "스타일"):
        m = re.search(r'"' + key + r'"\s*:\s*"((?:\\.|[^"\\])*)"', text)
        if m:
            fields["stylePrompt"] = m.group(1).replace('\\"', '"').replace("\\n", " ").strip()
            break

    for key in ("summary", "요약", "description"):
        m = re.search(r'"' + key + r'"\s*:\s*"((?:\\.|[^"\\])*)"', text)
        if m:
            fields["summary"] = m.group(1).replace('\\"', '"').replace("\\n", " ").strip()
            break

    for key in (
        "displayLyrics",
        "display_lyrics",
        "standardLyrics",
        "standard_lyrics",
        "정음가사",
        "정음 가사",
        "koreanLyrics",
        "korean_lyrics",
        "englishLyrics",
        "english_lyrics",
        "영어가사",
        "영어 가사",
    ):
        m = re.search(
            r'"' + key + r'"\s*:\s*"([\s\S]*?)(?="\s*,\s*"(?:lyrics|phoneticLyrics|g2pLyrics|g2p_lyrics|summary|stylePrompt|title)"|\s*"\s*\}|\s*\Z)',
            text,
        )
        if m:
            val = m.group(1).replace('\\"', '"').replace("\\n", "\n").replace("\\t", "\t")
            fields["displayLyrics"] = val.rstrip('"').strip()
            break

    for key in (
        "lyrics",
        "phoneticLyrics",
        "phonetic_lyrics",
        "g2pLyrics",
        "g2p_lyrics",
        "발음가사",
        "발음 가사",
        "가사",
        "vocalLyrics",
        "vocal_lyrics",
        "보컬가사",
        "보컬 가사",
    ):
        m = re.search(
            r'"' + key + r'"\s*:\s*"([\s\S]*?)(?="\s*,\s*"(?:displayLyrics|standardLyrics|summary|stylePrompt|title)"|\s*"\s*\}|\s*\Z)',
            text,
        )
        if m:
            val = m.group(1).replace('\\"', '"').replace("\\n", "\n").replace("\\t", "\t")
            fields["lyrics"] = val.rstrip('"').strip()
            break

    return fields


def fallback_parse_text(raw_text, language="ko"):
    """Extract lyrics, title, and prompt from markdown or unformatted text."""
    is_en = str(language).lower() == "en"
    text = clean_think_tags(raw_text)
    title = ""
    style = ""
    summary = ""
    g2p_lyrics = ""
    standard_lyrics = ""

    # Check title
    m = re.search(
        r"(?:\[|\*\*|\#)*\s*(?:곡\s*제목|제목|Title|Song\s*Title)\s*(?:\]|\*\*)*\s*[:：]\s*(.+)",
        text,
        re.IGNORECASE,
    )
    if m:
        raw_title_line = m.group(1).strip()
        # If quoted, extract quoted title
        q_m = re.search(r'["\']([^"\'\n\r]{2,50})["\']', raw_title_line)
        if q_m:
            title = sanitize_title(q_m.group(1), language=language)
        else:
            title = sanitize_title(raw_title_line, language=language)
    else:
        q_m = re.search(r'\b(?:title|제목)\s*(?:is|:|=|maybe)?\s*["\']([^"\'\n\r]{2,50})["\']', text, re.IGNORECASE)
        if q_m:
            title = sanitize_title(q_m.group(1), language=language)

    # Check style
    m = re.search(
        r"(?:\[|\*\*|\#)*\s*(?:영문\s*스타일\s*프롬프트|스타일\s*프롬프트|스타일|Style\s*Prompt|Style)\s*(?:\]|\*\*)*\s*[:：]\s*(.+)",
        text,
        re.IGNORECASE,
    )
    if m:
        style = m.group(1).strip().strip('"').strip("'").strip("*").strip()

    # Check summary
    m = re.search(
        r"(?:\[|\*\*|\#)*\s*(?:곡\s*구성\s*요약|작사\s*의도|요약|Summary)\s*(?:\]|\*\*)*\s*[:：]\s*(.+)",
        text,
        re.IGNORECASE,
    )
    if m:
        summary = m.group(1).strip().strip('"').strip("'").strip("*").strip()

    # Check lyrics sections
    g2p_match = re.search(
        r"(?:G2P|발음\s*표기|ACE-Step|Vocal\s*Engine|Vocal\s*Lyrics|Vocal)[^\n]*\n([\s\S]+?)(?=(?:###|\n\s*\[(?:곡\s*구성|정음|표준|Standard)|$))",
        text,
        re.IGNORECASE,
    )
    std_match = re.search(
        r"(?:정음|표준\s*맞춤법|화면\s*표시|Standard\s*Lyrics|Display\s*Lyrics)[^\n]*\n([\s\S]+?)(?=(?:###|\n\s*\[(?:곡\s*구성|G2P|발음|Vocal)|$))",
        text,
        re.IGNORECASE,
    )

    if g2p_match:
        g2p_lyrics = g2p_match.group(1).strip()
    if std_match:
        standard_lyrics = std_match.group(1).strip()

    tag_marker = r"\[en\]" if is_en else r"\[ko\]"
    if not g2p_lyrics:
        m_tag = re.search(r"(?m)^\s*" + tag_marker, text, re.IGNORECASE)
        if m_tag:
            g2p_lyrics = text[m_tag.start():].strip()
        else:
            m_struct = re.search(r"(?m)^\s*\[(?:Intro|Verse|Chorus)", text, re.IGNORECASE)
            if m_struct:
                g2p_lyrics = text[m_struct.start():].strip()

    # Check generic markdown headings like ### [가사] or ### 가사 or ### Lyrics
    if not g2p_lyrics and not standard_lyrics:
        m_lyrics_hd = re.search(
            r"(?:###|\*\*|\[)\s*(?:가사|Lyrics)\s*(?:###|\*\*|\])?\s*[:：]?\s*\n([\s\S]+?)(?=(?:###|\n\s*\[(?:곡\s*구성|요약|Summary)|$))",
            text,
            re.IGNORECASE,
        )
        if m_lyrics_hd:
            g2p_lyrics = m_lyrics_hd.group(1).strip()

    if not g2p_lyrics and not standard_lyrics:
        g2p_lyrics = text.strip()

    if not standard_lyrics:
        standard_lyrics = g2p_lyrics

    default_title = "New Song" if is_en else "곡 제목"
    default_style = "pop, acoustic guitar, emotional vocal, 100 BPM" if is_en else "ballad, emotional piano, heartfelt vocal"
    default_summary = "ACE-Step 맞춤 영문 가사 완성" if is_en else "가사 생성 완료"

    return {
        "title": title or default_title,
        "stylePrompt": style or default_style,
        "displayLyrics": standard_lyrics,
        "standardLyrics": standard_lyrics,
        "lyrics": g2p_lyrics,
        "summary": summary or default_summary,
    }


def extract_strict_json(raw_text):
    """Safely extract and parse JSON object strictly without heuristic fallbacks."""
    if not raw_text:
        return None
    cleaned = clean_think_tags(raw_text).strip()

    # Tier 1: Direct JSON parsing
    try:
        data = json.loads(cleaned, strict=False)
        if isinstance(data, dict):
            return data
    except (json.JSONDecodeError, ValueError):
        pass

    # Tier 2: Extract markdown code fence
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned)
    if match:
        fence_content = match.group(1).strip()
        try:
            data = json.loads(fence_content, strict=False)
            if isinstance(data, dict):
                return data
        except (json.JSONDecodeError, ValueError):
            pass
        first_b = fence_content.find("{")
        last_b = fence_content.rfind("}")
        if first_b != -1 and last_b != -1 and last_b > first_b:
            try:
                data = json.loads(fence_content[first_b : last_b + 1], strict=False)
                if isinstance(data, dict):
                    return data
            except (json.JSONDecodeError, ValueError):
                pass

    # Tier 3: Find outermost { and }
    first_brace = cleaned.find("{")
    last_brace = cleaned.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        snippet = cleaned[first_brace : last_brace + 1]
        try:
            data = json.loads(snippet, strict=False)
            if isinstance(data, dict):
                return data
        except (json.JSONDecodeError, ValueError):
            pass

    return None


def parse_json_response(raw_text, language="ko"):
    """Safely extract and parse JSON object from model output with multi-tier recovery."""
    strict = extract_strict_json(raw_text)
    if strict:
        return strict

    cleaned = clean_think_tags(raw_text).strip()

    # Tier 4: Regex-based field extraction for broken JSON (unescaped quotes, trailing commas)
    regex_fields = extract_json_fields_regex(cleaned)
    if regex_fields.get("lyrics") or regex_fields.get("displayLyrics"):
        return regex_fields

    # Tier 5: Fallback to heuristic text parsing (markdown headings, tags, plain lyrics)
    return fallback_parse_text(cleaned, language=language)


def test_api_key(api_key):
    """Verify that the provided EXAONE API key is valid."""
    if not api_key or not isinstance(api_key, str) or not api_key.strip():
        raise ValueError("EXAONE API 키를 입력해 주세요.")

    api_key = api_key.strip()
    url = get_api_endpoint()
    model = get_model_name()

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "ping"}],
        "max_tokens": 5,
        "temperature": 0.1,
    }

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "Authorization": f"Bearer {api_key}",
            "User-Agent": "SoriSoop/1.2",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if "choices" in data or "id" in data:
                return True
            return True
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            raise ValueError("API 키가 올바르지 않거나 인증에 실패했습니다 (HTTP 401/403).")
        if e.code == 404:
            raise ValueError(f"EXAONE 모델({model}) 또는 API 경로를 찾을 수 없습니다 (HTTP 404).")
        if e.code == 429:
            raise ValueError("API 요청 한도를 초과했습니다 (HTTP 429). 잠시 후 다시 시도해 주세요.")
        raise ValueError(f"EXAONE API 서버 오류가 발생했습니다 (HTTP {e.code}).")
    except urllib.error.URLError:
        raise ValueError("EXAONE API 서버에 연결할 수 없습니다. 인터넷 연결을 확인해 주세요.")
    except Exception as e:
        raise ValueError(f"API 키 확인 중 오류가 발생했습니다: {e}")


def _execute_chat_completion(url, payload, api_key, timeout_sec=None):
    """Execute the HTTP POST request to the EXAONE chat completions endpoint."""
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "Authorization": f"Bearer {api_key}",
            "User-Agent": "SoriSoop/1.2",
        },
        method="POST",
    )

    actual_timeout = timeout_sec if (timeout_sec is not None and timeout_sec > 0) else None

    try:
        with urllib.request.urlopen(req, timeout=actual_timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err_body = ""
        try:
            err_body = e.read().decode("utf-8")
        except Exception:
            pass

        # If response_format caused HTTP 400, retry once without response_format
        if e.code == 400 and "response_format" in payload and "response_format" in err_body.lower():
            retry_payload = dict(payload)
            del retry_payload["response_format"]
            return _execute_chat_completion(url, retry_payload, api_key, timeout_sec)

        if e.code in (401, 403):
            raise ValueError("EXAONE API 키가 올바르지 않거나 권한이 없습니다 (HTTP 401/403).")
        if e.code == 429:
            raise ValueError("EXAONE API 요청 한도를 초과했습니다 (HTTP 429). 잠시 후 다시 시도해 주세요.")
        if e.code >= 500:
            raise ValueError(f"EXAONE 서버 일시 장애가 발생했습니다 (HTTP {e.code}). 잠시 후 다시 시도해 주세요.")
        raise ValueError(f"EXAONE API 호출 실패 (HTTP {e.code})")
    except (TimeoutError, socket.timeout):
        sec_str = f" ({timeout_sec}초)" if timeout_sec else ""
        raise ValueError(
            f"EXAONE 서버 응답 시간이 초과되었습니다{sec_str}. 저사양 환경이거나 API 대기열이 길 경우 대기 시간을 '제한 없음' 또는 더 길게 설정한 뒤 다시 시도해 주세요."
        )
    except urllib.error.URLError as e:
        if isinstance(getattr(e, "reason", None), (socket.timeout, TimeoutError)) or "timed out" in str(e).lower():
            sec_str = f" ({timeout_sec}초)" if timeout_sec else ""
            raise ValueError(
                f"EXAONE 서버 응답 시간이 초과되었습니다{sec_str}. 저사양 환경이거나 API 대기열이 길 경우 대기 시간을 '제한 없음' 또는 더 길게 설정한 뒤 다시 시도해 주세요."
            )
        raise ValueError("EXAONE 서버에 연결할 수 없습니다. 인터넷 연결 상태를 확인해 주세요.")


def generate_lyrics(api_key, prompt, *, genre="", mood="", voice="", tempo="", timeout=None, language="ko"):
    """Request ACE-Step song lyrics generation from LG K-EXAONE 2.5 API."""
    if not api_key or not isinstance(api_key, str) or not api_key.strip():
        raise ValueError("EXAONE API 키가 설정되지 않았습니다. [설정]에서 API 키를 먼저 입력해 주세요.")
    if not prompt or not isinstance(prompt, str) or not prompt.strip():
        raise ValueError("곡의 주제나 이야기를 입력해 주세요.")

    api_key = api_key.strip()
    prompt = prompt.strip()
    url = get_api_endpoint()
    model = get_model_name()
    language = "en" if str(language).lower() == "en" else "ko"
    is_en = (language == "en")
    lang_name = "영문(English)" if is_en else "한국어"

    user_info_lines = [
        f"- 작사 언어: {lang_name} 곡 제목 및 노래 가사",
        f"- 주제 및 이야기: {prompt}",
    ]
    if genre:
        user_info_lines.append(f"- 장르 및 스타일: {genre.strip()}")
    if mood:
        user_info_lines.append(f"- 감정선 및 분위기: {mood.strip()}")
    if voice:
        user_info_lines.append(f"- 희망 보컬 음색: {voice.strip()}")
    if tempo:
        user_info_lines.append(f"- 템포: {tempo.strip()}")

    user_message = (
        f"다음 곡 기획 정보를 바탕으로 ACE-Step 전용 {lang_name} 노래 가사와 영문 스타일 프롬프트를 작성해 주세요.\n\n"
        "### [곡 기획 정보]\n" + "\n".join(user_info_lines)
    )

    timeout_sec = get_timeout_seconds(timeout)
    max_tokens = int(os.environ.get("EXAONE_MAX_TOKENS", str(DEFAULT_MAX_TOKENS)))
    reasoning_effort = os.environ.get("EXAONE_REASONING_EFFORT", "low").strip()
    system_prompt = get_system_prompt(language)

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        "temperature": 0.7,
        "max_tokens": max_tokens,
        "reasoning_effort": reasoning_effort,
        "response_format": {"type": "json_object"},
    }

    data = _execute_chat_completion(url, payload, api_key, timeout_sec)

    try:
        choice = data["choices"][0]
        msg = choice.get("message") or {}
        content = str(msg.get("content") or "").strip()
        reasoning = str(msg.get("reasoning_content") or "").strip()
        finish_reason = choice.get("finish_reason")
    except (KeyError, IndexError, TypeError):
        raise ValueError("EXAONE API 응답 형식이 올바르지 않습니다.")

    # Parse primary model content
    parsed = {}
    if content and content != "{}":
        try:
            parsed = parse_json_response(content, language=language)
        except Exception as e:
            print(f"[EXAONE Parser Warning] {e}\n[Raw Content]:\n{content}", flush=True)
            parsed = fallback_parse_text(content, language=language)

    raw_lyrics = _get_field(
        parsed,
        "lyrics",
        "phoneticLyrics",
        "phonetic_lyrics",
        "g2pLyrics",
        "g2p_lyrics",
        "발음가사",
        "발음 가사",
        "vocalLyrics",
        "vocal_lyrics",
    )
    raw_display = _get_field(
        parsed,
        "displayLyrics",
        "standardLyrics",
        "standard_lyrics",
        "display_lyrics",
        "정음가사",
        "정음 가사",
        "koreanLyrics",
        "korean_lyrics",
        "englishLyrics",
        "english_lyrics",
    )

    if not raw_lyrics and not raw_display:
        raw_lyrics = _get_field(parsed, "가사", "text", "content", "song")
        raw_display = raw_lyrics

    # Multi-tier recovery: If content lacked song content, inspect reasoning_content
    min_chars = 15 if is_en else 5
    char_pattern = r"[a-zA-Z]" if is_en else r"[\uac00-\ud7a3]"
    content_chars = len(re.findall(char_pattern, (raw_lyrics or "") + (raw_display or "")))

    if content_chars < min_chars and reasoning:
        has_song_markers = bool(
            re.search(
                r"(?:\[(?:Intro|Verse|Chorus|Bridge|Outro|ko|en)\]|###\s*\[?(?:정음|G2P|가사|발음|Lyrics|Standard|Vocal))",
                reasoning,
                re.IGNORECASE,
            )
        )
        strict_in_reasoning = extract_strict_json(reasoning)
        if has_song_markers or (
            isinstance(strict_in_reasoning, dict)
            and (strict_in_reasoning.get("lyrics") or strict_in_reasoning.get("displayLyrics"))
        ):
            try:
                reasoning_parsed = strict_in_reasoning if strict_in_reasoning else fallback_parse_text(reasoning, language=language)
            except Exception:
                reasoning_parsed = fallback_parse_text(reasoning, language=language)

            r_lyrics = _get_field(
                reasoning_parsed,
                "lyrics",
                "phoneticLyrics",
                "phonetic_lyrics",
                "g2pLyrics",
                "g2p_lyrics",
                "발음가사",
                "발음 가사",
                "vocalLyrics",
                "vocal_lyrics",
            )
            r_display = _get_field(
                reasoning_parsed,
                "displayLyrics",
                "standardLyrics",
                "standard_lyrics",
                "display_lyrics",
                "정음가사",
                "정음 가사",
                "koreanLyrics",
                "korean_lyrics",
                "englishLyrics",
                "english_lyrics",
            )
            if not r_lyrics and not r_display:
                r_lyrics = _get_field(reasoning_parsed, "가사", "text", "content", "song")
                r_display = r_lyrics

            if len(re.findall(char_pattern, (r_lyrics or "") + (r_display or ""))) >= min_chars:
                parsed = reasoning_parsed
                raw_lyrics = r_lyrics
                raw_display = r_display

    if not raw_lyrics and not raw_display:
        if finish_reason == "length":
            raise ValueError(
                "EXAONE 모델이 토큰 한도에 도달하여 가사 생성을 완료하지 못했습니다. 다시 시도해 주세요."
            )
        if not content:
            raise ValueError("EXAONE 모델이 유효한 가사 결과를 반환하지 않았습니다. 다시 시도해 주세요.")
        raise ValueError("생성된 가사를 찾을 수 없습니다. 다시 시도해 주세요.")

    lyrics = sanitize_lyrics(raw_lyrics, fallback_display=raw_display, language=language)
    display_lyrics = sanitize_display_lyrics(raw_display, fallback_lyrics=raw_lyrics, language=language)

    raw_title = _get_field(parsed, "title", "곡제목", "제목", "songTitle")
    title = sanitize_title(raw_title, default_topic=prompt, language=language)
    default_style = (
        "pop, acoustic guitar, emotional vocal, 100 BPM"
        if is_en
        else "ballad, acoustic piano, emotional vocal, 72 BPM"
    )
    style_prompt = (
        _get_field(parsed, "stylePrompt", "style_prompt", "style", "스타일프롬프트", "스타일")
        or default_style
    )
    default_summary = "ACE-Step 맞춤 영문 가사 완성" if is_en else "가사 생성 완료"
    summary = _get_field(parsed, "summary", "요약", "description") or default_summary

    return {
        "title": title,
        "stylePrompt": style_prompt,
        "displayLyrics": display_lyrics,
        "standardLyrics": display_lyrics,
        "lyrics": lyrics,
        "summary": summary,
        "language": language,
    }
