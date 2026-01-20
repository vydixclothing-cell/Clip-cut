import os
from faster_whisper import WhisperModel

class SubtitleEngine:
    def __init__(self, progress):
        self.progress = progress
        # Use small model for better accuracy
        self.model_size = "small" 

    def transcribe(self, src_path):
        model = WhisperModel(self.model_size, device="cpu", compute_type="int8")
        segments, info = model.transcribe(src_path, beam_size=5)
        
        result = []
        for segment in segments:
            result.append({
                "start": segment.start,
                "end": segment.end,
                "text": segment.text.strip()
            })
        return result
