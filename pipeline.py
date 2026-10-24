import os
import shutil
from image_generator import generate_scene_images
from generate_video import build_story_video
from upload_video import authenticate_youtube, upload_video

def run_story_pipeline(
    story_script: str,
    scene_prompts: list,
    title: str,
    description: str,
    tags: list,
    is_short: bool = False
):
    temp_folder = "temp_run"
    output_video = "final_output.mp4"

    try:
        # 1. Generate Images
        print("\n--- Step 1: Generating Scene Images ---")
        images = generate_scene_images(scene_prompts, output_folder=temp_folder, is_short=is_short)

        # 2. Render Video with Edge-TTS voiceover
        print("\n--- Step 2: Assembling Video and Voiceover ---")
        build_story_video(
            story_text=story_script,
            images=images,
            output_filename=output_video,
            is_short=is_short
        )

        # 3. Upload Directly to YouTube
        print("\n--- Step 3: Uploading to YouTube ---")
        youtube = authenticate_youtube()
        upload_video(
            youtube=youtube,
            file_path=output_video,
            title=title,
            description=description,
            tags=tags,
            privacy_status="private"  # Leave private while testing
        )
        print("\nPipeline executed successfully!")

    finally:
        # Cleanup temp scene files
        if os.path.exists(temp_folder):
            shutil.rmtree(temp_folder)
        if os.path.exists(output_video):
            os.remove(output_video)