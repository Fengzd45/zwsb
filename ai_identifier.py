import os
import re
import base64
import requests

if os.environ.get("COMMENTER_USER", "") == "github-actions[bot]":
    print("检测到是机器人自己的评论，跳过避免死循环。")
    exit(0)

def extract_image_urls(text):
    md_urls = re.findall(r'!\[.*?\]\((.*?)\)', text)
    html_urls = re.findall(r'<img [^>]*src="([^"]+)"', text)
    return md_urls + html_urls

def reply_to_issue(issue_number, repo, token, message):
    url = f"https://api.github.com/repos/{repo}/issues/{issue_number}/comments"
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
    return requests.post(url, json={"body": message}, headers=headers).status_code

def ask_gemini_botanist_pure_route(image_url, api_key, api_base):
    """纯中转/飞书专线路由，彻底废除直连谷歌原厂"""
    try:
        img_data = requests.get(image_url, timeout=30).content
        base64_image = base64.b64encode(img_data).decode('utf-8')
        
        prompt_text = """
        你现在是冯老的随身AI植物学家替身。请仔细观察这张植物照片，提供详尽的专家级鉴定：
        1. **植物标准名称**：中文名、英文常用名、精准的拉丁学名。
        2. **植物分类**：科、属。并明确归类为 "Grass", "Shrub", "Tree", "Conifer" 中的哪一种。
        3. **外观特征**：叶形、花期、果实特点等。
        4. **健康状态评估**：从画面上看，这株植物是否有病虫害、缺水或其他生长问题？如果有，请给出调理建议。
        
        请用亲切、专业、条理清晰的中文回复。
        """
        
        # 强制走 OpenAI 兼容格式的多模态中转专线
        url = f"{api_base.rstrip('/')}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        payload = {
            "model": "gemini-1.5-flash",
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt_text},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                ]
            }]
        }

        res = requests.post(url, json=payload, headers=headers, timeout=30)
        
        if res.status_code == 200:
            return res.json()['choices'][0]['message']['content']
            
        return f"❌ 专线网关拒绝了请求，状态码 ({res.status_code}): `{res.text[:300]}`"
        
    except Exception as e:
        return f"❌ 在专线通道内传输失败: {str(e)}"

if __name__ == "__main__":
    GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
    # 接收自定义大门
    API_BASE = os.environ.get("GEMINI_API_BASE", "").strip()
    issue_body = os.environ.get("ISSUE_BODY", "")
    issue_num = os.environ.get("ISSUE_NUMBER", "")
    repo = os.environ.get("REPOSITORY", "")
    token = os.environ.get("GITHUB_TOKEN", "")
    
    if not issue_body or not issue_num:
        exit(0)
    if not GEMINI_KEY:
        reply_to_issue(issue_num, repo, token, "❌ 保险柜里未检测到密钥。")
        exit(1)
    if not API_BASE:
        reply_to_issue(issue_num, repo, token, "❌ 程序报错：未在剧本(YAML)中配置 `GEMINI_API_BASE` 专线大门地址！")
        exit(1)
        
    image_urls = extract_image_urls(issue_body)
    if not image_urls:
        reply_to_issue(issue_num, repo, token, "🤖 未抓取到照片。")
    else:
        target_image = image_urls[0]
        reply_to_issue(issue_num, repo, token, f"🔍 **已强制锁定中转专线大门，替身正在递交新版 AQ 密钥，请稍候...**")
        result = ask_gemini_botanist_pure_route(target_image, GEMINI_KEY, API_BASE)
        reply_to_issue(issue_num, repo, token, f"🌿 **【AI植物学家替身鉴定报告】** 🌿\n\n{result}")
