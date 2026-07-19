import os
import re
import requests
import google.generativeai as genai

# 1. 防机器人自我评论死循环
if os.environ.get("COMMENTER_USER", "") == "github-actions[bot]":
    print("检测到是机器人自己的评论，跳过避免死循环。")
    exit(0)

def extract_image_urls(text):
    """
    升级版抓图逻辑：
    不管是用手机端直接粘贴附件、Markdown 格式还是普通的网页图片链接，
    只要包含常见图片后缀，全部一次性捞出来，确保不漏图。
    """
    # 匹配标准 Markdown 图片 ![...](url)
    md_urls = re.findall(r'!\[.*?\]\((.*?)\)', text)
    # 匹配 HTML 图片标签 <img src="...">
    html_urls = re.findall(r'<img [^>]*src="([^"]+)"', text)
    # 兜底匹配：直接粘贴出来的任何图片网址
    raw_urls = re.findall(r'(https?://[^\s\)]+\.(?:jpg|jpeg|png|webp|gif))', text, re.IGNORECASE)
    
    return md_urls + html_urls + raw_urls

def reply_to_issue(issue_number, repo, token, message):
    """GitHub 评论回复通用函数"""
    url = f"https://api.github.com/repos/{repo}/issues/{issue_number}/comments"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }
    data = {"body": message}
    response = requests.post(url, json=data, headers=headers)
    return response.status_code

if __name__ == "__main__":
    # 从 GitHub 环境中获取锁定的安全变量
    GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
    issue_body = os.environ.get("ISSUE_BODY", "")
    issue_num = os.environ.get("ISSUE_NUMBER", "")
    repo = os.environ.get("REPOSITORY", "")
    token = os.environ.get("GITHUB_TOKEN", "")
    
    # 基础安全检查
    if not issue_body or not issue_num:
        print("未检测到有效的 Issue 触发内容。")
        exit(0)
        
    if not GEMINI_KEY:
        reply_to_issue(issue_num, repo, token, "❌ 替身播报：未检测到密钥，请检查 GitHub Secrets 配置。")
        exit(1)
        
    # 执行抓图
    image_urls = extract_image_urls(issue_body)
    if not image_urls:
        reply_to_issue(issue_num, repo, token, "🤖 替身播报：冯老，您建了识别单，但保险柜里没看到您贴的植物照片呀，请把照片直接拖进对话框里。")
    else:
        # 取抓到的第一张照片进行分析
        target_image = image_urls[0]
        
        try:
            # 1. 配置顺利通关的标准官方密钥
            genai.configure(api_key=GEMINI_KEY)
            
            # 2. 网络下载图片
            img_data = requests.get(target_image, timeout=30).content
            image_part = {
                "mime_type": "image/jpeg",
                "data": img_data
            }
            
            # 3. 冯老专属的随身 AI 植物学家剧本
            prompt = (
                "你现在是冯老的随身AI植物学家替身。请仔细观察这张植物照片，提供详尽的专家级鉴定：\n"
                "1. **植物标准名称**：中文名、英文常用名、精准的拉丁学名。\n"
                "2. **植物分类**：科、属。并明确归类为 'Grass', 'Shrub', 'Tree', 'Conifer' 中的哪一种。\n"
                "3. **外观特征**：叶形、花期、果实特点等。\n"
                "4. **健康状态评估**：从状态来看这株植物是否有病虫害、缺水或其他生长问题？请给出调理建议。\n\n"
                "请用亲切、专业、条理清晰的中文回复。"
            )
            
            # 4. 🚀 【核心修复】：解决 404 找不到模型的兼容性问题
            response_text = ""
            try:
                print("尝试使用标准版本号调用 gemini-1.5-flash...")
                model = genai.GenerativeModel("gemini-1.5-flash")
                response = model.generate_content([image_part, prompt])
                response_text = response.text
            except Exception as e_flash:
                print(f"标准通道未匹配成功: {str(e_flash)}。正在自动切换正式版 models/ 全称通道...")
                # 备用防错路径：显式带上 models/ 前缀
                model = genai.GenerativeModel("models/gemini-1.5-flash")
                response = model.generate_content([image_part, prompt])
                response_text = response.text
            
            # 5. 发送最终的成功报告
            final_reply = f"🌿 **【AI植物学家替身鉴定报告】** 🌿\n\n{response_text}"
            reply_to_issue(issue_num, repo, token, final_reply)
            
        except Exception as e:
            # 如果依然遇到其他小碎步阻碍，直接在评论区打印错误说明
            reply_to_issue(issue_num, repo, token, f"❌ 替身看图时遇到了一点阻碍: `{str(e)}`")
