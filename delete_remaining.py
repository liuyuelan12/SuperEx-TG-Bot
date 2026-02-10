import os

# List of invalid sessions that failed to delete
invalid_sessions = [
    r"sessions\SuperExCN\+19017495411.session",
    r"sessions\SuperExCN\+19257942802.session"
]

for session_path in invalid_sessions:
    if os.path.exists(session_path):
        try:
            os.remove(session_path)
            print(f"Deleted: {session_path}")
        except Exception as e:
            print(f"Error deleting {session_path}: {e}")
    else:
        print(f"Not found: {session_path}")
