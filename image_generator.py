import os
import io
import time
import re
import urllib.parse
import urllib.request
from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont

# Load environment variables from .env
load_dotenv()

POLLINATIONS_API_KEY = os.getenv("POLLINATIONS_API_KEY", "sk_pXluCOP6eRVmGVsafFsrUHL8VKHGj84o")

# High fidelity FLUX diffusion model
POLLINATIONS_MODEL = "black-forest-labs/flux.1-schnell"

def build_enhanced_prompt(base_prompt: str) -> str:
    """
    Transforms story scene prompts into cinematic, vibrant Indian storybook illustrations.
    Combines classic Amar Chitra Katha expressive storytelling with modern animated feature aesthetics.
    """
    style_prefix = (
        "Masterpiece Indian comic folklore illustration, vibrant cinematic colors, "
        "Pixar and Amar Chitra Katha aesthetic, highly expressive character faces and emotions, "
        "dramatic volumetric lighting, intricate cultural textures, detailed scenic background, 8k resolution concept art, "
    )
    clean_prompt = base_prompt.strip()
    return f"{style_prefix}{clean_prompt}"

def create_fallback_card(prompt: str, output_path: str, width: int, height: int):
    """Creates a stylized gradient scene card as last-resort fallback."""
    img = Image.new("RGB", (width, height), color=(25, 18, 45))
    draw = ImageDraw.Draw(img)
    draw.rectangle([20, 20, width - 20, height - 20], outline=(230, 190, 80), width=4)
    img.save(output_path)
    print(f"Created fallback visual card: {output_path}")
    return output_path

def generate_image(prompt: str, output_path: str, is_short: bool = False):
    """
    Generates high-definition scene illustrations using Pollinations FLUX with API key.
    Aspect ratios: 9:16 (Shorts: 768x1344) or 16:9 (Long form: 1344x768).
    """
    print(f"\n[Art AI] Generating FLUX scene for: '{prompt[:50]}...'")

    width, height = (768, 1344) if is_short else (1344, 768)
    styled_prompt = build_enhanced_prompt(prompt)
    encoded_prompt = urllib.parse.quote(styled_prompt)

    # Primary official authenticated endpoint
    primary_url = (
        f"https://gen.pollinations.ai/image/{encoded_prompt}"
        f"?model={POLLINATIONS_MODEL}&width={width}&height={height}"
        f"&nologo=true&enhance=true"
    )

    # Legacy backup endpoint
    backup_url = (
        f"https://image.pollinations.ai/prompt/{encoded_prompt}"
        f"?model=flux&width={width}&height={height}"
        f"&nologo=true&enhance=true&key={POLLINATIONS_API_KEY}"
    )

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Authorization": f"Bearer {POLLINATIONS_API_KEY}"
    }

    for target_url in [primary_url, backup_url]:
        try:
            req = urllib.request.Request(target_url, headers=headers)
            with urllib.request.urlopen(req, timeout=40) as response:
                image_data = response.read()
                if len(image_data) > 1000:
                    with open(output_path, "wb") as f:
                        f.write(image_data)
                    print(f"[Art AI] Saved HD scene ({len(image_data) // 1024} KB): {output_path}")
                    return output_path
        except Exception as e:
            print(f"[Warning] Endpoint {target_url[:35]}... encountered issue: {e}. Trying fallback...")
            time.sleep(2)

    # Fallback visual card if both fail
    return create_fallback_card(prompt, output_path, width, height)

def generate_scene_images(prompts: list, output_folder: str = "generated_scenes", is_short: bool = False) -> list:
    """Generates a batch of high-definition images from a list of scene descriptions."""
    os.makedirs(output_folder, exist_ok=True)
    image_paths = []

    for idx, prompt in enumerate(prompts):
        filename = os.path.join(output_folder, f"scene_{idx + 1}.png")
        generate_image(prompt, filename, is_short=is_short)
        image_paths.append(filename)

    return image_paths

if __name__ == "__main__":
    test_scenes = [
        "A festive rural Indian village morning with children dressed in traditional clothes walking to the Eidgah fair.",
        "A poor young boy named Hamid looking happily at village toy shops filled with colorful clay figurines."
    ]
    saved_images = generate_scene_images(test_scenes, is_short=False)
    print("Test images created:", saved_images)
