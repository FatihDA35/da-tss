from __future__ import annotations

import tempfile
from pathlib import Path
from threading import Lock

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from starlette.background import BackgroundTask

from ema_lightning import EMA

app = FastAPI(title="DA TTS", docs_url=None, redoc_url=None)
_model: EMA | None = None
_model_lock = Lock()


INDEX_HTML = """<!doctype html>
<html lang="tr">
<head>
  <meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
  <title>DA TTS · EMA Lightning</title>
  <style>
    :root { color-scheme: dark; font-family: Inter, ui-sans-serif, system-ui, sans-serif; background:#101216; color:#f3f4f6; }
    * { box-sizing:border-box } body { margin:0; min-height:100vh; display:grid; place-items:center; padding:24px; }
    main { width:min(720px,100%); background:#191c22; border:1px solid #2b3039; border-radius:20px; padding:clamp(22px,5vw,42px); box-shadow:0 24px 80px #0005; }
    .eyebrow { color:#a6e36f; font-size:12px; font-weight:700; letter-spacing:.14em; text-transform:uppercase }
    h1 { margin:10px 0 8px; font-size:clamp(30px,6vw,44px); letter-spacing:-.04em }
    p { color:#a8adb8; line-height:1.55; margin:0 0 26px }
    label { display:block; font-size:14px; font-weight:650; margin:20px 0 9px }
    textarea { width:100%; min-height:210px; resize:vertical; border:1px solid #373d48; border-radius:12px; background:#111318; color:#f3f4f6; padding:14px; font:inherit; line-height:1.5; outline:none }
    textarea:focus,input:focus { border-color:#a6e36f }
    .row { display:flex; align-items:center; gap:14px; flex-wrap:wrap }
    input[type=file] { color:#bfc4ce; max-width:100%; font:inherit }
    .speed { display:flex; gap:12px; align-items:center; margin:22px 0 }
    input[type=range] { accent-color:#a6e36f; flex:1 }
    button { border:0; border-radius:11px; padding:13px 19px; background:#a6e36f; color:#17200f; font:700 15px inherit; cursor:pointer }
    button:disabled { opacity:.55; cursor:wait }
    .status { min-height:24px; margin:16px 0 0; font-size:14px; color:#a8adb8 }
    audio { width:100%; margin-top:18px; display:none }
    .hint { font-size:12px; color:#777e8b; margin-top:18px }
  </style>
</head>
<body><main>
  <div class="eyebrow">DA TTS · EMA Lightning</div>
  <h1>Türkçe metni sese çevir</h1>
  <p>Metni yaz veya UTF-8 kodlamalı bir .txt dosyası seç. Oluşan WAV dosyasını dinleyebilir ve indirebilirsin.</p>
  <form id="form">
    <label for="text">Metin</label>
    <textarea id="text" name="text" maxlength="30000" placeholder="Seslendirilecek metni buraya yaz…"></textarea>
    <label for="file">.txt dosyası (isteğe bağlı)</label>
    <input id="file" name="file" type="file" accept=".txt,text/plain">
    <div class="speed"><label for="speed" style="margin:0">Konuşma hızı</label><input id="speed" name="speed" type="range" min="0.5" max="2" step="0.05" value="1"><output id="speed-value">1.00×</output></div>
    <button id="submit" type="submit">WAV oluştur</button>
    <div id="status" class="status" role="status" aria-live="polite"></div>
    <audio id="audio" controls></audio>
  </form>
  <div class="hint">İlk istekte model Hugging Face üzerinden indirilir; sonraki başlangıçlarda cache kullanılır.</div>
</main>
<script>
const form=document.querySelector('#form'), text=document.querySelector('#text'), file=document.querySelector('#file');
const speed=document.querySelector('#speed'), speedValue=document.querySelector('#speed-value'), status=document.querySelector('#status');
const button=document.querySelector('#submit'), audio=document.querySelector('#audio');
speed.addEventListener('input',()=>speedValue.value=Number(speed.value).toFixed(2)+'×');
form.addEventListener('submit',async e=>{
  e.preventDefault(); status.textContent='Ses hazırlanıyor. İlk çalıştırmada model indiriliyor olabilir…'; button.disabled=true; audio.style.display='none';
  try {
    const data=new FormData(); data.set('text',text.value); data.set('speed',speed.value); if(file.files[0]) data.set('file',file.files[0]);
    const response=await fetch('/generate',{method:'POST',body:data});
    if(!response.ok){const error=await response.json().catch(()=>({detail:'İstek başarısız.'})); throw new Error(error.detail||'İstek başarısız.');}
    const blob=await response.blob(), url=URL.createObjectURL(blob), link=document.createElement('a');
    link.href=url; link.download='ema-ses.wav'; link.click(); audio.src=url; audio.style.display='block'; status.textContent='WAV hazır. İndirme başladı.';
  } catch(error){status.textContent=error.message;} finally{button.disabled=false;}
});
</script></body></html>"""


def get_model() -> EMA:
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:
                _model = EMA()
    return _model


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return INDEX_HTML


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/generate")
def generate(
    text: str = Form(""),
    speed: float = Form(1.0),
    file: UploadFile | None = File(None),
) -> FileResponse:
    if not 0.25 <= speed <= 4:
        raise HTTPException(status_code=422, detail="Hız 0.25 ile 4 arasında olmalı.")
    if file is not None and file.filename:
        if Path(file.filename).suffix.lower() != ".txt":
            raise HTTPException(status_code=400, detail="Yalnızca .txt dosyası yükleyebilirsin.")
        raw = file.file.read(1_000_001)
        if len(raw) > 1_000_000:
            raise HTTPException(status_code=413, detail="Metin dosyası en fazla 1 MB olabilir.")
        try:
            text = raw.decode("utf-8").strip()
        except UnicodeDecodeError as error:
            raise HTTPException(status_code=400, detail="Dosya UTF-8 kodlamalı olmalı.") from error
    text = text.strip()
    if not text:
        raise HTTPException(status_code=422, detail="Seslendirilecek metin boş olamaz.")
    if len(text) > 30_000:
        raise HTTPException(status_code=413, detail="Metin en fazla 30.000 karakter olabilir.")

    output_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as output:
            output_path = Path(output.name)
        get_model().say(text, speed=speed, path=str(output_path))
        return FileResponse(
            output_path,
            media_type="audio/wav",
            filename="ema-ses.wav",
            background=BackgroundTask(output_path.unlink, missing_ok=True),
        )
    except HTTPException:
        if output_path:
            output_path.unlink(missing_ok=True)
        raise
    except Exception as error:
        if output_path:
            output_path.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=f"Ses üretimi başarısız: {error}") from error
