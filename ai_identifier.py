import os
import base64
import requests

def identify_plant(image_path, text_prompt="请识别图中的植物并输出详细报告。"):
    # 1. Read and encode your image to base64
    with open(image_path, "rb") as image_file:
        image_bytes = base64.b64encode(image_file.read()).decode("utf-8")
        
    # 2. 使用正确的 Gemini API 端点
    model = "gemini-2.5-flash"  # 或者 gemini-1.5-flash
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    
    # 3. API key 通过 header 传递
    gemini_key = os.environ.get("GEMINI_API_KEY")
    if not gemini_key:
        return "错误：未设置 GEMINI_API_KEY 环境变量"
    
    headers = {
        "x-goog-api-key": gemini_key,
        "Content-Type": "application/json"
    }
    
    # 4. 正确的请求体格式
    payload = {
        "contents": [
            {
                "parts": [
                    {
                        "text": text_prompt
                    },
                    {
                        "inline_data": {
                            "mime_type": "image/jpeg",
                            "data": image_bytes
                        }
                    }
                ]
            }
        ]
    }
    
    response = requests.post(url, headers=headers, json=payload)
    
    if response.status_code == 200:
        result = response.json()
        try:
            # 提取生成的文本内容
            output_text = result["candidates"][0]["content"]["parts"][0]["text"]
            return output_text
        except (KeyError, IndexError) as e:
            return f"解析响应失败: {result}, 错误: {e}"
    else:
        return f"请求失败，状态码: {response.status_code}, 错误信息: {response.text}"

# 使用示例
if __name__ == "__main__":
    result = identify_plant("your_plant_image.jpg")
    print(result)
