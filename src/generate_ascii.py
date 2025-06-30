import os
import sys
from PIL import Image
import argparse

# --- Constants ---
ASCII_CHARS = "M%#*+=-:. "
ASCII_FILE = "ascii.txt"

def generate_ascii(image_path, width=70):
    """Generates ASCII from an image file and returns it as a string."""
    try:
        image = Image.open(image_path).convert('L')
        aspect_ratio = image.height / image.width
        # Halve the height to compensate for character aspect ratio
        height = int(aspect_ratio * width * 0.5)
        image = image.resize((width, height))
        
        pixels = image.getdata()
        ascii_str = "".join([ASCII_CHARS[pixel * (len(ASCII_CHARS)-1) // 255] for pixel in pixels])
        
        return "\n".join([ascii_str[i:i+width] for i in range(0, len(ascii_str), width)])
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
    args = parser.parse_args()

    # The script is in /src, so construct path relative to the root
    script_dir = os.path.dirname(__file__)
    root_dir = os.path.dirname(script_dir)
    image_path = os.path.join(root_dir, args.img_file)

    print(f"🎨 Generating ASCII from '{image_path}'...")
    ascii = generate_ascii(image_path)
    
    if ascii:
        try:
            output_path = os.path.join(root_dir, ASCII_FILE)
            with open(output_path, "w") as f:
                f.write(ascii)
            print(f"✅ ASCII successfully saved to {output_path}")
        except IOError as e:
            print(f"❌ Failed to write to file {ASCII_FILE}: {e}")
    else:
        print("❌ ASCII generation failed.")

if __name__ == '__main__':
    main() 