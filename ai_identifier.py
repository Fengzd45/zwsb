import os
import re
import requests
import google.generativeai as genai

# 配置大模型钥匙
GEMINI_KEY = os.environ.get("GEMINI_API_KEY")
if GEMINI_KEY:
    genai.configure(api_key=GEMINI_KEY)

def extract_image_urls(text):
    """从 Issue 的 Markdown 文本中提取出用户上传的图片链接"""
    # 匹配 Markdown 图片格式 ![image](url) 或 HTML 格式 <img src="url">
    urls = re.findall(r'!\[.*?\]\((.*?)\)', text)
    return urls

def reply_to_issue(issue_number, repo, token, message):
    """让替身在 GitHub Issue 下方发表评论回复"""
    url = f"https://api.github.com/repos/{repo}/issues/{issue_number}/comments"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }
    data = {"body": message}
    response = requests.post(url, json=data, headers=headers)
    return response.status_code

def ask_gemini_botanist(image_url):
    """驱动大模型替身睁眼看图并识别"""
    try:
        # 下载 Issue 中的图片缓存到云端
        img_data = requests.get(image_url).content
        image_parts = [
            {
                "mime_type": "image/jpeg",
                "data": img_data
            }
        ]
        
        prompt = """
        你现在是冯老的随身AI植物学家替身。请仔细观察这张植物照片，提供详尽的专家级鉴定：
        1. **植物标准名称**：中文名、英文常用名、精准的拉丁学名。
        2. **植物分类**：科、属。并明确归类为 "Grass", "Shrub", "Tree", "Conifer" 中的哪一种。
        3. **外观特征**：叶形、花期、果实特点等。
        4. **健康状态评估**：从画面上看，这株植物是否有病虫害、缺水或其他生长问题？如果有，请给出调理建议。
        
        请用亲切、专业、条理清晰的中文回复。
        """
        
        model = genai.GenerativeModel("gemini-1.5-pro")
        response = model.generate_content([image_parts[0], prompt])
        return response.text
    except Exception as e:
        return f"❌ 替身在看图时眼睛开小差了: {str(e)}"

if __name__ == "__main__":
    issue_body = os.environ.get("ISSUE_BODY", "")
    issue_num = os.environ.get("ISSUE_NUMBER", "")
    repo = os.environ.get("REPOSITORY", "")
    token = os.environ.get("GITHUB_TOKEN", "")
    
    if not issue_body or not issue_num:
        print("未检测到有效的 Issue 内容。")
        exit(0)
        
    image_urls = extract_image_urls(issue_body)
    
    if not image_urls:
        reply_to_issue(issue_num, repo, token, "🤖 **替身播报**：冯老，您建了识别单，但保险柜里没看到您贴的植物照片呀，请把照片直接拖进对话框里。")
    else:
        # 抓取第一张照片进行识别
        target_image = image_urls[0]
        print(f"正在识别图片: {target_image}")
        
        # 占位提示
        reply_to_issue(issue_num, repo, token, "🔍 **替身正在闭眼搜寻知识库，请稍候...**")
        
        # 核心识别
        result = ask_gemini_botanist(target_image)
        
        # 最终答复
        final_reply = f"🌿 **【AI植物学家替身鉴定报告】** 🌿\n\n{result}"
        reply_to_issue(issue_num, repo, token, final_reply)
        print("鉴定报告已成功送达 Issue 评论区！")
