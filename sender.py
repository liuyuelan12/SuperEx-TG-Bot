import os
import pandas as pd
from telethon import TelegramClient
import asyncio
import random
from telethon.tl.types import ReactionEmoji
from telethon.tl.functions.messages import SendReactionRequest
from telethon.tl.functions.channels import JoinChannelRequest
import argparse
import sys
import csv
import json
import config

# Force UTF-8 encoding for Windows console
if sys.platform.startswith('win'):
    sys.stdout.reconfigure(encoding='utf-8')

# Configuration Constants
DEFAULT_MIN_INTERVAL = 5
DEFAULT_MAX_INTERVAL = 120

def parse_args():
    parser = argparse.ArgumentParser(description='Telegram message sender')
    parser.add_argument('--groups', nargs='+', help='Specify group names (keys in config) to run')
    parser.add_argument('--loop', action='store_true', help='Enable continuous message sending mode')
    parser.add_argument('--max-messages', type=int, help='Limit number of messages to send per group')
    parser.add_argument('--prefer-media', action='store_true', help='Prioritize media messages')
    return parser.parse_args()

def load_group_config():
    """Load config and normalize to a dictionary keyed by Session Folder or custom ID"""
    try:
        with open(config.GROUP_CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        # Convert list to dict if it's a list. 
        # Dict key will be 'session_folder' for identification if not specified
        if isinstance(data, list):
            new_config = {}
            for item in data:
                # Use session_folder as key if available, else something unique
                key = item.get('session_folder', 'default')
                new_config[key] = item
            return new_config
        return data
    except Exception as e:
        print(f"Error loading config: {e}")
        return {}

def get_message_text(message_data):
    """Safe extraction of message text content"""
    # Normalized search for various possible header names for 'content'
    lower_map = {str(k).strip().lower(): v for k, v in message_data.items()}
    for k in ('content', 'message_content', 'text', 'message'):
        v = lower_map.get(k)
        if v is not None and not pd.isna(v) and str(v).strip() != '':
            return str(v)
    return None

def get_message_type(message_data):
    """Determine message type (text, photo, video, etc.)"""
    lower_map = {str(k).strip().lower(): v for k, v in message_data.items()}
    for k in ('type', 'message_type', 'msg_type'):
        v = lower_map.get(k)
        if v is not None and not pd.isna(v) and str(v).lower() != 'nan':
            return str(v).lower()
    return 'text'

def get_message_meta(message_data, key_name):
    """Helper to get columns like media_file, id, etc."""
    lower_map = {str(k).strip().lower(): v for k, v in message_data.items()}
    return lower_map.get(str(key_name).strip().lower())

def get_session_files(session_folder):
    """Find .session files in the specified subdirectory under SESSIONS_DIR"""
    target_dir = os.path.join(config.SESSIONS_DIR, session_folder)
    if not os.path.isdir(target_dir):
        print(f"Warning: Session directory {target_dir} not found.")
        return []
    return [os.path.join(target_dir, f) for f in os.listdir(target_dir) if f.endswith('.session')]

async def try_connect(session_path, proxy_config):
    """Connect to Telegram using a specific proxy"""
    client = TelegramClient(
        session_path,
        config.API_ID,
        config.API_HASH,
        proxy=proxy_config,
        connection_retries=None,
        retry_delay=1
    )
    try:
        # print(f"Connecting with proxy {proxy_config[1]}...") 
        await client.connect()
        if await client.is_user_authorized():
            return client
        await client.disconnect()
        return None
    except Exception:
        try:
            await client.disconnect()
        except:
            pass
        return None

async def init_clients_for_group(session_folder, group_link):
    """Initialize all valid sessions for a group and ensure they have joined"""
    session_files = get_session_files(session_folder)
    clients = []
    
    print(f"[{session_folder}] Found {len(session_files)} session files. Initializing...")
    
    for session_file in session_files:
        client = None
        # Try proxies until one works
        # Shuffle proxies to distribute load? Or keep order. config.PROXY_LIST is usually short.
        # Let's just try sequentially or random. Random is better for avoiding same proxy spam if list is long.
        proxies = list(config.PROXY_LIST)
        # random.shuffle(proxies) # User requested fixed order: try first, then second.
        
        for proxy in proxies:
            client = await try_connect(session_file, proxy)
            if client:
                break
        
        if client:
            # Check/Join Group
            try:
                entity = await client.get_entity(group_link)
                # Just getting entity often works if already joined. 
                # explicit Join check is expensive, maybe just try JoinChannelRequest catch error?
                # But 'get_entity' works for public groups even if not joined.
                # Let's try to join to be safe.
                try:
                    await client(JoinChannelRequest(entity))
                except Exception as e:
                    if "already participant" not in str(e).lower():
                        pass # Ignore if already inside or other minor errors
            except Exception as e:
                print(f"[{session_folder}] Error joining group {group_link}: {e}")
                
            clients.append(client)
        else:
            print(f"[{session_folder}] Failed to connect session: {os.path.basename(session_file)}")

    return clients

async def send_message_safe(client, entity, message_data, reply_to=None, media_base_dir=None):
    """Send a message (text or media) handling errors"""
    
    # Get user info for logging
    try:
        me = await client.get_me()
        user_info = f"{me.first_name} (@{me.username} ID:{me.id})"
    except:
        user_info = "Unknown User"

    msg_type = get_message_type(message_data)
    kwargs = {}
    if reply_to:
        kwargs['reply_to'] = reply_to
        
    try:
        if msg_type == 'text':
            text = get_message_text(message_data)
            if text:
                await client.send_message(entity, text, **kwargs)
                return True
                
        elif msg_type in ['photo', 'video', 'file']:
            media_path_raw = get_message_meta(message_data, 'media_file')
            text = get_message_text(message_data) # Caption
            
            # Fix: Handle NaN/Float from pandas
            if pd.isna(media_path_raw):
                media_path_raw = None
            else:
                media_path_raw = str(media_path_raw).strip()
                if not media_path_raw: 
                    media_path_raw = None

            # Fallback: if media_file col is empty, try using 'content' column
            if not media_path_raw and text and ('/' in text or '.' in text): 
                 # Heuristic: if content looks like a path, use it.
                 media_path_raw = text
                 # Since we used text as the path, we shouldn't use it as caption anymore
                 text = None
            
            if not media_path_raw:
                print(f"[{user_info}] Warning: Media message missing path. Row data: {message_data}")
                return False

            # Avoid sending the path as a caption if they are identical
            if text and media_path_raw and text.strip() == media_path_raw.strip():
                text = None
                
            # Resolve Media Path
            if os.path.isabs(media_path_raw):
                full_path = media_path_raw
            else:
                clean_path = media_path_raw.lstrip('/\\')
                potential_paths = []
                if media_base_dir:
                    potential_paths.append(os.path.join(media_base_dir, clean_path))
                potential_paths.append(os.path.join(config.BASE_DIR, clean_path))
                
                full_path = None
                for p in potential_paths:
                    if os.path.exists(p):
                        full_path = p
                        break
            
            if not full_path or not os.path.exists(full_path):
                print(f"[{user_info}] Error: Media file not found: {media_path_raw}")
                return False
                
            await client.send_file(entity, full_path, caption=text, **kwargs)
            return True
            
    except Exception as e:
        print(f"[{user_info}] Send failed: {e}")
        # If it's a connection error, try to disconnect so we reconnect next time
        try:
            await client.disconnect()
        except:
            pass
        return False
        
    return False

async def worker(group_key, config_item, args):
    """Worker task for a single group configuration"""
    group_link = config_item['group_link']
    topic_id = config_item.get('topic_id')
    session_folder = config_item['session_folder']
    csv_file = config_item['csv_file']
    media_base_dir = config_item.get('media_base_dir')
    
    # Interval configuration
    min_interval = config_item.get('min_interval', DEFAULT_MIN_INTERVAL)
    max_interval = config_item.get('max_interval', DEFAULT_MAX_INTERVAL)
    
    # Resolve absolute paths
    if not os.path.isabs(csv_file):
        csv_file = os.path.join(config.BASE_DIR, csv_file)
    if media_base_dir and not os.path.isabs(media_base_dir):
        # Join with BASE_DIR or CSV dir? Usually BASE_DIR relative.
        media_base_dir = os.path.join(config.BASE_DIR, media_base_dir)
        
    print(f"[{group_key}] Starting worker for {group_link} (Topic: {topic_id})")
    
    # Load Messages
    try:
        df = pd.read_csv(csv_file)
        messages = df.to_dict('records')
    except Exception as e:
        print(f"[{group_key}] Failed to load CSV {csv_file}: {e}")
        return

    # Filter messages if needed
    if args.max_messages:
        messages = messages[:args.max_messages]

    # Initialize Clients
    raw_clients = await init_clients_for_group(session_folder, group_link)
    if not raw_clients:
        print(f"[{group_key}] No active clients. Aborting.")
        return
    
    # Cache user info
    clients = [] # List of (client, me)
    for c in raw_clients:
        try:
            me = await c.get_me()
            clients.append((c, me))
        except Exception as e:
            print(f"[{group_key}] Error getting info for a client: {e}. Skipping.")
    
    if not clients:
        print(f"[{group_key}] No healthy clients after check. Aborting.")
        return

    print(f"[{group_key}] Active clients: {len(clients)}")

    # Force stdout to utf-8 for Windows console
    sys.stdout.reconfigure(encoding='utf-8')
    
    # Loop configuration
    should_loop = args.loop or config_item.get('loop', False)

    # Main Loop
    while True:
        # Round-robin messages? Or random?
        # Requirement implies "Repeating" content usually, but logic in previous sender was sequential.
        # Let's stick to simple sequential iteration through CSV rows.
        
        for i, msg_data in enumerate(messages):
            # Select client
            client, me = random.choice(clients)
            
            # Fetch recent to decide interaction (random reply etc) - Optional Feature from previous sender?
            # User requirement just says "send messages". Simplification: Just send.
            # But previous sender had complex logic (reply rate etc). Keeping it simple first unless requested.
            # "Sender script... send messages".
            # Let's assume direct send to topic/group.
            
            reply_target = topic_id # Default reply to topic ID (Thread)
            
            # If we want to reply to recent messages (simulating convo), we need to fetch history.
            # Let's keep it robust: Send to Topic.
            
            # me = await client.get_me() # Cached
            # print(f"[{group_key}] Sending msg {i} via {me.first_name}...")
            
            # Ensure client is connected
            if not client.is_connected():
                # print(f"[{group_key}] Reconnecting client for {me.first_name}...")
                try:
                    await client.connect()
                except Exception as e:
                    print(f"[{group_key}] Failed to reconnect {me.first_name}: {e}")
                    continue

            success = await send_message_safe(client, group_link, msg_data, reply_to=reply_target, media_base_dir=media_base_dir)
            
            if success:
                # Interval
                wait = random.uniform(min_interval, max_interval)
                print(f"[{group_key}] Sent msg {i}. Waiting {wait:.1f}s...")
                
                # If wait time is long, disconnect to save resources and avoid timeouts
                # Telegram/Proxies often kill idle connections stats > 30s
                if wait > 30:
                    try:
                        await client.disconnect()
                    except:
                        pass
                
                await asyncio.sleep(wait)
            else:
                print(f"[{group_key}] Failed to send msg {i}. Skipping delay.")
                # If failed, it might be a connection issue. Ensure disconnect so we reconnect next time.
                try:
                    await client.disconnect()
                except:
                    pass
                
        if not should_loop:
            break
        print(f"[{group_key}] Cycle finished. Restarting...")
        await asyncio.sleep(5)

    # Cleanup
    for c, _ in clients: # clients is list of tuples (client, me)
        await c.disconnect()

async def main():
    args = parse_args()
    group_config = load_group_config()
    
    if not group_config:
        print("No group config found or valid.")
        return

    tasks = []
    
    # keys are 'session_folder' names based on my load_group_config logic
    target_keys = args.groups if args.groups else group_config.keys()
    
    for key in target_keys:
        if key in group_config:
            tasks.append(worker(key, group_config[key], args))
        else:
            print(f"Config for '{key}' not found.")
            
    if tasks:
        await asyncio.gather(*tasks)
    else:
        print("Nothing to run.")

if __name__ == "__main__":
    asyncio.run(main())