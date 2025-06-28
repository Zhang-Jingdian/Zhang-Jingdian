# 🚀 GitHub Profile 自动化设置指南

欢迎使用这个超酷的自动化GitHub Profile项目！

## 📋 必要步骤

### 1. 创建GitHub仓库
- 创建一个名为 `Zhang-Jingdian` 的**公开**仓库
- 将此项目代码推送到该仓库

### 2. 获取GitHub Personal Access Token
1. 访问：GitHub → Settings → Developer settings → Personal access tokens → Fine-grained tokens
2. 点击 "Generate new token"
3. 设置权限：
   - **Account permissions**: `read:Followers`, `read:Starring`, `read:Watching`
   - **Repository permissions**: `read:Commit statuses`, `read:Contents`, `read:Issues`, `read:Metadata`, `read:Pull Requests`

### 3. 配置Repository Secrets
1. 在你的仓库中：Settings → Secrets and variables → Actions
2. 添加两个secrets：
   - `ACCESS_TOKEN`: 你刚才创建的GitHub token
   - `USER_NAME`: `Zhang-Jingdian`

### 4. 启用GitHub Actions
- 在仓库的 Actions 标签页启用工作流

## ⚡ 工作原理

- **自动更新**: 每天凌晨4点自动运行
- **手动触发**: 当你推送代码到main分支时也会运行
- **数据收集**: 自动统计你的GitHub数据并更新SVG图像

## 🎨 个性化信息

当前配置的个人信息：
- **用户名**: Zhang-Jingdian
- **邮箱**: 2157429750@qq.com
- **生日**: 2024-08-28
- **技术栈**: Python, Java, C/C++, CSS, TypeScript, JavaScript, HTML, Vue, Astro, Uni-app
- **语言**: 中文, 英文

## 🔧 如何修改信息

如果需要修改个人信息，编辑以下文件：
- `dark_mode.svg` 和 `light_mode.svg` - 更新显示的个人信息
- `today.py` - 修改生日日期

## 📊 首次运行

第一次运行后，你的profile会显示：
- 年龄计算
- 仓库统计
- 提交数量
- Star数量
- 代码行数统计

享受你的自动化GitHub Profile吧！🎉 