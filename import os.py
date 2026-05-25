import os 
from google import genai
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

def main():
    # Retrieve API key from environment
    api_key = os.getenv("GEMINI_API_KEY")
    
    if not api_key:
        print("Error: GEMINI_API_KEY not found in environment or .env file.")
        print("Please create a .env file and add your API key: GEMINI_API_KEY=your_api_key_here")
        return

    # Initialize the Gemini Client
    client = genai.Client(api_key=api_key)

    # System instruction to define MOSES
    system_instruction = (
        "Your name is MOSES. You are a wise and helpful AI assistant. "
        "You provide clear, concise, and insightful answers to any questions. "
        "Always identify yourself as MOSES if asked."
    )

    print("--- MOSES AI Model is ready ---")
    print("Type 'exit' or 'quit' to end the conversation.")

    # Start a chat session
    # The new SDK doesn't have a direct 'start_chat' like the old one in the same way,
    # but it supports chat sessions.
    chat = client.chats.create(
        model="gemini-1.5-flash",
        config={"system_instruction": system_instruction}
    )

    while True:
        try:
            user_input = input("You: ")
            if user_input.lower() in ["exit", "quit"]:
                print("MOSES: Farewell. May wisdom guide you.")
                break
            
            if not user_input.strip():
                continue

            response = chat.send_message(user_input)
            print(f"MOSES: {response.text}")
        
        except KeyboardInterrupt:
            print("\nMOSES: Farewell.")
            break
        except Exception as e:
            print(f"An error occurred: {e}")

if __name__ == "__main__":
    main()
