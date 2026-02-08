import os
import asyncio
import sys
import argparse
from telethon import TelegramClient, errors
import config
import random

# Phone Numbers List
PHONE_NUMBERS = [
    '+19092884592',
    '+18624223419',
    '+19017495411',
    '+18628013319',
    '+19097071406'
]

async def try_connect_with_proxy(phone_number, proxy_config, session_dir):
    """Attempt to connect and generate session file"""
    try:
        # Create session path
        phone_clean = phone_number.replace(' ', '')
        session_path = os.path.join(session_dir, phone_clean)
        
        print(f"\nProcessing {phone_number}...")
        print(f"Session path: {session_path}.session")
        
        # Create proxy dict for Telethon
        # config.PROXY_LIST elements are tuples: (type, addr, port, rdns, user, pass)
        # We need to map them correctly.
        # config.PROXY_LIST example: ("socks5", "50.3.54.17", 443, True, "VYHMOLXmzmCy", "X9FgH374SH")
        
        p = proxy_config
        proxy = {
            'proxy_type': p[0],
            'addr': p[1],
            'port': p[2],
            'rdns': p[3],
            'username': p[4],
            'password': p[5]
        }
        
        print(f"Using proxy: {proxy['addr']}:{proxy['port']}")

        client = TelegramClient(
            session_path,
            config.API_ID,
            config.API_HASH,
            proxy=proxy
        )
        
        await client.connect()
        
        if not await client.is_user_authorized():
            print(f"Requesting login code for {phone_number}...")
            try:
                await client.send_code_request(phone_number)
            except errors.PhoneNumberBannedError:
                print(f"[ERROR] Phone number {phone_number} is banned!")
                return False
            except Exception as e:
                print(f"[ERROR] Failed to send code: {e}")
                return False

            code = input(f"Enter code for {phone_number}: ")
            
            try:
                await client.sign_in(phone_number, code)
            except errors.SessionPasswordNeededError:
                pw = input("Two-step verification enabled. Enter password: ")
                await client.sign_in(password=pw)
            except Exception as e:
                print(f"[ERROR] Failed to sign in: {e}")
                return False
        
        print(f"[SUCCESS] Session created for {phone_number}!")
        await client.disconnect()
        return True

    except Exception as e:
        print(f"[ERROR] Unexpected error for {phone_number}: {e}")
        return False

async def main():
    parser = argparse.ArgumentParser(description='Generate Telegram Sessions')
    # Use parse_known_args to handle arbitrary flags (like -SuperExGlobal) without defining them upfront
    # This allows us to capture whatever flag the user passes
    _, unknown = parser.parse_known_args()
    
    folder_name = None
    if unknown:
        # Take the first unknown argument that starts with -
        for arg in unknown:
            if arg.startswith('-'):
                folder_name = arg.lstrip('-')
                break
    
    if not folder_name:
        print("Error: Please provide a target folder flag (e.g. -SuperExGlobal)")
        return

    # Create target directory
    target_dir = os.path.join(config.SESSIONS_DIR, folder_name)
    os.makedirs(target_dir, exist_ok=True)
    print(f"Files will be saved to: {target_dir}")
    
    # Process numbers
    for phone in PHONE_NUMBERS:
        # Pick a random proxy for each connection attempt
        if not config.PROXY_LIST:
            print("Error: No proxies found in config.PROXY_LIST")
            return
            
        proxy = random.choice(config.PROXY_LIST)
        
        await try_connect_with_proxy(phone, proxy, target_dir)
        
    print("\nAll Done.")

if __name__ == "__main__":
    asyncio.run(main())
