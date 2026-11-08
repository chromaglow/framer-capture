"""Generate framer/assets/framer.ico (16-256 px) and click.wav. Run as the first build step."""
import sys
from pathlib import Path
from PIL import Image, ImageDraw

# Setup paths
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from framer.sounds import synth_click_wav_bytes  # noqa: E402

def main():
    ASSETS = ROOT / "framer" / "assets"
    ASSETS.mkdir(parents=True, exist_ok=True)

    sizes = [16, 24, 32, 48, 64, 128, 256]
    images = []

    for size in sizes:
        # Supersampling factor
        scale = 4
        sw, sh = size * scale, size * scale
        
        # Create base image
        img = Image.new("RGBA", (sw, sh), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        
        # Constants for the drawing
        bg_color = "#16181D"
        accent_color = "#22D3EE"
        radius = (size * 0.22) * scale
        m = (size * 0.22) * scale
        arm = (size * 0.20) * scale
        w = max(1, round(size * 0.11)) * scale
        
        # Draw rounded background
        draw.rounded_rectangle(
            [0, 0, sw - 1, sh - 1],
            radius=radius,
            fill=bg_color
        )
        
        # Corner brackets
        # Top-left: (m, m) arms right and down
        # Top-right: (sw - m, m) arms left and down
        # Bottom-left: (m, sh - m) arms right and up
        # Bottom-right: (sw - m, sh - m) arms left and up
        corners = [
            # Top-left
            {"pt": (m, m), "arms": [(m + arm, m), (m, m + arm)]},
            # Top-right
            {"pt": (sw - m, m), "arms": [(sw - m - arm, m), (sw - m, m + arm)]},
            # Bottom-left
            {"pt": (m, sh - m), "arms": [(m + arm, sh - m), (m, sh - m - arm)]},
            # Bottom-right
            {"pt": (sw - m, sh - m), "arms": [(sw - m - arm, sh - m), (sw - m, sh - m - arm)]},
        ]

        for corner in corners:
            x, y = corner["pt"]
            # Draw the two arm segments
            for end_pt in corner["arms"]:
                draw.line([corner["pt"], end_pt], fill=accent_color, width=w)
            # Draw the joining square
            draw.rectangle(
                [x - w//2, y - w//2, x + w//2, y + w//2],
                fill=accent_color
            )

        # Resize back to original size
        img = img.resize((size, size), Image.Resampling.LANCZOS)
        images.append(img)

    # Sort images largest first for ICO format (256 down to 16)
    images.sort(key=lambda x: x.width, reverse=True)

    # Save ICO
    icon_path = ASSETS / "framer.ico"
    images[0].save(
        icon_path,
        format="ICO",
        sizes=[(im.width, im.height) for im in images],
        append_images=images[1:]
    )

    # Save 256 PNG
    png_path = ASSETS / "icon_256.png"
    images[0].save(png_path)

    # Save WAV
    wav_path = ASSETS / "click.wav"
    with open(wav_path, "wb") as f:
        f.write(synth_click_wav_bytes())

    print(f"Created icon: {icon_path}")
    print(f"Created reference: {png_path}")
    print(f"Created sound: {wav_path}")

if __name__ == "__main__":
    main()