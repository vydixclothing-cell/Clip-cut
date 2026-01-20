class PlatformPresets:
    def __init__(self):
        self.presets = {
            "shorts": {"width": 1080, "height": 1920, "aspect": 9/16},
            "reels_instagram": {"width": 1080, "height": 1920, "aspect": 9/16},
            "reels_facebook": {"width": 1080, "height": 1920, "aspect": 9/16},
        }

    def get(self, platform):
        return self.presets.get(platform, self.presets["shorts"])
