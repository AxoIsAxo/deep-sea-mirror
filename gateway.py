import json
import os
import hashlib
import time
import hmac
import zlib
import base64
import sqlite3
from datetime import datetime
try:
    from deep_sea.cli import DeepSea
except ImportError:
    from cli import DeepSea

# Deep Sea Gateway v0.4.0
# The bridges between HTTP/API and the Decentralized Ocean

GATEWAY_DB = 'core/gateway.db'

class DeepSeaGateway:
    def __init__(self):
        self._init_db()
        self.ds = DeepSea()

    def _init_db(self):
        conn = sqlite3.connect(GATEWAY_DB)
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS api_keys (
            key_id TEXT PRIMARY KEY,
            secret TEXT,
            owner TEXT,
            quota_bytes INTEGER,
            used_bytes INTEGER,
            status TEXT DEFAULT 'active'
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS usage_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key_id TEXT,
            timestamp REAL,
            action TEXT,
            bytes_transferred INTEGER
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS repo_ownership (
            key_id TEXT,
            repo_name TEXT,
            PRIMARY KEY (key_id, repo_name)
        )''')
        conn.commit()
        conn.close()

    def create_api_key(self, owner, quota=1024*1024*100): # 100MB default
        key_id = "ds_key_" + hashlib.sha256(os.urandom(16)).hexdigest()[:12]
        secret = base64.b64encode(os.urandom(24)).decode('utf-8')
        
        conn = sqlite3.connect(GATEWAY_DB)
        c = conn.cursor()
        c.execute("INSERT INTO api_keys (key_id, secret, owner, quota_bytes, used_bytes) VALUES (?, ?, ?, ?, ?)",
                  (key_id, secret, owner, quota, 0))
        conn.commit()
        conn.close()
        return key_id, secret

    def authenticate(self, key_id, signature, payload):
        """HMAC-SHA256 Auth for the Gateway."""
        conn = sqlite3.connect(GATEWAY_DB)
        c = conn.cursor()
        c.execute("SELECT secret, status, quota_bytes, used_bytes FROM api_keys WHERE key_id=?", (key_id,))
        res = c.fetchone()
        conn.close()
        
        if not res or res[1] != 'active':
            return False, "Invalid or inactive key"
        
        secret, _, quota, used = res
        
        # Verify HMAC
        expected_sig = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected_sig, signature):
            return False, "Signature mismatch"
            
        if used >= quota:
            return False, "Quota exceeded"
            
        return True, None

    def proxy_push(self, key_id, packet, group="alt.test"):
        """Verify, Log, and Push a signed packet to Usenet."""
        repo_name = packet.get('repo')
        
        # 1. Log Usage and Ownership
        packet_size = len(json.dumps(packet))
        conn = sqlite3.connect(GATEWAY_DB)
        c = conn.cursor()
        c.execute("UPDATE api_keys SET used_bytes = used_bytes + ? WHERE key_id = ?", (packet_size, key_id))
        c.execute("INSERT INTO usage_logs (key_id, timestamp, action, bytes_transferred) VALUES (?, ?, ?, ?)",
                  (key_id, time.time(), "PUSH", packet_size))
        c.execute("INSERT OR IGNORE INTO repo_ownership (key_id, repo_name) VALUES (?, ?)", (key_id, repo_name))
        conn.commit()
        conn.close()

        # 2. Broadcast to Ocean
        return self.ds.push(packet, group)

    def get_client_repos(self, key_id):
        """Return repos owned by this key."""
        conn = sqlite3.connect(GATEWAY_DB)
        c = conn.cursor()
        c.execute("SELECT repo_name FROM repo_ownership WHERE key_id = ?", (key_id,))
        repos = [row[0] for row in c.fetchall()]
        conn.close()
        return repos

    def delete_repo(self, key_id, repo_name):
        """Remove repo from gateway index (Cannot delete from Usenet)."""
        conn = sqlite3.connect(GATEWAY_DB)
        c = conn.cursor()
        c.execute("DELETE FROM repo_ownership WHERE key_id = ? AND repo_name = ?", (key_id, repo_name))
        success = c.rowcount > 0
        conn.commit()
        conn.close()
        return success

    def rename_repo(self, key_id, old_name, new_name):
        """Rename repo in gateway index."""
        conn = sqlite3.connect(GATEWAY_DB)
        c = conn.cursor()
        # Check if new name already exists for this user
        c.execute("SELECT 1 FROM repo_ownership WHERE key_id = ? AND repo_name = ?", (key_id, new_name))
        if c.fetchone():
            conn.close()
            return False, "New name already in use"
            
        c.execute("UPDATE repo_ownership SET repo_name = ? WHERE key_id = ? AND repo_name = ?", (new_name, key_id, old_name))
        success = c.rowcount > 0
        conn.commit()
        conn.close()
        return success, None

if __name__ == "__main__":
    gw = DeepSeaGateway()
    # Test key generation
    kid, sec = gw.create_api_key("Axo_Primary")
    print(f"Gateway Ready. Test Key: {kid}")
    print(f"Secret: {sec}")
