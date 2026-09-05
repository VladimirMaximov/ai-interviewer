# Runtime presenter for the hackathon prototype

The presenter pipeline is asynchronous and audio-first. Invitation creation stores an immutable question snapshot and queues one idempotent asset per question. XTTS v2 produces the multilingual WAV; MuseTalk v1.5 produces a lip-synced MP4 on the serialized GPU queue. If MuseTalk fails, the candidate still hears the WAV over the static interviewer portrait. Browser speech remains the last fallback.

## Target host

- NVIDIA Tesla T4 16 GB with a working NVIDIA Container Toolkit
- 6 CPU cores, 32 GB RAM, and SSD storage
- Ubuntu 24.04; Docker Engine with Compose v2
- GPU worker concurrency exactly one

The backend image uses Python 3.12. The isolated presenter image/runtime uses Python 3.10 because the validated MuseTalk/OpenMMLab stack is pinned in `deploy/images/presenter-requirements.txt`. Model weights and the MuseTalk checkout must be mounted at `/models` and `/opt/MuseTalk`; they are deliberately excluded from Git and images.

Set `MUSETALK_ROOT` to the prepared MuseTalk v1.5 checkout (including its downloaded weights) and `PRESENTER_MODELS_PATH` to the private directory containing the interviewer portrait and any local caches. XTTS downloads `tts_models/multilingual/multi-dataset/xtts_v2` into its normal user cache on first worker start; for a repeatable demo, warm that cache once before opening candidate links and persist it under the model mount. The configured voice identifier is `XTTS_VOICE`; no phonetic preprocessing or prerecorded per-question audio is used.

After cloning the official MuseTalk checkout, populate its inference weights with
`python deploy/scripts/bootstrap_presenter_models.py "$MUSETALK_ROOT"`. The script
downloads only MuseTalk 1.5 and the components used during inference; it is safe
to rerun and never places weights in Git.

Required environment values are documented in `.env.example`. Enable runtime generation with `PRESENTER_ENABLED=true`; keep it false on developer machines without CUDA. Validate the host with `nvidia-smi`, then start `deploy/docker-compose.prototype.yml` and check `/health` plus `/ready`.

No candidate recording, transcript, generated WAV/MP4, model weight, credential, or `.env` file may be committed. Presenter media is stored privately in S3/MinIO and exposed only through short-lived URLs after recruiter or invitation-token authorization.
