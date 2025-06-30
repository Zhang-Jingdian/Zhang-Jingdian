import os
import sys
from PIL import Image
import argparse

# --- Constants ---
# Character set for retro pixel art style
ASCII_CHARS = " ░▒▓█"
DEFAULT_IMAGE_FILE = "ascii.png"
OUTPUT_DIR = "output"
OUTPUT_ASCII_FILE = "ascii.txt"

def generate_ascii(image_path, width=None, height=None):
    """
    Generates ASCII from an image file.
    Automatically scales to fit a target container if no dimensions are given.
    """
    # Constants for the target container in the SVG
    MAX_WIDTH_CHARS = 45
    MAX_HEIGHT_LINES = 26  # Approx. 400px / 15px line height
    CHAR_ASPECT_RATIO_CORRECTION = 0.5  # To compensate for non-square characters

    try:
        image = Image.open(image_path).convert('L')
        img_width, img_height = image.size
        img_aspect_ratio = img_height / img_width

        if width and height:
            # Manual override: use provided dimensions
            new_width, new_height = width, height
        elif width:
            # Manual width: calculate height
            new_width = width
            new_height = int(img_aspect_ratio * new_width * CHAR_ASPECT_RATIO_CORRECTION)
        elif height:
            # Manual height: calculate width
            new_height = height
            new_width = int(new_height / (img_aspect_ratio * CHAR_ASPECT_RATIO_CORRECTION))
        else:
            # Automatic scaling: fit to the container
            # Check if scaling to max width would exceed max height
            scaled_height = int(img_aspect_ratio * MAX_WIDTH_CHARS * CHAR_ASPECT_RATIO_CORRECTION)
            if scaled_height > MAX_HEIGHT_LINES:
                # It's a "tall" image, so scale based on height
                new_height = MAX_HEIGHT_LINES
                new_width = int(new_height / (img_aspect_ratio * CHAR_ASPECT_RATIO_CORRECTION))
            else:
                # It's a "wide" image, so scale based on width
                new_width = MAX_WIDTH_CHARS
                new_height = scaled_height

        # Ensure dimensions are valid before resizing
        if not new_width or not new_height or new_width <= 0 or new_height <= 0:
             print(f"❌ Error: Invalid dimensions calculated ({new_width}x{new_height}).")
             return None

        image = image.resize((new_width, new_height))
        
        # Build the ASCII text block row by row to prevent alignment issues
        ascii_rows = []
        for y in range(new_height):
            row_str = ""
            for x in range(new_width):
                pixel = image.getpixel((x, y))
                # For 'L' mode, pixel is an integer. Handle potential type issues gracefully.
                if isinstance(pixel, int):
                    char_index = (pixel * (len(ASCII_CHARS) - 1)) // 255
                    row_str += ASCII_CHARS[char_index]
                else:
                    # Fallback for unexpected pixel formats, though 'L' mode should prevent this.
                    row_str += " " 
            ascii_rows.append(row_str)
        
        return "\n".join(ascii_rows)
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
            # Ensure output directory exists
            output_dir_path = os.path.join(root_dir, OUTPUT_DIR)
            os.makedirs(output_dir_path, exist_ok=True)
            
            output_file_path = os.path.join(output_dir_path, OUTPUT_ASCII_FILE)
            with open(output_file_path, "w") as f:
                f.write(ascii_content)
            print(f"✅ ASCII successfully saved to {output_file_path}")
        except IOError as e:
            print(f"❌ Failed to write to file {OUTPUT_ASCII_FILE}: {e}")
    else:
        print("❌ ASCII generation failed.")

if __name__ == '__main__':
    main() 