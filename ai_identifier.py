import os
import base64
import requests

def identify_plant(image_path, text_prompt="请识别图中的植物并输出详细报告。"):
    # 1. Read and encode your image to base64
    with open(image_path, "rb") as image_file:
        image_bytes = base64.b64encode(image_file.read()).decode("utf-8")
        
    # 2. Use the modern 2026 Interactions API endpoint
    url = "https://generativelanguage.googleapis.com/v1beta/interactions"
    
    # 3. Securely pass the AQ. key via headers
    gemini_key = os.environ.get("GEMINI_API_KEY")
    headers = {
        "x-goog-api-key": gemini_key,
        "Content-Type": application/json"
    }
    
    # 4. Construct the Interactions API payload format
    payload = {
        "model": "gemini-2.5-flash",  # Or "gemini-3.5-flash" depending on tier
        "input": [
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
    
    response = requests.post(url, headers=headers, json=payload)
    
    if response.status_code == 200:
        result = response.json()
        # The new API packages outputs inside an array of steps
        # Extracting text from the final output step
        try:
            output_text = result["outputs"][-1]["text"]
            return output_text
        except (KeyError, IndexError):
            return f"解析响应失败: {result}"
    else:
        return f"请求失败，状态码: {response.status_code}, 错误信息: {response.text}"
