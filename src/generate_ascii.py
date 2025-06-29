import os
import sys
import requests
from PIL import Image
import io
from dotenv import load_dotenv

# --- Constants ---
ASCII_CHARS = "M%#*+=-:. "
ART_FILE = "ascii_art.txt"

# --- Functions ---
def user_getter(username, token):
    """Fetches user avatar URL via GitHub GraphQL API."""
    headers = {"Authorization": f"bearer {token}"}
    query = "query($username: String!) { user(login: $username) { avatarUrl } }"
    variables = {"username": username}
    try:
        response = requests.post("https://api.github.com/graphql", json={'query': query, 'variables': variables}, headers=headers)
        response.raise_for_status()
        data = response.json()
        if data and data.get('data') and data['data'].get('user'):
            return data['data']['user']['avatarUrl']
    except requests.exceptions.RequestException as e:
        print(f"❌ API query failed: {e}")
    return None

def generate_ascii_avatar(image_url, width=35):
    """Generates ASCII art from an image URL and returns it as a string."""
    try:
        response = requests.get(image_url, stream=True)
        response.raise_for_status()
        image = Image.open(io.BytesIO(response.content)).convert('L')
        aspect_ratio = image.height / image.width
        height = int(aspect_ratio * width * 0.5)
        image = image.resize((width, height))
        
        pixels = image.getdata()
        ascii_str = "".join([ASCII_CHARS[pixel * (len(ASCII_CHARS)-1) // 255] for pixel in pixels])
        
        return "\n".join([ascii_str[i:i+width] for i in range(0, len(ascii_str), width)])
    except Exception as e:
        print(f"❌ Failed to generate ASCII art: {e}")
    return None

def main():
    """Main function to generate and save ASCII art."""
    print("🚀 Starting ASCII art generation...")
    load_dotenv()
    
    token = os.getenv("ACCESS_TOKEN")
    username = os.getenv("USER_NAME")

    if not token or not username:
        print("❌ 错误：请确保 .env 文件中已设置 ACCESS_TOKEN 和 USER_NAME。")
        sys.exit(1)
        
    print(f"👤 Fetching avatar for user: {username}")
    avatar_url = user_getter(username, token)
    
    if not avatar_url:
        print("❌ Could not fetch avatar URL. Exiting.")
        sys.exit(1)
        
    print("🎨 Generating ASCII art from avatar...")
    ascii_art = generate_ascii_avatar(avatar_url)
    
    if ascii_art:
        try:
            # Save to root directory
            output_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ART_FILE)
            with open(output_path, "w") as f:
                f.write(ascii_art)
            print(f"✅ ASCII art successfully saved to {output_path}")
        except IOError as e:
            print(f"❌ Failed to write to file {ART_FILE}: {e}")
    else:
        print("❌ ASCII art generation failed.")

if __name__ == '__main__':
    main() 