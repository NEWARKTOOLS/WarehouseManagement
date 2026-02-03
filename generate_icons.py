"""
Generate PWA icons for WMS application.
Run this script once to create the icon files.
Requires: pip install pillow
"""

from PIL import Image, ImageDraw

def create_icon(size, filename):
    """Create a simple warehouse icon"""
    # Create image with blue background
    img = Image.new('RGBA', (size, size), (13, 110, 253, 255))
    draw = ImageDraw.Draw(img)

    # Calculate scaling
    scale = size / 512

    # Draw warehouse roof (triangle)
    roof_points = [
        (256 * scale, 96 * scale),  # top
        (416 * scale, 160 * scale),  # right
        (96 * scale, 160 * scale),   # left
    ]
    draw.polygon(roof_points, fill=(255, 255, 255, 255))

    # Draw warehouse body
    body = [
        96 * scale, 160 * scale,
        416 * scale, 416 * scale
    ]
    draw.rectangle(body, fill=(255, 255, 255, 80))

    # Draw boxes/shelves
    box1 = [176 * scale, 240 * scale, 240 * scale, 336 * scale]
    box2 = [272 * scale, 240 * scale, 336 * scale, 336 * scale]
    draw.rectangle(box1, fill=(255, 255, 255, 255))
    draw.rectangle(box2, fill=(255, 255, 255, 255))

    # Draw barcode lines at bottom
    barcode_y = 360 * scale
    barcode_h = 32 * scale
    bars = [
        (184, 8), (200, 4), (212, 8), (228, 4),
        (240, 12), (260, 4), (272, 8), (288, 4),
        (300, 8), (316, 4)
    ]
    for x, w in bars:
        draw.rectangle([
            x * scale, barcode_y,
            (x + w) * scale, barcode_y + barcode_h
        ], fill=(255, 255, 255, 255))

    # Save
    img.save(filename, 'PNG')
    print(f"Created: {filename}")

if __name__ == '__main__':
    import os

    # Ensure directory exists
    img_dir = os.path.join(os.path.dirname(__file__), 'app', 'static', 'img')
    os.makedirs(img_dir, exist_ok=True)

    # Generate icons
    create_icon(192, os.path.join(img_dir, 'icon-192.png'))
    create_icon(512, os.path.join(img_dir, 'icon-512.png'))

    print("Icons generated successfully!")
