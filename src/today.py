import os
import sys
import requests
from lxml import etree
from dotenv import load_dotenv
from tqdm import tqdm

# --- Path Configuration ---
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(ROOT_DIR, "output")
ASCII_FILE_PATH = os.path.join(OUTPUT_DIR, "ascii.txt")
DARK_MODE_TEMPLATE_PATH = os.path.join(ROOT_DIR, "templates", "dark_mode.svg")
LIGHT_MODE_TEMPLATE_PATH = os.path.join(ROOT_DIR, "templates", "light_mode.svg")

# --- SVG Configuration ---
SVG_HEIGHT = 400
ASCII_LINE_HEIGHT = 15
ASCII_FONT_SIZE = 15
INFO_LINE_HEIGHT = 20
INFO_SEPARATOR_HEIGHT = 25

def check_env_vars():
    """Checks for required environment variables."""
    if not os.getenv("ACCESS_TOKEN") or not os.getenv("USER_NAME"):
        print("❌ 错误：环境变量 ACCESS_TOKEN 或 USER_NAME 未设置。")
        sys.exit(1)

def fetch_github_api(url, headers):
    """Generic function to fetch data from GitHub API."""
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"❌ API request to {url} failed: {e}")
        return None

def get_user_stats(username, token):
    """Fetches user's total public repos and followers."""
    url = f"https://api.github.com/users/{username}"
    headers = {"Authorization": f"bearer {token}"}
    data = fetch_github_api(url, headers)
    if not data:
        return 0, 0
    return data.get("public_repos", 0), data.get("followers", 0)

def get_total_commits(username, token):
    """Fetches user's total commits via the search API."""
    url = f"https://api.github.com/search/commits?q=author:{username}"
    headers = {
        "Authorization": f"bearer {token}",
        "Accept": "application/vnd.github.cloak-preview"
    }
    data = fetch_github_api(url, headers)
    if not data:
        return 0
    return data.get("total_count", 0)

def update_svg(template_path, output_path, stats, ascii_content):
    """Updates SVG with latest statistics and ASCII text, and saves it to the output directory."""
    try:
        tree = etree.parse(template_path)
    except etree.XMLSyntaxError as e:
        print(f"❌ Error parsing {template_path}: {e}")
        return

    root = tree.getroot()
    ns = {'svg': 'http://www.w3.org/2000/svg'}

    # Center ASCII content
    if ascii_content:
        ascii_container = root.find(".//*[@id='ascii']", namespaces=ns)
        if ascii_container is not None:
            # Clear existing content
            for element in list(ascii_container):
                ascii_container.remove(element)
            
            lines = ascii_content.splitlines()
            total_height = len(lines) * ASCII_LINE_HEIGHT
            # Start Y so the whole block is centered
            y_offset = (SVG_HEIGHT - total_height) / 2 + ASCII_FONT_SIZE

            # Use relative dy for subsequent lines for cleaner SVG code
            for i, line in enumerate(lines):
                attrs = {"x": "200"} # Horizontal center of the left panel
                if i == 0:
                    attrs['y'] = str(y_offset)
                else:
                    attrs['dy'] = str(ASCII_LINE_HEIGHT)
                
                tspan = etree.SubElement(ascii_container, "tspan", **attrs)
                tspan.text = line
                tspan.tail = '\n' + ' ' * 10 # Indentation for readability
            
            if len(ascii_container) > 0:
                ascii_container.text = '\n' + ' ' * 8
                ascii_container[-1].tail = '\n' + ' ' * 6

    # Update stats in the Info Panel
    info_panel = root.find(".//*[@id='info-panel']", namespaces=ns)
    if info_panel is not None:
        ids_to_update = {
            'commit_data': stats.get('commits', 0),
            'star_data': stats.get('stars', 0),
            'follower_data': stats.get('followers', 0)
        }
        for element_id, value in ids_to_update.items():
            element = info_panel.find(f".//*[@id='{element_id}']", namespaces=ns)
            if element is not None:
                element.text = f"{value:,}"

    # Write the modified tree to the output directory
    try:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        tree.write(output_path, pretty_print=True, xml_declaration=True, encoding='UTF-8')
    except IOError as e:
        print(f"❌ Failed to write SVG to {output_path}: {e}")

def main():
    """Main function."""
    load_dotenv()
    check_env_vars()
    
    username = os.getenv("USER_NAME")
    token = os.getenv("ACCESS_TOKEN")
    
    ascii_content = None
    try:
        with open(ASCII_FILE_PATH, "r") as f:
            ascii_content = f.read()
    except FileNotFoundError:
        print(f"🎨 Warning: {os.path.basename(ASCII_FILE_PATH)} not found. Skipping ASCII update.")
    except IOError as e:
        print(f"🎨 Warning: Could not read {os.path.basename(ASCII_FILE_PATH)}: {e}")

    with tqdm(total=3, desc="🚀 Updating profile stats") as pbar:
        pbar.set_description("📊 Fetching commits...")
        commits = get_total_commits(username, token)
        pbar.update(1)

        pbar.set_description("📊 Fetching repos and followers...")
        repos, followers = get_user_stats(username, token)
        pbar.update(1)

        # NOTE: The GitHub 'stars' count via this API method can be inaccurate as it sums stars from all repos.
        # A more accurate GraphQL query would be better for this in the future.
        stats = {'commits': commits, 'stars': repos, 'followers': followers}
        
        pbar.set_description("✍️ Writing to SVG files...")
        output_dark_path = os.path.join(OUTPUT_DIR, "dark_mode.svg")
        output_light_path = os.path.join(OUTPUT_DIR, "light_mode.svg")
        update_svg(DARK_MODE_TEMPLATE_PATH, output_dark_path, stats, ascii_content)
        update_svg(LIGHT_MODE_TEMPLATE_PATH, output_light_path, stats, ascii_content)
        pbar.update(1)

    print(f"✅ Profile updated successfully! Find your SVGs in the '{OUTPUT_DIR}' directory.")

if __name__ == '__main__':
    main() 