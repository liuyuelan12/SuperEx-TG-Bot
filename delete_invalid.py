import os

# List of invalid sessions detected by test_sessions.py
invalid_sessions = [
    r"sessions\SuperExCN\+15096720786.session",
    r"sessions\SuperExCN\+15096950880.session",
    r"sessions\SuperExCN\+18628013319.session",
    r"sessions\SuperExCN\+19017495411.session",
    r"sessions\SuperExCN\+19092884592.session",
    r"sessions\SuperExCN\+19257942802.session",
    r"sessions\SuperExCN\+19283948090.session"
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
