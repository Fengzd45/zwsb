import os
import re
import requests
import google.generativeai as genai

if os.environ.get("COMMENTER_USER", "") == "github-actions[bot]":
    print("检测到是机器人自己的评论，跳过避免死循环。")
    exit(0)

def extract_image_urls(text):
    """升级版抓图逻辑：不管是用手机自带附件、Markdown 还是普通链接，只要有图片后缀都捞出来"""
    # 1. 匹配标准 Markdown 图片 ![...](url)
    md_urls = re.findall(r'!\[.*?\]\((.*?)\)', text)
    # 2. 匹配 HTML 图片标签 <img src="...">
    html_urls = re.findall(r'<img [^>]*src="([^"]+)"', text)
    # 3. 兜底匹配：直接粘贴出来的任何图片网址
    raw_urls = re.findall(r'(https?://[^\s\)]+\.(?:jpg|jpeg|png|webp|gif))', text, re.IGNORECASE)
    
    return md_urls + html_urls + raw_urls

def reply_to_issue(issue_number, repo, token, message):
    url = f"https://api.github.com/repos/{repo}/issues/{issue_number}/comments"
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
    return requests.post(url, json={"body": message}, headers=headers).status_code

if __name__ == "__main__":
    GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
    issue_body = os.environ.get("ISSUE_BODY", "")
    issue_num = os.environ.get("ISSUE_NUMBER", "")
    repo = os.environ.get("REPOSITORY", "")
    token = os.environ.get("GITHUB_TOKEN", "")
    
    if not issue_body or not issue_num:
        exit(0)
        
    if not GEMINI_KEY:
        reply_to_issue(issue_num, repo, token, "❌ 未检测到密钥。")
        exit(1)
        
    image_urls = extract_image_urls(issue_body)
    if not image_urls:
        reply_to_issue(issue_num, repo, token, "🤖 替身播报：冯老，您建了识别单，但保险柜里没看到您贴的植物照片呀，请把照片直接拖进对话框里。")
    else:
        target_image = image_urls[0]
        try:
            # 既然密钥能过，保持这套最稳的认证
            genai.configure(api_key=GEMINI_KEY)
            
            img_data = requests.get(target_image, timeout=30).content
            image_part = {"mime_type": "image/jpeg", "data": img_data}
            
            prompt = "你现在是冯老的随身AI植物学家替身。请仔细观察这张植物照片，提供详尽的中文标准名称、科属及外观特征说明。"
            
            model = genai.GenerativeModel("gemini-1.5-flash")
            response = model.generate_content([image_part, prompt])
            
            final_reply = f"🌿 **【AI植物学家替身鉴定报告】** 🌿\n\n{response.text}"
            reply_to_issue(issue_num, repo, token, final_reply)
            
        except Exception as e:
            reply_to_issue(issue_num, repo, token, f"❌ 替身看图时遇到一点阻碍: `{str(e)}`")
