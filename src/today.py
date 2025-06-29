import os
import sys
import requests
from lxml import etree
from dotenv import load_dotenv
from tqdm import tqdm

# --- Path Configuration ---
# The script is in /src, so we need to go up one level for root
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ART_FILE_PATH = os.path.join(ROOT_DIR, "ascii_art.txt")
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

def update_svg(svg_path, stats, ascii_art):
    """Updates SVG with latest statistics and ASCII art."""
    try:
        tree = etree.parse(svg_path)
    except etree.XMLSyntaxError as e:
        print(f"❌ Error parsing {svg_path}: {e}")
        return
        
    root = tree.getroot()
    ns = {'svg': 'http://www.w3.org/2000/svg'}

    # Update stats
    ids_to_update = {
        'commit_data': stats.get('commits', 0),
        'star_data': stats.get('stars', 0),
        'follower_data': stats.get('followers', 0)
    }
    for element_id, value in ids_to_update.items():
        element = root.find(f".//*[@id='{element_id}']", namespaces=ns)
        if element is not None:
            element.text = f"{value:,}"

    # Update ASCII art
    if ascii_art:
        art_container = root.find(".//*[@id='ascii-art']", namespaces=ns)
        if art_container is not None:
            # Clear existing art
            for element in list(art_container):
                art_container.remove(element)
            
            # Add new art line by line
            y_start = 30
            y_step = 15
            for i, line in enumerate(ascii_art.splitlines()):
                tspan = etree.SubElement(art_container, "tspan", x="15", y=str(y_start + i * y_step))
                tspan.text = line

    tree.write(svg_path, pretty_print=True, xml_declaration=True, encoding='UTF-8')

def main():
    """Main function."""
    load_dotenv()
    check_env_vars()
    
    username = os.getenv("USER_NAME")
    
    ascii_art = None
    try:
        with open(ART_FILE_PATH, "r") as f:
            ascii_art = f.read()
    except FileNotFoundError:
        print(f"🎨 Warning: {os.path.basename(ART_FILE_PATH)} not found. Skipping ASCII art update.")
    except IOError as e:
        print(f"🎨 Warning: Could not read {os.path.basename(ART_FILE_PATH)}: {e}")

    with tqdm(total=2, desc="🚀 Updating profile stats") as pbar:
        pbar.set_description("📊 Fetching stats...")
        commits, stars, followers = stats_getter(username)
        stats = {'commits': commits, 'stars': stars, 'followers': followers}
        pbar.update(1)
        
        pbar.set_description("✍️ Writing to SVG files...")
        update_svg(DARK_MODE_SVG_PATH, stats, ascii_art)
        update_svg(LIGHT_MODE_SVG_PATH, stats, ascii_art)
        pbar.update(1)

    print("✅ Profile updated successfully!")

if __name__ == '__main__':
    main() 