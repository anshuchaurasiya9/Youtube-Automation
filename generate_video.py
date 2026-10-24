import os
import asyncio
import edge_tts
from moviepy.editor import (
    AudioFileClip,
    ImageClip,
    concatenate_videoclips
)
from PIL import Image

# Voices: 
# Hindi Male: 'hi-IN-MadhurNeural', Hindi Female: 'hi-IN-SwaraNeural'
# Indian English Male: 'en-IN-PrabhatNeural', Female: 'en-IN-NeerjaNeural'
VOICE = "hi-IN-MadhurNeural"
VOICE_RATE = os.getenv("VOICE_RATE", "+65%")

async def create_voiceover(text: str, output_audio: str, voice: str = VOICE, rate: str = VOICE_RATE):
    """Generates natural voiceover using Edge TTS at 1.65x playback speed."""
    print(f"Generating voiceover at {rate} speed...")
    communicate = edge_tts.Communicate(text, voice, rate=rate)
    await communicate.save(output_audio)
    print(f"Voiceover saved to {output_audio}")

def resize_and_crop(image_path: str, target_size: tuple) -> str:
    """Prepares images to match exact aspect ratio (1920x1080 or 1080x1920)."""
    with Image.open(image_path) as img:
        img_ratio = img.width / img.height
        target_ratio = target_size[0] / target_size[1]

        if img_ratio > target_ratio:
            new_width = int(target_ratio * img.height)
            offset = (img.width - new_width) // 2
            img_cropped = img.crop((offset, 0, offset + new_width, img.height))
        else:
            new_height = int(img.width / target_ratio)
            offset = (img.height - new_height) // 2
            img_cropped = img.crop((0, offset, img.width, offset + new_height))

        resized_path = f"processed_{os.path.basename(image_path)}"
        img_cropped.resize(target_size, Image.Resampling.LANCZOS).save(resized_path)
        return resized_path

def assemble_video(audio_path: str, image_paths: list, output_video: str, is_short: bool = False):
    """Combines images evenly across the audio length and exports the MP4."""
    print("Assembling video clips...")
    audio = AudioFileClip(audio_path)
    total_duration = audio.duration

    target_resolution = (1080, 1920) if is_short else (1920, 1080)
    clip_duration = total_duration / len(image_paths)

    clips = []
    processed_temp_files = []

    for img_path in image_paths:
        processed_img = resize_and_crop(img_path, target_resolution)
        processed_temp_files.append(processed_img)

        # Create image clip with cross-fade transition
        clip = (
            ImageClip(processed_img)
            .set_duration(clip_duration)
            .crossfadein(0.5)
        )
        clips.append(clip)

    final_video = concatenate_videoclips(clips, method="compose")
    final_video = final_video.set_audio(audio)

    print("Rendering final MP4...")
    final_video.write_videofile(
        output_video,
        fps=24,
        codec="libx264",
        audio_codec="aac",
        threads=4
    )

    # Clean up intermediate resized files
    for temp_file in processed_temp_files:
        if os.path.exists(temp_file):
            os.remove(temp_file)

    print(f"Video created successfully: {output_video}")

def build_story_video(story_text: str, images: list, output_filename: str, is_short: bool = False):
    audio_temp = "temp_voiceover.mp3"
    
    # 1. Generate Voice
    asyncio.run(create_voiceover(story_text, audio_temp))

    # 2. Render Video
    assemble_video(audio_temp, images, output_filename, is_short=is_short)

    # 3. Clean up temporary audio
    if os.path.exists(audio_temp):
        os.remove(audio_temp)

if __name__ == "__main__":
    # Example Hindi Story Snippet (Premchand's Idgah)
    sample_story = (
        "रमज़ान के पूरे तीस रोज़ों के बाद आज ईद आई है। कितना मनोहर, कितना सुहावना प्रभाव है। "
        "वृक्षों पर कुछ अजीब हरियाली है, खेतों में कुछ अजीब रौनक है, आसमान पर कुछ अजीब लालिमा है। "
        "गांव में कितनी हलचल है! मेले जाने की तैयारियां हो रही हैं।"
    )

    # Provide existing image paths on your PC
    # Place sample images like img1.jpg, img2.jpg in the same folder to test
    sample_images = ["img1.jpg", "img2.jpg"]

    # True for 9:16 Shorts, False for 16:9 Long Videos
    build_story_video(
        story_text=sample_story,
        images=sample_images,
        output_filename="output_story.mp4",
        is_short=False
    )