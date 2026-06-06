# Please install OpenAI SDK first: `pip3 install openai`
import os
import time
from openai import OpenAI

client = OpenAI(
    api_key='sk-239f3b3fa70647178c505ccae22d3eae',
    base_url="https://api.deepseek.com")

messages = [
    {"role": "system", "content": "You are a helpful assistant"},
]

print("DeepSeek 交互式聊天（输入 exit 退出）")
print("=" * 50)

while True:
    user_input = input("\n🧑 你: ")
    if user_input.strip().lower() == "exit":
        break

    messages.append({"role": "user", "content": user_input})

    start_time = time.perf_counter()
    first_token_time = None
    token_count = 0

    response = client.chat.completions.create(
        model="deepseek-v4-flash",
        messages=messages,
        stream=True,
        # reasoning_effort="high",
        extra_body={"thinking": {"type": "disabled"}}
    )

    print("🤖 助手: ", end='', flush=True)
    is_reasoning = True
    for chunk in response:
        delta = chunk.choices[0].delta
        if getattr(delta, 'reasoning_content', None):
            if first_token_time is None:
                first_token_time = time.perf_counter()
            if is_reasoning:
                print("\033[90m", end='', flush=True)  # 灰色开始
                is_reasoning = False
            print(delta.reasoning_content, end='', flush=True)
        if delta.content:
            if first_token_time is None:
                first_token_time = time.perf_counter()
            if not is_reasoning:
                # 思考结束，恢复颜色
                # 思考内容与回答之间留个换行
                print("\033[0m\n", end='', flush=True)
                is_reasoning = True
            token_count += 1
            print(delta.content, end='', flush=True)
    if not is_reasoning:
        print("\033[0m", end='', flush=True)  # 确保颜色重置

    end_time = time.perf_counter()
    total_time = end_time - start_time
    ttft = (first_token_time - start_time) * 1000 if first_token_time else 0
    gen_time = end_time - first_token_time if first_token_time else total_time
    speed = token_count / gen_time if gen_time > 0 else 0

    # 添加助手回复到历史
    # 简单起见，不累积完整回复内容了

    print()
    print(f"🕒 {ttft:.0f} ms  |  ⏱ {total_time*1000:.0f} ms  |  📦 {token_count} tokens  |  🚀 {speed:.1f} t/s")
