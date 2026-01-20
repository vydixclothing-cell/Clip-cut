import os
import yt_dlp

class YouTubeDownloader:
    def __init__(self, progress):
        self.progress = progress

    def list_formats(self, url):
        ydl_opts = {'quiet': True}
        formats = []
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            for f in info.get('formats', []):
                # Simple logic to filter video formats
                if f.get('vcodec') != 'none' and f.get('height'):
                    formats.append({
                        "id": f['format_id'],
                        "label": f"{f['height']}p",
                        "ext": f['ext']
                    })
        # Deduplicate by label for UI
        unique_formats = {}
        for f in formats:
            unique_formats[f['label']] = f
        return sorted(unique_formats.values(), key=lambda x: int(x['label'][:-1]))

    def download(self, url, quality, output_dir):
        # Map quality label (e.g. 1080p) to format selection
        # This is a simplified selection logic
        target_height = int(quality.replace('p', ''))
        
        filename_tmpl = os.path.join(output_dir, "%(title)s.%(ext)s")
        
        ydl_opts = {
            'format': f'bestvideo[height<={target_height}]+bestaudio/best[height<={target_height}]',
            'outtmpl': filename_tmpl,
            'merge_output_format': 'mp4',
            'quiet': True,
            'retries': 10,
            'fragment_retries': 10,
            'socket_timeout': 30,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            # If merge_output_format is used, the actual file might have different extension
            if 'merge_output_format' in ydl_opts:
                base, _ = os.path.splitext(filename)
                filename = f"{base}.{ydl_opts['merge_output_format']}"
                
        return filename
