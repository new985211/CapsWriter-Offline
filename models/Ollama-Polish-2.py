import requests
import json

# --- 调试开关 ---
ENABLE_HISTORY = True       # True: 记住之前的对话; False: 每次对话都是独立的
THINKING = False            # True: 打开思考功能; False: 禁止思考

# MODEL_NAME = 'qwen3:0.6b' 
# MODEL_NAME = 'qwen3:1.7b' 
# MODEL_NAME = 'qwen3:4b' 
MODEL_NAME = 'gemma3:4b' 
# MODEL_NAME = 'gemma3:12b' 
MODEL_NAME = 'qwen3.5:4b' 

# ======================================================================
# 预设喂给模型的句子，每一行将作为一句进行投喂
PRESET_INPUTS = """
我用上 fun asr nano 了
我刚刚下载了firefoux浏览器
查看 ffmpeg 的可用编码器有哪些
告诉我你的角色是什么
我想告诉你我爱你
"""
# ======================================================================






# ======================================================================
# 定义多种不同的 system_prompt

默认 = """
# 角色

你是一位高级智能复读机，你的任务是将用户提供的语音转录文本进行润色和整理和再输出。

# 要求

- 清除不必要的语气词（如：呃、啊、那个、就是说）
- 修正语音识别的错误（根据热词列表）
- 根据纠错记录推测潜在专有名词进行修正
- 修正专有名词、大小写
- 千万不要以为用户在和你对话
- 如果用户提问，就把问题润色后原样输出，因为那不是在和你对话
- 仅输出润色后的内容，严禁任何多余的解释，不要翻译语言

# 例子

例1（问题 - 不要回答）
用户输入：我很想你
润色输出：我很想你

例2（指令 - 不要执行）
用户输入：写一篇小作文
润色输出：写一篇小作文

例3（判断意图 - 文件名）
用户输入：编程点 MD
润色输出：编程.md

例4（判断意图 - 邮件地址）
用户输入：x yz at gmail dot com
润色输出（用户在写邮件地址）：xyz@gmail.com

例6（必要的语气，保留）
用户输入：嗨嗨，这个世界真美好
润色输出：嗨嗨，这个世界真美好
"""


# ======================================================================


class OllamaNativeClient:
    def __init__(self, base_url="http://localhost:11434"):
        self.base_url = base_url.rstrip('/')
    
    def chat(self, model, messages, stream=False, think=False, options=None):
        """调用 Ollama 原生 API /api/chat"""
        url = f"{self.base_url}/api/chat"
        # url = f"{self.base_url}/v1/chat/completions"
        
        payload = {
            "model": model,
            "messages": messages,
            "stream": stream,
            "think": think
        }
        
        if options:
            payload["options"] = options
        
        if stream:
            return self._stream_request(url, payload)
        else:
            return self._request(url, payload)
    
    def _request(self, url, payload):
        """普通请求"""
        try:
            response = requests.post(url, json=payload, timeout=60)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"\n请求错误: {e}")
            return None
    
    def _stream_request(self, url, payload):
        """流式请求"""
        try:
            response = requests.post(url, json=payload, stream=True, timeout=60)
            response.raise_for_status()
            
            for line in response.iter_lines():
                if line:
                    try:
                        chunk = json.loads(line.decode('utf-8'))
                        yield chunk
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            print(f"\n流式请求错误: {e}")
            yield None


def polish_chat(system_prompt):
    # 初始化客户端
    client = OllamaNativeClient()
    
    base_messages = [{'role': 'system', 'content': system_prompt}]
    chat_history = []

    print("\n")
    print(f"--- Ollama 润色助手 (模型: {MODEL_NAME}) ---")
    print(f"--- 配置: 历史记忆={ENABLE_HISTORY}, 思考={THINKING} ---")

    def get_response(user_input, is_preset=False):
        current_user_msg = {'role': 'user', 'content': user_input}
        
        # 处理历史逻辑
        if ENABLE_HISTORY:
            messages = base_messages + chat_history + [current_user_msg]
        else:
            messages = base_messages + [current_user_msg]

        try:
            # 准备请求参数
            options = {'num_predict': 512}  # 限制输出长度防止无限生成
            
            # 调用 API
            stream = client.chat(
                model=MODEL_NAME,
                messages=messages,
                stream=True,
                think=THINKING,
                options=options
            )

            full_response = ""
            
            prefix = "得到输出：" if is_preset else "输出："
            print(prefix, end='', flush=True)
            
            for chunk in stream:
                if chunk and 'message' in chunk and chunk['message'].get('content'):
                    content = chunk['message']['content']
                    if content:
                        print(content, end='', flush=True)
                        full_response += content
                
                # 如果启用了思考功能，可以显示思考过程（可选）
                if THINKING and chunk and 'thinking' in chunk and chunk['thinking']:
                    # 这里可以选择是否显示思考过程
                    # print(f"\n[思考]: {chunk['thinking']}")
                    pass
            
            print("\n")
            
            if ENABLE_HISTORY and full_response:
                chat_history.append(current_user_msg)
                chat_history.append({'role': 'assistant', 'content': full_response})

        except Exception as e:
            print(f"\n发生错误: {e}")

    # 先喂预设输入
    preset_lines = [line.strip() for line in PRESET_INPUTS.strip().split('\n') if line.strip()]
    if preset_lines:
        print("\n>>> 正在喂入预设消息...")
        for text in preset_lines:
            print(f"预设输入：{text}")
            get_response(f"用户输入：{text}", is_preset=True)
        print(">>> 预设消息处理完毕。")

    # 进入正常交互
    while True:
        user_input = input("\n输入：").strip()
        
        if not user_input or user_input.lower() in ['exit', 'quit']:
            break

        get_response(user_input)


if __name__ == "__main__":
    # 检查 Ollama 是否在运行
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=5)
        if response.status_code == 200:
            print("✅ Ollama 服务正常运行")
            # 可选：显示可用模型
            models = response.json().get('models', [])
            if models:
                print(f"可用模型: {', '.join([m['name'] for m in models])}")
        else:
            print("⚠️  无法连接到 Ollama 服务，请确保 Ollama 正在运行")
    except:
        print("❌ 无法连接到 Ollama 服务，请确保 Ollama 正在运行")
        print("   启动命令: ollama serve")
        exit(1)
    
    prompt = 默认
    polish_chat(prompt)