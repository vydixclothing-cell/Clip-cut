import os
import threading
import uuid
from datetime import datetime, timedelta
from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for
from werkzeug.utils import secure_filename
from clipcut.storage import Storage
from clipcut.progress import ProgressTracker
from clipcut.downloader import YouTubeDownloader
from clipcut.analysis import Analyzer
from clipcut.editor import Editor
from clipcut.subtitles import SubtitleEngine
from clipcut.scoring import Scoring
from clipcut.presets import PlatformPresets
from clipcut.dubbing import DubbingEngine
from clipcut.filter_library import FILTER_LIBRARY
from clipcut.filters import VideoFilters
import json
import tempfile
import shutil

app = Flask(__name__, template_folder="templates")
app.config["MAX_CONTENT_LENGTH"] = 1024 * 1024 * 1024
app.config["UPLOAD_EXTENSIONS"] = {".mp4", ".mkv", ".mov"}
storage = Storage(base_dir=os.path.join(os.getcwd(), "workspace"))
progress = ProgressTracker()
presets = PlatformPresets()


@app.route("/", methods=["GET"])
def index():
    return render_template("index.html", filter_library=FILTER_LIBRARY)


@app.route("/formats", methods=["POST"])
def formats():
    data = request.get_json(force=True)
    url = data.get("url", "")
    if not url:
        return jsonify({"error": "Missing URL"}), 400
    yd = YouTubeDownloader(progress)
    try:
        formats = yd.list_formats(url)
        return jsonify({"formats": formats})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def _get_duration(path):
    import subprocess
    cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", path]
    try:
        return float(subprocess.check_output(cmd).decode().strip())
    except:
        return 0.0

def _start_job(job_id, params, src_path):
    try:
        mode = params.get("mode", "clip")
        
        # Initialize common components
        progress.update(job_id, "status", "analyzing")
        
        if mode == "edit":
            # Direct Edit Mode - Skip AI Analysis
            duration = _get_duration(src_path)
            if duration == 0:
                 raise Exception("Could not determine video duration")
                 
            # Create a single segment for the whole video (or trimmed part)
            # If trim is set, Editor handles it, but we need to pass a valid segment covering the range.
            # Editor.render_clips logic: "Override segments if manual trim"
            # So we can just pass a dummy segment covering everything.
            ranked = [{"start": 0, "end": duration, "text": ""}]
            
            transcript = [] # No subtitles by default unless we run transcribe?
            # If user wants subtitles in Edit mode, we need to run transcribe.
            if params["subtitles"] or params["dubbing_enabled"]:
                 progress.update(job_id, "status", "transcribing")
                 subs = SubtitleEngine(progress)
                 transcript = subs.transcribe(src_path)
            
            analysis = [] # No scene analysis needed
            
        else:
            # Clip Generator Mode
            analyzer = Analyzer(progress)
            analysis = analyzer.run(src_path)
            progress.update(job_id, "status", "transcribing")
            subs = SubtitleEngine(progress)
            transcript = subs.transcribe(src_path)
            progress.update(job_id, "status", "selecting")
            scorer = Scoring()
            ranked = scorer.rank_segments(analysis, transcript, params["clip_duration"], params["num_clips"])

        progress.update(job_id, "status", "editing")
        ed = Editor(progress, presets)
        
        # Dubbing Workflow
        dubbing_engine = None
        if params.get("dubbing_enabled") and params.get("target_language"):
             dubbing_engine = DubbingEngine(progress)

        outputs = ed.render_clips(
            src_path=src_path,
            segments=ranked,
            platform=params["platform"],
            auto_edit=params["auto_edit"],
            burn_subs=params["subtitles"],
            transcript=transcript,
            analysis=analysis,
            job_id=job_id,
            dubbing_engine=dubbing_engine,
            target_language=params.get("target_language"),
            voice_gender=params.get("voice_gender", "Male"),
            subtitle_font=params.get("subtitle_font", "Arial"),
            subtitle_words=params.get("subtitle_words", 5),
            subtitle_animation=params.get("subtitle_animation", "None"),
            filters=params.get("filters"),
            trim_start=params.get("trim_start", 0),
            trim_end=params.get("trim_end", 0),
            transition_type=params.get("transition_type", "none"),
            bg_music_path=params.get("bg_music_path"),
            bg_volume=params.get("bg_volume", 0.2)
        )
        meta = []
        for out in outputs:
            score = scorer.clip_score(out, analysis, transcript)
            title, hashtags = scorer.generate_metadata(out, transcript)
            meta.append(
                {
                    "path": out["video_path"],
                    "srt_path": out.get("srt_path"),
                    "ass_path": out.get("ass_path"),
                    "start": out["start"],
                    "end": out["end"],
                    "score": score,
                    "title": title,
                    "hashtags": hashtags,
                }
            )
        if not meta:
            progress.update(job_id, "status", "error")
            progress.update(job_id, "error", "No clips generated. FFmpeg might have failed.")
        else:
            progress.update(job_id, "results", meta)
            progress.update(job_id, "status", "completed")
    except Exception as e:
        progress.update(job_id, "status", "error")
        progress.update(job_id, "error", str(e))


@app.route("/preview_frame", methods=["POST"])
def preview_frame():
    try:
        if "image" not in request.files:
            return jsonify({"error": "No image provided"}), 400
            
        image_file = request.files["image"]
        
        # Parse filters
        # They might come as a JSON string field 'filters' or individual fields
        # But our frontend will likely send them as individual fields or a JSON string.
        # Let's support both or just assume individual fields like /process
        # But simpler: frontend sends a 'filters' JSON string
        filters_str = request.form.get("filters", "{}")
        try:
            filters = json.loads(filters_str)
        except:
            filters = {}

        # Save input image
        ext = os.path.splitext(image_file.filename)[1] or ".jpg"
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp_in:
            image_file.save(tmp_in.name)
            input_path = tmp_in.name
            
        # Output path
        output_path = input_path.replace(ext, "_processed.jpg") # Force jpg for preview
        
        # Apply filters
        VideoFilters.apply_filters_to_image(input_path, filters, output_path)
        
        # Cleanup input
        try:
            os.remove(input_path)
        except:
            pass
            
        return send_file(output_path, mimetype="image/jpeg")
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/process", methods=["POST"])
def process():
    form = request.form
    platform = form.get("platform", "shorts")
    url = form.get("youtube_url", "").strip()
    quality = form.get("quality", "1080p").strip()
    clip_duration = int(form.get("clip_duration", "30"))
    num_clips = int(form.get("num_clips", "3"))
    auto_edit = form.get("auto_edit", "on") == "on"
    subtitles = form.get("subtitles", "on") == "on"
    dubbing_enabled = form.get("dubbing_enabled", "off") == "on"
    target_language = form.get("target_language", "")
    voice_gender = form.get("voice_gender", "Male")
    subtitle_font = form.get("subtitle_font", "Arial")
    subtitle_words = int(form.get("subtitle_words", "5"))
    
    # Extract filters
    filters = {
        "brightness": float(form.get("filter_brightness", "0")),
        "contrast": float(form.get("filter_contrast", "1")),
        "saturation": float(form.get("filter_saturation", "1")),
        "exposure": float(form.get("filter_exposure", "0")),
        "highlights": float(form.get("filter_highlights", "0")),
        "shadows": float(form.get("filter_shadows", "0")),
        "vignette": float(form.get("filter_vignette", "0")),
        "warmth": float(form.get("filter_warmth", "0")),
        "tint": float(form.get("filter_tint", "0")),
        "sharpness": float(form.get("filter_sharpness", "0")),
        "grayscale": int(form.get("filter_grayscale", "0")) == 1,
        "preset": form.get("filter_preset", "none"),
        "effect": form.get("filter_effect", "none")
    }
    
    # Extract trim and transition
    trim_start = float(form.get("trim_start", "0"))
    trim_end = float(form.get("trim_end", "0"))
    transition_type = form.get("transition_type", "none")
    mode = form.get("mode", "clip")

    job_id = uuid.uuid4().hex
    progress.init(job_id)
    progress.update(job_id, "status", "initializing")
    try:
        storage.init_job(job_id)
        
        # Handle Background Music
        bg_music_path = None
        bg_volume = float(form.get("bg_volume", "20")) / 100.0
        if "bg_music" in request.files:
            bg_f = request.files["bg_music"]
            if bg_f and bg_f.filename != "":
                bg_name = f"bg_{secure_filename(bg_f.filename)}"
                bg_dst = os.path.join(storage.job_dir(job_id), bg_name)
                bg_f.save(bg_dst)
                bg_music_path = bg_dst
        
        src_path = None
        if url:
            yd = YouTubeDownloader(progress)
            progress.update(job_id, "status", "downloading")
            src_path = yd.download(url, quality, storage.job_dir(job_id))
        else:
            f = request.files.get("video_file")
            if not f or f.filename == "":
                progress.update(job_id, "status", "error")
                progress.update(job_id, "error", "No input source")
                return jsonify({"error": "No input source provided (URL or File)"}), 400
            filename = secure_filename(f.filename)
            ext = os.path.splitext(filename)[1].lower()
            if ext not in app.config["UPLOAD_EXTENSIONS"]:
                progress.update(job_id, "status", "error")
                progress.update(job_id, "error", "Unsupported file type")
                return jsonify({"error": "Unsupported file type"}), 400
            dst = os.path.join(storage.job_dir(job_id), filename)
            f.save(dst)
            src_path = dst
        params = {
            "platform": platform,
            "quality": quality,
            "clip_duration": clip_duration,
            "num_clips": num_clips,
            "auto_edit": auto_edit,
            "subtitles": subtitles,
            "dubbing_enabled": dubbing_enabled,
            "target_language": target_language,
            "voice_gender": voice_gender,
            "subtitle_font": subtitle_font,
            "subtitle_words": subtitle_words,
            "filters": filters,
            "trim_start": trim_start,
            "trim_end": trim_end,
            "transition_type": transition_type,
            "mode": mode,
            "bg_music_path": bg_music_path,
            "bg_volume": bg_volume
        }
        t = threading.Thread(target=_start_job, args=(job_id, params, src_path), daemon=True)
        t.start()
        return jsonify({"job_id": job_id})
    except Exception as e:
        progress.update(job_id, "status", "error")
        progress.update(job_id, "error", str(e))
        return jsonify({"error": str(e)}), 500


@app.route("/progress/<job_id>", methods=["GET"])
def job_progress(job_id):
    return jsonify(progress.get(job_id))


@app.route("/download/<job_id>/<kind>", methods=["GET"])
def download(job_id, kind):
    info = progress.get(job_id)
    if not info or info.get("status") != "completed":
        return jsonify({"error": "Not ready"}), 400
    idx = int(request.args.get("i", "0"))
    results = info.get("results", [])
    if idx < 0 or idx >= len(results):
        return jsonify({"error": "Invalid index"}), 400
    target = results[idx]
    path = None
    if kind == "video":
        path = target["path"]
    elif kind == "srt":
        path = target.get("srt_path")
    elif kind == "ass":
        path = target.get("ass_path")
    else:
        return jsonify({"error": "Invalid kind"}), 400
    if not path or not os.path.exists(path):
        return jsonify({"error": "File not found"}), 404
    
    download_name = None
    if kind == "video":
        title = target.get("title", f"clip_{idx+1}")
        # Sanitize title for filename
        safe_title = "".join([c for c in title if c.isalnum() or c in (' ', '-', '_')]).strip()
        safe_title = safe_title.replace(" ", "_")
        if not safe_title:
            safe_title = f"clip_{idx+1}"
        download_name = f"{safe_title}.mp4"

    return send_file(path, as_attachment=True, download_name=download_name)


@app.route("/clean", methods=["POST"])
def clean():
    storage.cleanup_older_than(hours=8)
    return jsonify({"status": "ok"})


@app.route("/vocal_remove", methods=["POST"])
def vocal_remove():
    try:
        if "video_file" not in request.files:
            return jsonify({"error": "No file uploaded"}), 400
            
        file = request.files["video_file"]
        if file.filename == "":
            return jsonify({"error": "No selected file"}), 400
            
        # Create workspace/vocal if not exists
        vocal_dir = os.path.join(os.getcwd(), "workspace", "vocal")
        os.makedirs(vocal_dir, exist_ok=True)
        
        # Save input
        filename = secure_filename(file.filename)
        unique_id = str(uuid.uuid4())[:8]
        input_path = os.path.join(vocal_dir, f"{unique_id}_{filename}")
        file.save(input_path)
        
        # Demucs Output Directory
        demucs_out = os.path.join(vocal_dir, unique_id)
        os.makedirs(demucs_out, exist_ok=True)
        
        # Run Demucs
        # Use sys.executable to ensure we use the current python environment
        # Force CPU (-d cpu) to avoid potential CUDA/VRAM issues on user machine
        import subprocess
        import sys
        
        cmd = [
            sys.executable, "-m", "demucs.separate",
            "-n", "htdemucs", 
            "--two-stems=vocals", 
            "-d", "cpu",
            "-o", demucs_out,
            input_path
        ]
        
        print(f"Running Demucs: {' '.join(cmd)}")
        
        # We need to capture output to debug if it fails
        # Using subprocess.PIPE to handle large output better if needed, but capture_output is fine for now
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            # Extract the actual error from stderr (skipping progress bars)
            error_log = result.stderr
            print(f"Demucs Stderr: {error_log}") # Log full error to terminal
            
            # Try to find the last meaningful line
            lines = error_log.splitlines()
            # Filter out progress bars (lines containing '%|')
            clean_lines = [l for l in lines if "%|" not in l and l.strip()]
            short_error = clean_lines[-1] if clean_lines else "Unknown Demucs Error"
            
            raise Exception(f"Demucs failed: {short_error}")
            
        # Locate output files
        # Demucs structure: {demucs_out}/htdemucs/{filename_without_ext}/vocals.wav
        # Filename without ext might be tricky if demucs sanitizes it. 
        # But usually it's just the basename without extension.
        name_no_ext = os.path.splitext(filename)[0]
        
        # Demucs might sanitize spaces to underscores etc? 
        # Let's try to find the folder inside htdemucs
        model_out = os.path.join(demucs_out, "htdemucs")
        if not os.path.exists(model_out):
             # Fallback or check if structure is different
             raise Exception(f"Demucs output not found. Logs: {result.stderr}")
             
        # Find the subfolder (it should be the only one)
        subfolders = [f for f in os.listdir(model_out) if os.path.isdir(os.path.join(model_out, f))]
        if not subfolders:
             raise Exception("Demucs did not create a track folder.")
             
        track_folder = os.path.join(model_out, subfolders[0])
        
        vocals_wav = os.path.join(track_folder, "vocals.wav")
        no_vocals_wav = os.path.join(track_folder, "no_vocals.wav")
        
        if not os.path.exists(vocals_wav) or not os.path.exists(no_vocals_wav):
            raise Exception("Output wav files not found.")
            
        # Convert to MP3 to save bandwidth/space (Optional, but good for web)
        # We can just return wav or convert. Let's return wav for quality or mp3 for size.
        # User asked for download. MP3 is safer for compatibility.
        
        final_vocals = os.path.join(vocal_dir, f"{unique_id}_vocals.mp3")
        final_bg = os.path.join(vocal_dir, f"{unique_id}_background.mp3")
        
        subprocess.run(["ffmpeg", "-y", "-i", vocals_wav, "-q:a", "0", "-map", "a", final_vocals], check=True)
        subprocess.run(["ffmpeg", "-y", "-i", no_vocals_wav, "-q:a", "0", "-map", "a", final_bg], check=True)
        
        # Cleanup demucs folder
        try:
            shutil.rmtree(demucs_out)
        except:
            pass
        
        # Return download URLs
        return jsonify({
            "background_url": f"/download_vocal/{os.path.basename(final_bg)}",
            "vocals_url": f"/download_vocal/{os.path.basename(final_vocals)}"
        })
        
    except Exception as e:
        print(f"Vocal Remove Error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/download_vocal/<filename>")
def download_vocal(filename):
    vocal_dir = os.path.join(os.getcwd(), "workspace", "vocal")
    return send_file(os.path.join(vocal_dir, filename), as_attachment=True)


@app.route("/mix_audio", methods=["POST"])
def mix_audio():
    try:
        if "video_file" not in request.files or "bg_music" not in request.files:
            return jsonify({"error": "Missing video or music file"}), 400
            
        video_file = request.files["video_file"]
        bg_music_file = request.files["bg_music"]
        bg_volume = float(request.form.get("bg_volume", "20")) / 100.0
        
        if video_file.filename == "" or bg_music_file.filename == "":
            return jsonify({"error": "No selected file"}), 400
            
        # Create workspace/mixer if not exists
        mixer_dir = os.path.join(os.getcwd(), "workspace", "mixer")
        os.makedirs(mixer_dir, exist_ok=True)
        
        unique_id = str(uuid.uuid4())[:8]
        video_filename = secure_filename(video_file.filename)
        bg_filename = secure_filename(bg_music_file.filename)
        
        video_path = os.path.join(mixer_dir, f"{unique_id}_{video_filename}")
        bg_path = os.path.join(mixer_dir, f"{unique_id}_{bg_filename}")
        
        video_file.save(video_path)
        bg_music_file.save(bg_path)
        
        output_filename = f"mixed_{unique_id}_{video_filename}"
        output_path = os.path.join(mixer_dir, output_filename)
        
        # FFmpeg command to mix audio
        # We use -c:v copy for speed
        import subprocess
        cmd = [
            "ffmpeg", "-y",
            "-i", video_path,
            "-stream_loop", "-1", "-i", bg_path,
            "-filter_complex", f"[1:a]volume={bg_volume}[bg];[0:a][bg]amix=inputs=2:duration=first:dropout_transition=0,volume=2[outa]",
            "-map", "0:v", "-map", "[outa]",
            "-c:v", "copy", 
            "-c:a", "aac",
            output_path
        ]
        
        subprocess.run(cmd, check=True)
        
        return jsonify({
            "download_url": f"/download_mix/{output_filename}",
            "filename": output_filename
        })

    except Exception as e:
        print(f"Audio Mix Error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/download_mix/<filename>")
def download_mix(filename):
    mixer_dir = os.path.join(os.getcwd(), "workspace", "mixer")
    return send_file(os.path.join(mixer_dir, filename), as_attachment=True)

if __name__ == "__main__":
    storage.setup()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)


