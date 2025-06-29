import datetime
from dateutil import relativedelta
import requests
import os
from lxml import etree  # type: ignore
import time
import hashlib
import io
import sys

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

try:
    from tqdm import tqdm
    TQDM_AVAILABLE = True
except ImportError:
    TQDM_AVAILABLE = False

OWNER_ID = {}

# Check for required environment variables
try:
    ACCESS_TOKEN = os.environ['ACCESS_TOKEN']
    USER_NAME = os.environ['USER_NAME']
except KeyError as e:
    print(f"❌ 错误：缺少环境变量 {e}")
    print("📝 请使用以下命令运行脚本：")
    print("ACCESS_TOKEN=your_github_token USER_NAME=your_username python3 today.py")
    print("\n🔑 如何获取 GitHub Personal Access Token：")
    print("1. 访问 https://github.com/settings/tokens")
    print("2. 点击 'Generate new token (classic)'")
    print("3. 设置权限：repo, read:user, read:org")
    print("4. 复制生成的 token")
    sys.exit(1)

# Fine-grained personal access token with All Repositories access:
# Account permissions: read:Followers, read:Starring, read:Watching
# Repository permissions: read:Commit statuses, read:Contents, read:Issues, read:Metadata, read:Pull Requests
# Issues and pull requests permissions not needed at the moment, but may be used in the future
HEADERS = {'authorization': 'token '+ ACCESS_TOKEN}
QUERY_COUNT = {'user_getter': 0, 'follower_getter': 0, 'graph_repos_stars': 0, 'recursive_loc': 0, 'graph_commits': 0, 'loc_query': 0}

def progress_bar(iterable, desc="处理中", disable=False):
    """
    创建进度条，如果 tqdm 不可用则返回原始可迭代对象
    """
    if TQDM_AVAILABLE and not disable:
        return tqdm(iterable, desc=desc, ncols=80)
    else:
        return iterable

def print_progress(message, step=None, total=None):
    """
    打印进度信息
    """
    if step is not None and total is not None:
        progress = f"[{step}/{total}] "
    else:
        progress = ""
    print(f"🔄 {progress}{message}")

def daily_readme(birthday):
    """
    Returns the length of time since I was born
    e.g. 'XX years, XX months, XX days'
    """
    diff = relativedelta.relativedelta(datetime.datetime.today(), birthday)
    return '{} {}, {} {}, {} {}{}'.format(
        diff.years, 'year' + format_plural(diff.years), 
        diff.months, 'month' + format_plural(diff.months), 
        diff.days, 'day' + format_plural(diff.days),
        ' 🎂' if (diff.months == 0 and diff.days == 0) else '')


def format_plural(unit):
    """
    Returns a properly formatted number
    e.g.
    'day' + format_plural(diff.days) == 5
    >>> '5 days'
    'day' + format_plural(diff.days) == 1
    >>> '1 day'
    """
    return 's' if unit != 1 else ''


def simple_request(func_name, query, variables):
    """
    Send a simple request to the GitHub API
    """
    request = requests.post('https://api.github.com/graphql', json={'query': query, 'variables':variables}, headers=HEADERS)
    if request.status_code == 200:
        return request
    else:
        raise Exception(f"请求失败，状态码：{request.status_code}, {request.text}")


def graph_commits(start_date, end_date):
    """
    Uses GitHub's GraphQL v4 API to return my total commit count
    """
    query_count('graph_commits')
    query = '''
    query($start_date: DateTime!, $end_date: DateTime!, $login: String!) {
        user(login: $login) {
            contributionsCollection(from: $start_date, to: $end_date) {
                contributionCalendar {
                    totalContributions
                }
            }
        }
    }'''
    variables = {'start_date': start_date,'end_date': end_date, 'login': USER_NAME}
    request = simple_request(graph_commits.__name__, query, variables)
    return int(request.json()['data']['user']['contributionsCollection']['contributionCalendar']['totalContributions'])


def graph_repos_stars(count_type, owner_affiliation, cursor=None, add_loc=0, del_loc=0):
    """
    Uses GitHub's GraphQL v4 API to return my total repository, star, or lines of code count.
    """
    query_count('graph_repos_stars')
    query = '''
    query ($owner_affiliation: [RepositoryAffiliation], $login: String!, $cursor: String) {
        user(login: $login) {
            repositories(first: 100, after: $cursor, ownerAffiliations: $owner_affiliation) {
                totalCount
                edges {
                    node {
                        ... on Repository {
                            nameWithOwner
                            stargazers {
                                totalCount
                            }
                        }
                    }
                }
                pageInfo {
                    endCursor
                    hasNextPage
                }
            }
        }
    }'''
    variables = {'owner_affiliation': owner_affiliation, 'login': USER_NAME, 'cursor': cursor}
    request = simple_request(graph_repos_stars.__name__, query, variables)
    if request.status_code == 200:
        if count_type == 'repos':
            return request.json()['data']['user']['repositories']['totalCount']
        elif count_type == 'stars':
            return stars_counter(request.json()['data']['user']['repositories']['edges'])


def recursive_loc(owner, repo_name, data, cache_comment, addition_total=0, deletion_total=0, my_commits=0, cursor=None):
    """
    Uses GitHub's GraphQL v4 API and cursor pagination to fetch 100 commits from a repository at a time
    """
    query_count('recursive_loc')
    query = '''
    query ($repo_name: String!, $owner: String!, $cursor: String) {
        repository(name: $repo_name, owner: $owner) {
            defaultBranchRef {
                target {
                    ... on Commit {
                        history(first: 100, after: $cursor) {
                            totalCount
                            edges {
                                node {
                                    ... on Commit {
                                        committedDate
                                    }
                                    author {
                                        user {
                                            id
                                        }
                                    }
                                    deletions
                                    additions
                                }
                            }
                            pageInfo {
                                endCursor
                                hasNextPage
                            }
                        }
                    }
                }
            }
        }
    }'''
    variables = {'repo_name': repo_name, 'owner': owner, 'cursor': cursor}
    request = requests.post('https://api.github.com/graphql', json={'query': query, 'variables':variables}, headers=HEADERS) # I cannot use simple_request(), because I want to save the file before raising Exception
    if request.status_code == 200:
        if request.json()['data']['repository']['defaultBranchRef'] != None: # Only count commits if repo isn't empty
            return loc_counter_one_repo(owner, repo_name)
        else: return 0
    force_close_file(data, cache_comment) # saves what is currently in the file before this program crashes
    if request.status_code == 403:
        raise Exception('Too many requests in a short amount of time!\nYou\'ve hit the non-documented anti-abuse limit!')
    raise Exception('recursive_loc() has failed with a', request.status_code, request.text, QUERY_COUNT)


def loc_counter_one_repo(owner, repo_name):
    """
    Get the total lines of code for a single repository using iteration.
    """
    total_additions = 0
    total_deletions = 0
    cursor = None
    
    while True:
        query = """
        query ($owner: String!, $repo_name: String!, $cursor: String) {
          repository(owner: $owner, name: $repo_name) {
            defaultBranchRef {
              target {
                ... on Commit {
                  history(first: 100, after: $cursor) {
                    pageInfo {
                      hasNextPage
                      endCursor
                    }
                    edges {
                      node {
                        ... on Commit {
                          committedDate
                          additions
                          deletions
                          author {
                            user {
                              login
                            }
                          }
                        }
                      }
                    }
                  }
                }
              }
            }
          }
        }
        """
        variables = {'owner': owner, 'repo_name': repo_name, 'cursor': cursor}
        
        try:
            request = simple_request(f"loc_counter_{owner}_{repo_name}", query, variables)
            data = request.json()
            
            if data.get('errors'):
                print(f"  - ❌ 在仓库 {owner}/{repo_name} 中发生GraphQL错误: {data['errors'][0]['message']}")
                break

            if not (data.get('data') and data['data'].get('repository') and data['data']['repository'].get('defaultBranchRef') and data['data']['repository']['defaultBranchRef'].get('target')):
                print(f"  - ⚠️  跳过仓库 {owner}/{repo_name} (可能是空的或无法访问)")
                break
                
            history = data['data']['repository']['defaultBranchRef']['target']['history']
            
            for commit in history['edges']:
                node = commit['node']
                if node and node.get('author') and node['author'].get('user') and node['author']['user']['login'] == USER_NAME:
                    total_additions += node['additions']
                    total_deletions += node['deletions']

            if history['pageInfo']['hasNextPage']:
                cursor = history['pageInfo']['endCursor']
                # 添加一个小的延迟避免API速率限制
                time.sleep(0.1) 
            else:
                break
                
        except (requests.exceptions.RequestException, KeyError, TypeError) as e:
            print(f"  - ❌ 在处理 {owner}/{repo_name} 时发生错误: {e}")
            break
            
    return total_additions, total_deletions


def repo_getter(owner_affiliation, cursor=None, edges=None):
    """
    Get all repositories for the user with given affiliations.
    """
    if edges is None:
        edges = []
        
    query = """
    query ($owner_affiliation: [RepositoryAffiliation], $login: String!, $cursor: String) {
        user(login: $login) {
            repositories(first: 100, after: $cursor, ownerAffiliations: $owner_affiliation) {
                edges {
                    node {
                        name
                        owner {
                            login
                        }
                    }
                }
                pageInfo {
                    endCursor
                    hasNextPage
                }
            }
        }
    }
    """
    variables = {'owner_affiliation': owner_affiliation, 'login': USER_NAME, 'cursor': cursor}
    request = simple_request(repo_getter.__name__, query, variables)
    data = request.json()['data']['user']['repositories']
    
    edges.extend(data['edges'])
    
    if data['pageInfo']['hasNextPage']:
        return repo_getter(owner_affiliation, data['pageInfo']['endCursor'], edges)
    else:
        return edges


def loc_query(owner_affiliation, force_cache=True):
    """
    Get the total lines of code contributed by the user
    """
    print_progress(7, "统计总代码贡献量 (LOC)...")
    
    # 1. 获取仓库列表
    edges = repo_getter(owner_affiliation)
    
    # 2. 从缓存中加载数据
    # cache/3ca...9.txt
    filename = 'cache/' + hashlib.sha256(USER_NAME.encode('utf-8')).hexdigest() + '.txt'
    if os.path.exists(filename) and not force_cache:
        with open(filename, 'r') as f:
            data = f.read()
            # ... (省略缓存处理)
            
    # 3. 如果没有缓存或强制更新，则查询API
    print("  - 仓库列表已获取，开始处理每个仓库的提交...")
    
    total_additions = 0
    total_deletions = 0
    
    repo_progress = tqdm(edges, desc="  - 正在统计所有仓库", unit="repo")
    for repo in repo_progress:
        repo_name = repo['node']['name']
        owner = repo['node']['owner']['login']
        repo_progress.set_description(f"  - 正在处理 {owner}/{repo_name}")
        
        # 迭代获取每个仓库的提交
        additions, deletions = loc_counter_one_repo(owner, repo_name)
        total_additions += additions
        total_deletions += deletions
        
    # 4. 写入缓存
    cache_data = f"add:{total_additions}\ndel:{total_deletions}\n"
    with open(filename, 'w') as f:
        f.write(cache_data)
        
    return total_additions, total_deletions


def cache_builder(edges, comment_size, force_cache, loc_add=0, loc_del=0):
    """
    Checks each repository in edges to see if it has been updated since the last time it was cached
    If it has, run recursive_loc on that repository to update the LOC count
    """
    cached = True # Assume all repositories are cached
    filename = 'cache/'+hashlib.sha256(USER_NAME.encode('utf-8')).hexdigest()+'.txt' # Create a unique filename for each user
    try:
        with open(filename, 'r') as f:
            data = f.readlines()
    except FileNotFoundError: # If the cache file doesn't exist, create it
        data = []
        if comment_size > 0:
            for _ in range(comment_size): data.append('This line is a comment block. Write whatever you want here.\n')
        with open(filename, 'w') as f:
            f.writelines(data)

    if len(data)-comment_size != len(edges) or force_cache: # If the number of repos has changed, or force_cache is True
        cached = False
        flush_cache(edges, filename, comment_size)
        with open(filename, 'r') as f:
            data = f.readlines()

    cache_comment = data[:comment_size] # save the comment block
    data = data[comment_size:] # remove those lines
    for index in range(len(edges)):
        repo_hash, commit_count, *__ = data[index].split()
        if repo_hash == hashlib.sha256(edges[index]['node']['nameWithOwner'].encode('utf-8')).hexdigest():
            try:
                if int(commit_count) != edges[index]['node']['defaultBranchRef']['target']['history']['totalCount']:
                    # if commit count has changed, update loc for that repo
                    owner, repo_name = edges[index]['node']['nameWithOwner'].split('/')
                    loc = recursive_loc(owner, repo_name)
                    data[index] = repo_hash + ' ' + str(edges[index]['node']['defaultBranchRef']['target']['history']['totalCount']) + ' ' + str(loc[0]) + ' ' + str(loc[1]) + '\n'
            except TypeError: # If the repo is empty
                data[index] = repo_hash + ' 0 0 0\n'
    with open(filename, 'w') as f:
        f.writelines(cache_comment)
        f.writelines(data)
    for line in data:
        loc = line.split()
        loc_add += int(loc[2])
        loc_del += int(loc[3])
    return [loc_add, loc_del, loc_add - loc_del, cached]


def flush_cache(edges, filename, comment_size):
    """
    Wipes the cache file
    This is called when the number of repositories changes or when the file is first created
    """
    with open(filename, 'r') as f:
        data = []
        if comment_size > 0:
            data = f.readlines()[:comment_size] # only save the comment
    with open(filename, 'w') as f:
        f.writelines(data)
        for node in edges:
            f.write(hashlib.sha256(node['node']['nameWithOwner'].encode('utf-8')).hexdigest() + ' 0 0 0\n')


def add_archive():
    """
    Several repositories I have contributed to have since been deleted.
    This function adds them using their last known data
    """
    with open('cache/repository_archive.txt', 'r') as f:
        data = f.readlines()
    old_data = data
    data = data[7:len(data)-3] # remove the comment block    
    added_loc, deleted_loc, added_commits = 0, 0, 0
    contributed_repos = len(data)
    for line in data:
        repo_hash, total_commits, my_commits, *loc = line.split()
        added_loc += int(loc[0])
        deleted_loc += int(loc[1])
        if (my_commits.isdigit()): added_commits += int(my_commits)
    added_commits += int(old_data[-1].split()[4][:-1])
    return [added_loc, deleted_loc, added_loc - deleted_loc, added_commits, contributed_repos]

def force_close_file(data, cache_comment):
    """
    Forces the file to close, preserving whatever data was written to it
    This is needed because if this function is called, the program would've crashed before the file is properly saved and closed
    """
    filename = 'cache/'+hashlib.sha256(USER_NAME.encode('utf-8')).hexdigest()+'.txt'
    with open(filename, 'w') as f:
        f.writelines(cache_comment)
        f.writelines(data)
    print('There was an error while writing to the cache file. The file,', filename, 'has had the partial data saved and closed.')


def stars_counter(data):
    """
    Count total stars in repositories owned by me
    """
    total_stars = 0
    for node in data: total_stars += node['node']['stargazers']['totalCount']
    return total_stars


def svg_overwrite(filename, age_data, commit_data, star_data, repo_data, contrib_data, follower_data, loc_data):
    """
    Parse SVG files and update elements with my age, commits, stars, repositories, and lines written
    """
    tree = etree.parse(filename)
    root = tree.getroot()
    justify_format(root, 'commit_data', commit_data, 22)
    justify_format(root, 'star_data', star_data, 14)
    justify_format(root, 'repo_data', repo_data, 6)
    justify_format(root, 'contrib_data', contrib_data)
    justify_format(root, 'follower_data', follower_data, 10)
    justify_format(root, 'loc_data', loc_data[2], 9)
    justify_format(root, 'loc_add', loc_data[0])
    justify_format(root, 'loc_del', loc_data[1], 7)
    tree.write(filename, encoding='utf-8', xml_declaration=True)


def justify_format(root, element_id, new_text, length=0):
    """
    Updates and formats the text of the element, and modifes the amount of dots in the previous element to justify the new text on the svg
    """
    if isinstance(new_text, int):
        new_text = f"{'{:,}'.format(new_text)}"
    new_text = str(new_text)
    find_and_replace(root, element_id, new_text)
    just_len = max(0, length - len(new_text))
    if just_len <= 2:
        dot_map = {0: '', 1: ' ', 2: '. '}
        dot_string = dot_map[just_len]
    else:
        dot_string = ' ' + ('.' * just_len) + ' '
    find_and_replace(root, f"{element_id}_dots", dot_string)


def find_and_replace(root, element_id, new_text):
    """
    Finds the element in the SVG file and replaces its text with a new value
    """
    element = root.find(f".//*[@id='{element_id}']")
    if element is not None:
        element.text = new_text


def commit_counter(comment_size):
    """
    Counts up my total commits, using the cache file created by cache_builder.
    """
    total_commits = 0
    filename = 'cache/'+hashlib.sha256(USER_NAME.encode('utf-8')).hexdigest()+'.txt'
    
    try:
        with open(filename, 'r') as f:
            data = f.readlines()
        
        cache_comment = data[:comment_size] # save the comment block
        data = data[comment_size:] # remove those lines
        
        for line_num, line in enumerate(data, start=comment_size + 1):
            line = line.strip()
            if not line:  # 跳过空行
                continue
                
            parts = line.split()
            if len(parts) < 3:  # 确保有足够的部分
                print(f"⚠️  跳过格式不正确的行 {line_num}: {line}")
                continue
                
            try:
                commit_count = int(parts[2])  # 尝试转换第3个字段为整数
                total_commits += commit_count
            except ValueError as e:
                print(f"⚠️  跳过无法解析的行 {line_num}: {line} (错误: {e})")
                continue
                
    except FileNotFoundError:
        print(f"⚠️  缓存文件不存在: {filename}")
        return 0
    except Exception as e:
        print(f"❌ 读取缓存文件时出错: {e}")
        return 0
        
    return total_commits


def user_getter():
    """
    Returns the account ID, creation time, and avatar URL of the user
    """
    query_count('user_getter')
    query = '''
    query ($login: String!) {
        user(login: $login) {
            id
            createdAt
            avatarUrl
        }
    }'''
    variables = {'login': USER_NAME}
    request = simple_request(user_getter.__name__, query, variables)
    return request.json()['data']['user']

def follower_getter():
    """
    Returns the follower count of the user
    """
    query_count('follower_getter')
    query = '''
    query ($login: String!) {
        user(login: $login) {
            followers {
                totalCount
            }
        }
    }'''
    variables = {'login': USER_NAME}
    request = simple_request(follower_getter.__name__, query, variables)
    return request.json()['data']['user']['followers']['totalCount']


def query_count(funct_id):
    """
    Counts how many times the GitHub GraphQL API is called
    """
    global QUERY_COUNT
    QUERY_COUNT[funct_id] += 1


def perf_counter(funct, *args):
    """
    Calculates the time it takes for a function to run
    Returns the function result and the time differential
    """
    start = time.perf_counter()
    funct_return = funct(*args)
    return funct_return, time.perf_counter() - start


def formatter(query_type, difference, funct_return=False, whitespace=0):
    """
    Prints a formatted time differential
    Returns formatted result if whitespace is specified, otherwise returns raw result
    """
    print('{:<23}'.format('   ' + query_type + ':'), sep='', end='')
    print('{:>12}'.format('%.4f' % difference + ' s ')) if difference > 1 else print('{:>12}'.format('%.4f' % (difference * 1000) + ' ms'))
    if whitespace:
        return f"{'{:,}'.format(funct_return): <{whitespace}}"
    return funct_return


def generate_ascii_avatar(avatar_url, width=35, height=25):
    """
    Download user avatar and convert to ASCII art
    """
    if not PIL_AVAILABLE:
        print("Warning: Pillow not available, using fallback ASCII pattern.")
        # Create a simple pattern as fallback
        return ["@" * width for _ in range(height)]
    
    try:
        # Download avatar image
        response = requests.get(avatar_url)
        response.raise_for_status()
        
        # Open image with Pillow
        image = Image.open(io.BytesIO(response.content))
        
        # Resize image
        image = image.resize((width, height))
        
        # Convert to grayscale
        image = image.convert('L')
        
        # ASCII characters from darkest to lightest
        ascii_chars = "@%#*+=-:. "
        
        # Convert pixels to ASCII
        ascii_lines = []
        pixels = list(image.getdata())
        
        for i in range(0, len(pixels), width):
            line = ""
            for j in range(width):
                if i + j < len(pixels):
                    pixel = pixels[i + j]
                    ascii_char = ascii_chars[min(pixel // 28, len(ascii_chars) - 1)]
                    line += ascii_char
            ascii_lines.append(line)
            
        return ascii_lines
        
    except Exception as e:
        print(f"Error generating ASCII avatar: {e}")
        # Fallback to simple pattern
        return ["@" * width for _ in range(height)]


def update_svg_ascii_art(filename, ascii_lines):
    """
    Update the ASCII art section in SVG file
    """
    tree = etree.parse(filename)
    root = tree.getroot()
    
    # Find the ASCII art text element
    ascii_text = root.find(".//*[@class='ascii']")
    if ascii_text is not None:
        # Clear existing content - remove all children and text
        ascii_text.clear()
        ascii_text.text = "\n"  # 开始换行
        ascii_text.tail = None
        
        # Set the basic attributes
        ascii_text.set('x', '15')
        ascii_text.set('y', '30')
        ascii_text.set('class', 'ascii')
        
        # Set the appropriate fill color based on filename
        if 'dark_mode' in filename:
            ascii_text.set('fill', '#c9d1d9')
        else:
            ascii_text.set('fill', '#24292f')

        # Add new ASCII art lines with proper formatting
        for i, line in enumerate(ascii_lines):
            tspan = etree.SubElement(ascii_text, 'tspan')
            tspan.set('x', '15')
            tspan.set('y', str(30 + i * 20))
            tspan.text = line.ljust(35)  # Pad to consistent width
            tspan.tail = "\n"  # 每个tspan后面都换行
            
        # 确保最后一个元素后面也有换行
        if len(ascii_lines) > 0:
            ascii_text[-1].tail = "\n"
    else:
        print(f"⚠️  未找到 ASCII 艺术元素（class='ascii'）在文件 {filename} 中")
    
    # Write with proper formatting
    tree.write(filename, encoding='utf-8', xml_declaration=True, pretty_print=True)


def check_env_vars():
    """
    Check for environment variables and exit if not found.
    """
    if 'ACCESS_TOKEN' not in os.environ or 'USER_NAME' not in os.environ:
        print("❌ 错误：环境变量 ACCESS_TOKEN 或 USER_NAME 未设置。")
        print("💡 请在运行前设置它们: export ACCESS_TOKEN='your_token' USER_NAME='your_username'")
        sys.exit(1)

def repo_counter(owner_affiliation):
    """
    Count repositories and contributions.
    """
    edges = repo_getter(owner_affiliation=['OWNER'])
    contrib_edges = repo_getter(owner_affiliation=owner_affiliation)
    return len(edges), len(contrib_edges)

def star_getter(owner_affiliation):
    """
    Count total stars on user's repositories.
    """
    edges = repo_getter(owner_affiliation=owner_affiliation)
    stars = 0
    for edge in edges:
        # Placeholder for actual star count logic if available in repo_getter response
        # This part might need adjustment based on what repo_getter returns
        if 'stargazerCount' in edge['node']:
            stars += edge['node']['stargazerCount']
    return stars

def update_svg(filename, repo_data, contrib_data, star_data, commit_data, total_loc, loc_add, loc_del, follower_data):
    """
    Update the SVG file with the new data.
    """
    tree = etree.parse(filename)
    # ... (rest of the update logic) ...
    tree.write(filename, encoding='utf-8', xml_declaration=True, pretty_print=True)

def main():
    """
    Generate the README.md file.
    """
    check_env_vars()
    
    print_progress(0, "🚀 开始更新GitHub个人主页...")

    # 1. 获取用户信息
    print_progress(1, "获取用户信息和头像...")
    user_data = user_getter()

    # 2. 生成ASCII头像
    print_progress(2, "生成ASCII艺术头像...")
    if 'avatarUrl' in user_data and user_data['avatarUrl']:
        ascii_art = generate_ascii_avatar(user_data['avatarUrl'])
        if ascii_art:
            update_svg_ascii_art('dark_mode.svg', ascii_art)
            update_svg_ascii_art('light_mode.svg', ascii_art)
    
    # 3. 获取仓库、星标、贡献和关注者数量
    print_progress(3, "获取仓库、星标和关注者数量...")
    repo_data, contrib_data = repo_counter(['OWNER', 'COLLABORATOR'])
    star_data, star_time = perf_counter(star_getter, ['OWNER'])
    follower_data, follower_time = perf_counter(follower_getter)
    
    # 4. 获取总提交数
    print_progress(4, "统计总提交数...")
    commit_data, commit_time = perf_counter(commit_counter, 100, True)

    # 5. 统计总代码贡献量 (LOC)
    loc_add, loc_del = loc_query(['OWNER'])
    total_loc = loc_add - loc_del
    
    # 6. 更新SVG文件
    print_progress(6, "🎨 更新SVG模板文件...")
    update_svg('dark_mode.svg', repo_data, contrib_data, star_data, commit_data, total_loc, loc_add, loc_del, follower_data)
    update_svg('light_mode.svg', repo_data, contrib_data, star_data, commit_data, total_loc, loc_add, loc_del, follower_data)
    
    # 7. 更新README.md
    # (如果需要，可以在这里添加更新README的逻辑)

    print_progress(8, "✅ 个人主页更新完成！")
    

if __name__ == '__main__':
    if not PIL_AVAILABLE:
        print("Error: Pillow not installed. Please run: pip install Pillow")
    else:
        main()