import os
import sys
from PIL import Image
import argparse

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

    print(f"🎨 Generating ASCII from '{image_path}'...")
    ascii_content = generate_ascii(image_path, args.width, args.height)
    
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