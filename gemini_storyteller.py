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
    },
    {
        "title": "शेख चिल्ली और खयाली पुलाव! 🥚💥 हँसते-हँसते लोटपोट | Sheikh Chilli Comedy",
        "description": "शेख चिल्ली ने सपनों के महल में सिर हिलाया और सारे अंडे फूट गए! देखिए यह क्लासिक देसी कॉमेडी किस्सा! #SheikhChilli #ComedyShorts #DesiJokes #HindiStories",
        "tags": ["Sheikh Chilli", "Funny Kahaniya", "Desi Comedy", "Hindi Folktales", "Shorts", "Comedy Video"],
        "scenes": [
            {
                "scene_text": "सेठजी ने शेख चिल्ली को अंडों का बड़ा टोकरा सिर पर रखकर बाजार ले जाने के बदले दो आने दिए।",
                "image_prompt": "A comical goofy Sheikh Chilli balancing a gigantic wicker basket heaped with white eggs on his turban, walking proudly with a fat merchant watching."
            },
            {
                "scene_text": "शेख चिल्ली खयालों में खो गया: 'इन दो आने से मुर्गियां खरीदूंगा, फिर बकरियां, फिर हाथी और फिर राजकुमारी से शादी होगी!'",
                "image_prompt": "Dream bubble fantasy above Sheikh Chilli showing him wearing a golden crown riding a lavish decorated royal elephant, grinning foolishly in daydream."
            },
            {
                "scene_text": "आगे सोचा: 'मेरा नटखट बेटा जब मेरी बात नहीं मानेगा, तो मैं गुस्से में जोर से सिर हिलाकर कहूंगा—हरगिज नहीं!'",
                "image_prompt": "Sheikh Chilli making an exaggerated dramatic angry face, violently shaking his head left and right while walking in the middle of a dusty Indian street."
            },
            {
                "scene_text": "जैसे ही उसने सिर हिलाया, पूरा टोकरा धड़ाम से जमीन पर गिरा और सारे अंडों का ऑमलेट बन गया! सेठजी डंडा लेकर पीछे दौड़े।",
                "image_prompt": "Slapstick chaos on village road: eggs smashing everywhere with yellow yolk splashing, Sheikh Chilli eyes wide in comic shock as the angry merchant chases him with a cane."
            }
        ]
    },
    {
        "title": "गोपाल भांड़ और रसगुल्ले का भूत! 👻🍬 कंजूस हलवाई की छुट्टी | Gopal Bhar Story",
        "description": "जब कंजूस हलवाई ने बासी मिठाई बेची, तो गोपाल भांड़ ने भूत बनकर पूरी दुकान खाली करवा दी! #GopalBhar #FunnyStories #BengaliFolklore #HindiComedy",
        "tags": ["Gopal Bhar", "Funny Hindi", "Folktales", "Comedy", "Shorts", "Rasgulla"],
        "scenes": [
            {
                "scene_text": "गाँव का कंजूस हलवाई हमेशा बासी मिठाइयां बेचता और ग्राहकों से गाली-गलौज करता था। गोपाल भांड़ ने उसे सबक सिखाने की ठानी।",
                "image_prompt": "A grumpy, pot-bellied Indian sweet shop owner sitting cross-legged at a stall lined with trays of syrupy jalebis and gulab jamuns, scowling greedily."
            },
            {
                "scene_text": "रात के बारह बजे गोपाल सफेद चादर लपेटकर और मुंह पर लाल रंग लगाकर हलवाई की खिड़की पर आ धमका—'मुझे गरम-गरम रसगुल्ले चाहिए!'",
                "image_prompt": "A comical clumsy ghost wrapped in white sheets with flour-dusted face and wild eyes peeking menacingly into the lantern-lit sweet shop window at night."
            },
            {
                "scene_text": "डर के मारे हलवाई के हाथ-पैर कांपने लगे! उसने अपनी सारी ताज़ा मिठाइयों का थाल भूत की झोली में उड़ेल दिया।",
                "image_prompt": "The terrified sweet maker shaking uncontrollably on his knees, holding up a giant silver platter dripping with hot spongy rasgullas toward the sheet-clad ghost."
            },
            {
                "scene_text": "अगली सुबह जब हलवाई ने गोपाल को वही रसगुल्ले गाँव के बच्चों में बांटते देखा, तो अपना सिर पकड़कर रोने लगा!",
                "image_prompt": "Gopal Bhar laughing heartily in the morning sun feeding delicious sweets to joyful village children while the depressed sweet maker slumps on a stool in background."
            }
        ]
    },
    {
        "title": "पंडितजी और तीन ठगों का कुत्ता-बकरा कांड! 🐐🐕 मूर्खता की हद | Panchatantra Comedy",
        "description": "तीन ठगों ने कैसे एक मोटे ताजे बकरे को कुत्ता बताकर पंडितजी को चपत लगा दी? देखिए यह मजेदार किस्सा! #Panchatantra #FunnyFolktale #DesiComedy #Shorts",
        "tags": ["Panchatantra", "Brahmin And Goat", "Comedy Shorts", "Hindi Kahani", "Desi Humor"],
        "scenes": [
            {
                "scene_text": "पंडितजी यजमान से मिला मोटा-ताज़ा बकरा अपने कंधे पर लादकर खुशी-खुशी घर लौट रहे थे।",
                "image_prompt": "An eccentric Indian Pandit with tilak on forehead walking joyfully down a country path with a chubby, cheerful horned black goat resting on his shoulders."
            },
            {
                "scene_text": "रास्ते में तीन चालाक ठगों ने योजना बनाई। पहले ठग ने आकर कहा, 'पंडितजी, कंधे पर यह गंदा कुत्ता क्यों लाद रखा है?'",
                "image_prompt": "A sly cunning rogue villager pointing dramatically at the goat, whispering with mocked disgust as the Pandit looks puzzled and annoyed."
            },
            {
                "scene_text": "आगे चलकर दूसरे और तीसरे ठग ने भी कहा, 'राम-राम! पंडित होकर मरा हुआ बछड़ा और पागल कुत्ता ढो रहे हो!'",
                "image_prompt": "Two more mischievous villagers acting horrified with hands on their heads while the bewildered Pandit starts sweating nervously inspecting his own goat."
            },
            {
                "scene_text": "पंडितजी घबरा गए कि यह कोई भूतिया जानवर है! उन्होंने बकरे को तुरंत फेंका और जान बचाकर धोती संभालते हुए भागे। ठगों की दावत हो गई!",
                "image_prompt": "The panicked Pandit tossing the goat into the air and sprinting away holding his saffron dhoti, while the three laughing thieves high-five around the happy goat."
            }
        ]
    },
    {
        "title": "मुल्ला नसरुद्दीन का गायब गधा! 🐴🔍 हँसी नहीं रोक पाओगे | Mullah Nasruddin Jokes",
        "description": "मुल्ला नसरुद्दीन बैठकर गधे गिनते तो 9 निकलते, उतरते तो 10! जानिए इस बेवकूफी का मजेदार रहस्य! #MullahNasruddin #FunnyShorts #DesiJokes #Comedy",
        "tags": ["Mullah Nasruddin", "Funny Story", "Comedy Shorts", "Desi Jokes", "Hindi Kahani"],
        "scenes": [
            {
                "scene_text": "मुल्ला नसरुद्दीन मेले से दस गधे खरीदकर अपने गाँव की तरफ निकले।",
                "image_prompt": "A whimsical Mullah Nasruddin with a huge white turban riding a donkey leading a line of nine playful donkeys through a picturesque dusty village trail."
            },
            {
                "scene_text": "सड़क पर बैठे-बैठे उन्होंने गधे गिने—'एक, दो, तीन... नौ! अरे, दसवां गधा कहाँ गया?' मुल्ला के पसीने छूट गए।",
                "image_prompt": "Mullah Nasruddin sitting atop his donkey frantically counting his fingers with comical wide-eyed panic as he peers behind at the line of donkeys."
            },
            {
                "scene_text": "वे गधे से नीचे उतरे और फिर से जमीन पर खड़े होकर गिने—'अरे, अब तो पूरे दस हैं!'",
                "image_prompt": "Mullah Nasruddin standing on the ground scratching his beard with a relieved silly grin while counting each donkey pointing with a wooden stick."
            },
            {
                "scene_text": "फिर से गधे पर चढ़े और गिना तो फिर नौ! मुल्ला बोले, 'भाई, इस गधे पर बैठकर चलने से तो एक गधा गायब हो जाता है, मैं पैदल ही ठीक हूँ!'",
                "image_prompt": "Comical closing visual: Mullah happily walking on foot in front of all ten donkeys sweating in the heat, utterly convinced of his own brilliant logic."
            }
        ]
    },
    {
        "title": "बीरबल और दिल्ली के कौवों का हिसाब! 🦅😂 अकबर हुए हैरान | Birbal Ki Chaturai",
        "description": "अकबर ने पूछा दिल्ली में कितने कौवे हैं? बीरबल का ऐसा जवाब सुनकर पूरा दरबार लोटपोट हो गया! #AkbarBirbal #BirbalComedy #MughalSatire #HindiStories",
        "tags": ["Akbar Birbal", "Birbal Ki Chaturai", "Comedy Stories", "Historical Satire", "Shorts"],
        "scenes": [
            {
                "scene_text": "एक शाम दरबार की बालकनी से उड़ते कौवों को देखकर अकबर ने बीरबल की परीक्षा लेने की सोची।",
                "image_prompt": "Emperor Akbar standing on a grand royal palace balcony overlooking the Yamuna river at sunset, pointing smugly at a flock of black crows flying across the sky."
            },
            {
                "scene_text": "अकबर ने मुस्कुरा कर पूछा, 'बीरबल, क्या तुम बता सकते हो कि हमारे पूरे शहर में कुल कितने कौवे हैं?'",
                "image_prompt": "Mughal courtiers snickering and whispering behind their hands, thinking Birbal is finally trapped by the Emperor's impossible question."
            },
            {
                "scene_text": "बीरबल ने बिना पलक झपकाए तुरंत कहा, 'हुजूर, हमारी राजधानी में ठीक पचास हजार चार सौ बत्तीस कौवे हैं!'",
                "image_prompt": "Birbal smiling with supreme confidence, touching his heart with one hand and making a witty royal salam gesture before the astounded Emperor."
            },
            {
                "scene_text": "अकबर बोले, 'अगर कम या ज्यादा निकले तो?' बीरबल बोले, 'कम निकले तो पड़ोस के राज्य रिश्तेदारी में गए हैं, ज्यादा हुए तो उनके रिश्तेदार यहाँ छुट्टियां मनाने आए हैं!'",
                "image_prompt": "Emperor Akbar and the entire royal Mughal court bursting into roaring laughter as Birbal winks playfully under the palace chandeliers."
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
    You are an expert Indian comedic scriptwriter and folklore satirist specializing in viral, laugh-out-loud YouTube content.
    Generate an intensely funny, cliché, and entertaining Indian folk comedy or satirical village tale.

    ICONIC COMEDY TROPES TO LEVERAGE (Pick one entertaining angle):
    1. Classic Sheikh Chilli 'Khayali Pulao': Wild daydreaming leading to comical real-life disasters.
    2. Witty Courtier (Akbar-Birbal, Tenali Raman, Gopal Bhar): Outsmarting greedy zamindars, arrogant scholars, or stingy halwais.
    3. The Overconfident Desi Jugaad: A villager creating an absurd invention or scheme that backfires hilariously.
    4. The Ultra-Stingy Sethji / Greedy Merchant: Trying to save two pennies and losing his turban or pride in the process.
    5. Village Rumor & Superstition Chaos: A tiny misunderstanding (like a lost donkey or a harmless goat) treated like a ghost or imperial crisis.

    TONE & HUMOR GUIDELINES:
    - Language: Conversational, energetic Hindi with witty, relatable phrasing ('अरे बाप रे!', 'सारा खेल ही पलट गया', 'सिस्टम ही हिल गया').
    - Pacing: Fast-paced, punchy, buildup with a hilarious climax and ironic final punchline.
    - Format: {format_desc}
    - Exact Scene Count: Exactly {min_scenes} to {max_scenes} discrete visual scenes.

    CRITICAL SCENE-BY-SCENE REQUIREMENT:
    You must divide the story into discrete, synchronized scenes.
    For each scene:
    - 'scene_text': The exact Hindi narration spoken during this visual (1-2 punchy, expressive sentences).
    - 'image_prompt': A vivid, highly descriptive English visual prompt for generating the illustration in FLUX diffusion. Include exaggerated comical facial expressions (eyes popping, jaws dropping, sneaky grins), character clothing, dynamic action, warm lighting, and traditional Indian storybook aesthetics.
    
    Previous topics to AVOID repeating: {json.dumps(past_topics, ensure_ascii=False)}

    Return STRICTLY valid JSON adhering to the following structure:
    {{
      "title": "Catchy, click-worthy YouTube title in Hinglish/Hindi with relevant emojis",
      "description": "Engaging 2-3 sentence description with hashtags",
      "tags": ["tag1", "tag2", "tag3", "tag4", "tag5"],
      "scenes": [
        {{
          "scene_text": "Hindi narration for this visual moment...",
          "image_prompt": "Detailed comedic visual scene description with expressive characters and environment..."
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
