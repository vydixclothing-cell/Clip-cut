
def generate_filters():
    filters = {}
    
    # User Requested Presets
    # "Punch", "Golden", "Radiate", "Warm Contrast", "Calm", "Cool Light", "Vivid Cool", "Dramatic Cool"
    
    filters["punch"] = {
        "label": "Punch",
        "css": "contrast(1.3) saturate(1.3)",
        "ffmpeg": ["eq=contrast=1.3:saturation=1.3"]
    }
    
    filters["golden"] = {
        "label": "Golden",
        "css": "sepia(0.3) contrast(1.1) saturate(1.2)",
        "ffmpeg": ["eq=contrast=1.1:saturation=1.2", "colorbalance=rs=0.1:gs=0.05:bs=-0.15"]
    }
    
    filters["radiate"] = {
        "label": "Radiate",
        "css": "brightness(1.1) contrast(1.1) saturate(1.1)",
        "ffmpeg": ["eq=brightness=0.1:contrast=1.1:saturation=1.1"]
    }
    
    filters["warm_contrast"] = {
        "label": "Warm Contrast",
        "css": "contrast(1.2) sepia(0.2)",
        "ffmpeg": ["eq=contrast=1.2", "colorbalance=rs=0.1:bs=-0.1"]
    }
    
    filters["calm"] = {
        "label": "Calm",
        "css": "contrast(0.9) saturate(0.8) brightness(1.05)",
        "ffmpeg": ["eq=contrast=0.9:saturation=0.8:brightness=0.05"]
    }
    
    filters["cool_light"] = {
        "label": "Cool Light",
        "css": "hue-rotate(180deg) sepia(0.1) hue-rotate(-180deg) brightness(1.1)", # Approx
        "ffmpeg": ["eq=brightness=0.1", "colorbalance=bs=0.1:rs=-0.05"]
    }
    
    filters["vivid_cool"] = {
        "label": "Vivid Cool",
        "css": "saturate(1.4) hue-rotate(180deg) sepia(0.1) hue-rotate(-180deg)",
        "ffmpeg": ["eq=saturation=1.4", "colorbalance=bs=0.15:rs=-0.1"]
    }
    
    filters["dramatic_cool"] = {
        "label": "Dramatic Cool",
        "css": "contrast(1.3) saturate(0.8) hue-rotate(180deg) sepia(0.2) hue-rotate(-180deg)",
        "ffmpeg": ["eq=contrast=1.3:saturation=0.8", "colorbalance=bs=0.2:rs=-0.2"]
    }

    # 1. Basic (1-5)
    for i in range(1, 6):
        con = 1.0 + (i * 0.05)
        sat = 1.0 + (i * 0.05)
        name = f"basic_{i}"
        filters[name] = {
            "label": f"Basic {i}",
            "css": f"contrast({con}) saturate({sat})",
            "ffmpeg": [f"eq=contrast={con}:saturation={sat}"]
        }

    # 2. Vintage (1-5)
    for i in range(1, 6):
        sepia = 0.2 + (i * 0.05)
        name = f"vintage_{i}"
        filters[name] = {
            "label": f"Vintage {i}",
            "css": f"sepia({sepia}) contrast(1.1)",
            "ffmpeg": [f"eq=contrast=1.1:saturation=0.7", f"colorbalance=rs={0.1 + i*0.02}:bs=-{0.1 + i*0.02}"]
        }

    # 3. B&W (1-5)
    for i in range(1, 6):
        con = 1.0 + (i * 0.1)
        name = f"bw_{i}"
        filters[name] = {
            "label": f"B&W {i}",
            "css": f"grayscale(1) contrast({con})",
            "ffmpeg": [f"eq=saturation=0:contrast={con}"]
        }

    # 4. Cinematic (1-5)
    for i in range(1, 6):
        name = f"cine_{i}"
        rs = -0.05 * i
        bs = 0.05 * i
        filters[name] = {
            "label": f"Cinematic {i}",
            "css": f"contrast(1.2) saturate(1.1) sepia(0.1)", 
            "ffmpeg": [f"eq=contrast=1.2:saturation=1.1", f"colorbalance=rs={rs}:bs={bs}:rh={-rs}:bh={-bs}"]
        }

    return filters

FILTER_LIBRARY = generate_filters()
