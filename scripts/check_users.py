import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.chat_log_service import ChatLogService

def main():
    service = ChatLogService()
    users = service.get_all_user_ids()
    print(f"Users found in chat logs: {users}")

if __name__ == "__main__":
    main()
