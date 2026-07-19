import os
import re
import base64
import requests
import time

# 1. 防机器人自我评论死循环
if os.environ.get("COMMENTER_USER", "") == "github-actions[bot]":
    print("检测到是机器人自己的评论，跳过避免死循环。")
    exit(0)

def extract_image_urls(text):
    md_urls = re.findall(r'!\[.*?\]\((.*?)\)', text)
    html_urls = re.findall(r'<img [^>]*src="([^"]+)"', text)
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
        reply_to_issue(issue_num, repo, token, "❌ 替身播报：未检测到密钥，请检查 GitHub Secrets 配置。")
        exit(1)
        
    image_urls = extract_image_urls(issue_body)
    if not image_urls:
        reply_to_issue(issue_num, repo, token, "🤖 替身播报：冯老，未看到您贴的植物照片，请等照片上传完毕后再提交。")
    else:
        target_image = image_urls[0]
        
        try:
            # 2. 下载图片并转化为 Base64 编码
            img_res = requests.get(target_image, timeout=30)
            img_base64 = base64.b64encode(img_res.content).decode('utf-8')
            
            prompt_text = (
                "你现在是冯老的随身AI植物学家替身。请仔细观察这张植物照片，提供详尽的专家级鉴定：\n"
                "1. **植物标准名称**：中文名、英文常用名、精准的拉丁学名。\n"
                "2. **植物分类**：科、属。并明确归类为 'Grass', 'Shrub', 'Tree', 'Conifer' 中的哪一种。\n"
                "3. **外观特征**：叶形、花期、果实特点等。\n"
                "4. **健康状态评估**：从生长状态看这株植物是否有病虫害或缺水？请给出具体调理建议。\n\n"
                "请用亲切、专业、条理清晰的中文回复。"
            )
            
            # 3. 剥离所有幻觉，只写官方百分百存在的真实路径
            real_models = [
                "v1/models/gemini-2.0-flash",       # 官方最新 2.0 正式版
                "v1beta/models/gemini-1.5-flash"    # 官方最稳 1.5 经典版 (备用)
            ]
            
            payload = {
                "contents": [{
                    "parts": [
                        {"text": prompt_text},
                        {"inlineData": {"mimeType": "image/jpeg", "data": img_base64}}
                    ]
                }]
            }
            
            success = False
            error_logs = []
            
            for model_path in real_models:
                url = f"https://generativelanguage.googleapis.com/{model_path}:generateContent?key={GEMINI_KEY}"
                
                # 🚀 针对 GitHub Actions 的核心重试机制（破 429 必杀技）
                for attempt in range(3): 
                    print(f"正在敲门：{model_path} (第 {attempt+1} 次尝试)...")
                    res = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=40)
                    
                    if res.status_code == 200:
                        response_data = res.json()
                        response_text = response_data['candidates'][0]['content']['parts'][0]['text']
                        final_reply = f"🌿 **【AI植物学家替身鉴定报告】** 🌿\n\n{response_text}"
                        reply_to_issue(issue_num, repo, token, final_reply)
                        success = True
                        break
                        
                    elif res.status_code == 429:
                        print(f"遇到 GitHub 节点拥堵 (429)，等待 10 秒后重试...")
                        time.sleep(10)  # 避开并发高峰，稍微等一下就能进去
                        
                    else:
                        # 记录真实的错误详情，不再瞎猜
                        error_msg = f"• {model_path} 拒入: 状态码 {res.status_code}, 详情: {res.text[:100]}"
                        error_logs.append(error_msg)
                        break # 如果是 400 或 404 这种死错误，不重试，直接换下个模型
                
                if success:
                    break
            
            if not success:
                log_message = "❌ 替身尝试失败。详细排查日志：\n" + "\n".join(error_logs)
                reply_to_issue(issue_num, repo, token, log_message)
                
        except Exception as e:
            reply_to_issue(issue_num, repo, token, f"❌ 替身看图时遭遇底层阻碍: `{str(e)}`")
