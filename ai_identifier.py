import os
import re
import requests
import google.generativeai as genai
import tempfile

# 1. 死循环防御：如果是机器人自己的回复，直接退出
if os.environ.get("COMMENTER_USER", "") == "github-actions[bot]":
    print("检测到是机器人自己的评论，跳过避免死循环。")
    exit(0)

# 2. 配置大模型钥匙
GEMINI_KEY = os.environ.get("GEMINI_API_KEY")
if GEMINI_KEY:
    genai.configure(api_key=GEMINI_KEY)

def extract_image_urls(text):
    """从 Issue 的 Markdown 文本中提取出用户上传的图片链接"""
    # 兼容 Markdown 格式 ![]() 和 HTML <img src="">
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
    """驱动大模型替身睁眼看图并识别（修复了图片传递问题）"""
    try:
        # 下载 Issue 中的图片
        img_data = requests.get(image_url, timeout=30).content
        
        # 使用 tempfile 保存为临时文件，这是 Gemini 官方最稳妥的方式
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp_file:
            tmp_file.write(img_data)
            tmp_path = tmp_file.name
        
        # 上传到 Gemini 获取 URI
        uploaded_file = genai.upload_file(tmp_path, mime_type="image/jpeg")
        
        # 构建提示词
        prompt = """
        你现在是冯老的随身AI植物学家替身。请仔细观察这张植物照片，提供详尽的专家级鉴定：
        1. **植物标准名称**：中文名、英文常用名、精准的拉丁学名。
        2. **植物分类**：科、属。并明确归类为 "Grass", "Shrub", "Tree", "Conifer" 中的哪一种。
        3. **外观特征**：叶形、花期、果实特点等。
        4. **健康状态评估**：从画面上看，这株植物是否有病虫害、缺水或其他生长问题？如果有，请给出调理建议。
        
        请用亲切、专业、条理清晰的中文回复。
        """
        
        model = genai.GenerativeModel("gemini-1.5-pro")
        # 传递 URI 给大模型
        response = model.generate_content([uploaded_file, prompt])
        
        # 清理临时文件
        os.remove(tmp_path)
        
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
