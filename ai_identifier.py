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

def ask_gemini_botanist(image_url, api_key):
    """识别植物"""
    try:
        # 显式配置
        genai.configure(api_key=api_key)
        
        # 下载图片
        img_data = requests.get(image_url, timeout=30).content
        image_part = {
            "mime_type": "image/jpeg",
            "data": img_data
        }
        
        prompt = "你现在是冯老的随身AI植物学家替身。请仔细观察这张植物照片，提供详尽的中文标准名称、科属及外观特征说明。"
        
        model = genai.GenerativeModel("gemini-1.5-flash")
        response = model.generate_content([image_part, prompt])
        return response.text
        
    except Exception as e:
        return f"❌ 替身看图时被拒门外，详细报错:\n`{str(e)}`"

if __name__ == "__main__":
    GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "")
    issue_body = os.environ.get("ISSUE_BODY", "")
    issue_num = os.environ.get("ISSUE_NUMBER", "")
    repo = os.environ.get("REPOSITORY", "")
    token = os.environ.get("GITHUB_TOKEN", "")
    
    if not issue_body or not issue_num:
        print("未检测到有效的 Issue 内容。")
        exit(0)
        
    # 【核心安全排查：透视这把钥匙】
    key_report = ""
    if not GEMINI_KEY:
        key_report = "❌ **密钥透视报告**：云端根本没有拿到任何密钥，变量为空！"
    else:
        clean_key = GEMINI_KEY.strip()
        has_space = "是" if len(GEMINI_KEY) != len(clean_key) else "否"
        key_report = (
            f"🔍 **密钥安全透视报告**：\n"
            f"- 接收到的密钥总长度：{len(GEMINI_KEY)} 位\n"
            f"- 密钥开头前两个字母是：`{GEMINI_KEY[:2]}`\n"
            f"- 密钥结尾两个字母是：`{GEMINI_KEY[-2:]}`\n"
            f"- 是否包含前后隐形空格或换行：`{has_space}`\n"
            f"*(注：此报告不泄漏中间真实密码，安全可查)*"
        )
    
    # 先把透视报告发到评论区，让我们看看到底送进去的是个什么
    reply_to_issue(issue_num, repo, token, key_report)
    
    if not GEMINI_KEY:
        exit(1)
        
    image_urls = extract_image_urls(issue_body)
    if not image_urls:
        reply_to_issue(issue_num, repo, token, "🤖 没看到照片代码，请重新拖入。")
    else:
        target_image = image_urls[0]
        # 使用去除了可能存在的前后空格的干净密钥去请求
        result = ask_gemini_botanist(target_image, GEMINI_KEY.strip())
        
        final_reply = f"🌿 **【AI植物学家替身鉴定报告结果】** 🌿\n\n{result}"
        reply_to_issue(issue_num, repo, token, final_reply)
