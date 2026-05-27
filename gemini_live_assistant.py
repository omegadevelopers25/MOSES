import os
import json
import requests
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

def main():
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        print("Error: OPENROUTER_API_KEY not found in environment.")
        return

    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    
    payload = {
        "model": "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
        "messages": [
            {
                "role": "user",
                "content": "How many r's are in the word 'strawberry'?"
            }
        ],
        "stream": True
    }

    try:
        response = requests.post(url, headers=headers, json=payload, stream=True)
        response.raise_for_status()

        print("MOSES (OpenRouter): ", end="", flush=True)
        for line in response.iter_lines():
            if line:
                line_text = line.decode("utf-8").strip()
                if line_text.startswith("data: "):
                    data_str = line_text[len("data: "):]
                    if data_str == "[DONE]":
                        break
                    
                    try:
                        data = json.loads(data_str)
                        delta = data.get("choices", [{}])[0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            print(content, end="", flush=True)
                        
                        # Handle usage/reasoning tokens if provided in the stream or final chunk
                        usage = data.get("usage")
                        if usage:
                            reasoning = usage.get("reasoning_tokens")
                            if reasoning:
                                print(f"\n\n[Reasoning tokens: {reasoning}]")
                    except json.JSONDecodeError:
                        continue
        print()
    except Exception as e:
        print(f"\nError connecting to OpenRouter: {e}")

if __name__ == "__main__":
    main()
