import os
import re
import requests

# 1. 防死循环
if os.environ.get("COMMENTER_USER", "") == "github-actions[bot]":
    print("检测到是机器人自己的评论，跳过避免死循环。")
    exit(0)

# 2. 【关键修复】根据官方提示，必须从 preview 导入！
from vertexai.preview.generative_models import GenerativeModel, Part
import vertexai

# 3. 读取 API Key 并初始化
GEMINI_KEY = os.environ.get("GEMINI_API_KEY")
if GEMINI_KEY:
    # 使用 preview 模式初始化
    vertexai.init(project="", location="us-central1", api_key=GEMINI_KEY)
else:
    print("错误：未检测到 GEMINI_API_KEY 环境变量！")
    exit(1)

def extract_image_urls(text):
    """从 Issue 的 Markdown 文本中提取图片链接"""
    urls = re.findall(r'!\[.*?\]\((.*?)\)', text)
    if not urls:
        urls = re.findall(r'<img.*?src="(.*?)"', text)
    return urls

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

def ask_gemini_botanist(image_url):
    """识别植物"""
    try:
        # 下载图片
        img_data = requests.get(image_url, timeout=30).content
        
        # 转换为 Gemini 专用格式
        image_part = Part.from_data(img_data, mime_type="image/jpeg")
        
        prompt = """
        你现在是冯老的随身AI植物学家替身。请仔细观察这张植物照片，提供详尽的专家级鉴定：
        1. **植物标准名称**：中文名、英文常用名、精准的拉丁学名。
        2. **植物分类**：科、属。并明确归类为 "Grass", "Shrub", "Tree", "Conifer" 中的哪一种。
        3. **外观特征**：叶形、花期、果实特点等。
        4. **健康状态评估**：从画面上看，这株植物是否有病虫害、缺水或其他生长问题？如果有，请给出调理建议。
        
        请用亲切、专业、条理清晰的中文回复。
        """
        
        # 使用 preview 包下的模型
        model = GenerativeModel("gemini-1.5-flash")
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
        reply_to_issue(issue_num, repo, token, "🤖 **替身播报**：冯老，您建了识别单，但没看到照片，请把照片直接拖进对话框里。")
    else:
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
