import os
import asyncio
from telethon import TelegramClient, errors
import config
import glob

async def check_and_clean(folder_name):
    session_dir = os.path.join(config.SESSIONS_DIR, folder_name)
    if not os.path.exists(session_dir):
        print(f"Directory not found: {session_dir}")
        return

    session_files = glob.glob(os.path.join(session_dir, "*.session"))
    print(f"Checking {len(session_files)} sessions in {folder_name}...")

    for session_path in session_files:
        phone = os.path.basename(session_path).replace('.session', '')
        
        # Use a random proxy
        proxy = config.PROXY_LIST[0] 
        proxy_dict = {
            'proxy_type': proxy[0],
            'addr': proxy[1],
            'port': proxy[2],
            'rdns': proxy[3],
            'username': proxy[4],
            'password': proxy[5]
        }

        client = TelegramClient(session_path, config.API_ID, config.API_HASH, proxy=proxy_dict)
        
        try:
            await client.connect()
            if not await client.is_user_authorized():
                print(f"[INVALID] {phone} - Not authorized. Deleting...")
                await client.disconnect()
                os.remove(session_path)
                continue
            
            # Optional: Check if we can actually fetch something (to catch Revoked/Duplicated keys)
            # await client.get_me() 
            
            print(f"[VALID] {phone}")
            await client.disconnect()

        except (errors.AuthKeyDuplicatedError, errors.UserDeactivatedError, errors.SessionRevokedError) as e:
            print(f"[INVALID] {phone} - {type(e).__name__}. Deleting...")
            await client.disconnect()
            try:
                os.remove(session_path)
            except Exception as del_err:
                print(f"Failed to delete {session_path}: {del_err}")
        except Exception as e:
            print(f"[ERROR] {phone} - {e}")
            await client.disconnect()

async def main():
    print("Starting cleanup...")
    await check_and_clean("SuperExCN")
    await check_and_clean("SuperExGlobal")
    print("Cleanup finished.")

if __name__ == "__main__":
    asyncio.run(main())
