import socket
import ssl
import json
import base64
import zlib
import sqlite3
import hashlib
import os
import time
from datetime import datetime

# Deep Sea Core Protocol v0.3.0
# "The ocean is deep, and the truth is preserved in the current."

class DeepSeaCore:
    def __init__(self, db_path=None):
        if db_path is None:
            # Use absolute path based on workspace root
            self.db_path = os.path.join('/root/.openclaw/workspace', 'core/deep_sea.db')
        else:
            self.db_path = db_path
        self.creds = self._load_creds()
        self._init_db()

    def _load_creds(self):
        creds = {}
        creds_path = os.path.join('/root/.openclaw/workspace', '.usenet_creds')
        if os.path.exists(creds_path):
            with open(creds_path, 'r') as f:
                for line in f:
                    if '=' in line:
                        k, v = line.strip().split('=', 1)
                        creds[k.strip()] = v.strip()
        return creds

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS commits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            msg_id TEXT UNIQUE,
            repo TEXT,
            author TEXT,
            timestamp TEXT,
            message TEXT,
            sig TEXT,
            packet BLOB
        )''')
        conn.commit()
        conn.close()

    def _nntp_command(self, sock, cmd, wait_for=None):
        sock.sendall((cmd + "\r\n").encode('utf-8'))
        resp = ""
        while True:
            chunk = sock.recv(4096).decode('utf-8', errors='ignore')
            resp += chunk
            if "\r\n" in resp:
                break
        return resp

    def fetch_recent(self, group="alt.test", limit=50):
        """Scan Usenet for Deep Sea packets."""
        if not self.creds: return []
        
        host = self.creds.get('NNTP_HOST')
        port = int(self.creds.get('NNTP_PORT', 563))
        user = self.creds.get('NNTP_USER')
        password = self.creds.get('NNTP_PASS')

        found = 0
        try:
            context = ssl.create_default_context()
            with socket.create_connection((host, port)) as raw_sock:
                with context.wrap_socket(raw_sock, server_hostname=host) as sock:
                    sock.recv(4096) # Welcome
                    self._nntp_command(sock, f"AUTHINFO USER {user}")
                    self._nntp_command(sock, f"AUTHINFO PASS {password}")
                    
                    resp = self._nntp_command(sock, f"GROUP {group}")
                    # Resp looks like: 211 42 1 42 alt.test
                    parts = resp.split()
                    if len(parts) < 4: return []
                    
                    last_article = int(parts[3])
                    first_article = max(int(parts[2]), last_article - limit)
                    
                    print(f"🌊 Scanning {group} (Articles {first_article} to {last_article})...")
                    
                    for i in range(last_article, first_article, -1):
                        article_resp = self._nntp_command(sock, f"ARTICLE {i}")
                        if not article_resp.startswith("220"): continue
                        
                        # Read body until "."
                        body = article_resp
                        while not body.strip().endswith("\r\n."):
                            body += sock.recv(8192).decode('utf-8', errors='ignore')
                        
                        if "[DEEPSEA]" in body:
                            self._process_packet(body, f"usenet:{group}:{i}")
                            found += 1
        except Exception as e:
            print(f"Error fetching: {e}")
            
        return found

    def _process_packet(self, raw_body, msg_id):
        try:
            # Extract JSON from body (very simple parser)
            start = raw_body.find('{')
            end = raw_body.rfind('}') + 1
            if start == -1 or end == 0: return
            
            packet = json.loads(raw_body[start:end])
            if packet.get('v') != "0.2.0": return
            
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            c.execute("INSERT OR IGNORE INTO commits (msg_id, repo, author, timestamp, message, sig, packet) VALUES (?, ?, ?, ?, ?, ?, ?)",
                      (msg_id, packet['repo'], packet.get('author', 'Unknown'), packet['ts'], packet['msg'], packet['sig'], zlib.compress(json.dumps(packet).encode())))
            conn.commit()
            conn.close()
        except Exception as e:
            pass

    def get_commits(self, repo=None):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        if repo:
            c.execute("SELECT repo, author, timestamp, message, sig FROM commits WHERE repo=? ORDER BY timestamp DESC", (repo,))
        else:
            c.execute("SELECT repo, author, timestamp, message, sig FROM commits ORDER BY timestamp DESC")
        rows = c.fetchall()
        conn.close()
        return [{"repo": r, "author": a, "ts": t, "msg": m, "sig": s} for r, a, t, m, s in rows]

if __name__ == "__main__":
    core = DeepSeaCore()
    print("Refreshing Deep Sea index...")
    n = core.fetch_recent()
    print(f"Done. Found {n} new commits.")
