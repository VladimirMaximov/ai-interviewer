# Backend: local speech recognition

The default speech-to-text provider is local `whisper.cpp` with the multilingual `small` model.
Candidate audio is passed to the local backend process and is not sent to a cloud transcription
provider. This is the baseline because candidate answers are normally longer than 25 seconds.

## Local setup

## Full local demo

In three terminals from the repository root:

```bash
docker compose up -d
PYTHONPATH=backend alembic -c backend/alembic.ini upgrade head
PYTHONPATH=backend python backend/scripts/create_demo_invitation.py
```

Install backend dependencies once with `pip install -e ./backend`, then run the API with
`PYTHONPATH=backend uvicorn app.main:app --reload`. In another terminal run `npm --prefix frontend run dev`.
Open the URL printed by `create_demo_invitation.py`. It is synthetic, expires after 24 hours, and is intended only for local testing.

Install `ffmpeg` and build the `whisper-cli` executable. Download a multilingual Whisper GGML
model, then configure its explicit local path:

```bash
git clone https://github.com/ggml-org/whisper.cpp.git
cd whisper.cpp
cmake -B build
cmake --build build --config Release
sh ./models/download-ggml-model.sh small
```

Set these environment variables only when overriding defaults:

```bash
TRANSCRIPTION_PROVIDER=whisper_cpp
WHISPER_CPP_BINARY=/absolute/path/to/whisper-cli
WHISPER_CPP_MODEL=/absolute/path/to/ggml-small.bin
```

The input must be converted to the format required by the installed `whisper-cli` version (the
current upstream CLI documents 16-bit WAV input); the upload pipeline will perform that conversion
before transcription.

GigaAM v3 (`v3_e2e_rnnt`) and RouterAI are optional benchmark adapters, not production defaults.
They may replace the baseline only after comparison on synthetic technical answers longer than
25 seconds, with recorded transcription accuracy and latency.
