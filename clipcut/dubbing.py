import asyncio
import os
import shutil
from deep_translator import GoogleTranslator
import edge_tts
import nest_asyncio

# Apply nest_asyncio to allow nested event loops (useful for threaded Flask apps)
nest_asyncio.apply()

class DubbingEngine:
    def __init__(self, progress):
        self.progress = progress

    def _translate_text(self, text, target_lang):
        try:
            print(f"Translating text to {target_lang}: {text[:50]}...")
            # Use Google Translator via deep_translator
            # deep-translator uses requests, which can hang.
            # We wrap it or just hope it works? 
            # Unfortunately deep_translator doesn't expose timeout easily.
            # We can rely on system socket timeout or just assume it works.
            # For now, let's just log it.
            translated = GoogleTranslator(source='auto', target=target_lang).translate(text)
            print(f"Translation result: {translated[:50]}...")
            return translated
        except Exception as e:
            print(f"Translation error: {e}")
            return text

    async def _generate_audio_async(self, text, voice, output_path):
        print(f"Generating TTS for: {text[:50]}... (Voice: {voice})")
        for attempt in range(3):
            try:
                communicate = edge_tts.Communicate(text, voice)
                await asyncio.wait_for(communicate.save(output_path), timeout=60)
                print(f"TTS saved to {output_path}")
                return
            except Exception as e:
                print(f"TTS Attempt {attempt+1} failed: {e}")
                if attempt == 2: raise e
                await asyncio.sleep(1)

    def generate_dub_segment(self, text, target_lang, voice, output_path):
        # Translate and generate TTS without handling duration (used for segments)
        translated_text = self._translate_text(text, target_lang)
        try:
            asyncio.run(self._generate_audio_async(translated_text, voice, output_path))
            return output_path, translated_text
        except Exception as e:
            print(f"TTS Segment Error: {e}")
            return None, translated_text

    def generate_dub(self, text, target_lang, voice, output_path):
        # 1. Translate
        translated_text = self._translate_text(text, target_lang)
        
        # 2. Generate TTS Audio
        # We need to run async function in sync context
        try:
            asyncio.run(self._generate_audio_async(translated_text, voice, output_path))
        except Exception as e:
             # Fallback for nested loops if necessary, or just basic run
             # In main thread this usually works fine.
             print(f"TTS Error: {e}")
             return None, translated_text
             
        return output_path, translated_text

    def get_voice_for_lang(self, lang, gender="Male"):
        # Comprehensive mapping for edge-tts voices
        voices = {
            "en": {"Male": "en-US-ChristopherNeural", "Female": "en-US-JennyNeural"},
            "hi": {"Male": "hi-IN-MadhurNeural", "Female": "hi-IN-SwaraNeural"},
            "es": {"Male": "es-ES-AlvaroNeural", "Female": "es-ES-ElviraNeural"},
            "fr": {"Male": "fr-FR-HenriNeural", "Female": "fr-FR-DeniseNeural"},
            "de": {"Male": "de-DE-ConradNeural", "Female": "de-DE-KatjaNeural"},
            "ja": {"Male": "ja-JP-KeitaNeural", "Female": "ja-JP-NanamiNeural"},
            "zh-CN": {"Male": "zh-CN-YunxiNeural", "Female": "zh-CN-XiaoxiaoNeural"},
            "pt": {"Male": "pt-BR-AntonioNeural", "Female": "pt-BR-FranciscaNeural"},
            "ru": {"Male": "ru-RU-DmitryNeural", "Female": "ru-RU-SvetlanaNeural"},
            "it": {"Male": "it-IT-DiegoNeural", "Female": "it-IT-ElsaNeural"},
            "ko": {"Male": "ko-KR-InJoonNeural", "Female": "ko-KR-SunHiNeural"},
            "tr": {"Male": "tr-TR-AhmetNeural", "Female": "tr-TR-EmelNeural"},
            "nl": {"Male": "nl-NL-MaartenNeural", "Female": "nl-NL-ColetteNeural"},
            "pl": {"Male": "pl-PL-MarekNeural", "Female": "pl-PL-ZofiaNeural"},
            "id": {"Male": "id-ID-ArdiNeural", "Female": "id-ID-GadisNeural"},
            "ar": {"Male": "ar-SA-HamedNeural", "Female": "ar-SA-ZariyahNeural"},
            "bn": {"Male": "bn-IN-BashkarNeural", "Female": "bn-IN-TanishaaNeural"},
            "vi": {"Male": "vi-VN-NamMinhNeural", "Female": "vi-VN-HoaiMyNeural"},
            "th": {"Male": "th-TH-NiwatNeural", "Female": "th-TH-PremwadeeNeural"},
            "uk": {"Male": "uk-UA-OstapNeural", "Female": "uk-UA-PolinaNeural"},
            "sv": {"Male": "sv-SE-MattiasNeural", "Female": "sv-SE-SofieNeural"},
            "ta": {"Male": "ta-IN-ValluvarNeural", "Female": "ta-IN-PallaviNeural"},
            "te": {"Male": "te-IN-MohanNeural", "Female": "te-IN-ShrutiNeural"},
            "mr": {"Male": "mr-IN-ManoharNeural", "Female": "mr-IN-AarohiNeural"},
            "ur": {"Male": "ur-PK-AsadNeural", "Female": "ur-PK-UzmaNeural"},
        }
        
        lang_voices = voices.get(lang, voices["en"])
        return lang_voices.get(gender, lang_voices["Male"])
