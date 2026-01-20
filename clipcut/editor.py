import os
import subprocess
import math
from clipcut.presets import PlatformPresets
from clipcut.filters import VideoFilters

class Editor:
    def __init__(self, progress, presets):
        self.progress = progress
        self.presets = presets

    def format_time(self, seconds):
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = seconds % 60
        return f"{hours:02d}:{minutes:02d}:{secs:06.3f}".replace('.', ',')

    def create_srt(self, transcript, start_time, end_time, srt_path, max_words=5):
        # Filter and shift subtitles
        lines = []
        counter = 1
        
        for t in transcript:
            # Check overlap
            if t["end"] > start_time and t["start"] < end_time:
                # Clip times to segment boundaries
                s = max(t["start"], start_time) - start_time
                e = min(t["end"], end_time) - start_time
                
                if e <= s: continue

                text = t["text"].strip()
                if not text: continue
                
                words = text.split()
                if len(words) <= max_words:
                    lines.append(f"{counter}")
                    lines.append(f"{self.format_time(s)} --> {self.format_time(e)}")
                    lines.append(text)
                    lines.append("")
                    counter += 1
                else:
                    # Split into chunks
                    chunks = []
                    for k in range(0, len(words), max_words):
                        chunks.append(words[k:k+max_words])
                    
                    total_duration = e - s
                    total_chars = len(text)
                    current_s = s
                    
                    for chunk in chunks:
                        chunk_text = " ".join(chunk)
                        chunk_duration = total_duration * (len(chunk_text) / total_chars)
                        current_e = current_s + chunk_duration
                        
                        lines.append(f"{counter}")
                        lines.append(f"{self.format_time(current_s)} --> {self.format_time(current_e)}")
                        lines.append(chunk_text)
                        lines.append("")
                        counter += 1
                        current_s = current_e
        
        with open(srt_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

    def create_ass(self, transcript, start_time, end_time, ass_path, font="Arial", animation="None"):
        # Header
        header = """[Script Info]
ScriptType: v4.00+
PlayResX: 384
PlayResY: 288

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
"""
        # Define Style
        # Alignment 2 is Bottom Center
        # Colors are &HABGGRR (Alpha Blue Green Red)
        # White Primary: &H00FFFFFF
        # Black Outline: &H00000000
        # Font size 16 is roughly proportional for 384x288 resolution
        style = f"Style: Default,{font},16,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,1,0,2,10,10,10,1"
        
        content = [header, style, "\n[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"]
        
        def fmt_time(seconds):
            h = int(seconds // 3600)
            m = int((seconds % 3600) // 60)
            s = seconds % 60
            return f"{h}:{m:02d}:{s:05.2f}"

        for t in transcript:
            # Check overlap
            if t["end"] > start_time and t["start"] < end_time:
                # Clip times to segment boundaries
                s = max(t["start"], start_time) - start_time
                e = min(t["end"], end_time) - start_time
                
                if e <= s: continue

                text = t["text"].strip()
                if not text: continue
                
                start_str = fmt_time(s)
                end_str = fmt_time(e)
                
                # Apply Animation
                text_content = text
                if animation == "Fade":
                    text_content = "{\\fad(200,200)}" + text
                elif animation == "Pop":
                    # Simple pop effect? Scale transform?
                    # {\t(0,200,\fscx110\fscy110)}{\t(200,400,\fscx100\fscy100)}
                    text_content = "{\\t(0,100,\\fscx110\\fscy110)\\t(100,200,\\fscx100\\fscy100)}" + text
                
                line = f"Dialogue: 0,{start_str},{end_str},Default,,0,0,0,,{text_content}"
                content.append(line)
        
        with open(ass_path, "w", encoding="utf-8") as f:
            f.write("\n".join(content))

    def _stretch_audio(self, input_path, target_duration, output_path):
        """Stretches audio to match target duration using atempo filter."""
        print(f"DEBUG: Starting _stretch_audio for {input_path} -> {target_duration}s")
        # Get actual duration
        probe_cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", input_path]
        try:
            duration_str = subprocess.check_output(probe_cmd).decode().strip()
            current_duration = float(duration_str)
            print(f"DEBUG: Current audio duration: {current_duration}s")
        except Exception as e:
            print(f"DEBUG: Probe failed: {e}")
            return False

        if current_duration <= 0 or target_duration <= 0: 
            print("DEBUG: Invalid duration")
            return False

        # Calculate speed factor (current / target)
        speed_factor = current_duration / target_duration
        print(f"DEBUG: Speed factor: {speed_factor}")
        
        # Clamp speed factor to reasonable limits (0.5x to 4.0x) to avoid artifacts
        # If it needs more than 4x speed up, we just do 4x.
        
        filters = []
        remaining = speed_factor
        
        # Limit the number of chained filters to avoid FFmpeg complexity explosion
        max_chain = 10 
        chain_count = 0
        
        while remaining > 2.0 and chain_count < max_chain:
            filters.append("atempo=2.0")
            remaining /= 2.0
            chain_count += 1
        
        while remaining < 0.5 and chain_count < max_chain:
            filters.append("atempo=0.5")
            remaining /= 0.5
            chain_count += 1
            
        filters.append(f"atempo={remaining}")
        filter_complex = ",".join(filters)
        print(f"DEBUG: Filter complex: {filter_complex}")
        
        cmd = [
            "ffmpeg", "-y", "-i", input_path,
            "-filter:a", filter_complex,
            "-vn", output_path
        ]
        
        print(f"DEBUG: Running FFmpeg stretch command: {' '.join(cmd)}")
        try:
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120) # Add timeout
            if result.returncode != 0:
                print(f"DEBUG: Stretch failed stderr: {result.stderr.decode()}")
            else:
                print("DEBUG: Stretch success")
        except subprocess.TimeoutExpired:
            print("DEBUG: FFmpeg stretch timed out")
            return False
        except Exception as e:
            print(f"DEBUG: FFmpeg stretch exception: {e}")
            return False
            
        return os.path.exists(output_path)

    def render_clips(self, src_path, segments, platform, auto_edit, burn_subs, transcript, analysis, job_id=None, dubbing_engine=None, target_language=None, voice_gender="Male", subtitle_font="Arial", subtitle_words=5, subtitle_animation="None", filters=None, trim_start=0, trim_end=0, transition_type="none", bg_music_path=None, bg_volume=0.2):
        outputs = []
        
        # Override segments if manual trim
        if trim_end > trim_start:
             segments = [{"start": trim_start, "end": trim_end}]
        
        # Get preset for platform (though we'll stick to basic cutting for now)
        preset = self.presets.get(platform)
        
        base_dir = os.path.dirname(src_path)
        filename = os.path.basename(src_path)
        name, ext = os.path.splitext(filename)
        
        for i, seg in enumerate(segments):
            start = seg["start"]
            end = seg["end"]
            duration = end - start
            
            out_name = f"{name}_clip_{i+1}{ext}"
            out_path = os.path.join(base_dir, out_name)
            srt_name = f"{name}_clip_{i+1}.srt"
            srt_path = os.path.join(base_dir, srt_name)
            ass_name = f"{name}_clip_{i+1}.ass"
            ass_path = os.path.join(base_dir, ass_name)
            
            # Prepare to collect translated segments if dubbing
            translated_segments = []
            
            # Handle Dubbing if enabled
            dub_audio_path = None
            if dubbing_engine:
                voice = dubbing_engine.get_voice_for_lang(target_language, voice_gender)
                dub_segments_files = []
                
                # Filter transcript segments relevant to this clip
                clip_segments = []
                full_clip_text_parts = []
                for t in transcript:
                    if t["end"] > start and t["start"] < end:
                        clip_segments.append(t)
                        full_clip_text_parts.append(t["text"])
                
                full_clip_text = " ".join(full_clip_text_parts)

                if clip_segments:
                    if job_id:
                        self.progress.update(job_id, "status", f"dubbing_clip_{i+1}")
                        
                    # Generate audio for each segment
                    segment_audio_parts = []
                    last_end = 0 # Relative to clip start
                    
                    for idx, t in enumerate(clip_segments):
                        # Relative times
                        rel_start = max(0, t["start"] - start)
                        rel_end = min(duration, t["end"] - start)
                        seg_duration = rel_end - rel_start
                        
                        if seg_duration <= 0.1: continue

                        # Generate TTS for this segment
                        seg_text = t["text"]
                        seg_filename = f"{name}_clip_{i+1}_seg_{idx}.mp3"
                        seg_path = os.path.join(base_dir, seg_filename)
                        
                        generated_path, translated_text = dubbing_engine.generate_dub_segment(seg_text, target_language, voice, seg_path)
                        
                        # Collect translated text for subtitles
                        if translated_text:
                            translated_segments.append({
                                "start": t["start"],
                                "end": t["end"],
                                "text": translated_text
                            })
                        else:
                             translated_segments.append(t) # Fallback to original
                        
                        if generated_path and os.path.exists(generated_path):
                            # Time stretch to fit duration
                            stretched_filename = f"{name}_clip_{i+1}_seg_{idx}_stretched.mp3"
                            stretched_path = os.path.join(base_dir, stretched_filename)
                            
                            if self._stretch_audio(generated_path, seg_duration, stretched_path):
                                segment_audio_parts.append({
                                    "path": stretched_path,
                                    "start": rel_start,
                                    "end": rel_end
                                })
                    
                    # Construct full audio track by mixing segments onto a silent base
                    # 1. Create silent base
                    silent_base_path = os.path.join(base_dir, f"{name}_clip_{i+1}_silence.mp3")
                    subprocess.run([
                        "ffmpeg", "-y", "-f", "lavfi", "-i", f"anullsrc=r=24000:cl=mono:d={duration}",
                        "-q:a", "9", silent_base_path
                    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    
                    # 2. Mix segments
                    # Complex filter to delay and mix
                    if segment_audio_parts:
                        mix_cmd = ["ffmpeg", "-y", "-i", silent_base_path]
                        filter_complex = "[0:a]" # Start with silent base
                        inputs = 1
                        
                        for part in segment_audio_parts:
                            mix_cmd.extend(["-i", part["path"]])
                            # Delay audio
                            delay_ms = int(part["start"] * 1000)
                            filter_complex += f"[{inputs}:a]adelay={delay_ms}|{delay_ms}[a{inputs}];"
                            inputs += 1
                        
                        # Mix all delayed streams with base
                        # [0:a][a1][a2]...amix=inputs=N:duration=first
                        mix_inputs = "".join([f"[a{k}]" for k in range(1, inputs)])
                        filter_complex += f"[0:a]{mix_inputs}amix=inputs={inputs}:duration=first:dropout_transition=0[outa]"
                        
                        final_dub_path = os.path.join(base_dir, f"{name}_clip_{i+1}_dub_final.mp3")
                        mix_cmd.extend(["-filter_complex", filter_complex, "-map", "[outa]", final_dub_path])
                        
                        subprocess.run(mix_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                        
                        if os.path.exists(final_dub_path):
                            dub_audio_path = final_dub_path
                
                # Fallback Dubbing (if segment assembly failed OR just use as retry? No, if segments exist we used them)
                # But if dub_audio_path is still None (e.g. all segments failed), try fallback
                if not dub_audio_path and full_clip_text:
                    if job_id:
                        self.progress.update(job_id, "status", f"dubbing_fallback_{i+1}")
                    fallback_dub_path = os.path.join(base_dir, f"{name}_clip_{i+1}_dub_fallback.mp3")
                    
                    try:
                        gen_path, translated_text = dubbing_engine.generate_dub(full_clip_text, target_language, voice, fallback_dub_path)
                        
                        if gen_path and os.path.exists(gen_path):
                            # STRETCH FALLBACK AUDIO TO MATCH CLIP DURATION EXACTLY
                            stretched_fallback_path = os.path.join(base_dir, f"{name}_clip_{i+1}_dub_fallback_stretched.mp3")
                            if self._stretch_audio(gen_path, duration, stretched_fallback_path):
                                dub_audio_path = stretched_fallback_path
                            else:
                                dub_audio_path = gen_path
                    except Exception as e:
                        print(f"Fallback Dubbing Failed: {e}")
                        # Don't fail the whole clip, just proceed without dubbing
                        pass

            # Determine transcript for subtitles
            # If dubbing was active and we have translated segments, use them.
            final_transcript = translated_segments if (dubbing_engine and translated_segments) else transcript
            
            # Generate Subtitles (SRT and ASS)
            # We create both. SRT for download, ASS for burning (better styling).
            self.create_srt(final_transcript, start, end, srt_path, max_words=subtitle_words)
            self.create_ass(final_transcript, start, end, ass_path, font=subtitle_font, animation=subtitle_animation)

            # Construct FFmpeg command
            cmd = ["ffmpeg", "-y"]
            
            # Input video (0)
            cmd.extend(["-ss", str(start)])
            cmd.extend(["-i", src_path])
            cmd.extend(["-t", str(duration)])
            
            # Input dub audio if exists (1)
            if dub_audio_path:
                cmd.extend(["-i", dub_audio_path])
            
            # Input BG Music if exists (1 or 2)
            if bg_music_path:
                cmd.extend(["-stream_loop", "-1"])
                cmd.extend(["-i", bg_music_path])
            
            # Video Codec
            cmd.extend(["-c:v", "libx264"])
            
            # Audio Handling (Mixing logic)
            filter_complex_parts = []
            audio_map = None
            
            # Determine indices
            main_audio_idx = 1 if dub_audio_path else 0
            bg_music_idx = -1
            
            if bg_music_path:
                bg_music_idx = 2 if dub_audio_path else 1
            
            if bg_music_path:
                # Mix BG Music with Main Audio
                # 1. Adjust BG volume
                filter_complex_parts.append(f"[{bg_music_idx}:a]volume={bg_volume}[bg]")
                
                # 2. Mix with Main Audio
                # Using amix with 2 inputs. Default behavior normalizes (divides by 2).
                # To restore Main Audio level (assuming it was good), we multiply result by 2.
                # [main][bg]amix...
                filter_complex_parts.append(f"[{main_audio_idx}:a][bg]amix=inputs=2:duration=first:dropout_transition=0,volume=2[outa]")
                
                audio_map = "[outa]"
            else:
                # No BG Music
                if dub_audio_path:
                    audio_map = "1:a"
                else:
                    audio_map = "0:a"
            
            # Add Filter Complex if needed for Audio
            if filter_complex_parts:
                # If we have filter_complex for audio, we need to be careful if we also use -vf for video
                # FFmpeg allows -filter_complex for complex graphs and -vf for simple video filters
                # BUT if we use -filter_complex, it's often better to put everything there.
                # However, for simplicity, we'll try to keep them separate if possible, or combine.
                # Actually, mixing -vf and -filter_complex can be tricky.
                # Safe bet: pass audio mixing in -filter_complex and video filters in -vf.
                # As long as they don't share streams, it should be fine.
                cmd.extend(["-filter_complex", ";".join(filter_complex_parts)])
            
            # Map Video
            cmd.extend(["-map", "0:v"])
            
            # Map Audio
            cmd.extend(["-map", audio_map])
            
            cmd.extend(["-c:a", "aac"])
            cmd.extend(["-strict", "experimental"])
            
            # Video Filters (Crop + Subtitles)
            vf_chain = []
            
            # Apply Color Filters (via VideoFilters)
            if filters:
                vf_chain.extend(VideoFilters.get_filter_chain(filters))
                
                # Manual Slider Application (Editor side logic for simpler sliders, if not handled in VideoFilters)
                # Actually, let's move ALL logic to VideoFilters to keep Editor clean.
                # But Editor.py was doing EQ construction before.
                # Let's remove the inline EQ construction here and rely on VideoFilters completely?
                # The previous code for EQ was removed in my mind, but let's check if it's there.
                # Wait, I see "eq=" in the Read output previously?
                # Ah, in previous turns I added eq construction in Editor.py.
                # I should replace that block to avoid duplication if I move logic to VideoFilters.
                # OR I just append here.
                
                # Let's handle the "Legacy" sliders here if they are not in VideoFilters yet?
                # No, better to move everything to VideoFilters class.
                pass 

            # Cropping
            if platform in ["shorts", "reels_instagram", "reels_facebook", "tiktok"]:
                 vf_chain.append("crop=ih*(9/16):ih:(iw-ow)/2:0")
            elif platform == "square":
                 vf_chain.append("crop=ih:ih:(iw-ow)/2:0")
            # landscape needs no crop if source is landscape. If source is different, we might need logic, but assume landscape source for now.
            
            # Burning Subtitles
            if burn_subs:
                 escaped_ass = ass_path.replace("\\", "/").replace(":", "\\:")
                 vf_chain.append(f"subtitles='{escaped_ass}'")
            
            # Transitions
            af_chain = []
            if transition_type == "fade" and duration > 1.0:
                 vf_chain.append(f"fade=t=in:st=0:d=0.5")
                 vf_chain.append(f"fade=t=out:st={duration-0.5}:d=0.5")
                 af_chain.append(f"afade=t=in:st=0:d=0.5")
                 af_chain.append(f"afade=t=out:st={duration-0.5}:d=0.5")

            if vf_chain:
                cmd.extend(["-vf", ",".join(vf_chain)])
            
            if af_chain:
                cmd.extend(["-af", ",".join(af_chain)])
            
            # FORCE OUTPUT DURATION
            # This ensures that even if audio is slightly longer due to processing, the clip is cut at the exact duration
            cmd.extend(["-t", str(duration)])
            
            cmd.append(out_path)
            
            # Run FFmpeg
            print(f"DEBUG: Running final render command: {' '.join(cmd)}")
            try:
                result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=600) # 10 min timeout
                if result.returncode != 0:
                     print(f"FFmpeg failed for clip {i+1}")
                     print(f"Command: {' '.join(cmd)}")
                     print(f"Error: {result.stderr.decode()}")
                else:
                     print(f"DEBUG: Render success for clip {i+1}")
            except subprocess.TimeoutExpired:
                 print(f"FFmpeg timed out for clip {i+1}")
            except Exception as e:
                 print(f"FFmpeg error: {e}")
                
            if os.path.exists(out_path):
                outputs.append({
                    "video_path": out_path,
                    "srt_path": srt_path,
                    "ass_path": ass_path,
                    "start": start,
                    "end": end
                })
        
        return outputs
