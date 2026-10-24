import os
import sys
import json
import re
import datetime
import urllib.parse
import urllib.request
from dotenv import load_dotenv
from google import genai
from google.genai import types
from pipeline import run_story_pipeline

# Load environment variables (.env)
load_dotenv()

# Ensure UTF-8 output on Windows consoles
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# 1. Set your Gemini API key (or set it in your system environment variables)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
POLLINATIONS_API_KEY = os.getenv("POLLINATIONS_API_KEY", "sk_pXluCOP6eRVmGVsafFsrUHL8VKHGj84o")

HISTORY_FILE = "generated_history.json"

def get_today_format():
    """
    Decides format based on schedule:
    - Monday (0), Wednesday (2), Friday (4) -> Short (9:16)
    - Tuesday (1), Saturday (5) -> Long (16:9)
    - Thursday / Sunday -> Rest or custom
    """
    weekday = datetime.datetime.today().weekday()
    if weekday in [0, 2, 4]:
        return True, "Shorts (under 60 seconds, fast-paced, punchy, humorous)"
    else:
        return False, "Long Video (engaging 3-4 minute narrative, comic drama, expressive)"

def load_past_topics():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save_topic(title):
    history = load_past_topics()
    history.append({"title": title, "date": str(datetime.date.today())})
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

# Fallback curated classic folklore stories in case of network or API issues
BACKUP_STORIES = [
    {
        "title": "बीरबल की अनोखी खिचड़ी! 😂 | Akbar Birbal Funny Story #Shorts",
        "description": "अकबर और बीरबल की इस मजेदार कहानी को देखकर आपकी हंसी नहीं रुकेगी! #AkbarBirbal #HindiKahaniya #DesiHumor",
        "tags": ["Akbar Birbal", "Hindi Stories", "Funny Hindi", "Shorts", "Desi Comedy"],
        "script": "एक बार बादशाह अकबर ने ऐलान किया कि जो भी भरी सर्दी में यमुना के ठंडे पानी में रात भर खड़ा रहेगा, उसे भारी इनाम मिलेगा। एक गरीब धोबी ने यह कारनामा कर दिखाया। लेकिन जब इनाम लेने पहुंचा, तो अकबर ने कहा कि तुम तो महल के दिए की गर्मी से बच गए! बीरबल को यह अन्याय पसंद नहीं आया। अगले दिन बीरबल ने बहुत ऊंची टहनी पर खिचड़ी की हांडी टांग दी और नीचे जमीन पर हल्की आग जला दी। अकबर ने पूछा, 'बीरबल, इतनी दूर से खिचड़ी कैसे पकेगी?' बीरबल ने मुस्कुराकर कहा, 'जहांपनाह, ठीक वैसे ही जैसे धोबी को मीलों दूर महल के दिए से गर्मी मिल गई थी!' अकबर बात समझ गए और धोबी को इनाम दे दिया।",
        "prompts": [
            "Emperor Akbar in majestic royal Mughal silk attire sitting on an ornate gold throne, smiling with wit while Birbal stands beside him gesturing humorously",
            "A poor humble villager shivering inside the freezing misty Yamuna river at night, looking toward a glowing golden palace lantern in the far distance",
            "Birbal sitting leisurely in a peaceful royal garden, watching an earthen clay pot hung 20 feet up in a tree with tiny smoke and flames below on grass",
            "Emperor Akbar laughing heartily and handing a sparkling bag of gold coins to the delighted poor villager, with Birbal smiling proudly in the sun"
        ]
    },
    {
        "title": "तेनाली रामन और चोरों की धुलाई! 🤣 | Tenali Raman Comedy #Shorts",
        "description": "तेनाली रामन ने चोरों से अपने पूरे खेत में पानी कैसे डलवाया? देखिए यह मजेदार किस्सा! #TenaliRaman #FunnyShorts #Comedy",
        "tags": ["Tenali Raman", "Shorts", "Hindi Stories", "Folk Tales", "Comedy"],
        "script": "एक रात तेनाली रामन को पता चला कि उनके घर में दो चोर छिपे हुए हैं। उन्होंने जोर से अपनी पत्नी से कहा, 'सुनती हो, आजकल चोर बहुत घूम रहे हैं। हम अपने सारे गहने और सोने के सिक्के इस भारी लोहे के बक्से में बंद करके कुएं में छुपा देते हैं।' तेनाली ने बक्से में खूब सारे भारी पत्थर भरे और जोर की आवाज के साथ कुएं में फेंक दिया। चोर बड़े खुश हुए। उन्होंने सोचा कि पहले कुएं का पानी खाली करना पड़ेगा तभी बक्सा मिलेगा। रात भर चोर कुएं से पानी निकाल-निकाल कर क्यारियों में डालते रहे। सुबह जब तेनाली बाहर आए तो मुस्कुरा कर बोले, 'धन्यवाद भाइयो, मेरे पूरे खेत में पानी डालने के लिए!' चोर सिर पर पैर रखकर भाग खड़े हुए।",
        "prompts": [
            "Tenali Raman in traditional white dhoti whispering mischievously to his wife inside a lantern-lit South Indian heritage home, two comical thieves spying through window",
            "Tenali Raman lifting a heavy studded wooden chest and tossing it with a giant dramatic splash into an ancient stone well under moonlight",
            "Two exhausted comic thieves covered in mud and sweat frantically pulling wooden buckets of water from the deep stone well into lush green garden beds",
            "Tenali Raman standing smiling in the morning golden sunrise with hands folded in gratitude as the terrified exhausted thieves run away across the fields"
        ]
    }
]

def generate_story_pollinations_fallback(prompt: str, is_short: bool) -> dict:
    """Fallback text generator using Pollinations API or curated backup stories."""
    print("[AI Story] Generating dynamic story using Pollinations AI...")
    try:
        body = json.dumps({
            "model": "openai/gpt-5.4-nano",
            "messages": [
                {"role": "system", "content": "You are a professional humorous Indian storyteller and content creator. Return ONLY valid JSON."},
                {"role": "user", "content": prompt}
            ],
            "response_format": {"type": "json_object"}
        }).encode("utf-8")
        
        req = urllib.request.Request(
            "https://gen.pollinations.ai/v1/chat/completions",
            data=body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {POLLINATIONS_API_KEY}",
                "User-Agent": "Mozilla/5.0"
            }
        )
        
        with urllib.request.urlopen(req, timeout=45) as response:
            content = response.read().decode("utf-8")
            data = json.loads(content)
            story_json_str = data["choices"][0]["message"]["content"]
            match = re.search(r"\{.*\}", story_json_str, re.DOTALL)
            if match:
                parsed = json.loads(match.group(0))
                if all(k in parsed for k in ["title", "description", "tags", "script", "prompts"]):
                    print(f"[AI Story] Dynamic Story generated: {parsed['title']}")
                    return parsed
    except Exception as err:
        print(f"[Warning] Online fallback encountered issue: {err}")

    # If online fallback fails or schema is incomplete, use curated classic folklore story
    print("[AI Story] Using curated classic humorous folklore story...")
    import random
    story = random.choice(BACKUP_STORIES).copy()
    return story

def generate_dynamic_story():
    is_short, format_desc = get_today_format()
    past_topics = [item["title"] for item in load_past_topics()[-15:]]

    prompt = f"""
    You are an expert Indian humorous storyteller and content creator.
    Generate an original, hilarious, and engaging Indian story inspired by classic tropes, 
    NCERT-style folklore (Akbar-Birbal, Tenali Raman, Sheikh Chilli, Gopal Bhar, or quirky Indian village satires).

    Requirements:
    - Format: {format_desc}
    - Tone: Funny, sarcastic, witty, entertaining Hindi narration.
    - Previous topics to avoid repeating: {past_topics}
    - Number of visual scenes: {"3 to 4" if is_short else "6 to 8"}
    
    Return STRICTLY valid JSON with this schema:
    {{
      "title": "Catchy, click-worthy YouTube title in Hinglish/Hindi with relevant emojis",
      "description": "Engaging 2-sentence description with hashtags",
      "tags": ["tag1", "tag2", "tag3"],
      "script": "Complete engaging Hindi narration text. Keep it natural for voiceover.",
      "prompts": [
         "detailed image prompt 1 for comic illustration style, high detail",
         "detailed image prompt 2...",
         ...
      ]
    }}
    """

    story_data = None
    if GEMINI_API_KEY:
        print("[AI] Prompting Gemini for today's story...")
        try:
            client = genai.Client(api_key=GEMINI_API_KEY)
            response = client.models.generate_content(
                model="gemini-3.8-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json"
                )
            )
            story_data = json.loads(response.text)
        except Exception as e:
            print(f"[Warning] Gemini API error: {e}")
            story_data = generate_story_pollinations_fallback(prompt, is_short)
    else:
        story_data = generate_story_pollinations_fallback(prompt, is_short)

    story_data["is_short"] = is_short
    return story_data

def run_daily_automation():
    story = generate_dynamic_story()
    print(f"\n[AI] Story Generated: {story['title']}")
    print(f"[AI] Format: {'Short (9:16)' if story['is_short'] else 'Long (16:9)'}")

    # Pass straight into your video pipeline
    run_story_pipeline(
        story_script=story["script"],
        scene_prompts=story["prompts"],
        title=story["title"],
        description=story["description"],
        tags=story["tags"],
        is_short=story["is_short"]
    )

    save_topic(story["title"])
    print("[SUCCESS] Content fully generated, rendered, and uploaded!")

if __name__ == "__main__":
    run_daily_automation()