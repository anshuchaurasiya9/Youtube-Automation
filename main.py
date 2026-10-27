"""
main.py
-------
Master Execution Pipeline for Automated YouTube Story Publishing.
Fully hands-free, resilient, scheduled, and production-hardened.
"""

import os
import sys
import shutil
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime
from dotenv import load_dotenv

# Import refactored architectural modules
from gemini_storyteller import generate_story, record_history
from media_engine import render_story_video
from uploader import authenticate_youtube, upload_video_resumable

load_dotenv()

# Setup Dual Output Logging (Rotating File + Console)
LOG_FILE = "automation.log"
logger = logging.getLogger("YouTubeAutomation")
logger.setLevel(logging.INFO)

# Console handler with UTF-8 support
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
console_formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
console_handler.setFormatter(console_formatter)
logger.addHandler(console_handler)

# Rotating file handler (up to 5MB, 3 backups, safe against file locks)
try:
    file_handler = RotatingFileHandler(LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8", delay=True)
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(console_formatter)
    logger.addHandler(file_handler)
except Exception as e:
    logger.warning(f"Could not attach rotating file handler to {LOG_FILE}: {e}")

def run_pipeline() -> int:
    """
    Executes the entire YouTube content generation and publishing pipeline.
    Returns:
        0 on success, 1 on failure.
    """
    start_time = datetime.now()
    logger.info("=" * 70)
    logger.info(f"YOUTUBE AUTOMATION RUN STARTED AT {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 70)

    work_dir = "temp_pipeline_run"
    output_video = "master_video_render.mp4"

    try:
        # Phase 1: Content & Story Generation
        logger.info("\n>>> PHASE 1: Generating Story Package via LLM Logic...")
        story = generate_story()
        
        title = story["title"]
        description = story["description"]
        tags = story.get("tags", [])
        scenes = story.get("scenes", [])
        is_short = story.get("is_short", False)

        logger.info(f"[Pipeline] Title: {title}")
        logger.info(f"[Pipeline] Format: {'Shorts (9:16)' if is_short else 'Long Form (16:9)'}")
        logger.info(f"[Pipeline] Discrete Scenes to Render: {len(scenes)}")

        if not scenes:
            raise ValueError("Story package contained zero scenes. Aborting pipeline.")

        # Phase 2: Scene-by-Scene Audio-Visual Synthesis & Video Render
        logger.info("\n>>> PHASE 2: Synthesizing Audio & Rendering Synchronized Video...")
        render_story_video(
            scenes=scenes,
            output_filename=output_video,
            is_short=is_short,
            work_dir=work_dir
        )

        if not os.path.exists(output_video) or os.path.getsize(output_video) == 0:
            raise RuntimeError(f"Video output file {output_video} was not generated.")

        # Phase 3: YouTube Publishing
        logger.info("\n>>> PHASE 3: Uploading Video to YouTube...")
        yt_client = authenticate_youtube()
        upload_response = upload_video_resumable(
            youtube=yt_client,
            file_path=output_video,
            title=title,
            description=description,
            tags=tags,
            privacy_status="private"  # Keep 'private' as default for testing / review
        )

        video_id = upload_response.get("id", "UNKNOWN")

        # Phase 4: History & State Persistence
        logger.info("\n>>> PHASE 4: Persisting Execution Metadata...")
        record_history(title)

        elapsed = (datetime.now() - start_time).total_seconds()
        logger.info("=" * 70)
        logger.info(f"[SUCCESS] Pipeline executed successfully in {elapsed:.1f} seconds!")
        logger.info(f"[PUBLISHED] https://youtu.be/{video_id}")
        logger.info("=" * 70)
        return 0

    except Exception as e:
        logger.exception(f"[CRITICAL ERROR] Pipeline execution failed: {e}")
        return 1

    finally:
        # Phase 5: Resource Cleanup
        logger.info("\n>>> PHASE 5: Cleaning Temporary Pipeline Artifacts...")
        if os.path.exists(work_dir):
            try:
                shutil.rmtree(work_dir)
                logger.info(f"Cleaned working directory: {work_dir}")
            except Exception as e:
                logger.warning(f"Could not remove {work_dir}: {e}")

        if os.path.exists(output_video):
            try:
                os.remove(output_video)
                logger.info(f"Removed temporary video file: {output_video}")
            except Exception as e:
                logger.warning(f"Could not remove {output_video}: {e}")

if __name__ == "__main__":
    exit_code = run_pipeline()
    sys.exit(exit_code)
