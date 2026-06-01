"""
PlagIA 2 — Correction Serverless Function
Uses Groq (free) for text correction/humanization
"""
import json
import os
import asyncio
from http.server import BaseHTTPRequestHandler
import httpx


GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"


async def correct_with_groq(text: str, correction_type: str, source: str = "") -> dict:
    """Use Groq (Llama 3) for free text correction"""
    if not GROQ_API_KEY:
        return {
            "corrected": "",
            "error": "Groq API key not configured",
            "contact": {"email": "checkone076@gmail.com", "phone": "+237690895735"}
        }

    if correction_type == "plagiarism":
        prompt = f"""Reformule ce texte pour éviter le plagiat tout en gardant le même sens.
Le texte original est similaire à: "{source}"

Texte à reformuler:
{text}

Donne UNIQUEMENT le texte reformulé, sans explication."""
    else:
        prompt = f"""Humanise ce texte pour qu'il paraisse écrit par un humain (pas une IA).
Ajoute de la variation dans la longueur des phrases, des expressions naturelles, et un style plus personnel.

Texte à humaniser:
{text}

Donne UNIQUEMENT le texte humanisé, sans explication."""

    try:
        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "llama-3.3-70b-versatile",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.7,
            "max_tokens": 1024
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(GROQ_URL, headers=headers, json=payload)
            resp.raise_for_status()

        data = resp.json()
        corrected = data["choices"][0]["message"]["content"].strip()
        return {"corrected": corrected, "model": "llama-3.3-70b", "provider": "groq"}

    except Exception as e:
        return {"corrected": "", "error": str(e)}


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length)

        try:
            data = json.loads(body)
            text = data.get("text", "")
            correction_type = data.get("type", "ai")  # "plagiarism" or "ai"
            source = data.get("source", "")

            if not text:
                self.send_response(400)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Texte requis"}).encode())
                return

            result = asyncio.run(correct_with_groq(text, correction_type, source))

            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(result, ensure_ascii=False).encode())

        except Exception as e:
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
