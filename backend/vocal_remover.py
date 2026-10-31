import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Callable, Optional, Tuple

from .audio_video_processor import run_ffmpeg, get_audio_duration
from .config import FFMPEG_PATH, TEMP_DIR

logger = logging.getLogger("vocal_remover")
logger.setLevel(logging.INFO)


def _get_demucs_device() -> str:
    """Detect if PyTorch CUDA GPU is available for fast Demucs separation."""
    try:
        import torch
        if torch.cuda.is_available():
            return "cuda"
    except Exception:
        pass
    return "cpu"


def remove_vocals_dsp(input_audio_path: str, output_audio_path: str) -> bool:
    """
    Fast DSP center-channel vocal reduction using FFmpeg phase cancellation and bandpass.
    Executes in under a second without requiring neural network weights.
    """
    # Center channel cancellation + low-pass / high-pass compensation to keep bass and highs
    filter_graph = (
        "[0:a]stereotools=mlev=0.015625:slev=1.2[bg]; "
        "[0:a]lowpass=f=200[bass]; "
        "[bg][bass]amix=inputs=2:weights=1.0 0.8[out]"
    )
    args = [
        "-i", input_audio_path,
        "-filter_complex", filter_graph,
        "-map", "[out]",
        "-ac", "2",
        "-ar", "44100",
        output_audio_path
    ]
    success, err = run_ffmpeg(args)
    if not success:
        # Fallback simpler pan filter
        alt_args = [
            "-i", input_audio_path,
            "-af", "pan=stereo|c0=c0-c1|c1=c1-c0",
            output_audio_path
        ]
        success, err = run_ffmpeg(alt_args)
    return success


def separate_vocals_demucs(
    input_audio_path: str,
    output_dir: Optional[str] = None,
    model_name: str = "htdemucs",
    progress_callback: Optional[Callable[[str], None]] = None
) -> Tuple[Optional[str], Optional[str]]:
    """
    Uses Meta AI's Demucs (htdemucs) to separate audio into:
    1. BGM / Instrumental (no_vocals.wav)
    2. Vocals / Dialogue (vocals.wav)
    
    Supports CUDA GPU acceleration and direct Python API + CLI subprocess fallback.
    Returns (bgm_path, vocals_path).
    """
    out_dir = Path(output_dir or TEMP_DIR) / "demucs_out"
    out_dir.mkdir(parents=True, exist_ok=True)
    device = _get_demucs_device()

    if progress_callback:
        progress_callback(f"Running Demucs AI Vocal Separation ({model_name} on {device.upper()})...")

    # 1. Attempt Demucs Python API direct separation
    try:
        # pyrefly: ignore [missing-import]
        import demucs.api
        import torchaudio
        separator = demucs.api.Separator(model=model_name, device=device, shifts=1)
        origin, res = separator.separate_audio_file(input_audio_path)
        
        track_name = Path(input_audio_path).stem
        target_folder = out_dir / model_name / track_name
        target_folder.mkdir(parents=True, exist_ok=True)

        bgm_file = target_folder / "no_vocals.wav"
        vocal_file = target_folder / "vocals.wav"

        if "vocals" in res:
            vocals_tensor = res["vocals"]
            no_vocals_tensor = sum(tensor for stem, tensor in res.items() if stem != "vocals")
            torchaudio.save(str(bgm_file), no_vocals_tensor.cpu(), separator.samplerate)
            torchaudio.save(str(vocal_file), vocals_tensor.cpu(), separator.samplerate)
            logger.info(f"Demucs AI separation succeeded via Python API ({device}).")
            return str(bgm_file), str(vocal_file)
    except Exception as api_err:
        logger.debug(f"Demucs Python API invocation skipped/failed: {api_err}. Trying CLI subprocess...")

    # 2. CLI Subprocess Fallback
    python_executable = sys.executable or "python"
    cmd = [
        python_executable,
        "-m", "demucs.separate",
        "--two-stems=vocals",
        "-n", model_name,
        "-d", device,
        "-o", str(out_dir),
        input_audio_path
    ]

    env = os.environ.copy()
    if os.path.exists(r"C:\ffmpeg-8.0.1-essentials_build\bin"):
        env["PATH"] = r"C:\ffmpeg-8.0.1-essentials_build\bin;" + env.get("PATH", "")

    duration = get_audio_duration(input_audio_path) or 30.0
    timeout = max(90, int(duration * 4.0)) if device == "cpu" else max(60, int(duration * 1.5))

    try:
        res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", env=env, timeout=timeout)
        if res.returncode != 0:
            logger.error(f"Demucs CLI separation failed: {res.stderr}")
            return None, None

        track_name = Path(input_audio_path).stem
        target_folder = out_dir / model_name / track_name

        bgm_file = target_folder / "no_vocals.wav"
        vocal_file = target_folder / "vocals.wav"

        bgm_path = str(bgm_file) if bgm_file.exists() else None
        vocal_path = str(vocal_file) if vocal_file.exists() else None

        return bgm_path, vocal_path

    except subprocess.TimeoutExpired:
        logger.warning(f"Demucs vocal separation timed out after {timeout}s. Falling back to fast DSP center-channel vocal reduction.")
        return None, None
    except Exception as e:
        logger.error(f"Demucs separation error: {e}", exc_info=True)
        return None, None


def separate_vocals_bs_roformer(
    input_audio_path: str,
    output_dir: Optional[str] = None,
    model_name: str = "model_bs_roformer_ep_317_sdr_12.9755.ckpt",
    progress_callback: Optional[Callable[[str], None]] = None
) -> Tuple[Optional[str], Optional[str]]:
    """
    Uses Band-Split RoFormer (BS-RoFormer) SOTA AI Model to separate audio into:
    1. BGM / Instrumental
    2. Vocals / Dialogue

    Falls back to Demucs if audio-separator / BS-RoFormer is unavailable or encounters an error.
    Returns (bgm_path, vocal_path).
    """
    out_dir = Path(output_dir or TEMP_DIR) / "bs_roformer_out"
    out_dir.mkdir(parents=True, exist_ok=True)
    device = _get_demucs_device()

    if progress_callback:
        progress_callback(f"Running BS-RoFormer SOTA AI Separation ({model_name} on {device.upper()})...")

    # List of known valid BS-RoFormer model filenames in audio-separator
    valid_models = [
        model_name,
        "model_bs_roformer_ep_317_sdr_12.9755.ckpt",
        "model_bs_roformer_ep_368_sdr_12.9628.ckpt"
    ]

    # 1. Direct Python API call via audio_separator
    for m_filename in valid_models:
        try:
            # pyrefly: ignore [missing-import]
            from audio_separator.separator import Separator
            sep = Separator(
                output_dir=str(out_dir),
                output_format="WAV"
            )
            sep.load_model(model_filename=m_filename)
            output_files = sep.separate(input_audio_path)
            
            bgm_path, vocal_path = None, None
            for f in output_files:
                f_str = str(out_dir / f) if not os.path.isabs(f) else f
                f_lower = Path(f_str).stem.lower()
                if "vocal" in f_lower:
                    vocal_path = f_str
                elif any(k in f_lower for k in ("instrumental", "no_vocal", "bgm", "other")):
                    bgm_path = f_str
                elif not bgm_path:
                    bgm_path = f_str

            if bgm_path and os.path.exists(bgm_path):
                logger.info(f"BS-RoFormer separation succeeded via audio_separator Python API ({m_filename}).")
                return bgm_path, vocal_path
        except Exception as api_err:
            logger.debug(f"audio_separator API attempt for {m_filename} failed: {api_err}")

    # 2. CLI Subprocess Fallback
    target_model = valid_models[1]  # model_bs_roformer_ep_317_sdr_12.9755.ckpt
    audio_sep_bin = shutil.which("audio-separator") or "audio-separator"
    cmd = [
        audio_sep_bin,
        input_audio_path,
        "--model_filename", target_model,
        "--output_dir", str(out_dir),
        "--output_format", "WAV"
    ]


    env = os.environ.copy()
    if os.path.exists(r"C:\ffmpeg-8.0.1-essentials_build\bin"):
        env["PATH"] = r"C:\ffmpeg-8.0.1-essentials_build\bin;" + env.get("PATH", "")

    duration = get_audio_duration(input_audio_path) or 30.0
    timeout = max(120, int(duration * 4.0)) if device == "cpu" else max(60, int(duration * 1.5))

    try:
        res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", env=env, timeout=timeout)
        if res.returncode == 0:
            gen_files = list(out_dir.glob("*.wav"))
            bgm_path, vocal_path = None, None
            for f_path in gen_files:
                f_name = f_path.stem.lower()
                if "vocal" in f_name:
                    vocal_path = str(f_path)
                elif any(k in f_name for k in ("instrumental", "no_vocal", "bgm", "other")):
                    bgm_path = str(f_path)
                elif not bgm_path:
                    bgm_path = str(f_path)
            if bgm_path and os.path.exists(bgm_path):
                logger.info("BS-RoFormer separation succeeded via audio_separator CLI.")
                return bgm_path, vocal_path
        else:
            logger.warning(f"audio_separator CLI failed: {res.stderr}")
    except Exception as e:
        logger.warning(f"BS-RoFormer CLI separation exception: {e}")

    return None, None


def extract_clean_bgm(
    input_audio_path: str,
    output_bgm_path: str,
    method: str = "ai_bs_roformer",
    progress_callback: Optional[Callable[[str], None]] = None
) -> bool:
    """
    Extracts pure BGM track from audio based on chosen model:
    - 'ai_bs_roformer': Band-Split RoFormer SOTA model (ep 317)
    - 'bs_roformer_ep368': Band-Split RoFormer model (ep 368)
    - 'ai_demucs': Meta AI Demucs (htdemucs)
    - 'fast_dsp': Fast FFmpeg center-channel phase cancellation
    - 'auto': Automatic cascade (BS-RoFormer -> Demucs -> Fast DSP)
    """
    m = (method or "ai_bs_roformer").lower()

    if m == "fast_dsp":
        if progress_callback:
            progress_callback("Applying instant DSP center-channel vocal reduction...")
        return remove_vocals_dsp(input_audio_path, output_bgm_path)

    if m in ("ai_demucs", "demucs"):
        if progress_callback:
            progress_callback("Isolating BGM using Meta Demucs AI Model...")
        bgm_path, _ = separate_vocals_demucs(input_audio_path, progress_callback=progress_callback)
        if bgm_path and os.path.exists(bgm_path):
            shutil.copy2(bgm_path, output_bgm_path)
            return True
        logger.warning("Demucs failed, falling back to fast DSP vocal reduction.")
        return remove_vocals_dsp(input_audio_path, output_bgm_path)

    # For BS-RoFormer options ('ai_bs_roformer', 'bs_roformer_ep368', 'auto', etc.)
    ckpt = "model_bs_roformer_ep_368_sdr_12.9628.ckpt" if m == "bs_roformer_ep368" else "model_bs_roformer_ep_317_sdr_12.9755.ckpt"

    if progress_callback:
        progress_callback(f"Isolating BGM using BS-RoFormer SOTA AI ({ckpt})...")
    
    bgm_path, _ = separate_vocals_bs_roformer(input_audio_path, model_name=ckpt, progress_callback=progress_callback)

    if bgm_path and os.path.exists(bgm_path):
        shutil.copy2(bgm_path, output_bgm_path)
        return True

    # Fallback 1: Demucs
    logger.warning("BS-RoFormer failed or unavailable, falling back to Demucs AI model.")
    if progress_callback:
        progress_callback("BS-RoFormer fallback: Isolating BGM using Meta Demucs AI Model...")
    bgm_path, _ = separate_vocals_demucs(input_audio_path, progress_callback=progress_callback)

    if bgm_path and os.path.exists(bgm_path):
        shutil.copy2(bgm_path, output_bgm_path)
        return True

    # Fallback 2: Fast DSP
    logger.warning("Demucs failed, falling back to fast DSP vocal reduction.")
    if progress_callback:
        progress_callback("AI models fallback: applying DSP center-channel vocal reduction...")
    return remove_vocals_dsp(input_audio_path, output_bgm_path)


