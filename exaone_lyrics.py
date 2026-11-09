"""LG K-EXAONE 2.5 API client for generating ACE-Step compatible song lyrics."""
import json
import os
import re
import socket
import urllib.error
import urllib.request

EXAONE_DEFAULT_API_URL = "https://api.exaone.ai/v1/chat/completions"
EXAONE_DEFAULT_MODEL = "k-exaone_v2.5"
DEFAULT_REQUEST_TIMEOUT = 120
DEFAULT_MAX_TOKENS = 8192

SYSTEM_PROMPT = """당신은 AI 음악 생성 모델 'ACE-Step' 전용 전문 작사가이자 프롬프트 엔지니어입니다.
사용자가 제공하는 [곡 기획 정보]를 분석하여 최상의 가창력을 발휘할 수 있는 '영문 스타일 프롬프트'와 '노래 가사'를 작성하세요.

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


def get_api_endpoint():
    return os.environ.get("EXAONE_API_URL", EXAONE_DEFAULT_API_URL).strip()


def get_model_name():
    return os.environ.get("EXAONE_MODEL", EXAONE_DEFAULT_MODEL).strip()


def get_timeout_seconds():
    try:
        return max(30, int(os.environ.get("EXAONE_TIMEOUT", str(DEFAULT_REQUEST_TIMEOUT))))
    except (ValueError, TypeError):
        return DEFAULT_REQUEST_TIMEOUT


def clean_think_tags(text):
    """Remove reasoning process tags like <think>...</think> if present."""
    if not text:
        return ""
    return re.sub(r"<think>[\s\S]*?</think>", "", text).strip()


REASONING_LEAK_PATTERNS = [
    r"\b(?:maybe|displaylyrics|structure tags|conversions|avoid tricky|need g2p|let's design|let's draft|too long|shorten|syllables|in json|valid json)\b",
    r"(?:count\s*[:：]|\bwe need\b|\bcan output\b|\bmultiline strings\b)",
]


def _is_reasoning_line(line):
    """Check if a line is internal model reasoning or thought leak rather than song lyrics."""
    if not line:
        return False
    # Syllable counter patterns: e.g. "Count: ..." or "가(1) 을(2) 바(3)..."
    if re.search(r"\bcount\s*[:：]", line, re.IGNORECASE) or re.search(r"[\uac00-\ud7a3]\s*\(\d+\)", line):
        return True
    # Meta reasoning headers
    if re.match(r"^\s*(?:Theme|Title|DisplayLyrics|Need|We need|Let's draft|Let's design)\s*[:：]", line, re.IGNORECASE):
        return True
    # If the line contains 5+ Korean characters, it's a song line!
    korean_chars = len(re.findall(r"[\uac00-\ud7a3]", line))
    if korean_chars >= 5:
        return False
    t_lower = line.lower()
    return any(re.search(pat, t_lower) for pat in REASONING_LEAK_PATTERNS)


def _contains_reasoning_leak(text):
    if not text:
        return False
    t_lower = text.lower()
    for pat in REASONING_LEAK_PATTERNS:
        if re.search(pat, t_lower):
            return True
    return False


def sanitize_title(title, default_topic=""):
    """Clean and validate song title to prevent prompt/reasoning leakage."""
    if not title or not isinstance(title, str):
        return default_topic or "새로운 노래"
    t = clean_think_tags(title).strip().strip('"').strip("'")
    t = t.split("\n")[0].strip()

    # Match quoted title at beginning: e.g. "가을의 온기" or '가을의 온기' maybe...
    q_match = re.match(r'^["\']?([^"\'\n\r]{2,40})["\']?\s*(?:maybe|DisplayLyrics|\.|$)', t, re.IGNORECASE)
    if q_match:
        cand = q_match.group(1).strip().strip('"\'.,')
        if cand and len(re.findall(r"[\uac00-\ud7a3a-zA-Z0-9]", cand)) >= 2:
            if not _contains_reasoning_leak(cand):
                return cand

    if _contains_reasoning_leak(t):
        ko_match = re.match(r"^([\uac00-\ud7a3\s0-9]{2,30})", t)
        if ko_match:
            cand = ko_match.group(1).strip().strip('"\'.,')
            if cand:
                return cand
        return default_topic or "새로운 노래"

    cand = t.strip('"\'.,')
    if len(cand) > 50:
        cand = cand[:50].strip()
    return cand or (default_topic or "새로운 노래")


def sanitize_lyrics(lyrics, fallback_display=""):
    """Clean and validate G2P lyrics, ensuring [ko] tag and stripping English reasoning leakage."""
    if not lyrics or not isinstance(lyrics, str):
        lyrics = fallback_display or ""
    text = clean_think_tags(lyrics).strip()

    # Match [ko] as standalone tag or line start
    m_ko = re.search(r"(?m)^\s*\[ko\]", text)
    if m_ko:
        text = text[m_ko.start():].strip()
    else:
        # Check if there is an [Intro] or [Verse] or [Chorus] after English reasoning
        for marker in (r"(?m)^\s*\[Intro", r"(?m)^\s*\[Verse", r"(?m)^\s*\[Chorus"):
            m = re.search(marker, text)
            if m:
                before = text[:m.start()].strip()
                if before and len(re.findall(r"[\uac00-\ud7a3]", before)) < 3:
                    text = text[m.start():].strip()
                break

    # Clean and normalize [ko] tag
    text = re.sub(r"^(?:\[ko\]\s*)+", "", text).strip()
    # Format [ko] followed by structure tags
    text = "[ko]\n" + text
    text = re.sub(r"^\[ko\]\s*\[", "[ko]\n[", text)

    # Filter out pure reasoning / syllable-counter lines
    lines = text.split("\n")
    cleaned_lines = []
    for line in lines:
        if not _is_reasoning_line(line):
            cleaned_lines.append(line)
    text = "\n".join(cleaned_lines).strip()
    if not text.startswith("[ko]"):
        text = "[ko]\n" + text

    # Validate that lyrics actually contain Korean song content
    korean_chars = len(re.findall(r"[\uac00-\ud7a3]", text))
    if korean_chars < 5:
        if fallback_display:
            fb_text = clean_think_tags(fallback_display).strip()
            fb_lines = [l for l in fb_text.split("\n") if not _is_reasoning_line(l)]
            fb_text = "\n".join(fb_lines).strip()
            fb_text = re.sub(r"^(?:\[ko\]\s*)+", "", fb_text).strip()
            if len(re.findall(r"[\uac00-\ud7a3]", fb_text)) >= 5:
                return "[ko]\n" + fb_text

        raise ValueError("생성된 가사에 한국어 내용이 부족합니다. 다시 시도해 주세요.")

    return text


def sanitize_display_lyrics(display_lyrics, fallback_lyrics=""):
    """Clean display/standard lyrics, stripping [ko] tag and internal thoughts."""
    if not display_lyrics or not isinstance(display_lyrics, str):
        display_lyrics = fallback_lyrics or ""
    text = clean_think_tags(display_lyrics).strip()

    # Strip [ko] if present in standard display lyrics
    if text.startswith("[ko]"):
        text = text[4:].strip()

    # Strip English thought preamble if present before song structure markers
    for marker in (r"(?m)^\s*\[Intro", r"(?m)^\s*\[Verse", r"(?m)^\s*\[Chorus"):
        m = re.search(marker, text)
        if m and m.start() > 0:
            before = text[:m.start()].strip()
            if before and len(re.findall(r"[\uac00-\ud7a3]", before)) < 3:
                text = text[m.start():].strip()
            break

    lines = text.split("\n")
    cleaned_lines = [line for line in lines if not _is_reasoning_line(line)]
    text = "\n".join(cleaned_lines).strip()

    korean_chars = len(re.findall(r"[\uac00-\ud7a3]", text))
    if korean_chars < 5:
        if fallback_lyrics:
            fb_text = clean_think_tags(fallback_lyrics).strip()
            if fb_text.startswith("[ko]"):
                fb_text = fb_text[4:].strip()
            fb_lines = [l for l in fb_text.split("\n") if not _is_reasoning_line(l)]
            fb_text = "\n".join(fb_lines).strip()
            if len(re.findall(r"[\uac00-\ud7a3]", fb_text)) >= 5:
                return fb_text
        raise ValueError("생성된 정음 가사에 한국어 내용이 부족합니다. 다시 시도해 주세요.")

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


def fallback_parse_text(raw_text):
    """Extract lyrics, title, and prompt from markdown or unformatted text."""
    text = clean_think_tags(raw_text)
    title = ""
    style = ""
    summary = ""
    g2p_lyrics = ""
    standard_lyrics = ""

    # Check title
    m = re.search(
        r"(?:\[|\*\*|\#)*\s*(?:곡\s*제목|제목|Title)\s*(?:\]|\*\*)*\s*[:：]\s*(.+)",
        text,
        re.IGNORECASE,
    )
    if m:
        raw_title_line = m.group(1).strip()
        # If quoted, extract quoted title
        q_m = re.search(r'["\']([^"\'\n\r]{2,40})["\']', raw_title_line)
        if q_m:
            title = sanitize_title(q_m.group(1))
        else:
            title = sanitize_title(raw_title_line)
    else:
        q_m = re.search(r'\b(?:title|제목)\s*(?:is|:|=|maybe)?\s*["\']([^"\'\n\r]{2,30})["\']', text, re.IGNORECASE)
        if q_m:
            title = sanitize_title(q_m.group(1))

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
        r"(?:G2P|발음\s*표기|ACE-Step)[^\n]*\n([\s\S]+?)(?=(?:###|\n\s*\[(?:곡\s*구성|정음|표준)|$))",
        text,
        re.IGNORECASE,
    )
    std_match = re.search(
        r"(?:정음|표준\s*맞춤법|화면\s*표시)[^\n]*\n([\s\S]+?)(?=(?:###|\n\s*\[(?:곡\s*구성|G2P|발음)|$))",
        text,
        re.IGNORECASE,
    )

    if g2p_match:
        g2p_lyrics = g2p_match.group(1).strip()
    if std_match:
        standard_lyrics = std_match.group(1).strip()

    if not g2p_lyrics:
        m_ko = re.search(r"(?m)^\s*\[ko\]", text)
        if m_ko:
            g2p_lyrics = text[m_ko.start():].strip()
        else:
            m_struct = re.search(r"(?m)^\s*\[(?:Intro|Verse|Chorus)", text)
            if m_struct:
                g2p_lyrics = text[m_struct.start():].strip()

    # Check generic markdown headings like ### [가사] or ### 가사
    if not g2p_lyrics and not standard_lyrics:
        m_lyrics_hd = re.search(
            r"(?:###|\*\*|\[)\s*(?:가사|Lyrics)\s*(?:###|\*\*|\])?\s*[:：]?\s*\n([\s\S]+?)(?=(?:###|\n\s*\[(?:곡\s*구성|요약)|$))",
            text,
            re.IGNORECASE,
        )
        if m_lyrics_hd:
            g2p_lyrics = m_lyrics_hd.group(1).strip()

    if not g2p_lyrics and not standard_lyrics:
        g2p_lyrics = text.strip()

    if not standard_lyrics:
        standard_lyrics = g2p_lyrics

    return {
        "title": title or "곡 제목",
        "stylePrompt": style or "ballad, emotional piano, heartfelt vocal",
        "displayLyrics": standard_lyrics,
        "standardLyrics": standard_lyrics,
        "lyrics": g2p_lyrics,
        "summary": summary or "가사 생성 완료",
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


def parse_json_response(raw_text):
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
    return fallback_parse_text(cleaned)


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
        with urllib.request.urlopen(req, timeout=15) as resp:
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


def _execute_chat_completion(url, payload, api_key, timeout_sec):
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

    try:
        with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
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
        raise ValueError(
            f"EXAONE 서버 응답 시간이 초과되었습니다 ({timeout_sec}초). 무료 API 대기열이 길 수 있으니 잠시 후 다시 시도해 주세요."
        )
    except urllib.error.URLError as e:
        if isinstance(getattr(e, "reason", None), (socket.timeout, TimeoutError)) or "timed out" in str(e).lower():
            raise ValueError(
                f"EXAONE 서버 응답 시간이 초과되었습니다 ({timeout_sec}초). 잠시 후 다시 시도해 주세요."
            )
        raise ValueError("EXAONE 서버에 연결할 수 없습니다. 인터넷 연결 상태를 확인해 주세요.")


def generate_lyrics(api_key, prompt, *, genre="", mood="", voice="", tempo=""):
    """Request ACE-Step song lyrics generation from LG K-EXAONE 2.5 API."""
    if not api_key or not isinstance(api_key, str) or not api_key.strip():
        raise ValueError("EXAONE API 키가 설정되지 않았습니다. [설정]에서 API 키를 먼저 입력해 주세요.")
    if not prompt or not isinstance(prompt, str) or not prompt.strip():
        raise ValueError("곡의 주제나 이야기를 입력해 주세요.")

    api_key = api_key.strip()
    prompt = prompt.strip()
    url = get_api_endpoint()
    model = get_model_name()

    user_info_lines = [f"- 주제 및 이야기: {prompt}"]
    if genre:
        user_info_lines.append(f"- 장르 및 스타일: {genre.strip()}")
    if mood:
        user_info_lines.append(f"- 감정선 및 분위기: {mood.strip()}")
    if voice:
        user_info_lines.append(f"- 희망 보컬 음색: {voice.strip()}")
    if tempo:
        user_info_lines.append(f"- 템포: {tempo.strip()}")

    user_message = (
        "다음 곡 기획 정보를 바탕으로 ACE-Step 전용 가사와 영문 스타일 프롬프트를 작성해 주세요.\n\n"
        "### [곡 기획 정보]\n" + "\n".join(user_info_lines)
    )

    timeout_sec = get_timeout_seconds()
    max_tokens = int(os.environ.get("EXAONE_MAX_TOKENS", str(DEFAULT_MAX_TOKENS)))
    reasoning_effort = os.environ.get("EXAONE_REASONING_EFFORT", "low").strip()

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
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
            parsed = parse_json_response(content)
        except Exception as e:
            print(f"[EXAONE Parser Warning] {e}\n[Raw Content]:\n{content}", flush=True)
            parsed = fallback_parse_text(content)

    raw_lyrics = _get_field(
        parsed,
        "lyrics",
        "phoneticLyrics",
        "phonetic_lyrics",
        "g2pLyrics",
        "g2p_lyrics",
        "발음가사",
        "발음 가사",
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
    )

    if not raw_lyrics and not raw_display:
        raw_lyrics = _get_field(parsed, "가사", "text", "content", "song")
        raw_display = raw_lyrics

    # Multi-tier recovery: If content lacked Korean song content, inspect reasoning_content
    # Only salvage from reasoning if it contains song structure markers or strict JSON
    combined_korean = len(re.findall(r"[\uac00-\ud7a3]", (raw_lyrics or "") + (raw_display or "")))
    if combined_korean < 5 and reasoning:
        has_song_markers = bool(
            re.search(
                r"(?:\[(?:Intro|Verse|Chorus|Bridge|Outro|ko)\]|###\s*\[?(?:정음|G2P|가사|발음))",
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
                reasoning_parsed = strict_in_reasoning if strict_in_reasoning else fallback_parse_text(reasoning)
            except Exception:
                reasoning_parsed = fallback_parse_text(reasoning)

            r_lyrics = _get_field(
                reasoning_parsed,
                "lyrics",
                "phoneticLyrics",
                "phonetic_lyrics",
                "g2pLyrics",
                "g2p_lyrics",
                "발음가사",
                "발음 가사",
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
            )
            if not r_lyrics and not r_display:
                r_lyrics = _get_field(reasoning_parsed, "가사", "text", "content", "song")
                r_display = r_lyrics

            if len(re.findall(r"[\uac00-\ud7a3]", (r_lyrics or "") + (r_display or ""))) >= 5:
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

    lyrics = sanitize_lyrics(raw_lyrics, fallback_display=raw_display)
    display_lyrics = sanitize_display_lyrics(raw_display, fallback_lyrics=raw_lyrics)

    raw_title = _get_field(parsed, "title", "곡제목", "제목", "songTitle")
    title = sanitize_title(raw_title, default_topic=prompt)
    style_prompt = (
        _get_field(parsed, "stylePrompt", "style_prompt", "style", "스타일프롬프트", "스타일")
        or "ballad, acoustic piano, emotional vocal, 72 BPM"
    )
    summary = _get_field(parsed, "summary", "요약", "description") or "가사 생성 완료"

    return {
        "title": title,
        "stylePrompt": style_prompt,
        "displayLyrics": display_lyrics,
        "standardLyrics": display_lyrics,
        "lyrics": lyrics,
        "summary": summary,
    }
