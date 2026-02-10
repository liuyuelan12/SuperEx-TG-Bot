import os

# Updated list of invalid sessions detected by test_sessions.py for SuperExGlobal
invalid_sessions = [
    r"sessions\SuperExGlobal\+18049424725.session",
    r"sessions\SuperExGlobal\+18177557854.session",
    r"sessions\SuperExGlobal\+18285968568.session",
    r"sessions\SuperExGlobal\+18324810966.session",
    r"sessions\SuperExGlobal\+18565250604.session",
    r"sessions\SuperExGlobal\+5521973750470.session",
    r"sessions\SuperExGlobal\+5588933006436.session",
    r"sessions\SuperExGlobal\+5591985380212.session"
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
