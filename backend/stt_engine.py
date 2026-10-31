import json
import logging
import os
import re
from pathlib import Path
from types import SimpleNamespace
from typing import Callable, Dict, List, Optional, Tuple

from .config import DEFAULT_GEMINI_API_KEY
from .translation_engine import get_gemini_client, generate_content_with_retry_and_fallback

logger = logging.getLogger("stt_engine")
logger.setLevel(logging.INFO)

# Global model caches so models aren't reloaded repeatedly
_whisper_cache = {}
_sensevoice_cache = {}


def prepare_speech_enhanced_audio(audio_path: str) -> str:
    """
    Produces a speech-clarified, 16kHz mono WAV for high-quality STT detection.
    Optimized to preserve whispery speech, reverberant inner thoughts, and character monologues.
    """
    if not audio_path or not os.path.exists(audio_path):
        return audio_path

    # Avoid redundant re-enhancement if already processed
    if "stt_enhanced_" in os.path.basename(audio_path):
        return audio_path

    try:
        from .audio_video_processor import run_ffmpeg, get_audio_duration
        from .config import TEMP_DIR

        orig_dur = get_audio_duration(audio_path)

        enhanced_path = os.path.join(TEMP_DIR, f"stt_enhanced_v3_{Path(audio_path).stem}.wav")
        if os.path.exists(enhanced_path) and os.path.getsize(enhanced_path) > 1024:
            if orig_dur and orig_dur > 0:
                cached_dur = get_audio_duration(enhanced_path)
                if abs(cached_dur - orig_dur) <= 0.15:
                    return enhanced_path
                else:
                    logger.info(f"Invalidating stale enhanced audio cache (cached: {cached_dur:.2f}s, orig: {orig_dur:.2f}s)")
                    try:
                        os.remove(enhanced_path)
                    except Exception:
                        pass
            else:
                return enhanced_path

        # Clean speech audio pipeline:
        # 1. highpass=40   — cut sub-bass rumble (<40Hz) while keeping full male voice fundamentals and deep inner-monologue chest resonance
        # 2. lowpass=12000 — preserve full upper vocal spectrum up to 12kHz so sibilants, quiet consonants, and reverb tails of inner thoughts are never lost
        # 3. dynaudnorm    — dynamic normalization with g=21 to lift quiet/whispered character speech and faint inner-monologue
        af_chain = "highpass=f=40,lowpass=f=12000,dynaudnorm=p=0.95:m=5:s=3:g=21:r=0.9"
        args = [
            "-i", audio_path,
            "-vn",
            "-ar", "16000",
            "-ac", "1",
            "-af", af_chain,
            "-c:a", "pcm_s16le",
        ]
        if orig_dur and orig_dur > 0:
            args.extend(["-t", f"{orig_dur:.3f}"])
        args.extend(["-y", enhanced_path])

        ok, err = run_ffmpeg(args)
        if ok and os.path.exists(enhanced_path) and os.path.getsize(enhanced_path) > 1024:
            logger.info(f"Speech audio enhanced for STT (duration {orig_dur:.2f}s): {enhanced_path}")
            return enhanced_path
        else:
            logger.warning(f"Audio enhancement skipped ({err}). Using original audio.")
            return audio_path
    except Exception as e:
        logger.warning(f"Error enhancing audio for STT: {e}. Using original audio.")
        return audio_path


def get_stt_initial_prompt(language: Optional[str] = None) -> str:
    """
    Provides a tailored initial prompt to guide Whisper towards strict verbatim transcription,
    specifically instructing it to capture character inner thoughts, internal monologue,
    reverberant thoughts, voiceovers, and quiet whispers without dropping a single word.
    """
    lang = (language or "").lower().strip()
    if lang in ("km", "khmer"):
        return "សូមចម្លងពាក្យសម្តីរបស់តួអង្គទាំងអស់ឱ្យបានគ្រប់ម៉ាត់ រួមទាំងការនិយាយក្នុងចិត្ត (Inner monologue/សម្លេងគិតក្នុងចិត្ត), សម្លេងរៀបរាប់ (Voiceover), សម្លេងបន្ទរ (Reverb/Echo), និងសម្លេងខ្សឹប ដោយមិនរំលងពាក្យសូម្បីតែមួយម៉ាត់ឡើយ។"
    elif lang in ("en", "english"):
        return "Hello. Please transcribe all character dialogue, inner thoughts, internal monologue, voiceover narration, reverberant thoughts, and whispers verbatim without skipping any words. Every spoken word and thought must be captured completely."
    elif lang in ("zh", "chinese"):
        return "请逐字逐句完整转录所有人物的对话、内心独白、心声心语、旁白叙述及低语，切勿遗漏任何词语或句子，保留全部细节和标点符号。"
    elif lang in ("ja", "japanese"):
        return "すべての登場人物のセリフ、モノローグ（心の声・内面描写）、回想ナレーション、囁き声を一語一句漏らさず正確に文字起こししてください。"
    elif lang in ("th", "thai"):
        return "กรุณาถอดเสียงบทสนทนาของตัวละครทั้งหมดให้ครบถ้วนทุกคำ รวมถึงเสียงพูดในใจ (บทพูดในใจ / เสียงคิดในใจ), เสียงบรรยาย, เสียงสะท้อน, และเสียงกระซิบ ไม่ข้ามแม้แต่คำเดียว"
    return "Please transcribe all character dialogue, inner thoughts, internal monologue, voiceovers, and whispers verbatim without skipping any words or thoughts. Every spoken word must be captured completely."


def is_filler_or_hallucination(text: str) -> bool:
    """
    Filters out non-dialogue hallucinated sounds, breathing artifacts,
    Whisper-specific boilerplate hallucinations, and pure noise tokens.
    Preserves all real character dialogue across all languages (Khmer, Chinese, English, Japanese, Thai, etc.).
    """
    if not text or not str(text).strip():
        return True

    text_str = str(text).strip()

    # 1. Pure punctuation or symbols
    if re.fullmatch(r"[\s\.,!\?…~_\-–—:;\"'«»“”‘’\(\)\[\]\{\}♪♫♬♩🎶\*\#\/\\|]+", text_str):
        return True

    # 2. Sound effect tags like [music], (laughter), [applause]
    text_clean = text_str.lower().strip()
    if re.fullmatch(r"[\[\(](?:music|applause|laughter|silence|audio|sound|cheering|chuckle|sigh|gasp|screaming|crying)[\]\)]", text_clean):
        return True

    # 3. Pure non-verbal vocal noise tokens (e.g. laughter, screaming)
    # Note: Short character responses like 'hmm', 'shh', 'oh', 'ah', 'yes', 'no' are kept as valid dialogue
    noise_tokens = {
        "haha", "hahaha", "hahahaha", "hehe", "hehehe", "pfft",
        "ahhhhh", "aaaaah",
    }
    latin_words = [w.lower() for w in re.findall(r"[a-zA-Z]+", text_str)]
    # Only filter if it contains ONLY noise tokens AND contains no CJK/Khmer/Thai/Korean characters
    has_cjk_or_khmer = bool(re.search(r"[\u1780-\u17FF\u4E00-\u9FFF\u3040-\u30FF\u0E00-\u0E7F\uAC00-\uD7AF]", text_str))
    if latin_words and all(w in noise_tokens for w in latin_words) and not has_cjk_or_khmer:
        return True

    # Repeated laughter or screaming pattern like "hahahaha"
    if re.fullmatch(r"(?:ha|he|ah|eh|oh|er|uh|mm|hm){3,}", text_clean):
        return True

    # 4. Whisper hallucination boilerplate (common false positives on silence/outro)
    whisper_hallucinations = {
        "thanks for watching", "thank you for watching", "thanks for listening",
        "thank you for listening", "please subscribe", "like and subscribe",
        "don't forget to subscribe", "subscribe to my channel",
        "subtitles by", "translated by", "transcribed by", "captions by",
        "www.youtube.com", "http", "https",
        "谢谢大家观看", "感谢收看", "请订阅", "点赞和订阅",
        "សូមអរគុណសម្រាប់ការទស្សនា", "សូម subscribe",
    }
    norm_phrase = re.sub(r"[^\w\s\u1780-\u17FF\u4E00-\u9FFF\u3040-\u30FF\u0E00-\u0E7F\uAC00-\uD7AF]", "", text_clean).strip()
    if norm_phrase in whisper_hallucinations:
        return True

    return False


# Incomplete syntactic connectors that should never sit alone as an isolated subtitle
DANGLING_CONNECTORS = {
    # Pronouns & determiners
    "i", "you", "he", "she", "we", "they", "it", "my", "your", "his", "her", "our", "their",
    "what", "which", "who", "whom", "whose", "where", "when", "why", "how",
    "that", "this", "these", "those", "a", "an", "the",
    # Conjunctions
    "and", "but", "or", "so", "because", "if", "though", "although", "while", "as", "than",
    "either", "neither", "nor", "since", "until", "unless",
    # Prepositions
    "to", "for", "with", "in", "on", "at", "from", "by", "of", "about", "into", "through",
    "over", "under", "after", "before", "between", "against", "without",
    # Auxiliary verbs & modals
    "is", "are", "was", "were", "am", "be", "been", "being",
    "have", "has", "had", "do", "does", "did",
    "will", "would", "shall", "should", "can", "could", "may", "might", "must",
    "not", "just", "really", "very",
    # Khmer syntactic connectors & conjunctions
    "ថា", "ហើយ", "ដែល", "ពីព្រោះ", "ព្រោះ", "ប៉ុន្តែ", "តែ", "និង", "ឬ", "បើ", "ប្រសិនបើ", "ដូចជា", "ដើម្បី", "គឺ", "នូវ"
}

TERMINAL_PUNCT_REGEX = re.compile(r"[\.!\?។៕…][\"'»”’\s\)]*$")
EXCLAMATION_PUNCT_REGEX = re.compile(r"[!！][\"'»”’\s\)]*$")

# Short standalone exclamation and urgent interjection callouts in Khmer and English
EXCLAMATION_INTERJECTIONS_KM = {
    "ឈប់", "ឈប់សិន", "ប្រយ័ត្ន", "ជួយផង", "អ្ហះ", "កុំ"
}
EXCLAMATION_INTERJECTIONS_EN = {
    "hey", "wait", "stop", "look", "watch out", "help", "run", "freeze"
}


def is_exclamatory_or_interjection(text: str) -> bool:
    """Checks if a dialogue text is an explicit exclamation or urgent callout."""
    if not text:
        return False
    t = text.strip()
    # 1. Explicit exclamation mark ! or ！
    if bool(EXCLAMATION_PUNCT_REGEX.search(t)):
        return True
    # 2. Short standalone urgent interjection (1-2 words only)
    words = t.split()
    if len(words) <= 2:
        first_clean = re.sub(r"[^\w\u1780-\u17FF]", "", words[0].lower())
        full_clean = re.sub(r"[^\w\u1780-\u17FF]", "", t.lower())
        if first_clean in EXCLAMATION_INTERJECTIONS_EN or full_clean in EXCLAMATION_INTERJECTIONS_EN:
            return True
        if first_clean in EXCLAMATION_INTERJECTIONS_KM or full_clean in EXCLAMATION_INTERJECTIONS_KM:
            return True
    return False


def split_compound_dialogue_segment(seg: Dict) -> List[Dict]:
    """
    Splits a run-on dialogue segment containing multiple sentences, exclamations (ឧទាន !),
    or full stops (ខណ្ឌ ។/.) into separate crisp subtitle segments with proportional timestamps.
    Prevents dialogue from different thoughts or characters from staying jammed together.
    """
    text = (seg.get("text") or "").strip()
    if not text:
        return [seg]

    # Split pattern: periods, exclamation marks, question marks, and Khmer Khan (។ / ៕) followed by space or end
    # Retains the punctuation mark on the preceding clause
    split_pattern = r"(?<=[!！\?？\.。។៕])\s+(?=[A-Za-z0-9\u1780-\u17FF])"
    parts = [p.strip() for p in re.split(split_pattern, text) if p.strip()]

    if len(parts) <= 1:
        return [seg]

    start_t = float(seg.get("start", 0.0))
    end_t = float(seg.get("end", start_t + 1.0))
    total_dur = max(0.4, end_t - start_t)

    # Estimate timing based on character lengths
    lengths = [max(1, len(re.sub(r"\s+", "", p))) for p in parts]
    total_len = sum(lengths)

    sub_segs = []
    curr_t = start_t
    base_id = seg.get("id", 1)

    for idx, (p, p_len) in enumerate(zip(parts, lengths)):
        p_dur = round((p_len / total_len) * total_dur, 2)
        p_dur = max(0.35, p_dur)
        p_end = round(curr_t + p_dur, 2)

        # On the last part, snap to original end_t
        if idx == len(parts) - 1:
            p_end = max(round(curr_t + 0.35, 2), end_t)

        new_s = dict(seg)
        new_s["text"] = p
        new_s["start"] = round(curr_t, 2)
        new_s["end"] = round(p_end, 2)
        
        # Detect emotion if exclamation mark present
        if bool(EXCLAMATION_PUNCT_REGEX.search(p)) and new_s.get("emotion") == "neutral":
            new_s["emotion"] = "excited"

        sub_segs.append(new_s)
        curr_t = p_end + 0.05  # 50ms breathing gap between split clauses

    return sub_segs


def merge_dialogue_fragments(
    segments: List[Dict],
    max_gap: float = 0.55,
    max_combined_duration: float = 4.8,
    max_combined_words: int = 14
) -> List[Dict]:
    """
    Intelligently stitches broken speech fragments into complete, natural dialogue sentences
    WITHOUT accidentally gluing different characters' turns or distinct sentences together.
    Strictly preserves sentence boundaries (ខណ្ឌ ។ and ឧទាន !), exclamations, and speaker isolation.
    """
    if not segments:
        return []

    # First pass: split any compound run-on sentences within segments
    expanded: List[Dict] = []
    for s in segments:
        expanded.extend(split_compound_dialogue_segment(s))

    merged: List[Dict] = []

    for s in expanded:
        s_text = (s.get("text") or "").strip()
        if not s_text:
            continue

        s_start = round(float(s.get("start", 0.0)), 2)
        s_end = round(float(s.get("end", s_start + 0.5)), 2)
        s_speaker = s.get("speaker", "Speaker 1")
        s_lang = s.get("language", "en")

        if merged:
            prev = merged[-1]
            prev_text = prev.get("text", "").strip()
            prev_speaker = prev.get("speaker", "Speaker 1")
            prev_start = float(prev.get("start", 0.0))
            prev_end = float(prev.get("end", prev_start + 0.5))

            gap = round(s_start - prev_end, 2)
            combined_dur = round(s_end - prev_start, 2)
            prev_words = prev_text.split()
            curr_words = s_text.split()
            total_words = len(prev_words) + len(curr_words)

            # Check terminal punctuation (. ! ? ... ។ ៕) on previous segment
            prev_has_punct = bool(TERMINAL_PUNCT_REGEX.search(prev_text))
            prev_is_exclamation = bool(EXCLAMATION_PUNCT_REGEX.search(prev_text)) or is_exclamatory_or_interjection(prev_text)
            curr_is_exclamation = is_exclamatory_or_interjection(s_text)

            # Check if previous ended with dangling connector (e.g. "and", "because", "what I", "ខ្ញុំគិតថា")
            last_word = re.sub(r"[^\w\u1780-\u17FF]", "", prev_words[-1].lower()) if prev_words else ""
            prev_is_dangling = (last_word in DANGLING_CONNECTORS) or any(prev_text.endswith(conn) for conn in ("ថា", "ហើយ", "ដែល", "ពីព្រោះ", "ព្រោះ", "ប៉ុន្តែ", "តែ", "និង", "ឬ"))

            # Check capitalization of current segment
            first_char = s_text[0] if s_text else ""
            curr_is_capital = first_char.isupper()
            curr_is_continuation = first_char.islower()

            same_speaker = (prev_speaker == s_speaker) and bool(prev_speaker and s_speaker)

            # STRICT NON-MERGING CONDITIONS (Never merge when):
            # 1. Different characters/speakers speaking -> NEVER merge!
            # 2. Previous segment ends with period (ខណ្ឌ ។), exclamation (ឧទាន !), question (?) -> NEVER merge!
            # 3. Previous or current segment is an exclamation / callout ("ឈប់!", "Stop!", etc.) -> NEVER merge!
            # 4. Next segment starts with a question word or capitalized character turn and gap >= 0.28s -> NEVER merge!
            # 5. Gap >= 0.55s (normal) or >= 1.0s (dangling) -> distinct conversational pause -> NEVER merge!
            should_merge = False
            if same_speaker and combined_dur <= max_combined_duration and total_words <= max_combined_words:
                if not prev_has_punct and not prev_is_exclamation and not curr_is_exclamation:
                    if prev_is_dangling and gap <= 1.00:
                        should_merge = True
                    elif gap <= max_gap:
                        if curr_is_continuation and gap <= 0.45:
                            should_merge = True
                        elif not curr_is_capital and gap <= 0.50:
                            should_merge = True

            if should_merge:
                sep = "" if prev_text.endswith("-") else " "
                prev["text"] = f"{prev_text}{sep}{s_text}".strip()
                prev["end"] = max(prev_end, s_end)
                if s.get("khmer_text") and prev.get("khmer_text"):
                    prev["khmer_text"] = f"{prev['khmer_text']} {s['khmer_text']}".strip()
                elif s.get("khmer_text") and not prev.get("khmer_text"):
                    prev["khmer_text"] = s["khmer_text"].strip()
                continue
            else:
                # Ensure clean non-overlapping boundary between distinct character segments
                if prev_end > s_start:
                    prev["end"] = max(prev_start + 0.35, round(s_start - 0.05, 2))

        # Add as new separate segment
        merged.append({
            "id": len(merged) + 1,
            "start": s_start,
            "end": s_end,
            "text": s_text,
            "khmer_text": s.get("khmer_text", ""),
            "speaker": s_speaker,
            "language": s_lang,
            "voice": s.get("voice", "Khmer Male 01"),
            "emotion": s.get("emotion", "neutral")
        })

    for idx, seg in enumerate(merged, 1):
        seg["id"] = idx

    return merged


def split_words_into_dialogue_segments(words: list, detected_lang: str = "en") -> List[Dict]:
    """
    Groups word-level timestamps into crisp, distinct dialogue subtitle segments.
    Splits immediately at sentence boundaries, speaker turn-taking pauses, and character questions/answers.
    """
    if not words:
        return []

    def finish_segment(seg_words, idx, speaker_name="Speaker 1"):
        if not seg_words:
            return None

        # Clean only pure punctuation or music symbol artifacts from segment edges,
        # NEVER strip real spoken character words (e.g. 'Oh', 'Ah', 'Hmm', 'Yes', 'No', 'បាទ', 'ចាស', 'អូ')
        while seg_words and re.fullmatch(r"[\s\.,!\?…~_\-–—:;\"'«»“”‘’\(\)\[\]\{\}♪♫♬♩🎶\*\#\/\\|]+", seg_words[0].word.strip()):
            seg_words = seg_words[1:]
        if not seg_words:
            return None

        while seg_words and re.fullmatch(r"[\s\.,!\?…~_\-–—:;\"'«»“”‘’\(\)\[\]\{\}♪♫♬♩🎶\*\#\/\\|]+", seg_words[-1].word.strip()):
            seg_words = seg_words[:-1]
        if not seg_words:
            return None

        has_internal_spaces = any(w.word.startswith(" ") or w.word.endswith(" ") for w in seg_words[1:])
        if has_internal_spaces or (detected_lang and detected_lang in ("km", "zh", "ja", "th")):
            text = "".join(w.word for w in seg_words).strip()
        else:
            text = " ".join(w.word.strip() for w in seg_words if w.word.strip()).strip()

        # Reject only if text is purely empty, pure symbol, or hallucinated outro credit
        if not text or is_filler_or_hallucination(text):
            return None

        start_t = round(float(seg_words[0].start), 2)
        end_t = round(float(seg_words[-1].end), 2)
        # Ensure minimum subtitle display duration (at least 0.35s) so quick words are visible and dubbable
        if end_t <= start_t or (end_t - start_t) < 0.35:
            end_t = round(start_t + 0.35, 2)

        return {
            "id": idx,
            "start": start_t,
            "end": end_t,
            "text": text,
            "speaker": speaker_name,
            "language": detected_lang
        }

    raw_segments = []
    current_words = []
    seg_idx = 1
    current_speaker = "Speaker 1"

    for i, w in enumerate(words):
        current_words.append(w)
        word_text = w.word.strip()
        is_question = word_text.endswith(("?", "？"))
        is_exclaim = word_text.endswith(("!", "！"))
        is_period = word_text.endswith((".", "...", "。", "។", "៕", "…"))
        is_clause = word_text.endswith((",", "，", "、", ";", "；", ":", "："))
        
        pause_to_next = float(words[i + 1].start) - float(w.end) if i + 1 < len(words) else 0.0
        curr_duration = float(w.end) - float(current_words[0].start)
        word_count = len(current_words)

        last_word_clean = re.sub(r"[^\w]", "", word_text.lower())
        is_dangling = last_word_clean in DANGLING_CONNECTORS

        next_word_clean = words[i + 1].word.strip() if i + 1 < len(words) else ""
        next_is_capital = bool(next_word_clean and next_word_clean[0].isupper())
        next_is_lowercase = bool(next_word_clean and next_word_clean[0].islower())

        should_split = False
        # 1. Unambiguous sentence endpoints (? or !) -> ALWAYS split immediately
        if is_question or is_exclaim:
            should_split = True
        # 2. Khmer sentence terminator (ខណ្ឌ ។ ឬ ៕) -> ALWAYS split immediately
        elif word_text.endswith(("។", "៕")):
            should_split = True
        # 3. Period / full stop ending a thought
        elif is_period and (pause_to_next >= 0.03 or word_count >= 1):
            should_split = True
        # 4. Immediate split if current word is an exclamation / callout and small pause occurs
        elif is_exclamatory_or_interjection(word_text) and (pause_to_next >= 0.18 or word_count >= 1):
            should_split = True
        # 5. Conversational turn-taking pause (>= 0.24s) followed by capital letter or question word
        elif pause_to_next >= 0.24 and (next_is_capital or is_exclamatory_or_interjection(next_word_clean)) and not is_dangling:
            should_split = True
        # 6. Natural character dialogue turn pause (>= 0.35s) -> distinct character exchange
        elif pause_to_next >= 0.35 and not is_dangling:
            should_split = True
        # 7. Clause punctuation (, ;) when segment duration is already >= 1.8s and pause >= 0.15s
        elif is_clause and curr_duration >= 1.8 and pause_to_next >= 0.15 and not is_dangling:
            should_split = True
        # 8. Human breath cap (3.2s with pause, 4.5s hard cap)
        elif curr_duration >= 3.2 and pause_to_next >= 0.10 and not is_dangling:
            should_split = True
        elif curr_duration >= 4.5:
            should_split = True

        if should_split:
            seg = finish_segment(current_words, seg_idx, current_speaker)
            if seg:
                raw_segments.append(seg)
                seg_idx += 1
            current_words = []

    if current_words:
        seg = finish_segment(current_words, seg_idx, current_speaker)
        if seg:
            raw_segments.append(seg)

    return merge_dialogue_fragments(raw_segments)


def transcribe_with_whisper(
    audio_path: str,
    model_size: str = "base",
    language: Optional[str] = None,
    progress_callback: Optional[Callable[[str], None]] = None
) -> List[Dict]:
    """
    Transcribe audio using faster-whisper with speech dynamic enhancement,
    high-sensitivity VAD, verbatim character dialogue retention, and fallback.
    """
    from faster_whisper import WhisperModel

    # Map aliases to standard faster-whisper models
    size = model_size.lower().strip() if model_size else "small"
    if size in ("auto", "default"):
        size = "small"

    if progress_callback:
        progress_callback(f"Loading Whisper model ({size})...")

    global _whisper_cache
    if size not in _whisper_cache:
        # Detect device and thread pool
        num_threads = min(8, max(2, os.cpu_count() or 4))
        try:
            import torch
            device = "cuda" if torch.cuda.is_available() else "cpu"
            compute_type = "float16" if device == "cuda" else "int8"
        except Exception:
            device = "cpu"
            compute_type = "int8"

        try:
            _whisper_cache[size] = WhisperModel(
                size,
                device=device,
                compute_type=compute_type,
                cpu_threads=num_threads,
                num_workers=1
            )
            logger.info(f"Loaded faster-whisper model '{size}' on {device} ({compute_type}) with {num_threads} threads.")
        except Exception as e:
            logger.warning(f"Could not load faster-whisper on {device}: {e}. Fallback to CPU int8.")
            _whisper_cache[size] = WhisperModel(size, device="cpu", compute_type="int8", cpu_threads=num_threads)

    model = _whisper_cache[size]

    if progress_callback:
        progress_callback("Enhancing audio clarity for character speech...")

    # Enhance audio with dynamic range normalization and rumble cut
    enhanced_audio = prepare_speech_enhanced_audio(audio_path)

    if progress_callback:
        progress_callback(f"Running Whisper speech recognition ({size})...")

    lang_param = None if not language or language.lower() in ("auto", "detect") else language.lower()
    prompt = get_stt_initial_prompt(language)

    # Ultra-sensitive VAD settings tuned for cinema/anime dialogue & reverberant inner thoughts:
    # - threshold 0.08: captures muffled inner-monologue, reverb/echo tails, and faint thoughts in mind
    # - min_speech_duration_ms 40: captures ultra-short words and quick inner reactions
    # - min_silence_duration_ms 250: responsive speech boundaries
    # - speech_pad_ms 500: preserves speech onset and reverb echo tails of inner monologue
    vad_params = {
        "threshold": 0.08,
        "min_speech_duration_ms": 40,
        "max_speech_duration_s": 20.0,
        "min_silence_duration_ms": 250,
        "speech_pad_ms": 500,
    }

    # Hallucinated metadata/boilerplate and music symbols
    OUTRO_BOILERPLATE = {
        "thanks for watching", "thank you for watching", "thanks for listening",
        "thank you for listening", "please subscribe", "like and subscribe",
        "don't forget to subscribe", "subscribe to my channel",
        "subtitles by", "captions by", "transcribed by",
    }
    MUSIC_SYMBOLS = {"♪", "♫", "♬", "♩", "🎶"}
    NO_SPEECH_THRESHOLD = 0.95  # High tolerance: ensures speech over background music/SFX is kept
    MIN_AVG_LOGPROB = -2.85      # Tolerant logprob: keeps character speech in noisy or accented scenes

    def _execute_transcription(input_path: str, use_vad: bool = False):
        return model.transcribe(
            input_path,
            beam_size=5,
            best_of=5,                           # Consider top-5 candidate beams (better accuracy)
            temperature=[0.0, 0.2, 0.4],         # Greedy first, fallback to sampling if logprob too low
            language=lang_param,
            word_timestamps=True,
            vad_filter=use_vad,                  # False by default: allows reverberant inner thoughts & whispers to reach decoder
            vad_parameters=vad_params if use_vad else None,
            initial_prompt=prompt,
            condition_on_previous_text=False,    # Critical: prevents skipping dialogue after pauses/music
            no_speech_threshold=NO_SPEECH_THRESHOLD,
            compression_ratio_threshold=2.6,     # Reject highly-repeated garbage output (hallucination)
            log_prob_threshold=MIN_AVG_LOGPROB,  # Let Whisper itself reject low-confidence segments
            hallucination_silence_threshold=2.0, # Avoid trailing hallucinations on pauses
        )

    def _collect_segments(generator, detected_language: str):
        words_collected = []
        segs_collected = []
        s_id = 1

        for seg in generator:
            text = (seg.text or "").strip()
            if not text:
                continue

            no_speech_prob = getattr(seg, "no_speech_prob", 0.0) or 0.0
            if no_speech_prob > NO_SPEECH_THRESHOLD:
                logger.debug(f"Skipping silence segment [no_speech_prob={no_speech_prob:.2f}]: '{text[:60]}'")
                continue

            avg_logprob = getattr(seg, "avg_logprob", 0.0) or 0.0
            if avg_logprob < MIN_AVG_LOGPROB:
                logger.debug(f"Skipping garbage segment [logprob={avg_logprob:.2f}]: '{text[:60]}'")
                continue

            text_clean = text.strip()
            text_lower = text_clean.lower().strip(" .!?,:;\"'")

            # Skip pure music notes or sound effects in brackets
            if all(ch in MUSIC_SYMBOLS or ch in " \t\r\n" for ch in text_clean):
                continue
            if re.fullmatch(r"\[(music|applause|laughter|silence|audio|sound|cheering)\]", text_lower):
                continue
            if re.fullmatch(r"\((music|applause|laughter|silence|audio|sound|cheering)\)", text_lower):
                continue
            if text_lower in OUTRO_BOILERPLATE:
                logger.debug(f"Skipping outro boilerplate: '{text[:60]}'")
                continue
            if re.fullmatch(r"[\.\-_~\s]+", text_clean):
                continue

            if is_filler_or_hallucination(text):
                logger.debug(f"Skipping filler: '{text[:60]}'")
                continue

            start_time = round(float(seg.start), 2)
            end_time = round(float(seg.end), 2)
            if end_time <= start_time:
                end_time = round(start_time + 0.5, 2)

            # Preserve word tokens for dialogue segmentation
            if hasattr(seg, "words") and seg.words:
                words_collected.extend(seg.words)
            else:
                # Essential for inner thoughts, whispers, and reverberant voices where cross-attention
                # alignment does not generate sub-word timestamps: synthesize word tokens so
                # split_words_into_dialogue_segments NEVER drops inner thought text!
                split_words = text.split()
                if split_words:
                    num_w = len(split_words)
                    w_dur = max(0.05, (end_time - start_time) / num_w)
                    for wi, w_str in enumerate(split_words):
                        w_st = round(start_time + wi * w_dur, 2)
                        w_et = round(min(end_time, w_st + w_dur), 2)
                        words_collected.append(
                            SimpleNamespace(word=w_str, start=w_st, end=max(w_et, w_st + 0.05), probability=1.0)
                        )

            segs_collected.append({
                "id": s_id,
                "start": start_time,
                "end": end_time,
                "text": text,
                "language": detected_language
            })
            s_id += 1

        return segs_collected, words_collected

    # Primary pass: vad_filter=False ensures 100% of inner thoughts, reverberant monologues, and whispers reach Whisper!
    segments_generator, info = _execute_transcription(enhanced_audio, use_vad=False)
    detected_lang = info.language
    logger.info(f"Whisper detected language: {detected_lang} (probability: {info.language_probability:.2f})")

    raw_segments, all_words = _collect_segments(segments_generator, detected_lang)

    logger.info(f"Whisper produced {len(raw_segments)} speech segments (words: {len(all_words)})")

    # If word-level timestamps are available, produce refined dialogue segments
    from .audio_video_processor import get_audio_duration
    audio_dur = get_audio_duration(audio_path)

    final_segs = None
    if all_words:
        refined = split_words_into_dialogue_segments(all_words, detected_lang=detected_lang)
        if refined:
            logger.info(f"Refined {len(raw_segments)} raw chunks into {len(refined)} natural dialogue segments.")
            final_segs = refined

    if not final_segs:
        final_segs = merge_dialogue_fragments(raw_segments)
    else:
        # Guarantee no inner thoughts or character monologues from raw_segments are missed
        existing_text = " ".join(s.get("text", "") for s in final_segs)
        for raw_s in raw_segments:
            raw_t = (raw_s.get("text") or "").strip()
            if raw_t and len(raw_t) >= 2 and raw_t not in existing_text:
                logger.info(f"Preserving unmerged inner thought/speech segment: {raw_t}")
                final_segs.append(raw_s)
        final_segs.sort(key=lambda s: float(s.get("start", 0.0)))
        for idx, s in enumerate(final_segs, 1):
            s["id"] = idx

    # Hard clamp timestamps to physical audio duration to prevent Whisper chunk overshooting
    if audio_dur and audio_dur > 0 and final_segs:
        for s in final_segs:
            s["start"] = round(min(max(0.0, float(s.get("start", 0.0))), audio_dur), 2)
            s["end"] = round(min(max(float(s.get("start", 0.0)) + 0.2, float(s.get("end", 0.0))), audio_dur), 2)

    return final_segs


def extract_sensevoice_emotion(text: str) -> str:
    """Extract emotion from SenseVoice tags like <|HAPPY|>, <|SAD|>, <|ANGRY|>, etc."""
    upper = text.upper()
    if "<|ANGRY|>" in upper or "ANGRY" in upper:
        return "angry"
    elif "<|SAD|>" in upper or "SAD" in upper:
        return "sad"
    elif "<|HAPPY|>" in upper or "HAPPY" in upper or "<|LAUGHTER|>" in upper:
        return "excited"
    elif "<|FEARFUL|>" in upper or "<|FEAR|>" in upper:
        return "terrified"
    elif "<|WHISPER|>" in upper:
        return "whisper"
    return "neutral"


def clean_sensevoice_tags(text: str) -> str:
    """Removes SenseVoice special audio/emotion tokens like <|HAPPY|>, <|BGM|>, <|zh|>, etc."""
    cleaned = re.sub(r"<\|[^|>]+(?:\|>|(?=\s|$))", "", text)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def transcribe_with_sensevoice(
    audio_path: str,
    model_name: str = "iic/SenseVoiceSmall",
    language: Optional[str] = "auto",
    progress_callback: Optional[Callable[[str], None]] = None
) -> List[Dict]:
    """
    Transcribe audio using FunASR's SenseVoiceSmall model with automatic emotion detection.
    """
    from funasr import AutoModel

    if progress_callback:
        progress_callback("Loading SenseVoiceSmall model...")

    global _sensevoice_cache
    if model_name not in _sensevoice_cache:
        # Load SenseVoiceSmall model
        _sensevoice_cache[model_name] = AutoModel(
            model=model_name,
            trust_remote_code=True,
            device="cpu",
            disable_update=True
        )

    model = _sensevoice_cache[model_name]

    if progress_callback:
        progress_callback("Running SenseVoiceSmall transcription & emotion detection...")

    lang_code = "auto"
    if language and language.lower() not in ("auto", "detect"):
        lang_code = language.lower()

    # SenseVoice generate call
    res = model.generate(
        input=audio_path,
        language=lang_code,
        use_itn=True,
        batch_size_s=60
    )

    results = []
    seg_id = 1

    if isinstance(res, list) and len(res) > 0:
        item = res[0]
        # Check if timestamps / sentence segments exist
        if "sentence_info" in item and item["sentence_info"]:
            for s in item["sentence_info"]:
                raw_text = s.get("text", "")
                emo = extract_sensevoice_emotion(raw_text)
                cleaned = clean_sensevoice_tags(raw_text)
                if cleaned:
                    start = round(float(s.get("start", 0)) / 1000.0, 2)
                    end = round(float(s.get("end", 0)) / 1000.0, 2)
                    results.append({
                        "id": seg_id,
                        "start": start,
                        "end": max(end, start + 0.5),
                        "text": cleaned,
                        "language": lang_code,
                        "emotion": emo
                    })
                    seg_id += 1
        else:
            # Fallback to single text if sentence_info not present
            raw_text = item.get("text", "")
            emo = extract_sensevoice_emotion(raw_text)
            cleaned = clean_sensevoice_tags(raw_text)
            if cleaned:
                # Estimate duration from audio duration
                from .audio_video_processor import get_audio_duration
                total_dur = get_audio_duration(audio_path)
                results.append({
                    "id": 1,
                    "start": 0.0,
                    "end": round(total_dur, 2) if total_dur > 0 else 5.0,
                    "text": cleaned,
                    "language": lang_code,
                    "emotion": emo
                })

    return merge_dialogue_fragments(results)


def transcribe_with_gemini(
    audio_path: str,
    api_key: Optional[str] = None,
    model_name: str = "gemini-3.5-flash",
    progress_callback: Optional[Callable[[str], None]] = None
) -> List[Dict]:
    """
    Transcribe audio with precise timestamps using Gemini multimodal audio capabilities.
    """
    from google.genai import types

    client = get_gemini_client(api_key)

    if progress_callback:
        progress_callback(f"Uploading audio to Gemini for STT ({model_name})...")

    # Upload audio file
    uploaded_file = client.files.upload(file=audio_path)

    if progress_callback:
        progress_callback("Analyzing audio and extracting timed subtitles with Gemini...")

    system_instruction = """
You are an expert speech recognition and character dialogue subtitle generator with advanced speaker diarization and emotion detection.
Transcribe all spoken dialogue in the provided audio file with exact start and end timestamps in seconds.

CRITICAL VERBATIM MANDATE - CAPTURE EVERY SINGLE SPOKEN WORD & INNER THOUGHT (ចាប់យកពាក្យគ្រប់ម៉ាត់ មិនឱ្យរំលងសូម្បីមួយម៉ាត់):
1. You MUST transcribe EVERY SINGLE WORD spoken by every character from beginning to end without skipping, summarizing, omitting, or paraphrasing anything.
2. STRICT CHARACTER DIALOGUE ISOLATION (កុំអោយជាន់ Segment តួអង្គផ្សេងនិយាយ):
   - When two or more characters converse, you MUST NEVER combine words spoken by different characters into the same segment!
   - Even if Character B replies immediately after Character A, output two distinct segments with separate timestamps.
   - Character dialogue must NEVER overlap or bleed into another character's segment.
3. MANDATORY PUNCTUATION & SENTENCE BOUNDARIES (ត្រូវដឹងថាមានខណ្ឌ មានឧទាន និងសញ្ញាសួរ):
   - Every statement MUST have clear, explicit sentence punctuation:
     * Full stops / declarative ends: Khmer Khan (ខណ្ឌ "។" ឬ "៕") or standard period (".").
     * Exclamations & urgent callouts: Exclamation marks (ឧទាន "!" ឬ "！").
     * Questions & inquiries: Question marks ("?" ឬ "？").
   - NEVER output unpunctuated run-on sentences. Every character thought must end with proper punctuation.
4. ISOLATE CALLOUTS, INTERJECTIONS, AND EXCLAMATIONS (បំបែកពាក្យឧទានអោយនៅដាច់ដោយឡែក):
   - Short exclamations, urgent calls, and interjections (e.g. "Stop!", "Wait!", "No!", "Help!", "Watch out!", "ឈប់!", "ប្រយ័ត្ន!", "អូ!", "អ្ហះ!", "ជួយផង!") MUST be isolated into their own standalone segment.
   - Assign appropriate emotion ("angry", "excited", or "terrified") and exact duration.
5. Capture all character utterances: complete sentences, short replies, rapid exchanges, interjections (e.g. "yes", "no", "wait", "oh", "listen", "stop", "អើ", "ហ្នឹង", "អ្ហះ"), quiet remarks, and overlapping dialogue.
3. MANDATORY - CAPTURE CHARACTER INNER THOUGHTS & INTERNAL MONOLOGUE (ចាប់យកសម្លេងតួអង្គនិយាយក្នុងចិត្ត / គិតក្នុងចិត្ត / Voiceover / Telepathy / Soliloquy):
   - In movies, anime, dramas, and video clips, characters frequently talk inside their own mind without moving their mouth (inner thoughts / soliloquy / telepathic speech / voiceovers / សម្លេងនិយាយក្នុងចិត្ត / គិតក្នុងចិត្ត).
   - This speech is often soft, whispered, or filtered with dramatic audio reverb/echo.
   - You MUST detect, capture, and transcribe EVERY SINGLE WORD of character inner thoughts with exact start and end timestamps, exactly like regular dialogue!
   - Attribute the inner thought to the character thinking ("Speaker 1", "Speaker 2", etc.), and assign emotion ("whisper", "neutral", or appropriate emotional delivery).
4. Distinguish between different characters/speakers by their voice pitch, tone, acoustic characteristics, gender, age, and dialogue interaction.
5. If only one person/narrator speaks throughout, label all segments consistently as "Speaker 1" (or "Narrator").
6. If two or more characters converse, label them consistently (e.g. "Speaker 1", "Speaker 2", "Speaker 3") and identify their character type (adult male, adult female, young boy, young girl).
7. Ensure the same character has the exact same speaker label for all their lines across the entire audio.
8. Assign "voice" accurately from this exact list:
   - "Khmer Male 01" for adult male characters / deeper voices.
   - "Khmer Female 01" for adult female characters / women voices.
   - "Khmer Boy 01" for young boys / male children / teenage boys.
   - "Khmer Girl 01" for young girls / female children / cute high-pitched voices.
9. Detect the emotional expression for each segment: assign "emotion" from this list:
   - "neutral" (normal conversation)
   - "whisper" (whispering, soft secret, quiet inner thought)
   - "angry" (shouting, angry, aggressive, yelling)
   - "sad" (crying, sorrowful, depressed, grieving)
   - "excited" (cheerful, overjoyed, joyful, laughing)
   - "terrified" (scared, panicked, fearful, screaming)
   - "romantic" (loving, intimate, sensual, affectionate)
10. Transcribe 100% verbatim in the original spoken language.
11. Do not include pure background silence or music in the speech timestamps, but capture all character speech and inner thoughts over music.
12. Output MUST be a strictly valid JSON array of objects with the exact schema:
[
  {
    "id": 1,
    "start": 0.0,
    "end": 3.2,
    "text": "transcribed speech",
    "speaker": "Speaker 1",
    "voice": "Khmer Male 01",
    "emotion": "neutral"
  }
]
No preamble, markdown formatting or commentary. Return ONLY the raw JSON array.
"""

    try:
        response = generate_content_with_retry_and_fallback(
            client=client,
            model_name=model_name,
            contents=[
                uploaded_file,
                "Transcribe all character spoken dialogue AND character inner thoughts in mind (សម្លេងតួអង្គនិយាយក្នុងចិត្ត / គិតក្នុងចិត្ត / internal monologue / voiceover) completely verbatim without skipping a single word (ចាប់យកពាក្យគ្រប់ម៉ាត់ពីតួអង្គនិយាយ មិនអោយរំលងសូម្បីមួយពាក្យ). "
                "Capture every word spoken or thought in mind by each character with precise start and end timestamps, speaker identification, and emotion in seconds as a JSON list."
            ],
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.1,
                response_mime_type="application/json"
            ),
            progress_callback=progress_callback
        )

        response_text = response.text.strip()
        if response_text.startswith("```"):
            response_text = re.sub(r"^```(?:json)?\s*", "", response_text)
            response_text = re.sub(r"\s*```$", "", response_text)

        segments = json.loads(response_text)
        
        # Normalize fields
        valid_voices = {"Khmer Male 01", "Khmer Female 01", "Khmer Boy 01", "Khmer Girl 01"}
        valid_emotions = {"neutral", "whisper", "angry", "sad", "excited", "terrified", "romantic"}
        normalized = []
        for idx, s in enumerate(segments, 1):
            spk = str(s.get("speaker") or f"Speaker {idx}")
            vce = s.get("voice")
            if not vce or vce not in valid_voices:
                spk_lower = spk.lower()
                if "girl" in spk_lower or "female child" in spk_lower or "daughter" in spk_lower:
                    vce = "Khmer Girl 01"
                elif "boy" in spk_lower or "male child" in spk_lower or "son" in spk_lower:
                    vce = "Khmer Boy 01"
                elif "female" in spk_lower or "woman" in spk_lower or "sreymom" in spk_lower or "speaker 2" in spk_lower:
                    vce = "Khmer Female 01"
                else:
                    vce = "Khmer Male 01"

            emo = str(s.get("emotion") or "neutral").strip().lower()
            if emo not in valid_emotions:
                emo = "neutral"

            normalized.append({
                "id": idx,
                "start": round(float(s.get("start", 0.0)), 2),
                "end": round(float(s.get("end", 1.0)), 2),
                "text": str(s.get("text", "")).strip(),
                "speaker": spk,
                "voice": vce,
                "emotion": emo
            })
        return merge_dialogue_fragments(normalized)

    except Exception as e:
        logger.error(f"Gemini STT error: {e}")
        raise e
    finally:
        # Cleanup uploaded file from Gemini storage
        try:
            client.files.delete(name=uploaded_file.name)
        except Exception:
            pass


def estimate_segment_pitch_and_centroid(clip, sr: int = 16000) -> Tuple[Optional[float], Optional[float]]:
    """
    Computes accurate median fundamental frequency F0 (pitch) and spectral centroid (timbre)
    for an audio segment, using parabolic interpolation and robust peak detection to prevent
    octave errors and spurious pitch drift.
    """
    import numpy as np
    import scipy.signal as sig

    if len(clip) < int(sr * 0.05):
        return None, None

    # Spectral centroid (timbre / brightness: male ~500-1600Hz, female/child ~2000-3800Hz)
    n_fft = min(len(clip), 1024)
    win_spec = np.hanning(n_fft)
    spec_frame = clip[:n_fft] * win_spec
    fft_vals = np.abs(np.fft.rfft(spec_frame, n=n_fft))
    freqs = np.fft.rfftfreq(n_fft, 1.0 / sr)
    sum_fft = float(np.sum(fft_vals))
    centroid = float(np.sum(freqs * fft_vals) / sum_fft) if sum_fft > 0 else 1500.0

    # Bandpass filter 60Hz - 500Hz to remove low-frequency rumble and high-frequency harmonics
    sos = sig.butter(4, [60.0, 500.0], 'bandpass', fs=sr, output='sos')
    filtered_clip = sig.sosfilt(sos, clip)

    frame_len = int(sr * 0.045)  # 45ms analysis frame
    hop_len = int(sr * 0.015)    # 15ms hop
    pitches = []

    min_lag = int(sr / 450)  # max ~450Hz (~35 samples at 16k)
    max_lag = int(sr / 65)   # min ~65Hz (~246 samples at 16k)
    window = np.hanning(frame_len)

    for i in range(0, len(filtered_clip) - frame_len, hop_len):
        frame = filtered_clip[i:i + frame_len]
        rms = float(np.sqrt(np.mean(frame ** 2)))
        if rms < 0.008:
            continue
        f_norm = (frame - np.mean(frame)) * window
        energy = np.sum(f_norm ** 2)
        if energy <= 1e-7:
            continue

        corr = sig.correlate(f_norm, f_norm, mode='full')
        corr = corr[len(corr) // 2:]
        if max_lag >= len(corr) or min_lag >= max_lag:
            continue

        corr_slice = corr[min_lag:max_lag]
        if corr[0] <= 0:
            continue

        peaks, _ = sig.find_peaks(corr_slice, height=0.22 * corr[0], distance=int(sr / 500))
        if len(peaks) == 0:
            continue

        peak_lags = peaks + min_lag
        peak_vals = [corr[l] for l in peak_lags]
        max_val_idx = np.argmax(peak_vals)
        best_lag = peak_lags[max_val_idx]
        best_val = peak_vals[max_val_idx]

        # In autocorrelation, fundamental F0 gives the FIRST prominent peak at lag T0 = sr / F0.
        # Higher lag multiples (2*T0, 3*T0) also produce peaks because periodic signals repeat every n*T0.
        # Check if an earlier peak exists at ~0.5x or ~0.33x lag with strong correlation (>= 0.50 of max)
        for pl, pv in zip(peak_lags, peak_vals):
            if pl < best_lag:
                ratio = best_lag / float(pl)
                if abs(ratio - round(ratio)) < 0.18 and round(ratio) in (2, 3, 4):
                    if pv >= 0.50 * best_val:
                        best_lag = pl
                        best_val = pv
                        break

        # Parabolic interpolation for sub-sample lag refinement
        if 0 < best_lag < len(corr) - 1:
            alpha = corr[best_lag - 1]
            beta = corr[best_lag]
            gamma = corr[best_lag + 1]
            denom = 2 * (alpha - 2 * beta + gamma)
            delta = (alpha - gamma) / denom if abs(denom) > 1e-7 else 0.0
            refined_lag = best_lag + delta
        else:
            refined_lag = float(best_lag)

        f0 = sr / refined_lag
        if 65 <= f0 <= 450:
            pitches.append(f0)

    median_f0 = float(np.median(pitches)) if len(pitches) >= 2 else (pitches[0] if len(pitches) == 1 else None)
    return median_f0, centroid


def _classify_single_pitch(f0: Optional[float], centroid: Optional[float] = None) -> Tuple[str, str]:
    """
    Classifies a single speaker's voice based on pitch (F0) and spectral centroid (timbre).
    Returns (speaker_label, voice_name).
    """
    if f0 is None:
        return "Speaker 1", "Khmer Male 01"
    
    # Adult male: typically 65 - 175 Hz (or low spectral centroid < 1700Hz)
    if f0 < 175.0 or (f0 < 195.0 and centroid is not None and centroid < 1700.0):
        return "Speaker 1", "Khmer Male 01"
    # Adult female: typically 175 - 245 Hz
    elif f0 < 245.0:
        return "Speaker 2", "Khmer Female 01"
    # Child boy: typically 200 - 320 Hz with lower spectral brightness
    elif f0 < 310.0:
        if centroid is not None and centroid >= 2650.0:
            return "Speaker 3 (Girl)", "Khmer Girl 01"
        return "Speaker 3 (Boy)", "Khmer Boy 01"
    # Child girl: typically > 310 Hz or bright high pitch
    else:
        return "Speaker 3 (Girl)", "Khmer Girl 01"


def _detect_segment_emotion(text: str, f0: Optional[float], base_f0: Optional[float], rms: Optional[float], avg_rms: Optional[float]) -> str:
    """
    Auto-detect character dialogue emotion based on acoustic dynamics and textual cues.
    """
    txt = (text or "").strip()
    
    # 1. Textual punctuation & semantic indicators
    if re.search(r"[!！]{2,}|(?:HELP|NOOO|STOP|AAAA|ARGH|RUN)", txt, re.IGNORECASE):
        if rms and avg_rms and rms > avg_rms * 1.30:
            return "angry"
        return "terrified"
    elif re.search(r"[!！]", txt):
        if f0 and base_f0 and f0 > base_f0 + 30:
            return "angry"
        return "excited"
    elif re.search(r"\b(?:sorry|cry|crying|sad|died|miss you|tears|rip)\b|[…\.]{3,}", txt, re.IGNORECASE):
        if rms and avg_rms and rms < avg_rms * 0.85:
            return "sad"
    elif re.search(r"\b(?:shh|whisper|quiet|secret|listen closely)\b", txt, re.IGNORECASE):
        return "whisper"
    elif re.search(r"\b(?:love|honey|darling|sweetheart|babe|kiss)\b", txt, re.IGNORECASE):
        return "romantic"
    elif re.search(r"\b(?:yay|wow|awesome|great|amazing|haha|lol)\b", txt, re.IGNORECASE):
        return "excited"

    # 2. Acoustic indicators
    if f0 is not None and base_f0 is not None and rms is not None and avg_rms is not None:
        pitch_diff = f0 - base_f0
        # High energy + High pitch -> Angry or Excited
        if rms > avg_rms * 1.40 and pitch_diff > 25:
            return "angry"
        elif rms > avg_rms * 1.20 and pitch_diff > 18:
            return "excited"
        # Very low energy + low pitch -> Whisper
        elif rms < avg_rms * 0.55:
            return "whisper"
        # Low energy + lower pitch -> Sad
        elif rms < avg_rms * 0.75 and pitch_diff < -12:
            return "sad"
        # High pitch with moderate energy -> Terrified
        elif pitch_diff > 40 and rms < avg_rms * 1.15:
            return "terrified"

    return "neutral"


def diarize_segments_with_audio(audio_path: str, segments: List[Dict]) -> List[Dict]:
    """
    Performs acoustic speaker diarization and emotion detection on dialogue segments.
    Distinguishes characters by pitch (F0), spectral voice timbre, and emotional prosody.
    Uses multi-feature clustering (F0, spectral centroid, spectral rolloff, formant energy ratios)
    and silhouette analysis for adaptive cluster discovery.
    """
    if not segments or not audio_path or not os.path.exists(audio_path):
        return segments

    try:
        import numpy as np
        import soundfile as sf
        from sklearn.cluster import KMeans
        from sklearn.metrics import silhouette_score

        audio_data, sr = sf.read(audio_path)
        if audio_data.ndim > 1:
            audio_data = np.mean(audio_data, axis=1)

        total_samples = len(audio_data)

        features = []
        for s in segments:
            start_s = max(0.0, float(s.get("start", 0.0)))
            end_s = min(float(total_samples) / sr, float(s.get("end", start_s + 1.0)))
            start_idx = int(start_s * sr)
            end_idx = int(end_s * sr)

            if end_idx > start_idx:
                clip = audio_data[start_idx:end_idx]
                f0, centroid = estimate_segment_pitch_and_centroid(clip, sr)
                rms = float(np.sqrt(np.mean(clip ** 2))) if len(clip) > 0 else 0.0

                # Formant energy ratio in 100-1200Hz vs 1200-5000Hz (vocal tract shape)
                n_fft = min(len(clip), 1024)
                if n_fft >= 64:
                    win = np.hanning(n_fft)
                    fft_p = np.abs(np.fft.rfft(clip[:n_fft] * win, n=n_fft)) ** 2
                    frq = np.fft.rfftfreq(n_fft, 1.0 / sr)
                    low_e = float(np.sum(fft_p[(frq >= 100) & (frq < 1200)]))
                    high_e = float(np.sum(fft_p[(frq >= 1200) & (frq < 5000)]))
                    tot_e = max(1e-9, low_e + high_e)
                    formant_ratio = high_e / tot_e
                else:
                    formant_ratio = 0.3
            else:
                f0, centroid, rms, formant_ratio = None, None, 0.0, 0.3

            features.append((f0, centroid, rms, formant_ratio))

        # Collect valid voiced segments
        valid_f0s = [f0 for f0, _, _, _ in features if f0 is not None]
        valid_centroids = [c for _, c, _, _ in features if c is not None]
        valid_rms = [r for _, _, r, _ in features if r > 0]
        avg_rms = float(np.mean(valid_rms)) if valid_rms else 0.05
        avg_base_f0 = float(np.median(valid_f0s)) if valid_f0s else 140.0

        # Case 1: Insufficient audio evidence or very consistent single speaker
        f0_std = float(np.std(valid_f0s)) if len(valid_f0s) >= 3 else 0.0
        f0_range = float(max(valid_f0s) - min(valid_f0s)) if len(valid_f0s) >= 2 else 0.0

        # If exactly 2 segments with distinct pitch (range >= 40Hz), classify each directly
        if len(segments) == 2 and len(valid_f0s) == 2 and f0_range >= 40.0:
            for i, s in enumerate(segments):
                f0_val = features[i][0]
                cent_val = features[i][1]
                rms_val = features[i][2]
                spk, vce = _classify_single_pitch(f0_val, cent_val)
                s["speaker"] = spk
                s["voice"] = vce
                if not s.get("emotion") or s.get("emotion") == "neutral":
                    s["emotion"] = _detect_segment_emotion(s.get("text", ""), f0_val, f0_val, rms_val, avg_rms)
            # If both received Speaker 1 due to same category, make second Speaker 2
            if segments[0]["speaker"] == segments[1]["speaker"]:
                segments[1]["speaker"] = "Speaker 2"
            return segments

        if len(valid_f0s) < 2 or (f0_std < 24.0 and f0_range < 40.0):
            # Single speaker / narrator — assign based on median pitch & timbre
            median_pitch = float(np.median(valid_f0s)) if valid_f0s else 140.0
            median_centroid = float(np.median(valid_centroids)) if valid_centroids else None
            spk, vce = _classify_single_pitch(median_pitch, median_centroid)
            for i, s in enumerate(segments):
                s["speaker"] = spk
                s["voice"] = vce
                if not s.get("emotion") or s.get("emotion") == "neutral":
                    f0_val = features[i][0]
                    rms_val = features[i][2]
                    s["emotion"] = _detect_segment_emotion(s.get("text", ""), f0_val, median_pitch, rms_val, avg_rms)
            return segments

        # Case 2: Multi-character dialogue — build normalized feature space
        avg_f0 = float(np.mean(valid_f0s))
        avg_c = float(np.mean(valid_centroids)) if valid_centroids else 2000.0

        feat_matrix = []
        for f0, c, _, f_ratio in features:
            f0_val = f0 if f0 is not None else avg_f0
            c_val = c if c is not None else avg_c
            # Normalized features: pitch (weighted 2.5x), spectral centroid (1.0x), formant brightness (0.8x)
            feat_matrix.append([
                (f0_val / 100.0) * 2.5,
                (c_val / 1000.0),
                f_ratio * 0.8
            ])

        feat_arr = np.array(feat_matrix)

        # Adaptive cluster count selection (2 or 3) via Silhouette analysis
        n_distinct = 2
        km2 = KMeans(n_clusters=2, n_init=10, random_state=42)
        lbl2 = km2.fit_predict(feat_arr)
        labels = lbl2

        if len(valid_f0s) >= 7 and f0_range >= 65.0:
            km3 = KMeans(n_clusters=3, n_init=10, random_state=42)
            lbl3 = km3.fit_predict(feat_arr)
            c_sizes = [int(np.sum(lbl3 == k)) for k in range(3)]
            if min(c_sizes) >= 2:
                try:
                    s2 = silhouette_score(feat_arr, lbl2)
                    s3 = silhouette_score(feat_arr, lbl3)
                    if s3 > s2 * 0.88 and s3 > 0.35:
                        n_distinct = 3
                        labels = lbl3
                except Exception:
                    pass

        # Compute mean F0 and centroid per cluster
        cluster_mean_f0 = {}
        cluster_mean_centroid = {}
        for k in range(n_distinct):
            cluster_f0s = [features[i][0] for i, lbl in enumerate(labels) if lbl == k and features[i][0] is not None]
            cluster_centroids = [features[i][1] for i, lbl in enumerate(labels) if lbl == k and features[i][1] is not None]
            cluster_mean_f0[k] = float(np.mean(cluster_f0s)) if cluster_f0s else avg_f0
            cluster_mean_centroid[k] = float(np.mean(cluster_centroids)) if cluster_centroids else avg_c

        # Sort clusters by ascending mean F0 -> lowest pitch to highest
        sorted_clusters = sorted(cluster_mean_f0.keys(), key=lambda k: cluster_mean_f0[k])

        # Assign voice labels by pitch rank & acoustic characteristics
        mapping = {}
        if len(sorted_clusters) == 1:
            c0 = sorted_clusters[0]
            f0_0 = cluster_mean_f0.get(c0, 140.0)
            mapping[c0] = ("Speaker 1", "Khmer Male 01") if f0_0 < 175.0 else ("Speaker 2", "Khmer Female 01")
        elif len(sorted_clusters) == 2:
            c0, c1 = sorted_clusters[0], sorted_clusters[1]
            f0_0, f0_1 = cluster_mean_f0[c0], cluster_mean_f0[c1]
            cent_1 = cluster_mean_centroid.get(c1, 2000.0)

            if f0_0 < 175.0 or (f0_0 < 195.0 and cluster_mean_centroid.get(c0, 1500.0) < 1700.0):
                mapping[c0] = ("Speaker 1", "Khmer Male 01")
                if f0_1 >= 245.0:
                    if cent_1 >= 2650.0:
                        mapping[c1] = ("Speaker 3 (Girl)", "Khmer Girl 01")
                    else:
                        mapping[c1] = ("Speaker 3 (Boy)", "Khmer Boy 01")
                elif f0_1 >= 175.0:
                    mapping[c1] = ("Speaker 2", "Khmer Female 01")
                else:
                    # Both clusters are male: assign Speaker 1 and Speaker 2 with male voice
                    mapping[c1] = ("Speaker 2", "Khmer Male 01")
            else:
                # Both clusters are higher pitch (female/child)
                mapping[c0] = ("Speaker 1", "Khmer Female 01")
                if f0_1 >= 250.0:
                    mapping[c1] = ("Speaker 3 (Girl)", "Khmer Girl 01")
                else:
                    mapping[c1] = ("Speaker 2", "Khmer Female 01")
        else:  # >= 3 distinct clusters
            c0 = sorted_clusters[0]
            c1 = sorted_clusters[1]
            c2 = sorted_clusters[2]
            cent_2 = cluster_mean_centroid.get(c2, 2000.0)
            f0_2 = cluster_mean_f0.get(c2, 250.0)

            mapping[c0] = ("Speaker 1", "Khmer Male 01")
            mapping[c1] = ("Speaker 2", "Khmer Female 01")
            if cent_2 >= 2650.0 or f0_2 >= 300.0:
                mapping[c2] = ("Speaker 3 (Girl)", "Khmer Girl 01")
            else:
                mapping[c2] = ("Speaker 3 (Boy)", "Khmer Boy 01")
            for extra_idx in range(3, len(sorted_clusters)):
                ck = sorted_clusters[extra_idx]
                mapping[ck] = ("Speaker 3 (Girl)", "Khmer Girl 01") if cluster_mean_f0.get(ck, 250.0) >= 270.0 else ("Speaker 2", "Khmer Female 01")

        # Apply mapped speaker, voice, and auto emotion labels
        for i, s in enumerate(segments):
            spk, vce = mapping[labels[i]]
            s["speaker"] = spk
            s["voice"] = vce
            if not s.get("emotion") or s.get("emotion") == "neutral":
                cluster_base_f0 = cluster_mean_f0.get(labels[i], avg_base_f0)
                f0_val = features[i][0]
                rms_val = features[i][2]
                s["emotion"] = _detect_segment_emotion(s.get("text", ""), f0_val, cluster_base_f0, rms_val, avg_rms)

        # Temporal smoothing — two-pass: eliminate 1-segment spurious flickers
        for _ in range(2):
            for i in range(1, len(segments) - 1):
                prev_s = segments[i - 1]["speaker"]
                next_s = segments[i + 1]["speaker"]
                curr_dur = float(segments[i].get("end", 0)) - float(segments[i].get("start", 0))
                # Smooth isolated flip if neighbours agree AND segment is short (<1.6s)
                if prev_s == next_s and segments[i]["speaker"] != prev_s and curr_dur < 1.6:
                    segments[i]["speaker"] = prev_s
                    segments[i]["voice"] = segments[i - 1]["voice"]

        return segments

    except Exception as e:
        logger.warning(f"Acoustic speaker diarization error: {e}. Keeping default speaker labels.")
        return segments


def fit_segments_to_audio_duration(segments: List[Dict], total_duration: float) -> List[Dict]:
    """
    Ensures all transcribed segments are strictly bounded within [0.0, total_duration],
    non-colliding, and properly timed so no segment gets pushed beyond the video/audio length.
    Only the actual last segment gets tail-rebalancing (expanded back to guarantee enough
    speech room before the video ends). All other segments are simply clamped in-place.
    """
    if not segments or not total_duration or total_duration <= 0:
        return segments

    # Sort segments by start time
    sorted_segs = sorted(segments, key=lambda s: float(s.get("start", 0.0)))
    n = len(sorted_segs)
    if n == 0:
        return []

    min_gap = 0.05
    cleaned = []

    for i, s in enumerate(sorted_segs):
        copy_s = dict(s)
        raw_start = max(0.0, float(copy_s.get("start", 0.0)))
        raw_end = float(copy_s.get("end", raw_start + 1.0))
        if raw_end <= raw_start:
            raw_end = raw_start + 1.0

        start = round(raw_start, 2)
        end = round(max(start + 0.25, raw_end), 2)

        is_last = (i == n - 1)

        if is_last:
            # Only the true last segment gets tail rebalancing so it has ample speech room
            words = len(str(copy_s.get("text", "")).split())
            speech_room_needed = max(2.2, min(words * 0.45, 4.0)) if words >= 3 else 1.2
            end = round(total_duration, 2)
            # Pull start back only if the segment would be too short
            if (end - start) < speech_room_needed:
                start = round(max(0.0, total_duration - speech_room_needed), 2)
        else:
            # Non-last segments: clamp end to total_duration, never relocate
            end = round(min(end, total_duration), 2)
            start = round(min(start, max(0.0, end - 0.25)), 2)

        # Collision resolution with previous segment
        if cleaned:
            prev = cleaned[-1]
            if start < prev["end"]:
                # Trim previous segment end rather than pushing this one forward
                prev["end"] = max(prev["start"] + 0.25, round(start - min_gap, 2))
                # Sync prev duration if present
                if "duration" in prev:
                    prev["duration"] = round(prev["end"] - prev["start"], 2)
                start = round(prev["end"] + min_gap, 2)

        copy_s["start"] = start
        copy_s["end"] = end
        if "duration" in copy_s:
            copy_s["duration"] = round(end - start, 2)
        cleaned.append(copy_s)

    # Final pass: strictly clamp to [0, total_duration] and re-index
    for i, c in enumerate(cleaned):
        c["end"] = round(min(c["end"], total_duration), 2)
        c["start"] = round(min(max(0.0, c["start"]), max(0.0, c["end"] - 0.2)), 2)
        if "duration" in c:
            c["duration"] = round(c["end"] - c["start"], 2)
        c["id"] = i + 1

    return cleaned


def transcribe_audio(
    audio_path: str,
    engine: str = "whisper",
    model_name: Optional[str] = None,
    language: Optional[str] = None,
    voice: Optional[str] = "auto",
    api_key: Optional[str] = None,
    progress_callback: Optional[Callable[[str], None]] = None
) -> List[Dict]:
    """
    Unified STT function routing to Whisper, SenseVoiceSmall, or Gemini.
    If voice == 'auto', runs automated acoustic character speaker diarization.
    If a specific voice is selected (e.g. Male/Female/Boy/Girl), assigns only that chosen voice.
    """
    engine_lower = engine.lower()

    # Pre-process audio with highpass filter + dynamic normalization to boost faint or whispery speech
    stt_audio = prepare_speech_enhanced_audio(audio_path)

    if engine_lower == "whisper":
        size = "small" if not model_name or model_name.lower() in ("auto", "default") else model_name
        segs = transcribe_with_whisper(stt_audio, model_size=size, language=language, progress_callback=progress_callback)
        
    elif engine_lower == "sensevoice":
        m_name = model_name or "iic/SenseVoiceSmall"
        segs = transcribe_with_sensevoice(stt_audio, model_name=m_name, language=language, progress_callback=progress_callback)
        
    elif engine_lower == "gemini":
        g_model = "gemini-3.5-flash" if not model_name or str(model_name).lower() in ("auto", "default", "auto_detect") else model_name
        segs = transcribe_with_gemini(stt_audio, api_key=api_key, model_name=g_model, progress_callback=progress_callback)
        
    else:
        raise ValueError(f"Unsupported STT engine: {engine}. Choose from 'whisper', 'sensevoice', 'gemini'.")

    # If user explicitly selected a single voice (e.g. Male / Female / Boy / Girl), assign that voice to all segments
    voice_str = (voice or "auto").strip().lower()
    if voice_str not in ("auto", "none", ""):
        # Determine normalized voice and speaker
        if "girl" in voice_str or "sreymomneural-girl" in voice_str:
            chosen_voice = "Khmer Girl 01"
            chosen_spk = "Speaker 3 (Girl)"
        elif "boy" in voice_str or "pisethneural-boy" in voice_str:
            chosen_voice = "Khmer Boy 01"
            chosen_spk = "Speaker 3 (Boy)"
        elif "female" in voice_str or "sreymom" in voice_str:
            chosen_voice = "Khmer Female 01"
            chosen_spk = "Speaker 2"
        else:
            chosen_voice = "Khmer Male 01"
            chosen_spk = "Speaker 1"

        for s in segs:
            s["voice"] = chosen_voice
            s["speaker"] = chosen_spk

    # Otherwise (Auto Detect mode): Run acoustic speaker diarization on segments
    elif segs and audio_path and os.path.exists(audio_path):
        if progress_callback:
            progress_callback("Analyzing character voice pitch and assigning speakers...")
        segs = diarize_segments_with_audio(audio_path, segs)

    # Strictly fit segment timelines to total audio length so timestamps never exceed video duration
    if segs and audio_path and os.path.exists(audio_path):
        try:
            from .audio_video_processor import get_audio_duration
            total_dur = get_audio_duration(audio_path)
            if total_dur and total_dur > 0:
                segs = fit_segments_to_audio_duration(segs, total_dur)
        except Exception as e:
            logger.warning(f"Failed to fit segment timestamps to audio duration: {e}")

    return segs

