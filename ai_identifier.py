import os
import re
import base64
import requests
import time

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
    # 🔑 只读取硅基流动的 API Key
    SILICONFLOW_KEY = os.environ.get("SILICONFLOW_API_KEY", "").strip()
    issue_body = os.environ.get("ISSUE_BODY", "")
    issue_num = os.environ.get("ISSUE_NUMBER", "")
    repo = os.environ.get("REPOSITORY", "")
    token = os.environ.get("GITHUB_TOKEN", "")
    
    if not issue_body or not issue_num:
        exit(0)
        
    if not SILICONFLOW_KEY:
        reply_to_issue(issue_num, repo, token, "❌ 替身播报：未检测到密钥，请检查 GitHub Secrets 中是否配置了 SILICONFLOW_API_KEY。")
        exit(1)
        
    image_urls = extract_image_urls(issue_body)
    if not image_urls:
        reply_to_issue(issue_num, repo, token, "🤖 替身播报：冯老，未看到您贴的植物照片，请等照片上传完毕后再提交。")
    else:
        target_image = image_urls[0]
        
        try:
            img_res = requests.get(target_image, timeout=30)
            img_res.raise_for_status()
            
            mime_type = img_res.headers.get("Content-Type", "image/jpeg")
            if "text/html" in mime_type: 
                mime_type = "image/jpeg"
                
            img_base64 = base64.b64encode(img_res.content).decode('utf-8')
            
            prompt_text = (
                "你现在是冯老的随身AI植物学家替身。请仔细观察这张植物照片，提供详尽的专家级鉴定：\n"
                "1. **植物标准名称**：中文名、英文常用名、精准的拉丁学名。\n"
                "2. **植物分类**：科、属。并明确归类为 'Grass', 'Shrub', 'Tree', 'Conifer' 中的哪一种。\n"
                "3. **外观特征**：叶形、花期、果实特点等。\n"
                "4. **健康状态评估**：从生长状态看这株植物是否有病虫害或缺水？请给出具体调理建议。\n\n"
                "请用亲切、专业、条理清晰的中文回复。"
            )
            
            # 使用硅基流动稳定且识别强的开源视觉模型
            sf_url = "https://api.siliconflow.cn/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {SILICONFLOW_KEY}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": "Qwen/Qwen2-VL-7B-Instruct",
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt_text},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{mime_type};base64,{img_base64}"
                                }
                            }
                        ]
                    }
                ],
                "temperature": 0.3
            }
            
            print("正在调用硅基流动 Qwen2-VL 进行植物鉴定...")
            res = requests.post(sf_url, json=payload, headers=headers, timeout=60)
            
            if res.status_code == 200:
                response_data = res.json()
                response_text = response_data['choices'][0]['message']['content']
                final_reply = f"🌿 **【AI植物学家替身鉴定报告】** 🌿\n\n{response_text}"
                reply_to_issue(issue_num, repo, token, final_reply)
            else:
                reply_to_issue(issue_num, repo, token, f"❌ 替身叩门失败 (状态码 {res.status_code}): {res.text[:150]}")
                
        except Exception as e:
            reply_to_issue(issue_num, repo, token, f"❌ 替身看图时遭遇底层阻碍: `{str(e)}`")
