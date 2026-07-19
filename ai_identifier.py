import os
import re
import base64
import requests

# 1. 防机器人自我评论死循环
if os.environ.get("COMMENTER_USER", "") == "github-actions[bot]":
    print("检测到是机器人自己的评论，跳过避免死循环。")
    exit(0)

def extract_image_urls(text):
    """升级版全渠道抓图逻辑"""
    md_urls = re.findall(r'!\[.*?\]\((.*?)\)', text)
    html_urls = re.findall(r'<img [^>]*src="([^"]+)"', text)
    raw_urls = re.findall(r'(https?://[^\s\)]+\.(?:jpg|jpeg|png|webp|gif))', text, re.IGNORECASE)
    return md_urls + html_urls + raw_urls

def reply_to_issue(issue_number, repo, token, message):
    """GitHub 评论回复通用函数"""
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
            
            # 3. 冯老专属植物学家剧本
            prompt_text = (
                "你现在是冯老的随身AI植物学家替身。请仔细观察这张植物照片，提供详尽的专家级鉴定：\n"
                "1. **植物标准名称**：中文名、英文常用名、精准的拉丁学名。\n"
                "2. **植物分类**：科、属。并明确归类为 'Grass', 'Shrub', 'Tree', 'Conifer' 中的哪一种。\n"
                "3. **外观特征**：叶形、花期、果实特点等。\n"
                "4. **健康状态评估**：从生长状态看这株植物是否有病虫害或缺水？请给出具体调理建议。\n\n"
                "请用亲切、专业、条理清晰的中文回复。"
            )
            
            # 4. 🚀【核心修正】：精准匹配官方最新的通道与模型映射
            test_routes = [
                {"version": "v1", "model": "gemini-2.0-flash"},         # 稳定通道 2.0 旗舰多模态
                {"version": "v1", "model": "gemini-1.5-flash"},         # 稳定通道 1.5 经典多模态
                {"version": "v1beta", "model": "gemini-2.0-flash-exp"}, # 预览通道 2.0 实验模型
                {"version": "v1beta", "model": "gemini-1.5-flash"},     # 预览通道 1.5 模型
            ]
            
            success = False
            error_logs = []
            
            headers = {"Content-Type": "application/json"}
            payload = {
                "contents": [{
                    "parts": [
                        {"text": prompt_text},
                        {
                            "inlineData": {
                                "mimeType": "image/jpeg",
                                "data": img_base64
                            }
                        }
                    ]
                }]
            }
            
            for route in test_routes:
                ver = route["version"]
                mod = route["model"]
                url = f"https://generativelanguage.googleapis.com/{ver}/models/{mod}:generateContent?key={GEMINI_KEY}"
                
                print(f"正在尝试叩门：{ver} 版本的 {mod} 模型...")
                res = requests.post(url, json=payload, headers=headers, timeout=40)
                
                if res.status_code == 200:
                    response_data = res.json()
                    response_text = response_data['candidates'][0]['content']['parts'][0]['text']
                    
                    # 捞到了报告，立刻收工发送
                    final_reply = f"🌿 **【AI植物学家替身鉴定报告】** 🌿\n*(已自动匹配最佳通路: {ver}/{mod})*\n\n{response_text}"
                    reply_to_issue(issue_num, repo, token, final_reply)
                    success = True
                    break
                else:
                    error_logs.append(f"• {ver}/{mod} 门拒入 (状态码 {res.status_code})")
            
            # 如果全部门都试过了还是进不去，打印出尝试清单供排查
            if not success:
                log_message = "❌ 替身叩门一圈，所有新旧模型通道均未接纳此钥匙，请检查钥匙权限。\n详细排查日志：\n" + "\n".join(error_logs)
                reply_to_issue(issue_num, repo, token, log_message)
                
        except Exception as e:
            reply_to_issue(issue_num, repo, token, f"❌ 替身看图时遭遇底层阻碍: `{str(e)}`")
