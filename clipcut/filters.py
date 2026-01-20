from clipcut.filter_library import FILTER_LIBRARY

class VideoFilters:
    @staticmethod
    def get_filter_chain(filters):
        """
        Generates FFmpeg filter chain from filter parameters.
        filters: dict containing 'brightness', 'contrast', 'saturation', 'grayscale', 'preset'
        """
        chain = []
        
        # 1. Presets (Complex Color Grading)
        preset = filters.get("preset", "none")
        
        if preset in FILTER_LIBRARY:
            chain.extend(FILTER_LIBRARY[preset]["ffmpeg"])
        elif preset == "vintage":
            # Legacy/Fallback
            chain.append("colorbalance=rs=.2:gs=.1:bs=-.2")
            chain.append("vignette=PI/4")
        elif preset == "cinematic":
            chain.append("colorbalance=rs=-0.1:gs=-0.05:bs=0.2:rh=0.2:gh=0.1:bh=-0.2")
        elif preset == "cyberpunk":
            chain.append("colorbalance=rs=0.2:gs=-0.2:bs=0.3")
        elif preset == "warm":
            chain.append("colorbalance=rs=0.1:gs=0.1:bs=-0.15")
        elif preset == "cool":
            chain.append("colorbalance=rs=-0.1:gs=-0.05:bs=0.25")
        elif preset == "noir":
            chain.append("hue=s=0")
            chain.append("eq=contrast=1.5")
        elif preset == "sepia":
            chain.append("colorchannelmixer=.393:.769:.189:0:.349:.686:.168:0:.272:.534:.131")
        elif preset == "pastel":
            chain.append("eq=contrast=0.8:brightness=0.1:saturation=1.2")
            
        # 2. User Adjustments
        eq_parts = []
        
        # Brightness/Contrast/Saturation/Gamma(Exposure)
        bri = filters.get("brightness", 0.0)
        con = filters.get("contrast", 1.0)
        sat = filters.get("saturation", 1.0)
        
        # Exposure -> Gamma (Approx)
        # Exposure +1 -> Gamma 0.5?
        # Let's map exposure (-1.0 to 1.0) to brightness/gamma
        exp = filters.get("exposure", 0.0)
        if exp != 0:
            bri += exp * 0.1 # Simple brightness boost
            # Gamma adjustment for more natural exposure?
            # gamma = 1.0 - (exp * 0.5) 
            # eq_parts.append(f"gamma={gamma}")
            
        if filters.get("grayscale"):
            sat = 0
            
        if bri != 0.0:
            eq_parts.append(f"brightness={bri}")
        if con != 1.0:
            eq_parts.append(f"contrast={con}")
        if sat != 1.0:
            eq_parts.append(f"saturation={sat}")
            
        if eq_parts:
            chain.append("eq=" + ":".join(eq_parts))
            
        # 3. Advanced Sliders
        
        # Warmth/Tint (Color Balance)
        warmth = filters.get("warmth", 0.0) # -1 to 1
        tint = filters.get("tint", 0.0) # -1 to 1
        
        if warmth != 0 or tint != 0:
            # Warmth: Red/Yellow vs Blue
            # Tint: Green vs Magenta
            rs = warmth * 0.2
            bs = -warmth * 0.2
            gs = tint * 0.2
            chain.append(f"colorbalance=rs={rs}:bs={bs}:gs={gs}")
            
        # Vignette
        vig = filters.get("vignette", 0.0) # 0 to 1 (or 100)
        if vig > 0:
            # Angle: PI/5 * amount
            # If vig is 0-1 range
            angle = (3.14159 / 4) * vig
            chain.append(f"vignette={angle}")
            
        # Sharpness
        sharp = filters.get("sharpness", 0.0) # 0 to 1
        if sharp > 0:
            # luma_msize_x:luma_msize_y:luma_amount
            # 5:5:1.0 is strong
            amount = sharp * 1.5
            chain.append(f"unsharp=5:5:{amount}:5:5:0.0")

        # Highlights/Shadows (Curves)
        hil = filters.get("highlights", 0.0) # -1 to 1
        sha = filters.get("shadows", 0.0) # -1 to 1
        
        if hil != 0 or sha != 0:
            # Generate curves string
            # 0/0  0.25/y1  0.5/0.5  0.75/y2  1/1
            # Shadow point (0.25)
            y_sha = 0.25 + (sha * 0.1)
            # Highlight point (0.75)
            y_hil = 0.75 + (hil * 0.1)
            
            chain.append(f"curves=master='0/0 0.25/{y_sha} 0.75/{y_hil} 1/1'")

        # 4. Special Effects
        effect = filters.get("effect", "none")
        if effect == "glitch":
            # Chromatic aberration + slight shake (simulated)
            chain.append("chromashift=cbh=-5:cbv=-5:crh=5:crv=5")
            chain.append("noise=alls=20:allf=t+u")
        elif effect == "pixelate":
            # Scale down then up
            chain.append("scale=iw/10:ih/10:flags=nearest")
            chain.append("scale=iw*10:ih*10:flags=nearest")
        elif effect == "noise":
            chain.append("noise=alls=40:allf=t+u")
        elif effect == "blur":
            chain.append("boxblur=10:1")
        elif effect == "negate":
            chain.append("negate")
        elif effect == "edge":
            chain.append("edgedetect=low=0.1:high=0.4")
        elif effect == "mirror":
            chain.append("hflip")
        elif effect == "zoom":
             # Slow zoom in (requires complex filter, skipping for now or simple zoompan)
             pass
             
        return chain

    @staticmethod
    def apply_filters_to_image(image_path, filters, output_path):
        """
        Applies filters to a single image using FFmpeg.
        """
        import subprocess
        
        chain = VideoFilters.get_filter_chain(filters)
        vf_str = ",".join(chain) if chain else "null"
        
        cmd = [
            "ffmpeg", "-y",
            "-i", image_path,
            "-vf", vf_str,
            output_path
        ]
        
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

