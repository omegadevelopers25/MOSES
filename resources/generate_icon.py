"""Generate app icons for MOSES"""
from PIL import Image, ImageDraw, ImageFont
import os

def create_icon(size, output_path):
    """Create a simple icon with the MOSES logo"""
    # Create a square image with a dark background
    img = Image.new('RGB', (size, size), color='#05070b')
    draw = ImageDraw.Draw(img)
    
    # Draw a circle with cyan border
    margin = size // 10
    draw.ellipse([margin, margin, size-margin, size-margin], 
                 outline='#5cddff', width=size//20)
    
    # Draw "M" in the center
    try:
        # Try to use a system font
        font_size = size // 2
        font = ImageFont.truetype("arial.ttf", font_size)
    except:
        # Fall back to default font
        font = ImageFont.load_default()
    
    text = "M"
    # Get text bounding box
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    
    # Center the text
    x = (size - text_width) // 2
    y = (size - text_height) // 2
    
    draw.text((x, y), text, fill='#5cddff', font=font)
    
    # Save the image
    img.save(output_path)
    print(f"Created icon: {output_path}")

def main():
    icon_dir = os.path.dirname(os.path.abspath(__file__))
    base_path = os.path.join(icon_dir, 'moses_icon')
    
    # Create icons for different sizes
    sizes = [
        (72, 'icon-72.png'),
        (96, 'icon-96.png'),
        (128, 'icon-128.png'),
        (144, 'icon-144.png'),
        (152, 'icon-152.png'),
        (192, 'icon-192.png'),
        (384, 'icon-384.png'),
        (512, 'icon-512.png'),
    ]
    
    for size, filename in sizes:
        output_path = os.path.join(base_path, filename)
        create_icon(size, output_path)
    
    print("\nIcon generation complete!")
    print(f"Icons saved to: {base_path}")

if __name__ == "__main__":
    main()
