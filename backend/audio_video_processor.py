import json
import logging
import os
import re
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .config import FFMPEG_PATH, FFPROBE_PATH, TEMP_DIR

logger = logging.getLogger("audio_video_processor")
logger.setLevel(logging.INFO)


def run_ffmpeg(args: List[str]) -> Tuple[bool, str]:
    """Execute an FFmpeg command safely and return success flag and output."""
    cmd = [FFMPEG_PATH, "-y", "-hide_banner", "-loglevel", "error"] + args
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if res.returncode != 0:
            logger.error(f"FFmpeg command failed: {' '.join(cmd)}\nError: {res.stderr}")
            return False, res.stderr
        return True, res.stdout
    except Exception as e:
        logger.error(f"Exception running FFmpeg: {e}")
        return False, str(e)


def _compute_safe_boxblur_arg(strength_raw: int, box_w_px: float, box_h_px: float) -> str:
    """
    Computes FFmpeg boxblur arguments 'lr:lp:cr:cp' with plane dimension clamping.
    
    FFmpeg's libavfilter/vf_boxblur enforces:
      luma radius <= min(plane_w, plane_h) // 2
      chroma radius <= min(chroma_w, chroma_h) // 2
    For YUV420p video, chroma dimensions are halved (w/2, h/2), so chroma radius must be <= min_dim // 4.
    If the requested radius exceeds these bounds, FFmpeg aborts with:
      'Invalid chroma_param radius value X, must be >= 0 and <= Y' (-22).
    """
    raw_s = max(4, min(int(strength_raw * 0.25 + 4), 15))
    min_dim = max(4, int(min(box_w_px, box_h_px)))
    
    # 1-pixel safety headroom for integer truncations
    max_luma_r = max(1, (min_dim // 2) - 1)
    max_chroma_r = max(0, ((min_dim // 2) // 2) - 1)
    
    safe_lr = max(1, min(raw_s, max_luma_r))
    safe_cr = max(0, min(raw_s, max_chroma_r))
    power = max(1, min(max(2, safe_lr // 4), 3))
    
    return f"{safe_lr}:{power}:{safe_cr}:{power}"


def get_media_info(file_path: str) -> Dict[str, Any]:
    """Extract metadata from media file using ffprobe, prioritizing accurate video stream duration."""
    cmd = [
        FFPROBE_PATH,
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        file_path
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if res.returncode == 0:
            data = json.loads(res.stdout)
            has_video = any(s.get("codec_type") == "video" for s in data.get("streams", []))
            has_audio = any(s.get("codec_type") == "audio" for s in data.get("streams", []))
            
            width, height = None, None
            video_dur = None
            audio_dur = None
            for s in data.get("streams", []):
                if s.get("codec_type") == "video":
                    if not width:
                        width = s.get("width")
                        height = s.get("height")
                    if s.get("duration") and s.get("duration") != "N/A":
                        try:
                            vd = float(s.get("duration"))
                            if vd > 0.1 and (video_dur is None or vd < video_dur):
                                video_dur = vd
                        except ValueError:
                            pass
                    # Calculate duration from frame count and frame rate if duration tag is missing/imprecise
                    if not video_dur:
                        nb_frames = s.get("nb_frames")
                        r_fps = s.get("r_frame_rate") or s.get("avg_frame_rate")
                        if nb_frames and r_fps and "/" in str(r_fps):
                            try:
                                num, den = str(r_fps).split("/")
                                fps = float(num) / float(den) if float(den) > 0 else 0
                                if fps > 0 and int(nb_frames) > 0:
                                    video_dur = round(int(nb_frames) / fps, 3)
                            except Exception:
                                pass
                elif s.get("codec_type") == "audio":
                    if s.get("duration") and s.get("duration") != "N/A":
                        try:
                            ad = float(s.get("duration"))
                            if ad > 0.1 and (audio_dur is None or ad < audio_dur):
                                audio_dur = ad
                        except ValueError:
                            pass

            format_dur = float(data.get("format", {}).get("duration", 0.0))
            if has_video and video_dur and video_dur > 0.1:
                duration = video_dur
            elif has_audio and audio_dur and audio_dur > 0.1:
                duration = audio_dur
            elif format_dur > 0.1:
                duration = format_dur
            else:
                duration = 0.0

            duration = round(duration, 2)
                    
            return {
                "duration": duration,
                "has_video": has_video,
                "has_audio": has_audio,
                "width": width,
                "height": height,
                "format_name": data.get("format", {}).get("format_name", ""),
                "size_bytes": int(data.get("format", {}).get("size", 0))
            }
    except Exception as e:
        logger.error(f"ffprobe error for {file_path}: {e}")
        
    return {"duration": 0.0, "has_video": False, "has_audio": False}


def extract_audio(input_media: str, output_audio: str, sample_rate: int = 44100, channels: int = 2, duration: Optional[float] = None) -> bool:
    """Extract stereo WAV audio optimized for speech recognition and vocal separation."""
    args = [
        "-i", input_media,
        "-vn",
        "-acodec", "pcm_s16le",
        "-ac", str(channels),
        "-ar", str(sample_rate),
    ]
    if duration and duration > 0:
        args.extend(["-t", f"{duration:.3f}"])
    args.extend(["-y", output_audio])
    success, err = run_ffmpeg(args)
    return success


def get_audio_duration(audio_path: str) -> float:
    """Get accurate duration of an audio/video file in seconds without container tail padding."""
    cmd = [
        FFPROBE_PATH,
        "-v", "error",
        "-show_entries", "format=duration:stream=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        audio_path
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if res.returncode == 0 and res.stdout.strip():
            vals = []
            for line in res.stdout.strip().splitlines():
                v_str = line.strip()
                if v_str and v_str.upper() != "N/A":
                    try:
                        v_flt = float(v_str)
                        if v_flt > 0.1:
                            vals.append(v_flt)
                    except ValueError:
                        pass
            if vals:
                # Prefer exact video/audio stream length over container format tail padding
                return min(vals)
    except Exception as e:
        logger.error(f"Failed to get audio duration for {audio_path}: {e}")
    return 0.0


def time_stretch_audio(input_audio: str, output_audio: str, target_duration: float) -> bool:
    """
    Adjust audio playback speed using atempo filter so it matches target duration.
    atempo supports values between 0.5 and 2.0 per filter stage.
    """
    orig_duration = get_audio_duration(input_audio)
    if orig_duration <= 0 or target_duration <= 0:
        return False
        
    speed_factor = orig_duration / target_duration
    
    # Restrict speed factor to reasonable bounds (0.70x to 2.35x) so audio sounds natural while fitting time limit
    speed_factor = max(0.70, min(speed_factor, 2.35))
    
    # If speed change is negligible, copy file directly without subprocess overhead
    if abs(speed_factor - 1.0) < 0.03:
        try:
            shutil.copy2(input_audio, output_audio)
            return True
        except Exception:
            pass

    # Build atempo filter chain
    filters = []
    current_speed = speed_factor
    while current_speed > 2.0:
        filters.append("atempo=2.0")
        current_speed /= 2.0
    while current_speed < 0.5:
        filters.append("atempo=0.5")
        current_speed /= 0.5
    filters.append(f"atempo={current_speed:.4f}")
    
    filter_graph = ",".join(filters)
    args = [
        "-i", input_audio,
        "-filter:a", filter_graph,
        "-vn",
        output_audio
    ]
    success, _ = run_ffmpeg(args)
    return success


def stitch_dubbed_audio(
    segments: List[Dict],
    total_duration: float,
    output_audio_path: str
) -> bool:
    """
    Stitches individual segment audio files into a single full-length audio track,
    placing each segment at its precise start timestamp with silence in between.
    Guarantees that speech finishes cleanly before the total video duration.
    """
    if not segments:
        return False

    # Filter segments that have valid audio files
    valid_segments = [s for s in segments if s.get("audio_path") and os.path.exists(s["audio_path"])]
    if not valid_segments:
        logger.warning("No valid audio segments to stitch, generating blank audio track")
        dur = max(1.0, float(total_duration))
        args = [
            "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
            "-t", str(dur),
            "-acodec", "libmp3lame",
            output_audio_path
        ]
        success, _ = run_ffmpeg(args)
        return success

    inputs = []
    filter_complex = []
    
    current_free_ms = 0
    min_gap_ms = 50  # 50ms clean pause (avoids artificial cumulative timeline drift)
    total_dur_ms = int(total_duration * 1000) if total_duration > 0 else 0

    from .config import TEMP_DIR
    import uuid

    for i, seg in enumerate(valid_segments):
        seg_audio_path = seg["audio_path"]
        requested_start_ms = int(max(0.0, float(seg.get("start", 0.0))) * 1000)

        # Non-overlap guarantee: prevent collision with previous segment while keeping original timestamp
        actual_delay_ms = max(current_free_ms, requested_start_ms)

        # Measure audio duration
        seg_dur = get_audio_duration(seg_audio_path)
        seg_dur_ms = int(max(0.1, seg_dur) * 1000)

        # Check boundary with next segment to prevent pushing subsequent segments
        next_req_start_ms = None
        if i + 1 < len(valid_segments):
            try:
                next_req_start_ms = int(max(0.0, float(valid_segments[i + 1].get("start", 0.0))) * 1000)
            except (ValueError, TypeError):
                next_req_start_ms = None

        # If next segment exists, available window is up to next_req_start_ms - 40ms
        max_allowed_dur_ms = None
        if next_req_start_ms is not None and next_req_start_ms > actual_delay_ms:
            max_allowed_dur_ms = max(350, next_req_start_ms - actual_delay_ms - 40)
        elif total_dur_ms > 0:
            max_allowed_dur_ms = max(350, total_dur_ms - actual_delay_ms - 50)

        if max_allowed_dur_ms is not None and seg_dur_ms > max_allowed_dur_ms:
            target_dur_sec = max_allowed_dur_ms / 1000.0
            stretched_path = os.path.join(TEMP_DIR, f"seg_stitch_fit_{i}_{uuid.uuid4().hex[:6]}.mp3")
            if time_stretch_audio(seg_audio_path, stretched_path, target_dur_sec) and os.path.exists(stretched_path):
                seg_audio_path = stretched_path
                seg_dur = get_audio_duration(stretched_path)
                seg_dur_ms = int(max(0.1, seg_dur) * 1000)

        inputs.extend(["-i", seg_audio_path])
        current_free_ms = actual_delay_ms + seg_dur_ms + min_gap_ms

        filter_complex.append(f"[{i}:a]adelay={actual_delay_ms}|{actual_delay_ms}[a{i}]")
        
    mix_inputs = "".join(f"[a{i}]" for i in range(len(valid_segments)))
    filter_complex.append(
        f"{mix_inputs}amix=inputs={len(valid_segments)}:duration=longest:dropout_transition=0:normalize=0[mixed]"
    )
    
    # Pad and strictly trim to total_duration if provided
    if total_duration > 0:
        filter_complex.append(f"[mixed]atrim=0:{total_duration:.3f},apad=pad_dur={total_duration:.3f}[final]")
        final_label = "[final]"
    else:
        final_label = "[mixed]"

    args = inputs + [
        "-filter_complex", ";".join(filter_complex),
        "-map", final_label,
        "-ac", "2",
        "-ar", "44100",
    ]
    if total_duration > 0:
        args += ["-t", f"{total_duration:.3f}"]
    args.append(output_audio_path)

    success, err = run_ffmpeg(args)
    if not success:
        logger.error(f"Failed to stitch dubbed audio: {err}")
    return success


def mix_audio_with_video(
    video_path: str,
    dub_audio_path: str,
    output_video_path: str,
    mode: str = "bgm_isolate",
    bgm_audio_path: Optional[str] = None,
    ducking_volume: float = 0.12,
    bgm_volume: float = 0.35,
    dub_volume: float = 1.40,
    blur_subtitles: bool = False,
    subtitle_blur_box: Optional[Dict[str, float]] = None,
    aspect_ratio_mode: str = "original",
    canvas_blur_strength: int = 25,
    blur_objects: Optional[List[Dict[str, Any]]] = None,
    burn_subtitles: bool = False,
    subtitles_file: Optional[str] = None,
) -> bool:
    """
    Mixes audio track with the Khmer dubbed voice and optionally applies video blur features:
    - Audio Modes:
      - 'bgm_isolate': Mixes clean isolated BGM with Khmer dubbing voice.
      - 'ducking': Lowers original audio volume and layers Khmer voice over it.
      - 'replace': Completely mutes original audio and replaces with dubbed audio.
    - Video Filters:
      - 'blur_objects': Professional multi-region blur objects with shapes and timeline gating.
      - 'blur_subtitles': Erases original hardcoded subtitles/watermarks with boxblur.
      - 'aspect_ratio_mode': '9:16' (Shorts/TikTok) or '1:1' (Square) with blurred background.
    """
    media_info = get_media_info(video_path)
    has_original_audio = media_info.get("has_audio", False)

    # Determine input files and indices
    inputs = ["-i", video_path]
    dub_idx = 1

    if mode in ("bgm_isolate", "sidechain_ducking") and bgm_audio_path and os.path.exists(bgm_audio_path):
        inputs.extend(["-i", bgm_audio_path, "-i", dub_audio_path])
        bgm_idx = 1
        dub_idx = 2
    elif mode == "ducking" and has_original_audio:
        inputs.extend(["-i", dub_audio_path])
        dub_idx = 1
    else:
        inputs.extend(["-i", dub_audio_path])
        dub_idx = 1

    filter_complex_parts: List[str] = []

    # 1. Video Filters (Subtitle Masking & Blurred Canvas)
    active_blur_list = [b for b in (blur_objects or []) if b.get("enabled", True)]
    use_blur_objects = len(active_blur_list) > 0
    has_video_filter = bool(use_blur_objects or blur_subtitles or aspect_ratio_mode in ("9:16", "1:1", "4:5"))
    current_v = "0:v"

    vw = float(media_info.get("width") or 1920)
    vh = float(media_info.get("height") or 1080)
    video_aspect = vw / vh if vh > 0 else (16.0 / 9.0)

    if aspect_ratio_mode == "9:16":
        container_aspect = 9.0 / 16.0
    elif aspect_ratio_mode == "1:1":
        container_aspect = 1.0
    elif aspect_ratio_mode == "4:5":
        container_aspect = 4.0 / 5.0
    else:
        container_aspect = 16.0 / 9.0

    if use_blur_objects:
        for idx, b in enumerate(active_blur_list):
            bx = float(b.get("x", 0.0))
            by = float(b.get("y", 0.0))
            bw = float(b.get("width", b.get("w", 0.2)))
            bh = float(b.get("height", b.get("h", 0.15)))

            # If coordinates were set in player container coordinate space (e.g. 16:9 container with vertical video)
            if b.get("coord_space") != "video" and abs(video_aspect - container_aspect) > 0.03:
                if video_aspect > container_aspect:
                    # Letterbox (video has black bars top and bottom)
                    rw_frac = 1.0
                    rh_frac = container_aspect / video_aspect
                    ox_frac = 0.0
                    oy_frac = (1.0 - rh_frac) / 2.0
                else:
                    # Pillarbox (video has black bars left and right)
                    rh_frac = 1.0
                    rw_frac = video_aspect / container_aspect
                    oy_frac = 0.0
                    ox_frac = (1.0 - rw_frac) / 2.0

                bx = (bx - ox_frac) / rw_frac
                by = (by - oy_frac) / rh_frac
                bw = bw / rw_frac
                bh = bh / rh_frac

            bx = max(0.0, min(bx, 0.98))
            by = max(0.0, min(by, 0.98))
            bw = max(0.02, min(bw, 1.0 - bx))
            bh = max(0.02, min(bh, 1.0 - by))
            b_type = str(b.get("blurType", "gaussian")).lower()
            strength_raw = int(b.get("strength", 50))
            crop_w_px = max(4, (int(vw * bw) // 2) * 2)
            crop_h_px = max(4, (int(vh * bh) // 2) * 2)
            if b_type == "background":
                blur_arg = _compute_safe_boxblur_arg(strength_raw, vw, vh)
            else:
                blur_arg = _compute_safe_boxblur_arg(strength_raw, crop_w_px, crop_h_px)
            start_t = max(0.0, float(b.get("startTime", 0.0)))
            end_t = float(b.get("endTime", 999999.0))
            enable_expr = f"between(t,{start_t:.2f},{end_t:.2f})"

            crop_w = f"trunc(iw*{bw:.4f}/2)*2"
            crop_h = f"trunc(ih*{bh:.4f}/2)*2"
            crop_x = f"trunc(iw*{bx:.4f}/2)*2"
            crop_y = f"trunc(ih*{by:.4f}/2)*2"
            overlay_x = f"trunc(W*{bx:.4f}/2)*2"
            overlay_y = f"trunc(H*{by:.4f}/2)*2"

            v_base = f"v_base_{idx}"
            v_crop = f"v_crop_{idx}"
            v_blur = f"v_blur_{idx}"
            v_out = f"v_masked_{idx}"

            filter_complex_parts.append(f"[{current_v}]split[{v_base}][{v_crop}]")
            if b_type in ("pixelate", "mosaic"):
                block_size = max(4, min(int(strength_raw * 0.35 + 4), 36))
                filter_complex_parts.append(
                    f"[{v_crop}]crop=w={crop_w}:h={crop_h}:x={crop_x}:y={crop_y},"
                    f"scale=w=max(4\\,trunc(iw/{block_size})):h=max(4\\,trunc(ih/{block_size})):flags=neighbor,"
                    f"scale=w={crop_w}:h={crop_h}:flags=neighbor[{v_blur}]"
                )
            elif b_type == "background":
                # Background blur with subject center crop protection
                protect_pct = float(b.get("subjectProtection", 70)) / 100.0
                fg_w = f"trunc(iw*{max(0.2, protect_pct):.4f}/2)*2"
                fg_h = f"trunc(ih*{max(0.2, protect_pct):.4f}/2)*2"
                filter_complex_parts.append(
                    f"[{v_crop}]boxblur={blur_arg}[{v_blur}]"
                )
            else:
                filter_complex_parts.append(
                    f"[{v_crop}]crop=w={crop_w}:h={crop_h}:x={crop_x}:y={crop_y},boxblur={blur_arg}[{v_blur}]"
                )

            if b_type == "background":
                overlay_x = "0"
                overlay_y = "0"

            filter_complex_parts.append(
                f"[{v_base}][{v_blur}]overlay=x={overlay_x}:y={overlay_y}:enable='{enable_expr}'[{v_out}]"
            )
            current_v = v_out

    elif blur_subtitles:
        box = subtitle_blur_box or {}
        x = float(box.get("x", 0.0))
        y = float(box.get("y", 0.82))
        w = float(box.get("w", 1.0))
        h = float(box.get("h", 0.15))
        strength_raw = int(box.get("strength", 20))

        # If coordinates were set in player container coordinate space
        if box.get("coord_space") != "video" and abs(video_aspect - container_aspect) > 0.03:
            if video_aspect > container_aspect:
                rw_frac = 1.0
                rh_frac = container_aspect / video_aspect
                ox_frac = 0.0
                oy_frac = (1.0 - rh_frac) / 2.0
            else:
                rh_frac = 1.0
                rw_frac = video_aspect / container_aspect
                oy_frac = 0.0
                ox_frac = (1.0 - rw_frac) / 2.0

            x = (x - ox_frac) / rw_frac
            y = (y - oy_frac) / rh_frac
            w = w / rw_frac
            h = h / rh_frac

        # Restrict values to [0.0, 1.0]
        x = max(0.0, min(x, 0.98))
        y = max(0.0, min(y, 0.98))
        w = max(0.02, min(w, 1.0 - x))
        h = max(0.02, min(h, 1.0 - y))

        sub_w_px = max(4, (int(vw * w) // 2) * 2)
        sub_h_px = max(4, (int(vh * h) // 2) * 2)
        blur_arg = _compute_safe_boxblur_arg(strength_raw, sub_w_px, sub_h_px)

        crop_w_expr = f"trunc(iw*{w:.4f}/2)*2"
        crop_h_expr = f"trunc(ih*{h:.4f}/2)*2"
        crop_x_expr = f"trunc(iw*{x:.4f}/2)*2"
        crop_y_expr = f"trunc(ih*{y:.4f}/2)*2"

        overlay_x_expr = f"trunc(W*{x:.4f}/2)*2"
        overlay_y_expr = f"trunc(H*{y:.4f}/2)*2"

        filter_complex_parts.append(f"[{current_v}]split[v_base][v_crop]")
        filter_complex_parts.append(
            f"[v_crop]crop=w={crop_w_expr}:h={crop_h_expr}:x={crop_x_expr}:y={crop_y_expr},boxblur={blur_arg}[v_blurred]"
        )
        filter_complex_parts.append(f"[v_base][v_blurred]overlay=x={overlay_x_expr}:y={overlay_y_expr}[v_masked]")
        current_v = "v_masked"

    if aspect_ratio_mode in ("9:16", "1:1", "4:5"):
        if aspect_ratio_mode == "9:16":
            target_w, target_h = 1080, 1920
        elif aspect_ratio_mode == "4:5":
            target_w, target_h = 1080, 1350
        else:
            target_w, target_h = 1080, 1080

        bg_blur_arg = _compute_safe_boxblur_arg(canvas_blur_strength, target_w, target_h)

        filter_complex_parts.append(f"[{current_v}]split[v_fg][v_bg]")
        filter_complex_parts.append(
            f"[v_bg]scale={target_w}:{target_h}:force_original_aspect_ratio=increase,"
            f"crop={target_w}:{target_h},boxblur={bg_blur_arg},eq=brightness=-0.07:contrast=0.95[v_bg_blur]"
        )
        filter_complex_parts.append(
            f"[v_fg]scale={target_w}:{target_h}:force_original_aspect_ratio=decrease[v_fg_scaled]"
        )
        filter_complex_parts.append(f"[v_bg_blur][v_fg_scaled]overlay=(W-w)/2:(H-h)/2[v_canvas]")
        current_v = "v_canvas"

    # Burn Subtitles Filter (applied on top of video, aspect ratio & blur)
    if burn_subtitles and subtitles_file and os.path.exists(subtitles_file):
        has_video_filter = True
        escaped_sub = subtitles_file.replace("\\", "/").replace(":", "\\:").replace("'", "\\'")
        filter_name = "ass" if subtitles_file.lower().endswith(".ass") else "subtitles"
        filter_complex_parts.append(f"[{current_v}]{filter_name}='{escaped_sub}'[v_burned_subs]")
        current_v = "v_burned_subs"

    video_map = f"[{current_v}]" if has_video_filter else "0:v"

    # 2. Audio Filters
    if mode == "sidechain_ducking" and bgm_audio_path and os.path.exists(bgm_audio_path):
        # Dynamic sidechain compression for BGM ducking under narrator voice
        filter_complex_parts.append(f"[{bgm_idx}:a]volume={bgm_volume:.2f},aloop=loop=-1:size=2e+09[bgm_loop]")
        filter_complex_parts.append(f"[{dub_idx}:a]volume={dub_volume:.2f}[dub_speech]")
        filter_complex_parts.append(
            "[bgm_loop][dub_speech]sidechaincompress=threshold=0.07:ratio=7:attack=140:release=550[ducked_bgm]"
        )
        filter_complex_parts.append("[ducked_bgm][dub_speech]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[aout]")
        audio_map = "[aout]"
    elif mode == "bgm_isolate" and bgm_audio_path and os.path.exists(bgm_audio_path):
        filter_complex_parts.append(f"[{bgm_idx}:a]volume={bgm_volume:.2f}[bgm]")
        filter_complex_parts.append(f"[{dub_idx}:a]volume={dub_volume:.2f}[dub]")
        filter_complex_parts.append("[bgm][dub]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[aout]")
        audio_map = "[aout]"
    elif mode == "ducking" and has_original_audio:
        filter_complex_parts.append(f"[0:a]volume={ducking_volume:.2f}[orig]")
        filter_complex_parts.append(f"[{dub_idx}:a]volume={dub_volume:.2f}[dub]")
        filter_complex_parts.append("[orig][dub]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[aout]")
        audio_map = "[aout]"
    else:
        audio_map = f"{dub_idx}:a"

    # Build full arguments
    args = list(inputs)
    if filter_complex_parts:
        args.extend(["-filter_complex", ";".join(filter_complex_parts)])

    args.extend(["-map", video_map, "-map", audio_map])

    if has_video_filter:
        args.extend(["-c:v", "libx264", "-preset", "ultrafast", "-crf", "22", "-threads", "0", "-pix_fmt", "yuv420p"])
    else:
        args.extend(["-c:v", "copy"])

    args.extend(["-c:a", "aac", "-b:a", "192k", "-shortest", output_video_path])

    success, err = run_ffmpeg(args)
    if not success:
        logger.error(f"Failed to render mixed dubbed video: {err}")
    return success


def format_srt_timestamp(seconds: float) -> str:
    """Format seconds into SRT timestamp 00:00:00,000"""
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int(round((seconds - int(seconds)) * 1000))
    return f"{hrs:02d}:{mins:02d}:{secs:02d},{millis:03d}"


def format_vtt_timestamp(seconds: float) -> str:
    """Format seconds into WebVTT timestamp 00:00:00.000"""
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int(round((seconds - int(seconds)) * 1000))
    return f"{hrs:02d}:{mins:02d}:{secs:02d}.{millis:03d}"


def generate_srt(segments: List[Dict], output_path: str, text_key: str = "khmer_text") -> bool:
    """Generate a valid SRT subtitle file."""
    try:
        with open(output_path, "w", encoding="utf-8") as f:
            for idx, seg in enumerate(segments, 1):
                start = format_srt_timestamp(float(seg["start"]))
                end = format_srt_timestamp(float(seg["end"]))
                text = seg.get(text_key, seg.get("text", "")).strip()
                f.write(f"{idx}\n{start} --> {end}\n{text}\n\n")
        return True
    except Exception as e:
        logger.error(f"Failed to generate SRT: {e}")
        return False


def generate_vtt(segments: List[Dict], output_path: str, text_key: str = "khmer_text") -> bool:
    """Generate a valid WebVTT subtitle file."""
    try:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("WEBVTT\n\n")
            for idx, seg in enumerate(segments, 1):
                start = format_vtt_timestamp(float(seg["start"]))
                end = format_vtt_timestamp(float(seg["end"]))
                text = seg.get(text_key, seg.get("text", "")).strip()
                f.write(f"{idx}\n{start} --> {end}\n{text}\n\n")
        return True
    except Exception as e:
        logger.error(f"Failed to generate VTT: {e}")
        return False


def format_ass_timestamp(seconds: float) -> str:
    """Format seconds into ASS timestamp H:MM:SS.cc"""
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    centis = int(round((seconds - int(seconds)) * 100))
    return f"{hrs:d}:{mins:02d}:{secs:02d}.{centis:02d}"


def hex_to_ass_color(hex_str: str, opacity: float = 1.0) -> str:
    """Convert #RRGGBB or #RGB to ASS &HAABBGGRR format with alpha."""
    hex_clean = hex_str.lstrip("#").strip()
    if len(hex_clean) == 3:
        hex_clean = "".join([c * 2 for c in hex_clean])
    if len(hex_clean) < 6:
        hex_clean = "FFFFFF"
    r = int(hex_clean[0:2], 16)
    g = int(hex_clean[2:4], 16)
    b = int(hex_clean[4:6], 16)
    alpha_val = int(round((1.0 - max(0.0, min(1.0, opacity))) * 255))
    return f"&H{alpha_val:02X}{b:02X}{g:02X}{r:02X}"


def generate_ass(
    segments: List[Dict],
    output_path: str,
    style: Optional[Dict[str, Any]] = None,
    text_key: str = "khmer_text",
    dual_mode: bool = False,
) -> bool:
    """Generate professional Advanced Substation Alpha (.ass) subtitle file with full styling, box, and karaoke support."""
    try:
        s = style or {}
        raw_font = s.get("fontFamily", "Kantumruy Pro")
        
        # Font Fallback mapping for Windows FFmpeg Libass rendering
        font_map = {
            "Kantumruy Pro": "Kantumruy Pro, Khmer OS Battambang, Khmer UI, Arial",
            "Noto Sans Khmer": "Noto Sans Khmer, Khmer OS, Khmer UI, Arial",
            "Noto Serif Khmer": "Noto Serif Khmer, Khmer OS, Khmer UI, Times New Roman",
            "Khmer OS": "Khmer OS, Khmer UI, Arial",
            "Khmer OS Battambang": "Khmer OS Battambang, Khmer UI, Arial",
            "Khmer OS Siemreap": "Khmer OS Siemreap, Khmer UI, Arial",
            "Moul": "Khmer OS Muol, Khmer OS Muol Light, Khmer UI",
            "Khmer OS Muol": "Khmer OS Muol, Khmer OS Muol Light, Khmer UI",
            "Siemreap": "Khmer OS Siemreap, Khmer UI, Arial",
        }
        font_name = font_map.get(raw_font, raw_font)

        font_size = int(s.get("fontSize", 28))
        is_bold = -1 if s.get("bold", True) or str(s.get("fontWeight", "700")) in ("700", "800", "bold") else 0
        is_italic = -1 if s.get("italic", False) else 0
        primary_color = hex_to_ass_color(s.get("textColor", "#FFFFFF"), s.get("textOpacity", 100) / 100.0)
        outline_color = hex_to_ass_color(s.get("strokeColor", "#000000"), 1.0)
        
        bg_style = s.get("bgStyle", "none")
        use_opaque_box = bg_style in ("solid", "semi", "rounded", "blur", "glass_pill")
        border_style = 3 if use_opaque_box else 1
        
        if use_opaque_box:
            # BorderStyle 3 in ASS uses BackColour as the background bounding box fill
            bg_opacity = float(s.get("bgOpacity", 70)) / 100.0
            back_color = hex_to_ass_color(s.get("bgColor", "#000000"), bg_opacity)
            outline_width = max(2, int(s.get("bgPadding", 6)))
            shadow_depth = 0
        else:
            back_color = hex_to_ass_color(s.get("shadowColor", "#000000"), s.get("shadowOpacity", 80) / 100.0)
            outline_width = int(s.get("strokeWidth", 3)) if s.get("strokeEnabled", True) else 0
            shadow_depth = int(s.get("shadowBlur", 3)) if s.get("shadowEnabled", True) else 0

        align_map = {
            "top-left": 7, "top-center": 8, "top-right": 9,
            "mid-left": 4, "center": 5, "mid-right": 6,
            "bottom-left": 1, "bottom-center": 2, "bottom-right": 3,
        }
        align_val = align_map.get(s.get("positionPreset", "bottom-center"), 2)
        margin_v = int(s.get("marginV", 25))

        # Secondary subtitle style for dual-language mode
        sec_font_size = max(14, int(font_size * 0.75))
        sec_primary_color = "&H00D0D0D0"

        ass_content = [
            "[Script Info]",
            "Title: DubStudio AI Khmer Subtitles",
            "ScriptType: v4.00+",
            "WrapStyle: 0",
            "ScaledBorderAndShadow: yes",
            "YCbCr Matrix: TV.709",
            "PlayResX: 1920",
            "PlayResY: 1080",
            "",
            "[V4+ Styles]",
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
            f"Style: Default,{font_name},{font_size * 2},{primary_color},&H000000FF,{outline_color},{back_color},{is_bold},{is_italic},0,0,100,100,0,0,{border_style},{outline_width * 2},{shadow_depth * 2},{align_val},40,40,{margin_v * 2},1",
            f"Style: Secondary,{font_name},{sec_font_size * 2},{sec_primary_color},&H000000FF,{outline_color},{back_color},0,{is_italic},0,0,100,100,0,0,1,{max(1, outline_width)},{max(1, shadow_depth)},{align_val},40,40,{margin_v * 2 + 65},1",
            "",
            "[Events]",
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
        ]

        word_anim = s.get("wordAnim", "none")
        preset_key = s.get("preset", "")
        is_karaoke = (word_anim == "karaoke") or (preset_key == "karaoke")

        for seg in segments:
            start_sec = float(seg.get("start", 0.0))
            end_sec = float(seg.get("end", start_sec + 2.0))
            start_str = format_ass_timestamp(start_sec)
            end_str = format_ass_timestamp(end_sec)
            
            khmer_txt = (seg.get("khmer_text") or seg.get(text_key) or "").strip().replace("\n", "\\N")
            orig_txt = (seg.get("text") or "").strip().replace("\n", "\\N")

            # Progressive karaoke fill tag generation
            if is_karaoke and khmer_txt:
                duration_cs = max(10, int((end_sec - start_sec) * 100))
                words = [w for w in re.split(r"(\s+)", khmer_txt) if w]
                word_tokens = [w for w in words if w.strip()]
                total_tokens = max(1, len(word_tokens))
                cs_per_token = max(5, duration_cs // total_tokens)

                styled_parts = []
                for w in words:
                    if w.strip():
                        styled_parts.append(f"{{\\k{cs_per_token}}}{w}")
                    else:
                        styled_parts.append(w)
                rendered_khmer = "".join(styled_parts)
            else:
                rendered_khmer = khmer_txt

            if dual_mode and orig_txt and rendered_khmer:
                full_txt = f"{rendered_khmer}\\N{{\\rSecondary}}{orig_txt}"
            else:
                full_txt = rendered_khmer if rendered_khmer else orig_txt

            ass_content.append(f"Dialogue: 0,{start_str},{end_str},Default,,0,0,0,,{full_txt}")

        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(ass_content) + "\n")
        return True
    except Exception as e:
        logger.error(f"Failed to generate ASS: {e}")
        return False
