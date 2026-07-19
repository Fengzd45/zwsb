import os
import re
import base64
import requests

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

def ask_gemini_botanist_raw(image_url, api_key):
    """使用新版 AQ 密钥专用通道"""
    try:
        # 下载图片并转为 Base64
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
        
        payload = {
            "contents": [{
                "parts": [
                    {"inlineData": {"mimeType": "image/jpeg", "data": base64_image}},
                    {"text": prompt_text}
                ]
            }]
        }

        # 🚀 【核心适配】：针对 AQ 密钥，改用统一的通用 API 兼容通道，不再强冲 Google 原生 OAuth 门禁
        # 同时支持通过环境变量 GEMINI_API_BASE 自定义国内中转或飞书专线网关
        api_base = os.environ.get("GEMINI_API_BASE", "https://api.openai-hk.com/v1") # 默认尝试通用兼容代理，如有特定网关可在此修改
        
        if "googleapis.com" in api_base or api_base == "https://api.openai-hk.com/v1":
            # 如果是走通用标准路由
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
            headers = {"Content-Type": "application/json"}
        else:
            # 如果走专线网关，将 AQ 钥匙以标准 Bearer 令牌形式送入
            url = f"{api_base}/chat/completions"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}"
            }
            # 转换为聊天格式适配专线
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
            if "chat/completions" in url:
                return res.json()['choices'][0]['message']['content']
            return res.json()['candidates'][0]['content']['parts'][0]['text']
            
        return f"❌ 专线通道反馈状态码 ({res.status_code}): `{res.text[:300]}`"
        
    except Exception as e:
        return f"❌ 建立直连通道时发生意外中断: {str(e)}"

if __name__ == "__main__":
    GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
    issue_body = os.environ.get("ISSUE_BODY", "")
    issue_num = os.environ.get("ISSUE_NUMBER", "")
    repo = os.environ.get("REPOSITORY", "")
    token = os.environ.get("GITHUB_TOKEN", "")
    
    if not issue_body or not issue_num:
        print("没有有效的 Issue 内容。")
        exit(0)
        
    if not GEMINI_KEY:
        reply_to_issue(issue_num, repo, token, "❌ 保险柜里未检测到密钥。")
        exit(1)
        
    image_urls = extract_image_urls(issue_body)
    if not image_urls:
        reply_to_issue(issue_num, repo, token, "🤖 未抓取到照片，请等待加载完成后重新评论。")
    else:
        target_image = image_urls[0]
        
        # 占位提示
        reply_to_issue(issue_num, repo, token, "🔍 **新版 AQ 密钥专线已铺设，替身正在重新叩门，请稍候...**")
        
        # 执行识别
        result = ask_gemini_botanist_raw(target_image, GEMINI_KEY)
        
        # 回复最终结果
        final_reply = f"🌿 **【AI植物学家替身鉴定报告】** 🌿\n\n{result}"
        reply_to_issue(issue_num, repo, token, final_reply)
