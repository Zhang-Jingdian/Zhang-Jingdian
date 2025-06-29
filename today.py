import os
import sys
import time
import requests
import json
from lxml import etree
from dotenv import load_dotenv
from tqdm import tqdm
from datetime import datetime, timedelta
from PIL import Image
import io

# --- Constants and Globals ---
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
USER_NAME = os.getenv("USER_NAME")
OWNER_ID = ""  # Will be fetched later

# --- Environment Check ---
def check_env_vars():
    """Checks for required environment variables."""
    if not ACCESS_TOKEN or not USER_NAME:
        print("❌ 错误：环境变量 ACCESS_TOKEN 或 USER_NAME 未设置。")
        print("请按照以下步骤操作：")
        print("1. 在项目根目录创建一个 `.env` 文件。")
        print("2. 在文件中添加以下内容：")
        print("   ACCESS_TOKEN=your_github_personal_access_token")
        print("   USER_NAME=your_github_username")
        print("3. 或者，在运行脚本时直接提供环境变量。")
        sys.exit(1)

# --- Performance Counter ---
def perf_counter(func, *args):
    """A utility to measure the execution time of a function."""
    start_time = time.perf_counter()
    result = func(*args)
    end_time = time.perf_counter()
    return result, end_time - start_time

# --- API Getters ---
def run_query(query, variables):
    """Executes a GraphQL query."""
    headers = {"Authorization": f"bearer {ACCESS_TOKEN}"}
    try:
        response = requests.post("https://api.github.com/graphql", json={'query': query, 'variables': variables}, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"GraphQL query failed: {e}")
        if 'response' in locals() and 'X-RateLimit-Remaining' in response.headers and int(response.headers['X-RateLimit-Remaining']) == 0:
            print("Rate limit likely exceeded.")
        return None

def user_getter(username):
    """Fetches user ID, creation date, and avatar URL."""
    query = """
    query($username: String!) {
      user(login: $username) {
        id
        createdAt
        avatarUrl
      }
    }
    """
    variables = {"username": username}
    data = run_query(query, variables)
    if data and data.get('data') and data['data'].get('user'):
        user_data = data['data']['user']
        return user_data['id'], user_data['createdAt'], user_data['avatarUrl']
    return None, None, None

def contribution_getter(username):
    """Fetches contribution data for the last 365 days."""
    today = datetime.utcnow()
    from_date = (today - timedelta(days=365)).isoformat() + 'Z'
    query = """
    query ($username: String!, $from: DateTime) {
      user(login: $username) {
        contributionsCollection(from: $from) {
          contributionCalendar {
            weeks {
              contributionDays {
                date
                contributionCount
              }
            }
          }
        }
      }
    }
    """
    variables = {"username": username, "from": from_date}
    data = run_query(query, variables)
    contrib_map = {}
    if data and data.get('data', {}).get('user'):
        weeks = data['data']['user']['contributionsCollection']['contributionCalendar']['weeks']
        for week in weeks:
            for day in week['contributionDays']:
                count = day['contributionCount']
                level = 0
                if count > 0: level = 1
                if count > 8: level = 2
                if count > 16: level = 3
                if count > 24: level = 4
                contrib_map[day['date']] = level
    return contrib_map

def stats_getter(username):
    """Fetches commit, star, and follower counts."""
    query = """
    query ($username: String!) {
        user(login: $username) {
            contributionsCollection {
                totalCommitContributions
                restrictedContributionsCount
            }
            repositories(ownerAffiliations: OWNER, first: 100) {
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

# --- ASCII Art Generation ---
def generate_ascii_avatar(image_url, width=30):
    """Generates ASCII art from an image URL."""
    try:
        response = requests.get(image_url, stream=True)
        response.raise_for_status()
        image = Image.open(io.BytesIO(response.content)).convert('L') # Grayscale
        
        aspect_ratio = image.height / image.width
        height = int(aspect_ratio * width * 0.55) # 0.55 to correct for char aspect ratio
        image = image.resize((width, height))
        
        pixels = image.getdata()
        ascii_chars = "@%#*+=-:. "
        ascii_str = "".join([ascii_chars[pixel * (len(ascii_chars)-1) // 255] for pixel in pixels])
        
        return "\n".join([ascii_str[i:i+width] for i in range(0, len(ascii_str), width)])
    except Exception as e:
        print(f"Failed to generate ASCII art: {e}")
        return None

# --- SVG Updaters ---
def update_svg_data(svg_path, stats):
    """Updates SVG with latest statistics."""
    tree = etree.parse(svg_path)
    root = tree.getroot()
    ns = {'svg': 'http://www.w3.org/2000/svg', 'xhtml': 'http://www.w3.org/1999/xhtml'}

    ids_to_update = {
        'commit_data': stats.get('commits', 0),
        'star_data': stats.get('stars', 0),
        'follower_data': stats.get('followers', 0)
    }

    for element_id, value in ids_to_update.items():
        element = root.find(f".//*[@id='{element_id}']", namespaces=ns)
        if element is not None:
            element.text = f"{value:,}"
    
    tree.write(svg_path, pretty_print=True, xml_declaration=True, encoding='UTF-8')

def update_svg_contrib_graph(svg_path, contrib_data):
    """Updates SVG with contribution graph."""
    tree = etree.parse(svg_path)
    root = tree.getroot()
    ns = {'svg': 'http://www.w3.org/2000/svg'}

    graph_container = root.find(".//*[@id='contrib-graph']", namespaces=ns)
    if graph_container is None: return

    # Clear previous graph
    for element in graph_container.findall('svg:rect', namespaces=ns):
        graph_container.remove(element)

    today = datetime.now()
    start_of_week = today - timedelta(days=today.weekday() + 1) - timedelta(weeks=52)

    cell_size, cell_padding = 10, 2
    for i in range(53 * 7):
        date = start_of_week + timedelta(days=i)
        if date > today: continue

        week_num, day_of_week = divmod(i, 7)
        x = str(week_num * (cell_size + cell_padding))
        y = str(day_of_week * (cell_size + cell_padding))
        level = str(contrib_data.get(date.strftime('%Y-%m-%d'), 0))

        rect = etree.Element("rect", x=x, y=y, width=str(cell_size), height=str(cell_size), rx="2", ry="2", attrib={'class': 'contrib-cell', 'data-level': level})
        graph_container.append(rect)

    tree.write(svg_path, pretty_print=True, xml_declaration=True, encoding='UTF-8')

def update_svg_ascii_art(svg_path, avatar_url):
    """Updates SVG with ASCII art."""
    ascii_art = generate_ascii_avatar(avatar_url)
    if not ascii_art: return

    tree = etree.parse(svg_path)
    root = tree.getroot()
    ns = {'svg': 'http://www.w3.org/2000/svg'}
    
    art_container = root.find(".//*[@id='ascii-art-container']", namespaces=ns)
    if art_container is None: return

    # Clear previous art
    for element in list(art_container):
        art_container.remove(element)

    text_element = etree.Element("text")
    for i, line in enumerate(ascii_art.split('\n')):
        tspan = etree.SubElement(text_element, "tspan", x="0", dy="1em")
        tspan.text = line
        tspan.tail = "\n"  # Ensure each tspan is on a new line for readability
    art_container.append(text_element)
    
    tree.write(svg_path, pretty_print=True, xml_declaration=True, encoding='UTF-8')

# --- Main Execution ---
def main():
    """Main function."""
    load_dotenv()
    check_env_vars()
    
    global USER_NAME, ACCESS_TOKEN
    USER_NAME = os.getenv("USER_NAME")
    ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")

    with tqdm(total=5, desc="🚀 Updating GitHub Profile") as pbar:
        
        pbar.set_description("👤 Fetching user info")
        _, _, avatar_url = user_getter(USER_NAME)
        pbar.update(1)

        pbar.set_description("📊 Fetching stats")
        commits, stars, followers = stats_getter(USER_NAME)
        pbar.update(1)

        pbar.set_description("🗓️ Fetching contributions")
        contrib_data = contribution_getter(USER_NAME)
        pbar.update(1)
        
        stats = {'commits': commits, 'stars': stars, 'followers': followers}
        
        pbar.set_description("🖼️ Updating dark mode SVG")
        for svg_file in ['dark_mode.svg', 'light_mode.svg']:
            update_svg_data(svg_file, stats)
            update_svg_contrib_graph(svg_file, contrib_data)
            update_svg_ascii_art(svg_file, avatar_url)
        pbar.update(1)
        
        pbar.set_description("💡 Updating light mode SVG")
        # Creating light_mode.svg from dark_mode.svg
        with open('dark_mode.svg', 'r') as f:
            light_mode_content = f.read()
        
        # Replace colors for light mode
        color_replacements = {
            '#202020': '#ffffff',  # bg
            '#e0e0e0': '#333333',  # text
            '#a5d6ff': '#007bff',   # title
            '#c9d1d9': '#555555',   # subtitle, ascii
            '#ffa657': '#ff8c00',   # headers
            '#444': '#dddddd',       # chart stroke
            '#2a2a2a': '#eeeeee',   # cell stroke
            '#333': '#ebedf0',       # level 0
            '#0e4429': '#9be9a8',   # level 1
            '#006d32': '#40c463',   # level 2
            '#26a641': '#30a14e',   # level 3
            '#39d353': '#216e39'    # level 4
        }
        for dark, light in color_replacements.items():
            light_mode_content = light_mode_content.replace(dark, light)
        
        with open('light_mode.svg', 'w') as f:
            f.write(light_mode_content)
        pbar.update(1)

    print("\n✅ GitHub profile updated successfully!")

if __name__ == '__main__':
    main() 