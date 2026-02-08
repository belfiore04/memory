
import requests
import json
import time

BASE_URL = "http://localhost:8000"

def run_test():
    print("=== Testing AI Character Settings ===")
    
    # 1. Login to get token
    print("\n[1] Logging in...")
    login_data = {
        "username": "admin_user",  # Assuming this user exists from previous steps
        "password": "admin_password"
    }
    # Note: If admin_user doesn't exist, we might need to use an existing one or create one.
    # For now, let's try to list users first if login fails, or just use a known one.
    # Actually, let's try to register a temp user if we can, or assume an admin exists.
    # Since I don't know the password of existing users, I'll register a new one and promote it (if strict admin logic allows).
    # Wait, the previous steps migrated existing users to admin. I don't know their passwords.
    # But I can create a new user.
    
    # Let's create a new test user for verification
    test_username = f"test_persona_{int(time.time())}"
    test_password = "test_password"
    
    print(f"Registering new user: {test_username}")
    resp = requests.post(f"{BASE_URL}/auth/register", json={"username": test_username, "password": test_password})
    if resp.status_code != 200:
        print(f"Registration failed: {resp.text}")
        return
        
    user_id = resp.json()["user_id"]
    print(f"User registered: {user_id}")
    
    # Login
    resp = requests.post(f"{BASE_URL}/auth/login", data={"username": test_username, "password": test_password})
    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    print("Logged in successfully.")

    # 2. Check initial settings (should be null)
    print("\n[2] Checking initial settings...")
    resp = requests.get(f"{BASE_URL}/auth/persona", headers=headers)
    print(f"Initial settings: {resp.json()}")
    assert resp.json()["ai_name"] is None
    assert resp.json()["persona"] is None
    
    # 3. Update settings
    print("\n[3] Updating settings...")
    new_settings = {
        "ai_name": "Jarvis",
        "persona": "You are Jarvis, a helpful and slightly sarcastic AI assistant. You always address the user as 'Sir'."
    }
    resp = requests.put(f"{BASE_URL}/auth/persona", headers=headers, json=new_settings)
    assert resp.status_code == 200, f"Update failed: {resp.text}"
    print("Settings updated.")
    
    # 4. Check settings again
    resp = requests.get(f"{BASE_URL}/auth/persona", headers=headers)
    print(f"Updated settings: {resp.json()}")
    assert resp.json()["ai_name"] == "Jarvis"
    assert resp.json()["persona"] == new_settings["persona"]
    
    # 5. Test Chat (Chat Interact)
    # Note: Chat API calls LLM. Since we might not want to spend money or wait, verifying the settings update is the most critical part.
    # But the user asked to verify the effect.
    # We can use the 'prepare' endpoint which returns context, but it doesn't return the prompt.
    # The 'interact' endpoint returns 'debug_info' which contains 'prompt_preview'. This is perfect!
    
    print("\n[5] Testing Chat Prompt Injection...")
    interact_req = {
        "user_query": "Who are you?"
    }
    # Note: connect to /interact might invoke real LLM.
    # If the system is using a live LLM, this will cost tokens.
    # Let's see if we can just check the debug_info.
    try:
        resp = requests.post(f"{BASE_URL}/chat/{user_id}/interact", headers=headers, json=interact_req)
        if resp.status_code == 200:
            data = resp.json()
            debug_info = data.get("debug_info", {})
            prompt_preview = debug_info.get("prompt_preview", "")
            
            print("\n--- Prompt Preview ---")
            print(prompt_preview)
            print("----------------------")
            
            if "Jarvis" in prompt_preview and "sarcastic" in prompt_preview:
                print("\nSUCCESS: AI Name and Persona successfully injected into prompt!")
            else:
                print("\nFAILURE: AI Name or Persona NOT found in prompt.")
        else:
            print(f"Chat interaction failed: {resp.text}")
    except Exception as e:
        print(f"Chat interaction error: {e}")

if __name__ == "__main__":
    run_test()
