import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from google import genai
from google.genai import types

from .config import BASE_DIR, DATA_DIR, DEFAULT_GEMINI_API_KEY, FFMPEG_PATH, TEMP_DIR
from .translation_engine import extract_and_parse_json, generate_content_with_retry_and_fallback, get_gemini_client

logger = logging.getLogger("recap_engine")
logger.setLevel(logging.INFO)

BGM_DIR = DATA_DIR / "bgm"
BGM_DIR.mkdir(parents=True, exist_ok=True)

RECAP_STYLES = {
    "youtube": {
        "id": "youtube",
        "name": "សម្រាយរឿងតាម YouTube (YouTube Movie Recap Master)",
        "tone_instruction": (
            "Tone: The quintessential viral Cambodian YouTube Movie Recap tone (like Mr. Recap / Khmer Movie Recap). "
            "Professional, captivating, suspenseful, and smooth storytelling. "
            "Use signature recapper phrases: 'សូមស្វាគមន៍មកកាន់ការសម្រាយសាច់រឿង...', "
            "'រឿងរ៉ាវបានចាប់ផ្ដើមឡើងនៅពេលដែល...', 'ស្របពេលនោះដែរ...', 'ស្រាប់តែអ្វីដែលនឹកស្មានមិនដល់នោះគឺ...', "
            "'គាត់មិនបានដឹងខ្លួនទាល់តែសោះថា...', 'ចំណែកឯតួអង្គរបស់យើងវិញ...', 'ភ្លាមៗនោះ...', "
            "'តើប្រិយមិត្តយល់យ៉ាងណាដែរចំពោះរឿងនេះ? កុំភ្លេច Like និង Subscribe ម្នាក់មួយផងណា៎!'."
        )
    },
    "suspense": {
        "id": "suspense",
        "name": "អាថ៌កំបាំង / ភ័យរន្ធត់ (Suspense & Mystery)",
        "tone_instruction": (
            "Tone: Suspenseful, mysterious, dramatic, and dark. "
            "Use deep, intense vocabulary that builds curiosity and dread. "
            "Frequently use phrases like 'ប៉ុន្តែអ្វីដែលមិននឹកស្មានដល់...', 'រឿងរ៉ាវកាន់តែអាថ៌កំបាំងនៅពេល...', 'តើមានអ្វីលាក់កំបាំងនៅពីក្រោយ?'."
        )
    },
    "humorous": {
        "id": "humorous",
        "name": "កំប្លែង / បាញ់ៗ (Humorous & Sarcastic)",
        "tone_instruction": (
            "Tone: Funny, witty, sarcastic, lighthearted, and trendy Cambodian internet slang. "
            "Make fun of silly character decisions in an entertaining way. "
            "Use colloquial catchphrases like 'នែ កុំចេះតែថា!', 'មើលទៅដូចមិនស្រួលទេ', 'អែមហ្មងហើយលើកនេះ'."
        )
    },
    "action": {
        "id": "action",
        "name": "សកម្មភាព / កាប់ចាក់ (Action & Hype)",
        "tone_instruction": (
            "Tone: Energetic, fast-paced, hype, adrenaline-fueled, and epic. "
            "Highlight power, speed, tactics, and intense confrontations. "
            "Keep sentences punchy and dynamic, conveying urgency and excitement."
        )
    },
    "drama": {
        "id": "drama",
        "name": "កម្សត់ / ស្នេហា (Drama & Emotional)",
        "tone_instruction": (
            "Tone: Emotional, poignant, sympathetic, reflective, and touching. "
            "Focus on character heartaches, struggles, sacrifice, and deep feelings. "
            "Use warm and tender Khmer phrasing that evokes empathy."
        )
    }
}

RECAP_SYSTEM_INSTRUCTION = """
You are Cambodia's #1 Master YouTube Movie Recap Narrator (អ្នកសម្រាយរឿងអាជីពប្រចាំ YouTube និង TikTok កម្ពុជា ដូចជា Mr. Recap / Khmer Movie Recap).
Your channel has millions of views because you tell stories with DRAMA, SUSPENSE, INTRIGUE, and NATURAL KHMER PHRASING that keeps viewers glued to the screen.

YOUR SIGNATURE RECAP STYLE (ស្ទីលសម្រាយរឿងកុនតាម YouTube កម្ពុជា):
1. ENGAGING STORYTELLER VOICE + AUTHENTIC CHARACTER DIALOGUE (HYBRID MODE):
   - You must deliver a dynamic HYBRID balance between:
     A) CLEAR STORY EXPLANATION (ពន្យល់សាច់រឿងឱ្យយល់ច្បាស់):
        The Narrator ('speaker': 'Narrator') explains what is happening, character motives, hidden secrets, backstory, and consequences using authentic Cambodian recapper phrases:
        * "រឿងរ៉ាវបានចាប់ផ្ដើមឡើងនៅពេលដែល..." (The story begins when...)
        * "ស្របពេលនោះដែរ..." (Meanwhile...)
        * "ស្រាប់តែអ្វីដែលនឹកស្មានមិនដល់នោះគឺ..." (Suddenly, the unexpected happened...)
        * "គាត់មិនបានដឹងខ្លួនទាល់តែសោះថា..." (He had no clue that...)
        * "ចំណែកឯតួអង្គរបស់យើងវិញ..." (As for our protagonist...)
        * "ភ្លាមៗនោះ គ្រោះថ្នាក់ដ៏ធំមួយបានកើតឡើង..." (Instantly, grave danger struck...)
        * "មិនបង្អង់យូរ..." (Without hesitation...)
        * "តើប្រិយមិត្តយល់យ៉ាងណាដែរចំពោះរឿងនេះ? កុំភ្លេច Like និង Subscribe ម្នាក់មួយផងណា៎!" (Ending CTA)
     B) POWERFUL CHARACTER DIALOGUE MOMENTS (កន្លែងតួអង្គនិយាយផ្ទាល់):
        In key dramatic, climactic, argumentative, emotional, or funny moments, let the character speak their authentic dialogue directly!
        * Set 'speaker': 'Speaker 1' (for Male character) or 'Speaker 2' (for Female character).
        * Set 'tag': 'dialogue'.
        * Set 'emotion': matching emotion (e.g. 'angry', 'terrified', 'sad', 'romantic', 'sarcastic', 'excited', 'neutral').
     - Seamless Flow: Narrator explains the situation -> Character delivers punchy line -> Narrator explains the aftermath and keeps the story moving!

2. SMART WORD-PER-SECOND BUDGET (គណនាប្រវែងពាក្យខ្មែរតាមវិនាទី):
   - Natural Khmer movie recap speech rate is strictly 2.5 to 3.0 Khmer words per second (at 1.15x speed).
   - For a 3-second slot: strictly 7 to 9 Khmer words.
   - For a 5-second slot: strictly 12 to 15 Khmer words.
   - For a 7-second slot: strictly 17 to 21 Khmer words.
   - NEVER write more words than the slot allows so the narrator's voice fits cleanly without rushing or getting cut off.

3. 100% FAITHFUL TO THE ORIGINAL FOOTAGE:
   - Analyze the provided audio/video track and dialogue timeline. Recap the ACTUAL events, characters, actions, and emotions shown in the video.

4. TIMELINE & COHESION:
   - The narration across all scenes must form one seamless, continuous story flow.
   - Scene 1 hooks the viewer. Middle scenes build tension and conflict. The final scene delivers the climax/cliffhanger and smooth YouTube ending.

STRICT JSON OUTPUT SCHEMA:
Output ONLY a valid JSON array of objects:
[
  {
    "id": 1,
    "start": 0.0,
    "end": 4.8,
    "speaker": "Narrator",
    "voice": "km-KH-PisethNeural",
    "emotion": "suspense",
    "tag": "hook",
    "text": "The story begins with a mysterious break-in.",
    "khmer_text": "រឿងរ៉ាវបានចាប់ផ្ដើមឡើងនៅពេលដែលបុរសម្នាក់នេះ កំពុងតែព្យាយាមលួចចូលផ្ទះអាថ៌កំបាំងមួយ..."
  },
  {
    "id": 2,
    "start": 5.0,
    "end": 8.0,
    "speaker": "Speaker 1",
    "voice": "km-KH-PisethNeural",
    "emotion": "angry",
    "tag": "dialogue",
    "text": "Who are you?! Get out of my house right now!",
    "khmer_text": "ឯងជាអ្នកណា?! ចេញពីផ្ទះរបស់ខ្ញុំភ្លាមទៅ!"
  },
  {
    "id": 3,
    "start": 8.2,
    "end": 13.0,
    "speaker": "Narrator",
    "voice": "km-KH-PisethNeural",
    "emotion": "neutral",
    "tag": "story",
    "text": "Hearing this shout, our protagonist immediately tried to explain.",
    "khmer_text": "ឮសំឡេងស្រែកសួរគំរាមបែបនេះ តួអង្គយើងក៏ប្រញាប់លើកដៃបកស្រាយថា..."
  }
]
No markdown formatting, code blocks, or extra text. Output ONLY the raw JSON array.
"""


def fit_recap_segments_to_duration(
    segments: List[Dict],
    total_duration: float,
    min_pause: float = 0.25,
    narrator_voice: str = "km-KH-PisethNeural"
) -> List[Dict]:
    """
    Distributes all recap segments evenly across [0.0, total_duration - 0.25s].
    Preserves all input segments with equal time allocation, character speakers,
    emotions, and natural breathing gaps so timestamps never collide.
    """
    if not segments:
        return []

    dur = max(5.0, float(total_duration))
    max_end_time = round(dur - 0.25, 2)
    if max_end_time <= 2.0:
        max_end_time = dur

    num_segs = len(segments)

    # Distribute all N segments evenly across the duration
    slot_len = max_end_time / num_segs
    pause = min(min_pause, max(0.12, slot_len * 0.08))
    speech_dur = slot_len - pause

    formatted = []
    for idx, s in enumerate(segments):
        start = round(idx * slot_len, 2)
        end = round(min(max_end_time, start + speech_dur), 2)
        if idx == num_segs - 1:
            end = max_end_time

        txt = s.get("khmer_text", "").strip() or s.get("text", "").strip()
        speaker_val = s.get("speaker") or "Narrator"
        emotion_val = s.get("emotion") or "neutral"

        # Resolve voice according to speaker role
        voice_val = s.get("voice")
        if not voice_val:
            speaker_lower = speaker_val.lower()
            if speaker_val == "Speaker 2" or "female" in speaker_lower or "girl" in speaker_lower:
                voice_val = "km-KH-SreymomNeural"
            elif "boy" in speaker_lower:
                voice_val = "km-KH-PisethNeural-Boy"
            elif speaker_val == "Narrator":
                voice_val = narrator_voice or "km-KH-PisethNeural"
            else:
                voice_val = "km-KH-PisethNeural"

        formatted.append({
            "id": idx + 1,
            "start": start,
            "end": end,
            "text": s.get("text", "").strip() or f"Scene #{idx + 1}",
            "khmer_text": txt,
            "tag": s.get("tag", "story"),
            "speaker": speaker_val,
            "voice": voice_val,
            "emotion": emotion_val,
            "status": "Ready"
        })

    return formatted


def upload_media_to_gemini(client, media_path: str, progress_callback: Optional[Callable[[str], None]] = None) -> Optional[Any]:
    """
    Uploads audio or video file to Gemini Files API and waits until ACTIVE.
    """
    if not media_path or not os.path.exists(media_path) or os.path.getsize(media_path) < 500:
        return None

    file_size_mb = os.path.getsize(media_path) / (1024 * 1024)
    logger.info(f"Uploading media to Gemini: {media_path} ({file_size_mb:.2f} MB)...")
    if progress_callback:
        progress_callback(f"Uploading original media ({file_size_mb:.1f}MB) to Gemini for accurate story analysis...")

    uploaded = client.files.upload(file=media_path)
    logger.info(f"Uploaded file to Gemini: {uploaded.name}, state: {getattr(uploaded, 'state', None)}")

    # Poll until file is ACTIVE (especially for video)
    for _ in range(40):
        state_name = getattr(uploaded.state, "name", None) if hasattr(uploaded, "state") and uploaded.state else None
        if state_name == "PROCESSING":
            time.sleep(1.0)
            try:
                uploaded = client.files.get(name=uploaded.name)
            except Exception:
                break
        elif state_name in ("FAILED", "ERROR"):
            logger.warning(f"Gemini media processing failed: {getattr(uploaded, 'error', 'unknown error')}")
            return None
        else:
            break

    return uploaded


def generate_recap_script(
    segments: List[Dict],
    total_duration: float,
    audio_path: Optional[str] = None,
    video_path: Optional[str] = None,
    style: str = "suspense",
    include_hook: bool = True,
    include_cta: bool = True,
    pacing: str = "normal",
    hybrid_dialogue: bool = True,
    narrator_voice: str = "km-KH-PisethNeural",
    api_key: Optional[str] = None,
    model_name: str = "gemini-3.5-flash",
    progress_callback: Optional[Callable[[str], None]] = None
) -> List[Dict]:
    """
    Transforms transcript dialogue segments into an engaging third-person Khmer movie recap script.
    Guarantees strict fitting within total_duration while preserving all scene segments equally.
    Uploads original video / audio to Gemini for 100% faithful plot analysis.
    Supports Smart Word Budget (2.5-3.0 words/s) and Hybrid Narrator + Character Dialogue.
    """
    client = get_gemini_client(api_key)
    
    style_info = RECAP_STYLES.get(style, RECAP_STYLES["youtube"])
    style_prompt = style_info["tone_instruction"]

    transcript_summary = []
    for s in segments:
        t_str = s.get("text", "").strip() or s.get("khmer_text", "").strip()
        if t_str:
            transcript_summary.append(f"[{s.get('start', 0.0):.1f}s - {s.get('end', 0.0):.1f}s]: {t_str}")

    transcript_corpus = "\n".join(transcript_summary) if transcript_summary else "Visual scene without dialogue."
    dur = max(5.0, float(total_duration))

    # In YouTube movie recaps, each narrative beat/scene is ideally 4.5s to 7.0s
    # so the narrator can deliver rich, continuous storytelling without being chopped into 1-second fragments.
    if segments and 2 <= len(segments) <= 10 and (dur / len(segments)) >= 3.8:
        target_segments = len(segments)
    else:
        ideal_scene_len = 5.2
        target_segments = max(2, min(14, round(dur / ideal_scene_len)))

    slot_len = dur / max(1, target_segments)
    min_words_per_seg = max(6, int(slot_len * 2.3))
    max_words_per_seg = max(8, min(24, int(slot_len * 2.9)))

    user_instructions = [
        f"TOTAL VIDEO DURATION: EXACTLY {dur:.1f} SECONDS (STRICT HARD LIMIT).",
        f"TARGET SEGMENT COUNT: GENERATE EXACTLY {target_segments} SEGMENTS (one corresponding to each scene).",
        f"TIMESTAMPS: Segment 1 starts at 0.0s. The last segment MUST end at or before {dur - 0.3:.1f}s.",
        f"SMART WORD BUDGET: Each scene slot is approximately {slot_len:.1f}s. Write strictly between {min_words_per_seg} and {max_words_per_seg} Khmer words per scene (~2.5 - 2.8 words/sec). NEVER exceed this word budget.",
        f"Selected Narrative Style: {style_info['name']}.",
        f"Style Guidance: {style_prompt}",
    ]

    if hybrid_dialogue:
        user_instructions.append(
            "- HYBRID MODE ACTIVE (ពន្យល់សាច់រឿង + ទុកឱ្យតួអង្គនិយាយ): "
            "For segments explaining context, backstory, or thoughts, set 'speaker': 'Narrator' and 'tag': 'story'. "
            "For important dramatic, emotional, climactic, or funny lines, let the character speak directly with 'speaker': 'Speaker 1' (Male) or 'Speaker 2' (Female), 'tag': 'dialogue', and set appropriate 'emotion'."
        )

    if include_hook:
        user_instructions.append(
            "- Opening Hook: The very first segment MUST be a thrilling, short curiosity-inducing hook sentence tagged with 'tag': 'hook'."
        )
    if include_cta:
        user_instructions.append(
            "- Ending Call to Action: The final segment must be a smooth recap ending (e.g. 'តើអ្នកគិតយ៉ាងណាដែរ?') tagged with 'tag': 'cta'."
        )

    if pacing == "fast":
        user_instructions.append(
            "- Pacing: Fast-paced TikTok / Reels format (1.2x). Short punchy lines."
        )
    else:
        user_instructions.append(
            "- Pacing: Cinematic storytelling pacing, allowing moments for dramatic pauses."
        )

    user_prompt = (
        f"You are analyzing the ORIGINAL VIDEO / AUDIO of this scene.\n"
        f"YOUR PRIMARY DIRECTIVE: The recap narration MUST BE 100% FAITHFUL TO THE ACTUAL STORY of this original video. "
        f"Listen to the audio and examine the dialogue/sound timeline. Summarize the REAL events, characters, conflict, and actions happening in the video.\n\n"
        f"ACTUAL VIDEO CONTEXT & DIALOGUE TIMELINE:\n{transcript_corpus}\n\n"
        f"STRICT REQUIREMENTS:\n" + "\n".join(user_instructions) + "\n\n"
        f"CRITICAL RULES:\n"
        f"1. Summarize the REAL video content across the {target_segments} scenes. Do NOT invent a fake story.\n"
        f"2. For each scene, the 'text' field MUST be a brief description or dialogue of what actually happens in that scene.\n"
        f"3. The 'khmer_text' field MUST be the Khmer narration or character dialogue for that scene.\n"
        f"4. The entire script MUST finish before {dur:.1f}s. Return ONLY the JSON array."
    )

    uploaded_media = None
    contents = []

    # 1. Prefer uploading video file if <= 45MB so Gemini SEES and HEARS everything
    if video_path and os.path.exists(video_path) and os.path.getsize(video_path) <= 45 * 1024 * 1024:
        try:
            uploaded_media = upload_media_to_gemini(client, video_path, progress_callback)
        except Exception as vid_err:
            logger.warning(f"Could not upload video to Gemini, falling back to audio: {vid_err}")

    # 2. If video was not uploaded, upload the extracted 16kHz audio track
    if not uploaded_media and audio_path and os.path.exists(audio_path) and os.path.getsize(audio_path) > 1000:
        try:
            uploaded_media = upload_media_to_gemini(client, audio_path, progress_callback)
        except Exception as aud_err:
            logger.warning(f"Could not upload audio to Gemini: {aud_err}")

    if uploaded_media:
        contents.append(uploaded_media)

    contents.append(user_prompt)

    if progress_callback:
        progress_callback(f"Generating Khmer Recap script ({style}) with Gemini...")

    try:
        response = generate_content_with_retry_and_fallback(
            client=client,
            model_name=model_name,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=RECAP_SYSTEM_INSTRUCTION,
                temperature=0.35,
                response_mime_type="application/json"
            ),
            progress_callback=progress_callback
        )

        response_text = response.text.strip()
        recap_segments = extract_and_parse_json(response_text)

        # Strictly fit and clamp segments within total_duration
        formatted = fit_recap_segments_to_duration(recap_segments, dur, min_pause=0.25, narrator_voice=narrator_voice)
        return formatted

    except Exception as e:
        logger.error(f"Failed to generate recap script: {e}")
        fallback = []
        for idx, s in enumerate(segments):
            text = s.get("khmer_text", "") or s.get("text", "")
            fallback.append({
                "id": idx + 1,
                "text": text or f"Scene #{idx + 1}",
                "khmer_text": f"នៅត្រង់នេះ {text}" if text else "សាច់រឿងបន្ត...",
                "tag": "story",
                "speaker": "Narrator",
                "voice": "km-KH-PisethNeural",
                "status": "Ready"
            })
        if not fallback:
            fallback = [{
                "id": 1,
                "text": "Scene #1",
                "khmer_text": "សូមស្វាគមន៍មកកាន់ការសម្រាយរឿងដ៏ជក់ចិត្ត!",
                "tag": "hook",
                "speaker": "Narrator",
                "voice": "km-KH-PisethNeural",
                "status": "Ready"
            }]
        return fit_recap_segments_to_duration(fallback, dur, min_pause=0.25)

    finally:
        if uploaded_media:
            try:
                client.files.delete(name=uploaded_media.name)
            except Exception:
                pass


def generate_procedural_bgm(mood: str, output_path: Optional[str] = None, duration: float = 60.0) -> str:
    """
    Generates a clean ambient background music track using FFmpeg synthesis
    if no physical music file is available, ensuring the user always has working BGM.
    Returns the file path of the generated BGM.
    """
    if not output_path:
        output_path = str(BGM_DIR / f"bgm_{mood}.mp3")

    if os.path.exists(output_path) and os.path.getsize(output_path) > 1000:
        return str(output_path)

    dur = max(10.0, min(duration, 300.0))
    
    if mood == "suspense":
        filter_expr = (
            f"aevalsrc=exprs='0.08*sin(2*PI*110*t)+0.05*sin(2*PI*130.8*t)+0.04*sin(2*PI*164.8*t)+0.02*sin(2*PI*55*t)':s=44100:d={dur},"
            "lowpass=f=450,flanger=delay=15:speed=0.2:depth=3"
        )
    elif mood == "emotional":
        filter_expr = (
            f"aevalsrc=exprs='0.07*sin(2*PI*174.6*t)+0.06*sin(2*PI*220*t)+0.05*sin(2*PI*261.6*t)+0.04*sin(2*PI*329.6*t)':s=44100:d={dur},"
            "lowpass=f=600,chorus=0.7:0.9:55:0.4:0.25:2"
        )
    elif mood == "action":
        filter_expr = (
            f"aevalsrc=exprs='0.12*sin(2*PI*75*t)*(0.5+0.5*sin(2*PI*2.5*t))+0.06*sin(2*PI*150*t)+0.03*sin(2*PI*300*t)':s=44100:d={dur},"
            "bass=g=5:f=100,volume=1.2"
        )
    else:
        filter_expr = (
            f"aevalsrc=exprs='0.06*sin(2*PI*130.8*t)+0.05*sin(2*PI*196*t)+0.04*sin(2*PI*246.9*t)':s=44100:d={dur},"
            "lowpass=f=550"
        )

    import subprocess
    cmd = [
        FFMPEG_PATH, "-y",
        "-f", "lavfi",
        "-i", filter_expr,
        "-ac", "2",
        "-ar", "44100",
        "-b:a", "192k",
        str(output_path)
    ]
    try:
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    except Exception as e:
        logger.error(f"Failed to generate procedural BGM: {e}")
    return str(output_path)


def get_available_bgm_tracks() -> List[Dict[str, Any]]:
    """Returns all available BGM preset tracks and generated audio files."""
    presets = [
        {
            "id": "suspense",
            "name": "Cinematic Suspense (ភ័យរន្ធត់ & អាថ៌កំបាំង)",
            "mood": "suspense",
            "description": "Deep atmospheric drone for mystery, thriller, and plot twists.",
            "filename": "bgm_suspense.mp3"
        },
        {
            "id": "emotional",
            "name": "Emotional Piano Pad (កម្សត់ & ស្នេហា)",
            "mood": "emotional",
            "description": "Touching melody for drama, romance, and deep emotional scenes.",
            "filename": "bgm_emotional.mp3"
        },
        {
            "id": "action",
            "name": "Epic Action Hype (សកម្មភាព & រំភើប)",
            "mood": "action",
            "description": "Driving energetic beat for battles, chases, and power scenes.",
            "filename": "bgm_action.mp3"
        },
        {
            "id": "chill",
            "name": "Story Chill Documentary (រៀបរាប់ទូទៅ)",
            "mood": "chill",
            "description": "Gentle, non-intrusive backdrop for storytelling and exposition.",
            "filename": "bgm_chill.mp3"
        }
    ]

    results = []
    for p in presets:
        p_path = BGM_DIR / p["filename"]
        if not p_path.exists():
            generate_procedural_bgm(p["mood"], str(p_path), duration=120.0)
        
        results.append({
            **p,
            "path": str(p_path),
            "url": f"/api/recap/bgm-file/{p['id']}",
            "exists": p_path.exists()
        })

    for f in BGM_DIR.glob("custom_*.mp3"):
        results.append({
            "id": f.stem,
            "name": f"Custom: {f.stem.replace('custom_', '')}",
            "mood": "custom",
            "description": "Uploaded custom music track",
            "filename": f.name,
            "path": str(f),
            "url": f"/api/recap/bgm-file/{f.stem}",
            "exists": True
        })

    return results
