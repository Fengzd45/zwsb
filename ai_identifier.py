import os
import re
import requests
import google.generativeai as genai

# 1. 防机器人自我评论死循环
if os.environ.get("COMMENTER_USER", "") == "github-actions[bot]":
    print("检测到是机器人自己的评论，跳过避免死循环。")
    exit(0)

def extract_image_urls(text):
    """从 Issue 文本中提取图片链接"""
    md_urls = re.findall(r'!\[.*?\]\((.*?)\)', text)
    html_urls = re.findall(r'<img [^>]*src="([^"]+)"', text)
    return md_urls + html_urls

def reply_to_issue(issue_number, repo, token, message):
    """GitHub 评论回复"""
    url = f"https://api.github.com/repos/{repo}/issues/{issue_number}/comments"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }
    data = {"body": message}
    response = requests.post(url, json=data, headers=headers)
    return response.status_code

if __name__ == "__main__":
    # 获取环境变量
    GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
    issue_body = os.environ.get("ISSUE_BODY", "")
    issue_num = os.environ.get("ISSUE_NUMBER", "")
    repo = os.environ.get("REPOSITORY", "")
    token = os.environ.get("GITHUB_TOKEN", "")
    
    if not issue_body or not issue_num:
        exit(0)
        
    if not GEMINI_KEY:
        reply_to_issue(issue_num, repo, token, "❌ 未检测到密钥，请检查 GitHub Secrets 配置。")
        exit(1)
        
    image_urls = extract_image_urls(issue_body)
    if not image_urls:
        reply_to_issue(issue_num, repo, token, "🤖 未抓取到照片，请等待图片加载完成后重新评论。")
    else:
        target_image = image_urls[0]
        
        try:
            # 🚀 回归最原本、顺利通过的官方配置方式
            genai.configure(api_key=GEMINI_KEY)
            
            # 下载图片
            img_data = requests.get(target_image, timeout=30).content
            image_part = {
                "mime_type": "image/jpeg",
                "data": img_data
            }
            
            # 标准的替身植物学家剧本
            prompt = "你现在是冯老的随身AI植物学家替身。请仔细观察这张植物照片，提供详尽的中文标准名称、科属及外观特征说明。"
            
            # 调用官方模型
            model = genai.GenerativeModel("gemini-1.5-flash")
            response = model.generate_content([image_part, prompt])
            
            # 发送成功报告
            final_reply = f"🌿 **【AI植物学家替身鉴定报告】** 🌿\n\n{response.text}"
            reply_to_issue(issue_num, repo, token, final_reply)
            
        except Exception as e:
            # 如果有小碎步报错，直接打印在这里
            reply_to_issue(issue_num, repo, token, f"❌ 替身看图时遇到一点阻碍: `{str(e)}`")
