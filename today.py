import datetime
from dateutil import relativedelta
import requests
import os
from lxml import etree  # type: ignore
import time
import hashlib
import io
import sys
from io import BytesIO

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
    Returns a request, or raises an Exception if the response does not succeed.
    """
    request = requests.post('https://api.github.com/graphql', json={'query': query, 'variables':variables}, headers=HEADERS)
    if request.status_code == 200:
        return request
    raise Exception(func_name, ' has failed with a', request.status_code, request.text, QUERY_COUNT)


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
            return loc_counter_one_repo(owner, repo_name, data, cache_comment, request.json()['data']['repository']['defaultBranchRef']['target']['history'], addition_total, deletion_total, my_commits)
        else: return 0
    force_close_file(data, cache_comment) # saves what is currently in the file before this program crashes
    if request.status_code == 403:
        raise Exception('Too many requests in a short amount of time!\nYou\'ve hit the non-documented anti-abuse limit!')
    raise Exception('recursive_loc() has failed with a', request.status_code, request.text, QUERY_COUNT)


def loc_counter_one_repo(owner, repo_name, data, cache_comment, history, addition_total, deletion_total, my_commits):
    """
    Recursively call recursive_loc (since GraphQL can only search 100 commits at a time) 
    only adds the LOC value of commits authored by me
    """
    commits = history['edges']
    
    # 使用进度条显示commits处理进度
    for node in progress_bar(commits, desc=f"处理 {repo_name} 的提交", disable=len(commits) < 10):
        if node['node']['author']['user'] == OWNER_ID:
            my_commits += 1
            addition_total += node['node']['additions']
            deletion_total += node['node']['deletions']

    if history['edges'] == [] or not history['pageInfo']['hasNextPage']:
        return addition_total, deletion_total, my_commits
    else: 
        return recursive_loc(owner, repo_name, data, cache_comment, addition_total, deletion_total, my_commits, history['pageInfo']['endCursor'])


def loc_query(owner_affiliation, comment_size=0, force_cache=False, cursor=None, edges=[]):
    """
    Uses GitHub's GraphQL v4 API to query all the repositories I have access to (with respect to owner_affiliation)
    Queries 60 repos at a time, because larger queries give a 502 timeout error and smaller queries send too many
    requests and also give a 502 error.
    Returns the total number of lines of code in all repositories
    """
    query_count('loc_query')
    query = '''
    query ($owner_affiliation: [RepositoryAffiliation], $login: String!, $cursor: String) {
        user(login: $login) {
            repositories(first: 60, after: $cursor, ownerAffiliations: $owner_affiliation) {
                edges {
                    node {
                    ... on Repository {
                        nameWithOwner
                        defaultBranchRef {
                            target {
                                ... on Commit {
                                    history {
                                        totalCount
                                    }
                                }
                            }
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
    print('处理提交...') # 用通用提示替换硬编码
    request = simple_request(loc_query.__name__, query, variables)
    if request.json()['data']['user']['repositories']['pageInfo']['hasNextPage']:   # If repository data has another page
        edges += request.json()['data']['user']['repositories']['edges']            # Add on to the LoC count
        return loc_query(owner_affiliation, comment_size, force_cache, request.json()['data']['user']['repositories']['pageInfo']['endCursor'], edges)
    else:
        return cache_builder(edges + request.json()['data']['user']['repositories']['edges'], comment_size, force_cache)


def cache_builder(edges, comment_size, force_cache, loc_add=0, loc_del=0):
    """
    Builds a cache of repository data
    """
    filename = 'cache/'+hashlib.sha256(USER_NAME.encode('utf-8')).hexdigest()+'.txt' # Create a unique filename for each user
    try:
        with open(filename, 'r') as f:
            data = f.readlines()
            if len(data) > 0 and not force_cache: # If the file exists and has data
                for line in data:
                    if line.strip() != '':
                        repo_data = line.strip().split(' ')
                        if repo_data[0] in [edge['node']['nameWithOwner'] for edge in edges]:
                            if int(repo_data[1]) != graph_commits(repo_data[3], repo_data[4]): # If the number of commits has changed
                                cached = False
                                break
    except FileNotFoundError:
        # 如果缓存文件不存在，我们将创建一个新的
        cached = False
    except Exception as e:
        print(f"❌ 读取缓存文件时出错: {str(e)}")
        cached = False

    if not cached:
        try:
            # 确保缓存目录存在
            os.makedirs(os.path.dirname(filename), exist_ok=True)
            with open(filename, 'w') as f:
                if comment_size > 0:
                    for _ in range(comment_size): f.write('This line is a comment block. Write whatever you want here.\n')
                for node in edges:
                    owner, repo = node['node']['nameWithOwner'].split('/')
                    loc_data = loc_counter_one_repo(owner, repo, data, '', node['node']['defaultBranchRef']['target']['history'], 0, 0, 0)
                    total_commits = node['node']['defaultBranchRef']['target']['history']['totalCount']
                    f.write(f"{hashlib.sha256(node['node']['nameWithOwner'].encode('utf-8')).hexdigest()} {total_commits} {loc_data[2]} {loc_data[0]} {loc_data[1]}\n")
            cached = True
        except Exception as e:
            print(f"❌ 创建缓存文件时出错: {str(e)}")
            cached = False

    cache_comment = data[:comment_size] if 'data' in locals() else []  # save the comment block
    data = data[comment_size:] # remove those lines
    for index in range(len(edges)):
        repo_hash, commit_count, *__ = data[index].split()
        if repo_hash == hashlib.sha256(edges[index]['node']['nameWithOwner'].encode('utf-8')).hexdigest():
            try:
                if int(commit_count) != edges[index]['node']['defaultBranchRef']['target']['history']['totalCount']:
                    # if commit count has changed, update loc for that repo
                    owner, repo_name = edges[index]['node']['nameWithOwner'].split('/')
                    loc = recursive_loc(owner, repo_name, data, cache_comment)
                    data[index] = repo_hash + ' ' + str(edges[index]['node']['defaultBranchRef']['target']['history']['totalCount']) + ' ' + str(loc[2]) + ' ' + str(loc[0]) + ' ' + str(loc[1]) + '\n'
            except TypeError: # If the repo is empty
                data[index] = repo_hash + ' 0 0 0 0\n'
    with open(filename, 'w') as f:
        f.writelines(cache_comment)
        f.writelines(data)
    for line in data:
        loc = line.split()
        loc_add += int(loc[3])
        loc_del += int(loc[4])
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
            f.write(hashlib.sha256(node['node']['nameWithOwner'].encode('utf-8')).hexdigest() + ' 0 0 0 0\n')


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


def user_getter(username):
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
    variables = {'login': username}
    request = simple_request(user_getter.__name__, query, variables)
    user_data = request.json()['data']['user']
    return {'id': user_data['id']}, user_data['createdAt'], user_data['avatarUrl']

def follower_getter(username):
    """
    Returns the number of followers of the user
    """
    query_count('follower_getter')
    query = '''
    query($login: String!){
        user(login: $login) {
            followers {
                totalCount
            }
        }
    }'''
    request = simple_request(follower_getter.__name__, query, {'login': username})
    return int(request.json()['data']['user']['followers']['totalCount'])


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


def generate_ascii_avatar(image_url, width=35):
    """
    Generate ASCII art from user's GitHub avatar
    """
    try:
        response = requests.get(image_url)
        response.raise_for_status()
        
        image = Image.open(BytesIO(response.content))
        
        # Resize image
        aspect_ratio = image.height / image.width
        new_height = int(aspect_ratio * width * 0.55)
        resized_image = image.resize((width, new_height))
        
        # Convert to grayscale
        image = resized_image.convert('L')
        pixels = image.getdata()
        
        # Define ASCII characters from dark to light, ending with a space for the background
        ASCII_CHARS = ['#', 'S', '?', '%', '+', '*', ':', '.', ' ']
        
        # Map pixels to ASCII characters
        pixels_to_chars = "".join([ASCII_CHARS[pixel * len(ASCII_CHARS) // 256] for pixel in pixels])
        
        # Split into lines
        ascii_art_lines = [pixels_to_chars[i:i + width] for i in range(0, len(pixels_to_chars), width)]
        
        return ascii_art_lines

    except requests.exceptions.RequestException as e:
        print(f"❌  无法获取头像: {e}")
        return []
    except Exception as e:
        print(f"❌  生成 ASCII 艺术时出错: {e}")
        return []


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


def main():
    """
    main function
    """
    global OWNER_ID
    start_time = time.perf_counter()
    
    print("🚀 GitHub 个人资料更新器启动中...")
    print("=" * 50)
    
    # Step 1: Get user data
    print_progress("获取用户账户信息", 1, 8)
    user_result, user_time = perf_counter(user_getter, USER_NAME)
    OWNER_ID, acc_date, avatar_url = user_result
    formatter('账户数据', user_time)
    
    # Step 2: Generate ASCII avatar
    print_progress("生成 ASCII 头像艺术", 2, 8)
    ascii_avatar, avatar_time = perf_counter(generate_ascii_avatar, avatar_url)
    formatter('头像生成', avatar_time)

    # Step 3: Calculate age
    print_progress("计算账户年龄", 3, 8)
    age_data, age_time = perf_counter(daily_readme, datetime.datetime.strptime(acc_date, "%Y-%m-%dT%H:%M:%SZ"))
    formatter('年龄计算', age_time)
    
    # Step 4: Get lines of code
    print_progress("统计代码行数（可能需要较长时间）", 4, 8)
    total_loc, loc_time = perf_counter(loc_query, ['OWNER', 'COLLABORATOR', 'ORGANIZATION_MEMBER'], 7)
    formatter('代码行数 (已缓存)' if total_loc[-1] else '代码行数 (无缓存)', loc_time)
    
    # Step 5: Get commit data
    print_progress("统计提交次数", 5, 8)
    commit_data, commit_time = perf_counter(commit_counter, total_loc[-1])
    formatter('提交数据', commit_time)
    
    # Step 6: Get stars and repos
    print_progress("获取仓库和 Star 数据", 6, 8)
    star_data, star_time = perf_counter(graph_repos_stars, 'stars', ['OWNER', 'COLLABORATOR', 'ORGANIZATION_MEMBER'])
    formatter('Star 数据', star_time)
    repo_data, repo_time = perf_counter(graph_repos_stars, 'repos', ['OWNER'])
    formatter('仓库数据', repo_time)
    contrib_data, contrib_time = perf_counter(graph_repos_stars, 'repos', ['OWNER', 'COLLABORATOR', 'ORGANIZATION_MEMBER'])
    
    # Step 7: Get follower data
    print_progress("获取粉丝数据", 7, 8)
    follower_data, follower_time = perf_counter(follower_getter, USER_NAME)

    # Handle archived data for specific user
    if OWNER_ID == {'id': 'MDQ6VXNlcjU3MzMxMTM0'}: # only calculate for user Andrew6rant
        archived_data = add_archive()
        if isinstance(archived_data, list) and len(archived_data) > 0:
            for index in range(len(total_loc)-1):
                total_loc[index] = (total_loc[index] or 0) + (archived_data[index] or 0)
            contrib_data = (contrib_data or 0) + (archived_data[-1] or 0)
            commit_data = (commit_data or 0) + int(archived_data[-2] or 0)

    # Format numbers
    for index in range(len(total_loc)-1): 
        if total_loc[index] is not None:
            total_loc[index] = '{:,}'.format(total_loc[index])

    # Step 8: Update SVG files
    print_progress("更新 SVG 文件", 8, 8)
    print("  📄 更新 dark_mode.svg...")
    svg_overwrite('dark_mode.svg', age_data, commit_data, star_data, repo_data, contrib_data, follower_data, total_loc[:-1])
    print("  📄 更新 light_mode.svg...")
    svg_overwrite('light_mode.svg', age_data, commit_data, star_data, repo_data, contrib_data, follower_data, total_loc[:-1])
    
    # Update ASCII avatars in both SVG files
    print("  🎨 更新 ASCII 头像...")
    update_svg_ascii_art('dark_mode.svg', ascii_avatar)
    update_svg_ascii_art('light_mode.svg', ascii_avatar)

    # Final summary
    total_time = time.perf_counter() - start_time
    print("\n" + "=" * 50)
    print(f"✅ 更新完成！总耗时: {total_time:.3f}秒")
    print(f"📊 GitHub API 调用次数: {sum(QUERY_COUNT.values())}")
    
    print("\n📈 API 调用详情:")
    for funct_name, count in QUERY_COUNT.items(): 
        print(f'   {funct_name}: {count}')
    
    print("\n🎉 SVG 文件已更新，现在可以在 GitHub 个人主页查看效果！")


if __name__ == '__main__':
    if not PIL_AVAILABLE:
        print("Error: Pillow not installed. Please run: pip install Pillow")
    else:
        main()