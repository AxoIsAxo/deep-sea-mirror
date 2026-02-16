#!/usr/bin/env python3
import sys
import os
import socket
import ssl
import base64
from datetime import datetime

# Load credentials
CREDS_FILE = ".usenet_creds"

def load_creds():
    creds = {}
    if not os.path.exists(CREDS_FILE):
        return None
    with open(CREDS_FILE, "r") as f:
        for line in f:
            if "=" in line:
                k, v = line.strip().split("=", 1)
                creds[k] = v
    return creds

def post_text(subject, text, group="alt.test"):
    creds = load_creds()
    if not creds:
        print("Error: No credentials found.")
        return False

    host = creds['NNTP_HOST']
    port = int(creds['NNTP_PORT'])
    user = creds['NNTP_USER']
    password = creds['NNTP_PASS']

    print(f"Connecting to {host}:{port} via SSL...")
    try:
        context = ssl.create_default_context()
        with socket.create_connection((host, port)) as sock:
            with context.wrap_socket(sock, server_hostname=host) as ssock:
                def send(cmd):
                    ssock.sendall((cmd + "\r\n").encode('utf-8'))
                    resp = ssock.recv(4096).decode('utf-8')
                    return resp

                # Read initial welcome
                print(ssock.recv(4096).decode('utf-8').strip())

                # Auth
                send(f"AUTHINFO USER {user}")
                print(send(f"AUTHINFO PASS {password}").strip())

                # Post
                print(send("POST").strip())
                
                # Content
                ssock.sendall(f"From: Muddr <muddr@agent.local>\r\n".encode('utf-8'))
                ssock.sendall(f"Subject: {subject}\r\n".encode('utf-8'))
                ssock.sendall(f"Newsgroups: {group}\r\n".encode('utf-8'))
                ssock.sendall(f"Content-Type: text/plain; charset=utf-8\r\n\r\n".encode('utf-8'))
                ssock.sendall(f"{text}\r\n.\r\n".encode('utf-8'))
                
                print(ssock.recv(4096).decode('utf-8').strip())
                
                send("QUIT")
        
        print("✅ Post successful!")
        return True
    except Exception as e:
        print(f"❌ Failed: {e}")
        return False

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: ./deep_sea_post.py 'Subject' 'Message'")
        sys.exit(1)
    
    post_text(sys.argv[1], sys.argv[2])
