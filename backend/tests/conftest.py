"""
Test isolation: point the ledger + checkpointer at dedicated SHORT-path DBs
BEFORE any app module imports them. Keeps the real demo DBs untouched and the
Windows MAX_PATH fix intact.
"""

import os

os.environ["LEDGER_DB"] = r"C:\cg\test_ledger.db"
os.environ["ENGINE_CHECKPOINTS"] = r"C:\cg\test_engine_checkpoints.sqlite"
os.environ["AUDIT_DB"] = r"C:\cg\test_audit.db"
os.environ["CHAT_DB"] = r"C:\cg\test_chat.db"
