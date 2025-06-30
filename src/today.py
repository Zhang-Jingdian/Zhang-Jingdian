import os
import sys
import requests
from lxml import etree
from dotenv import load_dotenv
from tqdm import tqdm

# --- Path Configuration ---
# The script is in /src, so we need to go up one level for root
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASCII_FILE_PATH = os.path.join(ROOT_DIR, "ascii.txt")
DARK_MODE_SVG_PATH = os.path.join(ROOT_DIR, "templates", "dark_mode.svg")
LIGHT_MODE_SVG_PATH = os.path.join(ROOT_DIR, "templates", "light_mode.svg")

def check_env_vars():
    """Checks for required environment variables."""
    if not os.getenv("ACCESS_TOKEN") or not os.getenv("USER_NAME"):
        print("❌ 错误：环境变量 ACCESS_TOKEN 或 USER_NAME 未设置。")
        sys.exit(1)

def run_query(query, variables):
    """Executes a GraphQL query."""
    headers = {"Authorization": f"bearer {os.getenv('ACCESS_TOKEN')}"}
    try:
        response = requests.post("https://api.github.com/graphql", json={'query': query, 'variables': variables}, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"GraphQL query failed: {e}")
        return None

def stats_getter(username):
    """Fetches commit, star, and follower counts."""
    query = """
    query ($username: String!) {
        user(login: $username) {
            contributionsCollection {
                totalCommitContributions
                restrictedContributionsCount
            }
            repositories(ownerAffiliations: OWNER, first: 100, orderBy: {field: PUSHED_AT, direction: DESC}) {
                nodes {
                    stargazers {
                        totalCount
                    }
                }
            }
            followers {
                totalCount
            }
        }
    }
    """
    variables = {"username": username}
    data = run_query(query, variables)
    if not data or not data.get('data') or not data['data'].get('user'):
        return 0, 0, 0
    
    user_data = data['data']['user']
    commits = user_data['contributionsCollection']['totalCommitContributions'] + user_data['contributionsCollection']['restrictedContributionsCount']
    stars = sum(repo['stargazers']['totalCount'] for repo in user_data['repositories']['nodes'])
    followers = user_data['followers']['totalCount']
    return commits, stars, followers

def update_svg(svg_path, stats, ascii_content):
    """Updates SVG, dynamically positioning panels and centering content."""
    try:
        parser = etree.XMLParser(remove_blank_text=True)
        tree = etree.parse(svg_path, parser)
    except etree.XMLSyntaxError as e:
        print(f"❌ Error parsing {svg_path}: {e}")
        return
        
    root = tree.getroot()
    ns = {'svg': 'http://www.w3.org/2000/svg'}

    # Dynamically get dimensions from SVG
    width_str = root.get("width", "800px")
    height_str = root.get("height", "400px")
    svg_width = float(width_str.replace('px', ''))
    svg_height = float(height_str.replace('px', ''))
    
    # --- Left Panel (ASCII) ---
    if ascii_content:
        ascii_container = root.find(".//*[@id='ascii']", namespaces=ns)
        if ascii_container is not None:
            lines = ascii_content.splitlines()
            line_height = 15
            total_height = len(lines) * line_height
            y_start = (svg_height - total_height) / 2 + line_height

            for element in list(ascii_container):
                ascii_container.remove(element)
            
            ascii_container.text = '\n' + ' ' * 8
            for i, line in enumerate(lines):
                tspan = etree.SubElement(ascii_container, "tspan", x="15", y=str(y_start + i * line_height))
                tspan.text = line
                tspan.tail = '\n' + ' ' * 8
            if len(ascii_container) > 0:
                ascii_container[-1].tail = '\n' + ' ' * 6

    # --- Right Panel (Info) ---
    info_panel = root.find(".//*[@id='info-panel']", namespaces=ns)
    if info_panel is not None:
        # Dynamically position the panel to the right half
        right_panel_group = info_panel.getparent()
        right_panel_group.set('transform', f'translate({svg_width / 2}, 0)')

        # Update stats
        ids_to_update = {
            'commit_data': stats.get('commits', 0),
            'star_data': stats.get('stars', 0),
            'follower_data': stats.get('followers', 0)
        }
        for element_id, value in ids_to_update.items():
            element = info_panel.find(f".//*[@id='{element_id}']", namespaces=ns)
            if element is not None:
                element.text = f"{value:,}"

        # Vertically center the entire block
        info_lines = info_panel.findall('svg:tspan', namespaces=ns)
        total_info_height = len(info_lines) * 20 + 5 # Add a little extra for separators
        info_y_start = (svg_height - total_info_height) / 2 + 15
        
        current_y = info_y_start
        for tspan in info_lines:
            tspan.set('y', str(current_y))
            if '---' in (tspan.text or ''):
                 current_y += 25
            else:
                current_y += 20
    
    tree.write(svg_path, pretty_print=True, xml_declaration=True, encoding='UTF-8')

def main():
    """Main function."""
    load_dotenv()
    check_env_vars()
    
    username = os.getenv("USER_NAME")
    
    ascii_content = None
    try:
        with open(ASCII_FILE_PATH, "r") as f:
            ascii_content = f.read()
    except FileNotFoundError:
        print(f"🎨 Warning: {os.path.basename(ASCII_FILE_PATH)} not found. Skipping ASCII update.")
    except IOError as e:
        print(f"🎨 Warning: Could not read {os.path.basename(ASCII_FILE_PATH)}: {e}")

    with tqdm(total=2, desc="🚀 Updating profile stats") as pbar:
        pbar.set_description("📊 Fetching stats...")
        commits, stars, followers = stats_getter(username)
        stats = {'commits': commits, 'stars': stars, 'followers': followers}
        pbar.update(1)
        
        pbar.set_description("✍️ Writing to SVG files...")
        update_svg(DARK_MODE_SVG_PATH, stats, ascii_content)
        update_svg(LIGHT_MODE_SVG_PATH, stats, ascii_content)
        pbar.update(1)

    print("✅ Profile updated successfully!")

if __name__ == '__main__':
    main() 