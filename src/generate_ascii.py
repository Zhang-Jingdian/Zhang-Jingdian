import os
import sys
from PIL import Image
import argparse
from lxml import etree

# --- Constants ---
ASCII_CHARS = "M%#*+=-:. "
ASCII_FILE = "ascii.txt"

def generate_ascii(image_path, width=None, height=None):
    """Generates ASCII from an image file, preserving aspect ratio."""
    if width is None and height is None:
        width = 45  # Default width to fit the left panel

    try:
        image = Image.open(image_path).convert('L')
        img_width, img_height = image.size
        aspect_ratio = img_height / img_width
        char_height_correction = 0.5  # To compensate for non-square characters

        new_width = width
        new_height = height

        if new_width and new_height:
            # Both dimensions provided, use them as is
            pass
        elif new_width:
            # Width is provided, calculate height
            new_height = int(aspect_ratio * new_width * char_height_correction)
        elif new_height:
            # Height is provided, calculate width
            new_width = int(new_height / (aspect_ratio * char_height_correction))
        
        # Ensure dimensions are valid before resizing
        if not new_width or not new_height or new_width <= 0 or new_height <= 0:
             print(f"❌ Error: Invalid dimensions calculated ({new_width}x{new_height}).")
             return None

        image = image.resize((new_width, new_height))
        
        pixels = image.getdata()
        ascii_str = "".join([ASCII_CHARS[pixel * (len(ASCII_CHARS)-1) // 255] for pixel in pixels])
        
        return "\n".join([ascii_str[i:i+new_width] for i in range(0, len(ascii_str), new_width)])
    except FileNotFoundError:
        print(f"❌ Error: Image file not found at '{image_path}'")
        return None
    except Exception as e:
        print(f"❌ Failed to generate ASCII: {e}")
        return None

def main():
    """Main function to generate and save ASCII."""
    parser = argparse.ArgumentParser(description="Convert an image to ASCII.")
    parser.add_argument(
        '--file',
        dest='img_file',
        required=False,
        default='ascii.png',
        help="Path to the input image file (default: ascii.png in the project root)."
    )
    parser.add_argument(
        '--width',
        dest='width',
        type=int,
        help="The target width of the ASCII art (in characters)."
    )
    parser.add_argument(
        '--height',
        dest='height',
        type=int,
        help="The target height of the ASCII art (in characters)."
    )
    args = parser.parse_args()

    # The script is in /src, so construct path relative to the root
    script_dir = os.path.dirname(__file__)
    root_dir = os.path.dirname(script_dir)
    image_path = os.path.join(root_dir, args.img_file)
    
    # --- Dynamic Width Calculation ---
    final_width = args.width
    final_height = args.height
    
    # If width/height are not user-provided, calculate from SVG template
    if final_width is None and final_height is None:
        template_path = os.path.join(root_dir, "templates", "dark_mode.svg")
        try:
            tree = etree.parse(template_path)
            root = tree.getroot()
            width_str = root.get("width", "800px")
            font_size_str = root.get("font-size", "14px")
            
            svg_width = float(width_str.replace('px', ''))
            font_size = float(font_size_str.replace('px', ''))
            
            # Approximation for character width based on font size
            char_width_ratio = 0.6 
            char_pixel_width = font_size * char_width_ratio
            panel_pixel_width = svg_width / 2
            
            # Subtract some padding from the panel width
            padding = 30 # 15px on each side
            final_width = int((panel_pixel_width - padding) / char_pixel_width)

        except Exception as e:
            print(f"🎨 Warning: Could not read SVG template to get dimensions: {e}")
            print("Falling back to default width of 45.")
            final_width = 45 # Fallback to previous default

    print(f"🎨 Generating ASCII from '{image_path}'...")
    ascii_content = generate_ascii(image_path, final_width, final_height)
    
    if ascii_content:
        try:
            output_path = os.path.join(root_dir, ASCII_FILE)
            with open(output_path, "w") as f:
                f.write(ascii_content)
            print(f"✅ ASCII successfully saved to {output_path}")
        except IOError as e:
            print(f"❌ Failed to write to file {ASCII_FILE}: {e}")
    else:
        print("❌ ASCII generation failed.")

if __name__ == '__main__':
    main() 