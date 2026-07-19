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
    """绕过死板的 SDK，直接用原生底层网络请求叩门"""
    try:
        # 下载图片并转为 Base64 编码
        img_data = requests.get(image_url, timeout=30).content
        base64_image = base64.b64encode(img_data).decode('utf-8')
        
        # 组装标准的 Gemini 视觉请求体
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

        # 🚀 【通道 A】：尝试标准 API Key 挂载路由
        url_a = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
        res_a = requests.post(url_a, json=payload, headers={"Content-Type": "application/json"}, timeout=30)
        
        if res_a.status_code == 200:
            return res_a.json()['candidates'][0]['content']['parts'][0]['text']
            
        # 🚀 【通道 B】：如果通道 A 失败，自动切换为安全 Token 承载路由（Bearer 模式）
        url_b = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"
        headers_b = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        res_b = requests.post(url_b, json=payload, headers=headers_b, timeout=30)
        
        if res_b.status_code == 200:
            return res_b.json()['candidates'][0]['content']['parts'][0]['text']
            
        # 如果两条路都报错，把底层的真实现场打印出来
        return (
            f"❌ 两条原生通道均未通关，底层反馈如下：\n"
            f"**通道 A 状态码 ({res_a.status_code}):** `{res_a.text[:200]}`\n"
            f"**通道 B 状态码 ({res_b.status_code}):** `{res_b.text[:200]}`"
        )
        
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
        reply_to_issue(issue_num, repo, token, "🔍 **直连通道已建立，替身正在通过新版密钥叩门，请稍候...**")
        
        # 执行直连识别
        result = ask_gemini_botanist_raw(target_image, GEMINI_KEY)
        
        # 回复最终结果
        final_reply = f"🌿 **【AI植物学家替身鉴定报告】** 🌿\n\n{result}"
        reply_to_issue(issue_num, repo, token, final_reply)
