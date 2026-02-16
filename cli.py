import sqlite3
import zlib
import os
import json
import base64
import hashlib
from datetime import datetime

# Deep Sea: Agent-GitHub over Usenet
# v0.2.0 - Concept Archive Integration

DB_PATH = 'core/memory.db'
CREDS_FILE = '.usenet_creds'

class DeepSea:
    def __init__(self):
        self.creds = self._load_creds()
        
    def _load_creds(self):
        creds = {}
        if os.path.exists(CREDS_FILE):
            with open(CREDS_FILE, 'r') as f:
                for line in f:
                    if '=' in line:
                        k, v = line.strip().split('=', 1)
                        creds[k] = v
        return creds

    def create_commit(self, repo_path, message):
        """Package a directory into a Deep Sea commit packet."""
        files = {}
        for root, _, filenames in os.walk(repo_path):
            if '.git' in root or '__pycache__' in root: continue
            for filename in filenames:
                full_path = os.path.join(root, filename)
                rel_path = os.path.relpath(full_path, repo_path)
                with open(full_path, 'rb') as f:
                    content = f.read()
                    files[rel_path] = base64.b64encode(zlib.compress(content)).decode('utf-8')
        
        packet = {
            "v": "0.2.0",
            "type": "commit",
            "repo": os.path.basename(repo_path),
            "msg": message,
            "ts": datetime.now().isoformat(),
            "files": files
        }
        
        # Simple local signing placeholder (Identity link)
        packet_json = json.dumps(packet)
        sig = hashlib.sha256(packet_json.encode()).hexdigest()
        packet["sig"] = sig
        
        return packet

    def push(self, packet, group="alt.test"):
        """Push the packet to Usenet."""
        import json
        import sys
        import os
        import subprocess
        subject = f"[DEEPSEA] {packet['repo']} | {packet['msg']}"
        content = json.dumps(packet)
        
        # We need to load creds to call post_text if we import it
        sys.path.append('/root/.openclaw/workspace')
        try:
            import deep_sea_post
            # We must set the CREDS_FILE path for the imported module
            deep_sea_post.CREDS_FILE = '/root/.openclaw/workspace/.usenet_creds'
            success = deep_sea_post.post_text(subject, content, group)
            return success
        except Exception as e:
            return False

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python3 deep_sea.py <path_to_repo> <commit_message>")
        sys.exit(1)
        
    ds = DeepSea()
    repo = sys.argv[1]
    msg = sys.argv[2]
    
    print(f"🌊 Deep Sea: Packaging {repo}...")
    packet = ds.create_commit(repo, msg)
    print(f"📦 Packet created. Size: {len(json.dumps(packet))} bytes")
    
    if ds.push(packet):
        print("🚀 Commit pushed to the Deep Sea.")
    else:
        print("❌ Push failed.")
