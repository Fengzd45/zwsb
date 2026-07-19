import os
import re
import requests
import vertexai
from vertexai.generative_models import GenerativeModel, Part

# 1. 如果存在机器人自己发言的变量，防死循环
if os.environ.get("COMMENTER_USER", "") == "github-actions[bot]":
    print("检测到是机器人自己的评论，跳过避免死循环。")
    exit(0)

# 2. 读取 GitHub Secrets 里的 AQ 开头的 API Key
GEMINI_KEY = os.environ.get("GEMINI_API_KEY")

# 【核心改动】不需要 genai.configure，而是使用 vertexai 初始化
# 注意：Gemini 的默认服务端点在 us-central1
if GEMINI_KEY:
    vertexai.init(project="", location="us-central1", api_key=GEMINI_KEY)
else:
    print("错误：未检测到 GEMINI_API_KEY 环境变量！")
    exit(1)

def extract_image_urls(text):
    """从 Issue 的 Markdown 文本中提取出用户上传的图片链接"""
    urls = re.findall(r'!\[.*?\]\((.*?)\)', text)
    if not urls:
        urls = re.findall(r'<img.*?src="(.*?)"', text)
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
    """驱动大模型替身睁眼看图并识别 (使用 Vertex AI SDK)"""
    try:
        # 下载 Issue 中的图片
        img_data = requests.get(image_url, timeout=30).content
        
        # 【Vertex AI 专用格式】使用官方 Part 类封装二进制数据
        image_part = Part.from_data(img_data, mime_type="image/jpeg")
        
        prompt = """
        你现在是冯老的随身AI植物学家替身。请仔细观察这张植物照片，提供详尽的专家级鉴定：
        1. **植物标准名称**：中文名、英文常用名、精准的拉丁学名。
        2. **植物分类**：科、属。并明确归类为 "Grass", "Shrub", "Tree", "Conifer" 中的哪一种。
        3. **外观特征**：叶形、花期、果实特点等。
        4. **健康状态评估**：从画面上看，这株植物是否有病虫害、缺水或其他生长问题？如果有，请给出调理建议。
        
        请用亲切、专业、条理清晰的中文回复。
        """
        
        # 初始化模型 (Vertex AI 下 flash 模型同样免绑卡，响应极快)
        model = GenerativeModel("gemini-1.5-flash")
        
        # 发送请求
        response = model.generate_content([image_part, prompt])
        
        return response.text
        
    except Exception as e:
        print(f"Gemini API 详细报错: {e}")
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
        target_image = image_urls[0]
        print(f"正在识别图片: {target_image}")
        
        reply_to_issue(issue_num, repo, token, "🔍 **替身正在闭眼搜寻知识库，请稍候...**")
        
        result = ask_gemini_botanist(target_image)
        
        final_reply = f"🌿 **【AI植物学家替身鉴定报告】** 🌿\n\n{result}"
        reply_to_issue(issue_num, repo, token, final_reply)
        print("鉴定报告已成功送达 Issue 评论区！")
