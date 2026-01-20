import random

class Scoring:
    def rank_segments(self, analysis, transcript, clip_duration, num_clips):
        # Simple logic: create random segments of requested duration
        # A real implementation would score based on transcript keywords, audio volume, etc.
        
        video_duration = analysis["duration"]
        if video_duration < clip_duration:
            return [{"start": 0, "end": video_duration}]
            
        segments = []
        # Try to find segments that align with subtitle boundaries if possible
        # For now, just pick random start points that fit
        
        possible_starts = int(video_duration - clip_duration)
        if possible_starts <= 0:
             return [{"start": 0, "end": video_duration}]

        # Generate non-overlapping segments
        attempts = 0
        while len(segments) < num_clips and attempts < 100:
            start = random.randint(0, possible_starts)
            end = start + clip_duration
            
            # Check overlap
            overlap = False
            for s in segments:
                if not (end < s["start"] or start > s["end"]):
                    overlap = True
                    break
            
            if not overlap:
                segments.append({"start": start, "end": end})
            attempts += 1
            
        return sorted(segments, key=lambda x: x["start"])

    def clip_score(self, out, analysis, transcript):
        # Dummy score
        return round(random.uniform(7.0, 9.9), 1)

    def generate_metadata(self, out, transcript):
        # Extract text from transcript that falls within clip time
        text = ""
        start = out["start"]
        end = out["end"]
        
        words = []
        for t in transcript:
            if t["end"] > start and t["start"] < end:
                words.append(t["text"])
        
        full_text = " ".join(words)
        title = full_text[:50] + "..." if len(full_text) > 50 else full_text
        if not title:
            title = "Viral Video Clip"
            
        hashtags = "#viral #shorts #fyp"
        return title, hashtags
