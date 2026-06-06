# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

CapsWriter-Offline is a **Windows-only** offline speech-to-text tool. Hold CapsLock (or mouse X2), speak, release to type. It also supports file transcription (audio/video → SRT/TXT/JSON). Version 2.6.

## Architecture

**Client-server via WebSocket + multiprocessing.** Both sides use a Facade pattern with a single `start()` entry point.

```
Client (CapsWriterClient)          Server (CapsWriterServer)
├── AudioStreamManager             ├── ProcessManager (spawns RecognizerWorker in a child process)
├── ShortcutManager (global keys)  │     └── engines/  (ASR, punctuation, force-aligner)
├── WebSocketManager               │         ├── qwen_asr_gguf/  (default, best accuracy)
├── HotwordManager (phoneme RAG)   │         ├── fun_asr_gguf/
├── LLMHandler (external APIs)     │         ├── sensevoice_onnx/
├── TextOutput (typing/paste)      │         └── paraformer_onnx/
├── DiaryWriter                    ├── SocketManager (WebSocket server)
├── UDPController                  ├── merger/      (text & token merging)
└── TrayManager                    ├── formatter/   (ITN, punctuation cleanup)
                                   └── TrayManager
```

**Message flow**: Audio → `ClientState.queue_in` → WebSocket → Server multiprocessing `queue_in` → RecognizerWorker (child process) → `queue_out` → WebSocket back to client → postprocessing (hotwords, LLM) → text output.

**Protocol**: `core/protocol.py` — `AudioMessage` (client→server) and `RecognitionMessage` (server→client), JSON over WebSocket, audio as base64-encoded float32 16kHz mono. Internally, the server converts these to `core/server/schema.py` dataclasses: `Task` (child process input) and `Result` (child process output).

**Server pipeline** (`core/server/worker/pipeline.py`): `TaskPipeline.process()` produces two parallel outputs from each audio segment:
1. **Simple text merge** (`result.text`) — overlap-based concatenation, no timestamps needed. Used for real-time mic display and final output.
2. **Token-level merge** (`result.text_accu`) — SequenceMatcher dedup with timestamps. Used for SRT/subtitle generation. For file tasks on engines lacking native timestamps, the forced aligner (`core/server/engines/force_aligner_gguf/`) is invoked per-segment to generate them.

On `is_final`, `TextFormatter` (`core/server/formatter/`) applies ITN (Chinese digit normalization), punctuation cleanup, and whitespace normalization to both outputs.

## Key files

| File | Role |
|---|---|
| `core/client/app.py` | Client facade — instantiates everything, exposes `start()` |
| `core/server/app.py` | Server facade — instantiates everything, exposes `start()` |
| `core/protocol.py` | Message dataclasses shared by both sides |
| `core/server/schema.py` | Internal server dataclasses: `Task`, `Result`, `RecognitionSession` |
| `core/server/worker/pipeline.py` | `TaskPipeline` — ASR + punctuation + aligner orchestration, dual output paths |
| `core/server/worker/worker.py` | `RecognizerWorker` facade — child process lifecycle, delegates to ModelLoader + TaskHandler |
| `core/server/worker/process_manager.py` | Spawns/kills the recognition child process via `multiprocessing.Process` |
| `core/server/engines/factory.py` | `EngineFactory` — lazy-loads the configured ASR/aligner/punctuation engine |
| `core/server/engines/base.py` | Abstract bases: `BaseASREngine`, `BasePuncEngine`, `BaseAlignEngine`, `RecognitionStream` |
| `core/server/formatter/text_formatter.py` | `TextFormatter` — ITN, punctuation cleanup, whitespace normalization on final results |
| `config_client.py` | All client configuration (hotkeys, thresholds, LLM, paste behavior) |
| `config_server.py` | Server config (model type, GPU boost, model paths, engine args) |
| `core/client/hotword/manager.py` | `HotwordManager` — phoneme-based fuzzy matching and replacement |
| `core/client/llm/llm_handler.py` | `LLMHandler` — routes recognition results to LLM roles |
| `core/client/shortcut/shortcut_manager.py` | Global hotkey listening (CapsLock, X2, etc.) |
| `LLM/*.py` | LLM role config files (each is a Python module defining `name`, `system_prompt`, `api_key`, etc.) |
| `hot.txt` | Client-side hotwords list (phoneme RAG, mandatory replacement above threshold) |
| `hot-rule.txt` | Client-side regex replacement rules |
| `hot-server.txt` | Server-side hotwords (passed directly to the ASR engine) |

## Directory layout

- `core/client/` — Client code: audio capture, hotkeys, hotwords, LLM, text output, diary, file transcription
- `core/server/` — Server code: engines, WebSocket, worker process, text merging/formatting
- `core/tools/` — Shared utilities: Chinese ITN (digit normalization), zhconv (simplified↔traditional), signal handling, SRT generation
- `core/ui/` — Shared UI: toast notifications, tray icon, dialogs, context menus
- `internal/` — Bundled Python runtime + third-party packages (`.pyc`/`.dll`), used by the `.exe` builds
- `models/` — ML model files (downloaded separately from GitHub Releases)
- `docs/` — Chinese-language user documentation

## Configuration system

No CLI flags or env vars. All settings are Python class attributes in `config_client.py` (`ClientConfig`) and `config_server.py` (`ServerConfig`). Users edit these files directly. The `config_*.py` files also define `ModelPaths` (where models live) and engine-specific args classes (`ParaformerArgs`, `SenseVoiceArgs`, `FunASRNanoGGUFArgs`, `Qwen3ASRGGUFArgs`, `ForceAlignerGGUFArgs`).

## Development notes

- **Windows-only**: Uses `sounddevice`, `keyboard`, `mouse`, `pywin32`, `win32gui`, `win32clipboard`. Will not run on Linux/macOS.
- **No test suite** exists in this project.
- The `.exe` files are Nuitka-built bundles that use the `internal/` directory as their Python environment.
- To run from source for development, execute `core/client/app.py` and `core/server/app.py` directly with a Python that has the required Windows dependencies installed.
- **Multiprocessing model**: The server main process handles WebSocket I/O only. Recognition runs in a child `multiprocessing.Process` (the `RecognizerWorker`). Communication between main and child is via two `multiprocessing.Queue`s (`queue_in` for tasks, `queue_out` for results). A `Manager().list()` tracks active WebSocket socket IDs across the process boundary so the child can clean up sessions for disconnected clients.
- **GPU boost**: When enabled, the server runs `nvidia-smi -lmc` on first task to lock VRAM frequency, then `nvidia-smi -rmc` after a configurable idle timeout. Requires admin privileges.
- Hotword matching uses a custom phoneme-based RAG algorithm (`algo_phoneme.py`, `algo_calc.py`) — not a standard library.
- LLM roles are Python modules in `LLM/`. The `name` attribute (supports `|`-separated aliases) determines the trigger keyword, matched against the start of recognition text. `LLM/default.py` is the fallback when `name` is empty.
