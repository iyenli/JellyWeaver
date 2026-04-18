"""Generate JellyWeaver app icon: a stylised link-chain inside a rounded square."""
from PIL import Image, ImageDraw

SIZE = 256

def make_icon(size=SIZE):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    s = size

    # Background: deep navy rounded square
    r = s // 6
    d.rounded_rectangle([0, 0, s - 1, s - 1], radius=r, fill=(18, 22, 38, 255))

    # Two overlapping circles (link / chain symbol)
    # Catppuccin-ish palette: sapphire blue + mauve purple
    cx = s // 2
    cy = s // 2
    cr = s // 5        # circle radius
    gap = s // 8       # how far each circle is offset from centre
    lw = max(4, s // 20)  # ring line width

    # Left ring — sapphire
    lx = cx - gap
    d.ellipse([lx - cr, cy - cr, lx + cr, cy + cr], outline=(116, 199, 236, 255), width=lw)

    # Right ring — mauve
    rx = cx + gap
    d.ellipse([rx - cr, cy - cr, rx + cr, cy + cr], outline=(203, 166, 247, 255), width=lw)

    # Small accent dot in the centre overlap
    dot = lw
    d.ellipse([cx - dot, cy - dot, cx + dot, cy + dot], fill=(250, 179, 135, 255))

    return img

sizes = [16, 32, 48, 64, 128, 256]
frames = []
for sz in sizes:
    frames.append(make_icon(sz).resize((sz, sz), Image.LANCZOS))

frames[-1].save(
    "icon.ico",
    format="ICO",
    sizes=[(f.width, f.height) for f in frames],
    append_images=frames[:-1],
)
print("icon.ico written")
