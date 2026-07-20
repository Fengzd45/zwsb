import os
import re
import base64
import requests
import time

# 防止机器人自己触发自己
if os.environ.get("COMMENTER_USER", "") == "github-actions[bot]":
    print("检测到是机器人自己的评论，跳过避免死循环。")
    exit(0)

def extract_image_urls(text):
    """从 Markdown/HTML 中提取图片链接"""
    md_urls = re.findall(r'!\[.*?\]\((.*?)\)', text)
    html_urls = re.findall(r'<img [^>]*src="([^"]+)"', text)
    raw_urls = re.findall(r'(https?://[^\s\)]+\.(?:jpg|jpeg|png|webp|gif))', text, re.IGNORECASE)
    return md_urls + html_urls + raw_urls

def reply_to_issue(issue_number, repo, token, message):
    """回复 GitHub Issue"""
    url = f"https://api.github.com/repos/{repo}/issues/{issue_number}/comments"
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
    return requests.post(url, json={"body": message}, headers=headers).status_code

def identify_plant_with_siliconflow(image_base64, mime_type, api_key):
    """
    调用硅基流动 API 识别植物
    返回: (是否成功, 结果文本或错误信息)
    """
    # 当前硅基流动可用的视觉模型（2026年7月实测）
    # 按成功率排序：最稳的放前面
    candidate_models = [
        "Qwen/Qwen2.5-VL-72B-Instruct",      # 主力模型
        "Qwen/Qwen2-VL-72B-Instruct",        # 备选
        "deepseek-ai/deepseek-vl2",          # DeepSeek 视觉
        "OpenGVLab/InternVL2-26B",           # 开源视觉模型
    ]
    
    prompt_text = (
        "你现在是冯老的随身AI植物学家替身。请仔细观察这张植物照片，提供详尽的专家级鉴定：\n"
        "1. **植物标准名称**：中文名、英文常用名、精准的拉丁学名。\n"
        "2. **植物分类**：科、属。并明确归类为 'Grass', 'Shrub', 'Tree', 'Conifer' 中的哪一种。\n"
        "3. **外观特征**：叶形、花期、果实特点等。\n"
        "4. **健康状态评估**：从生长状态看这株植物是否有病虫害或缺水？请给出具体调理建议。\n\n"
        "请用亲切、专业、条理清晰的中文回复。"
    )
    
    sf_url = "https://api.siliconflow.cn/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    error_logs = []
    
    for model_name in candidate_models:
        print(f"🔄 正在尝试模型：{model_name}...")
        
        payload = {
            "model": model_name,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt_text},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime_type};base64,{image_base64}"
                            }
                        }
                    ]
                }
            ],
            "temperature": 0.3,
            "max_tokens": 2048
        }
        
        try:
            res = requests.post(sf_url, json=payload, headers=headers, timeout=90)
            
            if res.status_code == 200:
                response_data = res.json()
                response_text = response_data['choices'][0]['message']['content']
                return True, response_text
            else:
                error_msg = f"• {model_name} (状态码 {res.status_code})"
                try:
                    err_json = res.json()
                    error_msg += f": {err_json.get('message', res.text[:100])}"
                except:
                    error_msg += f": {res.text[:100]}"
                error_logs.append(error_msg)
                print(f"   ❌ {error_msg}")
                time.sleep(0.5)  # 短暂延迟避免频率限制
                
        except requests.exceptions.Timeout:
            error_logs.append(f"• {model_name}: 请求超时")
        except Exception as e:
            error_logs.append(f"• {model_name}: {str(e)}")
    
    return False, "\n".join(error_logs)


if __name__ == "__main__":
    # ===== 配置区 =====
    # 从环境变量读取（GitHub Actions 用）
    SILICONFLOW_KEY = os.environ.get("SILICONFLOW_API_KEY", "").strip()
    issue_body = os.environ.get("ISSUE_BODY", "")
    issue_num = os.environ.get("ISSUE_NUMBER", "")
    repo = os.environ.get("REPOSITORY", "")
    token = os.environ.get("GITHUB_TOKEN", "")
    # ==================
    
    # 如果没有 issue 信息，直接退出（本地测试时可用）
    if not issue_body or not issue_num:
        print("⚠️ 未检测到 Issue 环境变量，进入本地测试模式...")
        # 本地测试：读取本地图片
        test_image_path = "test_plant.jpg"
        if os.path.exists(test_image_path):
            with open(test_image_path, "rb") as f:
                img_base64 = base64.b64encode(f.read()).decode('utf-8')
            success, result = identify_plant_with_siliconflow(img_base64, "image/jpeg", SILICONFLOW_KEY)
            if success:
                print("🌿 识别结果：")
                print(result)
            else:
                print("❌ 识别失败：")
                print(result)
        else:
            print("💡 请将测试图片命名为 test_plant.jpg 放在当前目录")
        exit(0)
    
    # 检查密钥
    if not SILICONFLOW_KEY:
        reply_to_issue(issue_num, repo, token, 
                       "❌ 替身播报：未检测到硅基流动密钥，请检查 GitHub Secrets 中是否配置了 SILICONFLOW_API_KEY。")
        exit(1)
    
    # 提取图片
    image_urls = extract_image_urls(issue_body)
    if not image_urls:
        reply_to_issue(issue_num, repo, token, 
                       "🤖 替身播报：冯老，未看到您贴的植物照片，请等照片上传完毕后再提交。")
        exit(0)
    
    # 处理第一张图片
    target_image = image_urls[0]
    print(f"📸 正在处理图片：{target_image}")
    
    try:
        # 下载图片
        img_res = requests.get(target_image, timeout=30)
        img_res.raise_for_status()
        
        # 获取 MIME 类型
        mime_type = img_res.headers.get("Content-Type", "image/jpeg")
        if "text/html" in mime_type or not mime_type:
            # 如果返回的是网页，可能是 GitHub 的跳转链接，尝试添加 ?raw=true
            if "github.com" in target_image and "?" not in target_image:
                raw_url = target_image + "?raw=true"
                print(f"🔄 尝试获取原始图片：{raw_url}")
                img_res = requests.get(raw_url, timeout=30)
                img_res.raise_for_status()
                mime_type = img_res.headers.get("Content-Type", "image/jpeg")
        
        img_base64 = base64.b64encode(img_res.content).decode('utf-8')
        
        # 调用硅基流动识别
        success, result = identify_plant_with_siliconflow(img_base64, mime_type, SILICONFLOW_KEY)
        
        if success:
            final_reply = f"🌿 **【AI植物学家替身鉴定报告】** 🌿\n\n{result}"
            reply_to_issue(issue_num, repo, token, final_reply)
            print("✅ 识别成功，已回复 Issue")
        else:
            log_message = "❌ 替身叩门失败。详细日志：\n" + result
            reply_to_issue(issue_num, repo, token, log_message)
            print("❌ 所有模型均失败")
            
    except requests.exceptions.Timeout:
        reply_to_issue(issue_num, repo, token, "❌ 替身看图超时，图片可能太大或网络太慢。")
    except Exception as e:
        reply_to_issue(issue_num, repo, token, f"❌ 替身看图时遭遇底层阻碍: `{str(e)}`")
        print(f"❌ 错误：{e}")
