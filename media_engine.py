"""
media_engine.py
---------------
Per-scene Audio-Visual synchronization, Edge-TTS synthesis,
resilient Pollinations.ai image generation with fallback prompts,
and memory-efficient MoviePy v2.x / v1.x composition.
"""

import os
import re
import time
import asyncio
import logging
import urllib.parse
import urllib.request
from typing import List, Dict, Any, Tuple
from PIL import Image, ImageDraw
import edge_tts
from dotenv import load_dotenv
from tenacity import retry, stop_after_attempt, wait_exponential

# Dual compatibility imports for MoviePy v2.x and v1.x
try:
    from moviepy import ImageClip, AudioFileClip, concatenate_videoclips
except (ImportError, AttributeError):
    from moviepy.editor import ImageClip, AudioFileClip, concatenate_videoclips

load_dotenv()
logger = logging.getLogger("YouTubeAutomation")

# Audio Voice Configurations
HINDI_VOICE = "hi-IN-MadhurNeural"
VOICE_RATE = os.getenv("VOICE_RATE", "+65%")  # 1.65x playback speed for energetic narration

# Artistic prompt enhancement for Pollinations FLUX
STYLE_DIRECTION = (
    "Masterpiece Indian comic folklore illustration, rich vibrant saturated colors, "
    "Pixar and Amar Chitra Katha aesthetic, highly expressive character faces, "
    "dramatic atmospheric lighting, intricate cultural details, 8k resolution concept art, "
)

GENERALIZED_FALLBACK_PROMPT = (
    "A vivid and colorful Indian traditional storybook folklore scene with expressive characters, "
    "warm golden sunlight, rustic village architecture, highly detailed illustration."
)

def _set_clip_duration(clip, duration: float):
    """Compatible duration setter for MoviePy 2.x (.with_duration) and 1.x (.set_duration)."""
    if hasattr(clip, "with_duration"):
        return clip.with_duration(duration)
    return clip.set_duration(duration)

def _set_clip_audio(clip, audio):
    """Compatible audio setter for MoviePy 2.x (.with_audio) and 1.x (.set_audio)."""
    if hasattr(clip, "with_audio"):
        return clip.with_audio(audio)
    return clip.set_audio(audio)

def _apply_crossfade(clip, duration: float = 0.3):
    """Compatible transition setter across MoviePy versions."""
    if hasattr(clip, "with_effects"):
        try:
            from moviepy.video.fx import CrossFadeIn
            return clip.with_effects([CrossFadeIn(duration)])
        except Exception:
            pass
    if hasattr(clip, "crossfadein"):
        return clip.crossfadein(duration)
    return clip

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=3, max=15),
    reraise=True
)
def synthesize_scene_audio(text: str, output_path: str, voice: str = HINDI_VOICE, rate: str = VOICE_RATE) -> str:
    """Generates an edge-tts audio file for a single discrete scene at 1.65x speed."""
    logger.info(f"[TTS] Synthesizing audio (rate={rate}): '{text[:45]}...'")
    
    async def _run():
        communicate = edge_tts.Communicate(text, voice, rate=rate)
        await communicate.save(output_path)

    asyncio.run(_run())
    if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
        raise IOError(f"Audio file {output_path} was not written properly.")
    
    return output_path

def _create_emergency_card(prompt: str, output_path: str, width: int, height: int) -> str:
    """Creates a stylized decorative visual card if image APIs fail completely."""
    img = Image.new("RGB", (width, height), color=(28, 20, 48))
    draw = ImageDraw.Draw(img)
    draw.rectangle([25, 25, width - 25, height - 25], outline=(225, 185, 75), width=4)
    img.save(output_path)
    logger.warning(f"[Art Engine] Generated emergency visual card: {output_path}")
    return output_path

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=2, max=12),
    reraise=True
)
def _fetch_pollinations_raw(url: str, output_path: str, headers: dict) -> bool:
    """Network fetcher with exponential retry."""
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=35) as response:
        data = response.read()
        if len(data) > 1000:
            with open(output_path, "wb") as f:
                f.write(data)
            return True
    return False

def download_scene_image(prompt: str, output_path: str, is_short: bool = False) -> str:
    """
    Downloads scene image from Pollinations.ai with FLUX quality,
    handling aspect ratios, retries, and generalized prompt fallback.
    """
    width, height = (768, 1344) if is_short else (1344, 768)
    pollen_key = os.getenv("POLLINATIONS_API_KEY", "")

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    }
    if pollen_key:
        headers["Authorization"] = f"Bearer {pollen_key}"

    # Construct primary candidate prompt
    full_prompt = f"{STYLE_DIRECTION}{prompt.strip()}"
    encoded = urllib.parse.quote(full_prompt)

    # Candidate endpoints (Official gen API and legacy public fallback)
    urls_to_try = [
        f"https://gen.pollinations.ai/image/{encoded}?model=black-forest-labs/flux.1-schnell&width={width}&height={height}&nologo=true&enhance=true",
        f"https://image.pollinations.ai/prompt/{encoded}?model=flux&width={width}&height={height}&nologo=true&enhance=true"
    ]
    if pollen_key:
        urls_to_try[1] += f"&key={pollen_key}"

    logger.info(f"[Art Engine] Downloading image for: '{prompt[:45]}...'")

    # Attempt primary prompt
    for url in urls_to_try:
        try:
            if _fetch_pollinations_raw(url, output_path, headers):
                size_kb = os.path.getsize(output_path) // 1024
                logger.info(f"[Art Engine] Saved scene visual ({size_kb} KB): {output_path}")
                return output_path
        except Exception as err:
            logger.warning(f"[Art Engine] Primary image fetch failed on {url[:35]}... ({err})")

    # Graceful fallback: Retry with Generalized Fallback Prompt
    logger.info("[Art Engine] Trying generalized Indian folklore fallback prompt...")
    gen_encoded = urllib.parse.quote(f"{STYLE_DIRECTION}{GENERALIZED_FALLBACK_PROMPT}")
    fallback_url = f"https://image.pollinations.ai/prompt/{gen_encoded}?width={width}&height={height}&nologo=true"
    if pollen_key:
        fallback_url += f"&key={pollen_key}"

    try:
        if _fetch_pollinations_raw(fallback_url, output_path, headers):
            logger.info(f"[Art Engine] Saved fallback visual: {output_path}")
            return output_path
    except Exception as err:
        logger.error(f"[Art Engine] Generalized fallback prompt also failed: {err}")

    # Ultimate offline fallback
    return _create_emergency_card(prompt, output_path, width, height)

def prepare_image_dimensions(image_path: str, target_size: Tuple[int, int]) -> str:
    """Crops and scales image to exact aspect ratio without distortion."""
    with Image.open(image_path) as img:
        img_ratio = img.width / img.height
        target_ratio = target_size[0] / target_size[1]

        if img_ratio > target_ratio:
            new_width = int(target_ratio * img.height)
            offset = (img.width - new_width) // 2
            cropped = img.crop((offset, 0, offset + new_width, img.height))
        else:
            new_height = int(img.width / target_ratio)
            offset = (img.height - new_height) // 2
            cropped = img.crop((0, offset, img.width, offset + new_height))

        # Overwrite with precisely resized image
        cropped.resize(target_size, Image.Resampling.LANCZOS).save(image_path)
    return image_path

def build_scene_clip(image_path: str, audio_path: str, target_size: Tuple[int, int]):
    """
    Creates a discrete MoviePy clip where the image is strictly pinned
    to that specific audio file's exact duration.
    """
    # Ensure correct pixel dimensions
    prepare_image_dimensions(image_path, target_size)

    audio_clip = AudioFileClip(audio_path)
    duration = audio_clip.duration

    # Image clip pinned strictly to scene audio duration
    img_clip = ImageClip(image_path)
    img_clip = _set_clip_duration(img_clip, duration)
    img_clip = _set_clip_audio(img_clip, audio_clip)
    img_clip = _apply_crossfade(img_clip, 0.25)

    return img_clip, audio_clip

def render_story_video(
    scenes: List[Dict[str, str]],
    output_filename: str,
    is_short: bool,
    work_dir: str = "temp_render"
) -> str:
    """
    Master video assembly function:
    1. Iterates scene-by-scene.
    2. Synthesizes discrete TTS and downloads discrete image.
    3. Measures scene audio duration and locks the image duration to it.
    4. Sequentially concatenates all scenes into a synchronized MP4.
    """
    os.makedirs(work_dir, exist_ok=True)
    target_resolution = (1080, 1920) if is_short else (1920, 1080)
    
    scene_clips = []
    audio_clips_to_close = []

    try:
        logger.info(f"--- Step 1: Processing {len(scenes)} Scenes in Perfect Sync ---")
        for i, scene in enumerate(scenes, 1):
            text = scene["scene_text"]
            prompt = scene["image_prompt"]
            
            audio_path = os.path.join(work_dir, f"audio_scene_{i}.mp3")
            image_path = os.path.join(work_dir, f"visual_scene_{i}.png")

            # 1. Synthesize audio snippet
            synthesize_scene_audio(text, audio_path)

            # 2. Download visual
            download_scene_image(prompt, image_path, is_short=is_short)

            # 3. Build synchronized clip
            clip, audio = build_scene_clip(image_path, audio_path, target_resolution)
            scene_clips.append(clip)
            audio_clips_to_close.append(audio)
            logger.info(f"  [Scene {i}] Synced: {audio.duration:.2f}s | Visual: {os.path.basename(image_path)}")

        logger.info(f"--- Step 2: Concatenating and Rendering Final MP4 ({output_filename}) ---")
        final_video = concatenate_videoclips(scene_clips, method="compose")

        final_video.write_videofile(
            output_filename,
            fps=24,
            codec="libx264",
            audio_codec="aac",
            threads=4,
            preset="fast",
            logger=None  # Suppress verbose terminal spam
        )

        final_video.close()
        logger.info(f"[Video Engine] Successfully generated synchronized video: {output_filename}")
        return output_filename

    finally:
        # Close all clip references to release file locks on Windows
        for c in scene_clips:
            try:
                c.close()
            except Exception:
                pass
        for a in audio_clips_to_close:
            try:
                a.close()
            except Exception:
                pass

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    test_scenes = [
        {
            "scene_text": "एक गाँव में एक बहुत ही चतुर बीरबल रहते थे।",
            "image_prompt": "Birbal smiling thoughtfully in an ancient Indian village"
        },
        {
            "scene_text": "उन्होंने राजा को एक बहुत ही मजेदार सलाह दी।",
            "image_prompt": "Birbal talking happily to Emperor Akbar inside a royal Mughal palace"
        }
    ]
    out = render_story_video(test_scenes, "test_sync_video.mp4", is_short=True, work_dir="temp_test")
    print("Test video created:", out)
