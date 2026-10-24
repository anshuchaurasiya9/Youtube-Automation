"""
gemini_storyteller.py
---------------------
Architectural module for prompt engineering, schema validation,
schedule detection, and resilient LLM content generation using
google-genai structured JSON output with fallback mechanisms.
"""

import os
import sys
import json
import datetime
import logging
import urllib.parse
import urllib.request
from typing import List, Tuple, Dict, Any
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

# Load environment configuration
load_dotenv()

# Ensure Windows consoles print Hindi Unicode cleanly
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

logger = logging.getLogger("YouTubeAutomation")

# Pydantic schema for structured generation
class SceneItem(BaseModel):
    scene_text: str = Field(
        description="Narration text in Hindi for this specific visual scene. Natural, expressive, and conversational."
    )
    image_prompt: str = Field(
        description="Detailed English image generation prompt describing the visual scene characters, action, setting, and lighting."
    )

class StoryPackage(BaseModel):
    title: str = Field(description="Catchy, high-CTR YouTube title in Hindi/Hinglish with emojis.")
    description: str = Field(description="Engaging 2-3 sentence description with relevant hashtags.")
    tags: List[str] = Field(description="List of 5-8 SEO tags for YouTube metadata.")
    scenes: List[SceneItem] = Field(
        description="Ordered list of discrete scenes ensuring 1:1 synchronization between narration and visual."
    )

# Curated emergency fallback stories if all remote LLMs are unreachable
OFFLINE_BACKUP_STORIES = [
    {
        "title": "बीरबल की अनोखी खिचड़ी! 😂 | Akbar Birbal Funny Story #Shorts",
        "description": "अकबर और बीरबल की इस सदाबहार मजेदार कहानी को देखकर हंसी नहीं रुकेगी! #AkbarBirbal #HindiKahaniya #DesiHumor #Comedy",
        "tags": ["Akbar Birbal", "Hindi Stories", "Funny Hindi", "Shorts", "Desi Comedy", "Kahani"],
        "scenes": [
            {
                "scene_text": "एक कड़कड़ाती सर्दियों की रात में, बादशाह अकबर ने ऐलान किया कि जो भी यमुना के बर्फीले पानी में रात भर खड़ा रहेगा, उसे भारी इनाम मिलेगा।",
                "image_prompt": "Emperor Akbar in royal Mughal attire announcing an imperial decree in an opulent marble palace courtyard under cold winter moonlight."
            },
            {
                "scene_text": "एक गरीब धोबी ने यह कर दिखाया, लेकिन अकबर ने कहा कि तुम तो दूर महल के दिए की गर्मी से बच गए, इसलिए इनाम नहीं मिलेगा!",
                "image_prompt": "A poor humble Indian villager shivering in cold Yamuna river water at night, looking at a distant glowing golden lantern on a high palace balcony."
            },
            {
                "scene_text": "अगले दिन बीरबल ने बहुत ऊंची टहनी पर खिचड़ी की हांडी टांग दी और जमीन पर हल्की सी आग जला दी। अकबर बोले, 'बीरबल, इतनी दूर से खिचड़ी कैसे पकेगी?'",
                "image_prompt": "Birbal sitting comfortably in a lush royal garden, smiling as a cooking pot hangs 20 feet high in a tree with tiny smoke burning far below on the ground."
            },
            {
                "scene_text": "बीरबल ने मुस्कुरा कर कहा, 'हुजूर, ठीक वैसे ही जैसे धोबी को मीलों दूर महल के दिए से गर्मी मिल गई थी!' अकबर समझ गए और धोबी को सोने के सिक्कों से नवाजा।",
                "image_prompt": "Emperor Akbar laughing heartily and rewarding a heavy pouch of gold coins to the delighted poor villager, with Birbal smiling proudly in the sun."
            }
        ]
    },
    {
        "title": "तेनाली रामन और कुएं के चोर! 🤣 | Tenali Raman Comedy Folktale",
        "description": "तेनाली रामन ने चोरों से अपने पूरे खेत में पानी कैसे डलवाया? देखिए यह मजेदार किस्सा! #TenaliRaman #FunnyShorts #Comedy #FolkTales",
        "tags": ["Tenali Raman", "Shorts", "Hindi Stories", "Folk Tales", "Comedy", "Desi Stories"],
        "scenes": [
            {
                "scene_text": "एक रात तेनाली रामन को भनक लगी कि दो शातिर चोर उनके आंगन के पीछे झाड़ियों में छिपे हुए हैं।",
                "image_prompt": "Tenali Raman in a traditional dhoti noticing two comical shadowy thieves hiding behind banana leaves outside his southern Indian home at dusk."
            },
            {
                "scene_text": "तेनाली ने जोर से पत्नी से कहा, 'सुनती हो, आजकल चोर घूम रहे हैं, इसलिए सारे सोने के गहने इस भारी संदूक में भरकर कुएं में डाल देते हैं!'",
                "image_prompt": "Tenali Raman whispering cleverly to his wife inside a lantern-lit heritage Indian home while pointing subtly toward the window."
            },
            {
                "scene_text": "तेनाली ने संदूक में खूब सारे भारी पत्थर भरे और जोर के छपाक के साथ उसे कुएं में धकेल दिया। चोर खुशी से फूले नहीं समाए।",
                "image_prompt": "Tenali Raman tossing a large heavy brass-studded wooden chest with a giant dramatic splash into an ancient stone water well in his garden."
            },
            {
                "scene_text": "रात भर दोनों चोर कुएं से बाल्टी भर-भर कर पानी निकालते रहे ताकि संदूक तक पहुंच सकें, और वो सारा पानी तेनाली के सूखे खेतों में बहता रहा।",
                "image_prompt": "Two exhausted comical thieves soaked in water and sweat frantically pulling wooden buckets from the stone well into vegetable garden beds under the moon."
            },
            {
                "scene_text": "सुबह तेनाली हाथ जोड़कर बाहर आए और बोले, 'धन्यवाद भाइयो, मेरे सारे पौधों को पानी देने के लिए!' चोर बदहवास होकर सिर पर पैर रखकर भागे।",
                "image_prompt": "Tenali Raman standing in the golden morning sunrise with folded hands thanking the terrified tired thieves as they run away across green fields."
            }
        ]
    }
]

def determine_schedule_format() -> Tuple[bool, str, int, int]:
    """
    Decides video format based on Day of Week:
    - Monday (0), Wednesday (2), Friday (4) -> Shorts (9:16, 3-4 scenes, under 50s)
    - Tuesday (1), Saturday (5), Sunday (6), Thursday (3) -> Long Form (16:9, 7-9 scenes, 3-4 mins)
    
    Returns:
        (is_short, format_description, min_scenes, max_scenes)
    """
    weekday = datetime.datetime.today().weekday()
    if weekday in [0, 2, 4]:
        return (
            True,
            "YouTube Shorts (fast-paced, punchy, humorous, total narration strictly under 50 seconds)",
            3,
            4
        )
    else:
        return (
            False,
            "YouTube Long Form Video (deep comic narrative, expressive character dialogues, 3-4 minutes total narration)",
            7,
            9
        )

def load_history(history_file: str = "generated_history.json") -> List[Dict[str, str]]:
    """Loads past topic titles from local history file."""
    if os.path.exists(history_file):
        try:
            with open(history_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Could not read history file {history_file}: {e}")
    return []

def record_history(title: str, history_file: str = "generated_history.json") -> None:
    """Appends newly generated topic to history file."""
    history = load_history(history_file)
    history.append({
        "title": title,
        "date": str(datetime.date.today())
    })
    try:
        with open(history_file, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
        logger.info(f"Recorded '{title}' into {history_file}")
    except Exception as e:
        logger.error(f"Failed to record history to {history_file}: {e}")

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=3, max=20),
    reraise=True
)
def _generate_with_gemini(api_key: str, prompt: str, model_candidate: str = "gemini-2.5-flash") -> Dict[str, Any]:
    """Invokes google-genai structured JSON mode with automatic model fallback."""
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)
    
    # Try preferred model first; if deprecated/unavailable (404), fall back to modern stable models
    models_to_try = [model_candidate, "gemini-3.8-flash", "gemini-2.0-flash"]
    last_err = None

    for m in models_to_try:
        try:
            logger.info(f"[LLM] Requesting story from Gemini ({m})...")
            response = client.models.generate_content(
                model=m,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=StoryPackage
                )
            )
            data = json.loads(response.text)
            logger.info(f"[LLM] Gemini ({m}) successfully returned structured story.")
            return data
        except Exception as e:
            last_err = e
            err_str = str(e)
            if "404" in err_str or "NOT_FOUND" in err_str or "not available" in err_str:
                logger.warning(f"[LLM] Model {m} returned 404/unavailable. Trying next model...")
                continue
            else:
                # Other errors (e.g. 403 or network) should trigger retry or fallback
                raise e

    raise last_err

def _generate_with_pollinations_fallback(prompt: str) -> Dict[str, Any]:
    """Generates structured story JSON using Pollinations AI (supports both free keyless and pollen key)."""
    logger.info("[LLM] Generating story via Pollinations AI...")
    pollen_key = os.getenv("POLLINATIONS_API_KEY", "")
    
    if pollen_key:
        body = json.dumps({
            "model": "openai/gpt-5.4-nano",
            "messages": [
                {"role": "system", "content": "You are a master Indian humorous storyteller. Return STRICTLY valid JSON conforming to the requested schema."},
                {"role": "user", "content": prompt}
            ],
            "response_format": {"type": "json_object"}
        }).encode("utf-8")

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {pollen_key}",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        }

        req = urllib.request.Request(
            "https://gen.pollinations.ai/v1/chat/completions",
            data=body,
            headers=headers
        )

        with urllib.request.urlopen(req, timeout=45) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            content = result["choices"][0]["message"]["content"]
            data = json.loads(content)
            if "title" in data and "scenes" in data and len(data["scenes"]) > 0:
                return data
    else:
        # 100% Free unauthenticated keyless tier
        body = json.dumps({
            "messages": [
                {"role": "system", "content": "You are a master Indian humorous storyteller. Return STRICTLY valid JSON conforming to the schema with title, description, tags, and scenes."},
                {"role": "user", "content": prompt}
            ],
            "jsonMode": True
        }).encode("utf-8")

        req = urllib.request.Request(
            "https://text.pollinations.ai/",
            data=body,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
            }
        )

        with urllib.request.urlopen(req, timeout=45) as resp:
            content = resp.read().decode("utf-8")
            import re
            m = re.search(r"\{.*\}", content, re.DOTALL)
            if m:
                data = json.loads(m.group(0))
                if "title" in data and "scenes" in data and len(data["scenes"]) > 0:
                    return data

    raise ValueError("Pollinations response did not contain valid scenes schema.")

def generate_story() -> Dict[str, Any]:
    """
    Main entry point for story generation.
    Enforces schedule, past topic avoidance, and structured scene generation.
    """
    is_short, format_desc, min_scenes, max_scenes = determine_schedule_format()
    past_topics = [item["title"] for item in load_history()[-20:]]

    prompt = f"""
    You are an expert Indian humorous storyteller and creative scriptwriter for viral YouTube videos.
    Generate an original, hilarious, and engaging story inspired by classic Indian folk satire,
    Akbar-Birbal, Tenali Raman, Sheikh Chilli, Gopal Bhar, or quirky modern Indian village situations.

    Video Format: {format_desc}
    Target Scene Count: Exactly {min_scenes} to {max_scenes} discrete visual scenes.
    Narration Language: Natural, conversational Hindi (laced with witty Hinglish expressions where fun).
    
    CRITICAL SCENE-BY-SCENE REQUIREMENT:
    You must divide the story into discrete, synchronized scenes.
    For each scene:
    - 'scene_text': The exact Hindi narration spoken during this visual (1-2 sentences).
    - 'image_prompt': A vivid, highly descriptive English visual prompt for generating the illustration (characters, clothes, facial emotion, environment, lighting).
    
    Previous topics to AVOID repeating: {json.dumps(past_topics, ensure_ascii=False)}

    Return STRICTLY valid JSON adhering to the following structure:
    {{
      "title": "Catchy, click-worthy YouTube title in Hinglish/Hindi with relevant emojis",
      "description": "Engaging 2-3 sentence description with hashtags",
      "tags": ["tag1", "tag2", "tag3", "tag4", "tag5"],
      "scenes": [
        {{
          "scene_text": "Hindi narration for this visual moment...",
          "image_prompt": "Detailed cinematic visual scene description..."
        }}
      ]
    }}
    """

    story_data = None
    gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")

    if gemini_key:
        try:
            story_data = _generate_with_gemini(gemini_key, prompt, model_candidate="gemini-2.5-flash")
        except Exception as e:
            logger.warning(f"[LLM] Gemini generation failed ({e}). Attempting free AI fallback...")

    if not story_data:
        try:
            story_data = _generate_with_pollinations_fallback(prompt)
        except Exception as e:
            logger.error(f"[LLM] Pollinations AI fallback failed ({e}). Loading curated folklore story...")
            import random
            story_data = random.choice(OFFLINE_BACKUP_STORIES).copy()

    # Stamp format metadata
    story_data["is_short"] = is_short
    logger.info(f"[LLM] Final story selected: '{story_data.get('title')}' with {len(story_data.get('scenes', []))} scenes.")
    return story_data

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    story = generate_story()
    print("\n--- Generated Story Package ---")
    print("Title:", story["title"])
    print("Format:", "Shorts (9:16)" if story["is_short"] else "Long (16:9)")
    print(f"Total Scenes: {len(story['scenes'])}")
    for i, sc in enumerate(story["scenes"], 1):
        print(f"  [{i}] Text: {sc['scene_text'][:40]}... | Visual: {sc['image_prompt'][:40]}...")
