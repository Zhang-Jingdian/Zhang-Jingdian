#!/usr/bin/env python3
"""
🎮 Auto-update GitHub profile stats
Inspired by Andrew6rant's automated profile system
https://github.com/Andrew6rant/Andrew6rant
"""

import os
import re
import requests
from datetime import datetime
from typing import Dict, Any

def get_github_data(username: str, token: str) -> Dict[str, Any]:
    """获取GitHub用户的统计数据"""
    headers = {'Authorization': f'token {token}'}
    
    # 获取用户基本信息
    user_url = f"https://api.github.com/users/{username}"
    user_data = requests.get(user_url, headers=headers).json()
    
    # 获取仓库信息
    repos_url = f"https://api.github.com/users/{username}/repos?per_page=100"
    repos_data = requests.get(repos_url, headers=headers).json()
    
    # 计算统计数据
    total_stars = sum(repo['stargazers_count'] for repo in repos_data)
    total_forks = sum(repo['forks_count'] for repo in repos_data)
    public_repos = user_data['public_repos']
    followers = user_data['followers']
    
    # 获取提交数据（简化版本）
    # 注意：真实实现需要更复杂的API调用来获取准确的提交数
    commits = "9,001+"  # 占位符，Andrew6rant使用更复杂的计算
    
    return {
        'repositories': public_repos,
        'stars': total_stars,
        'followers': followers,
        'commits': commits,
        'lines_of_code': '2,048,576',  # 占位符 - 需要代码统计工具
        'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')
    }

def update_readme_stats(stats: Dict[str, Any]) -> None:
    """更新README.md中的统计数据"""
    
    # 读取当前README
    with open('README.md', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 更新统计数据的正则表达式模式
    stats_pattern = r'(╔════════════════════ LIVE METRICS ═══════════════════╗\n║  📦 REPOSITORIES: )\d+(\s+🌟 TOTAL STARS: )\d+(.*?\n║  👥 FOLLOWERS: )\d+(\s+🔄 COMMITS: )[^║]+(.*?\n║  📏 LINES OF CODE: )[^(]+ \(auto-updated\)(.*?\n║  ⚡ LAST UPDATE: )[^║]+( ║\n╚════════════════════════════════════════════════════╝)'
    
    replacement = (
        f"╔════════════════════ LIVE METRICS ═══════════════════╗\n"
        f"║  📦 REPOSITORIES: {stats['repositories']}    🌟 TOTAL STARS: {stats['stars']}      ║  \n"
        f"║  👥 FOLLOWERS: {stats['followers']}      🔄 COMMITS: {stats['commits']}          ║\n"
        f"║  📏 LINES OF CODE: {stats['lines_of_code']} lines (auto-updated)  ║\n"
        f"║  ⚡ LAST UPDATE: {stats['last_updated']}          ║\n"
        f"╚════════════════════════════════════════════════════╝"
    )
    
    # 如果找到模式则替换，否则在指定位置插入
    if re.search(stats_pattern, content):
        content = re.sub(stats_pattern, replacement, content)
    else:
        print("📝 Stats pattern not found, please check README format")
        return
    
    # 写回文件
    with open('README.md', 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("✅ README.md updated with latest stats!")

def main():
    """主函数 - 像Andrew6rant一样自动更新profile"""
    
    # 从环境变量获取配置
    username = os.getenv('GITHUB_REPOSITORY', '').split('/')[0] or 'zjd'
    token = os.getenv('GITHUB_TOKEN')
    
    if not token:
        print("❌ GITHUB_TOKEN not found in environment variables")
        return
    
    try:
        print(f"🚀 Fetching GitHub data for {username}...")
        stats = get_github_data(username, token)
        
        print(f"📊 Stats: {stats['repositories']} repos, {stats['stars']} stars, {stats['followers']} followers")
        
        print("📝 Updating README.md...")
        update_readme_stats(stats)
        
        print(f"🎉 Profile auto-updated at {stats['last_updated']}")
        
    except Exception as e:
        print(f"❌ Error updating profile: {e}")

if __name__ == "__main__":
    main() 