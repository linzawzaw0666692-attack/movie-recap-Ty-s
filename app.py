import base64
import re
import asyncio
import edge_tts
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

app = FastAPI()

# ============ CORS Configuration ============
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=3600,
)

VOICE_MAP = {
    "thiha": "my-MM-ThihaNeural",
    "nilar": "my-MM-NilarNeural"
}
RATE = "+30%"


class TTSRequest(BaseModel):
    text: str
    voice: str = "thiha"


def srt_time(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds % 1) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


async def synth_line(text: str, voice: str) -> bytes:
    communicate = edge_tts.Communicate(text, voice, rate=RATE)
    audio = b""
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio += chunk["data"]
    return audio


@app.get("/")
def root():
    return {"status": "ok", "message": "Edge TTS API is running"}


# ============ OPTIONS Handler (CORS Preflight) ============
@app.options("/tts")
async def tts_options():
    return {"ok": True}


@app.post("/tts")
async def tts(req: TTSRequest):
    text = req.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="စာသား ထည့်ပါ")

    voice_name = VOICE_MAP.get(req.voice, VOICE_MAP["thiha"])

    lines = [l.strip() for l in re.split(r'(?<=[။!?\n])', text) if l.strip()]
    if not lines:
        raise HTTPException(status_code=400, detail="စာကြောင်း မရှိပါ")

    audio_all = b""
    segments = []
    current = 0.0

    for line in lines:
        audio = await synth_line(line, voice_name)
        audio_all += audio

        char_count = len(line.replace(" ", ""))
        duration = max(char_count / 6.5, 1.2)

        segments.append({
            "start": current,
            "end": current + duration,
            "text": line
        })
        current += duration

    srt = ""
    for i, seg in enumerate(segments, 1):
        srt += f"{i}\n{srt_time(seg['start'])} --> {srt_time(seg['end'])}\n{seg['text']}\n\n"

    return JSONResponse({
        "audio": base64.b64encode(audio_all).decode(),
        "srt": srt,
        "duration": current
    })
