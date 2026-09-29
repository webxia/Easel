# Creative Modes

Creative Modes are versioned expression contracts for Easel. They do not replace the Director Agent, Profile, Route, Skill or media Runtime.

```text
Profile       -> who speaks; facts, audience, boundaries
Director      -> what is worth saying; Content Core and narrative choices
Creative Mode -> how this work should feel, look, sound and be reviewed
Capability    -> what this chat request asks Easel to do
Route         -> internal execution choice resolved by the backend
Skills        -> image, video, TTS, subtitle, audio and assembly execution
```

## Runtime contract

A chat request may include `creativeMode`. Easel validates the requested package under `creative_modes/<id>/`, binds it to the chat session, and injects its contract alongside the selected Profile. The same `main` OpenClaw Agent remains the Director.

The first mode is `clear_memo_video`, a reusable expression contract rather than a route or backend selector. It must not choose providers, create a separate video pipeline, override the Profile, or force every topic into a fixed script. It does require a Content Core and Director Treatment before production choices, then applies its visual, audio, editing and QC rules only to applicable work.

## Package format

Each package contains a JSON contract and human-readable bibles:

```text
creative_modes/<id>/
  mode.json
  director-treatment.md
  visual-bible.md
  audio-bible.md
  editing-bible.md
  qc-rubric.md
```

`mode.json` is machine-readable metadata for the UI and version audit. It does not declare or select production Routes. The Director receives only the Mode identity and boundaries at chat start. After it has made a Content Core, the relevant Markdown Bible is read as a stage contract: visual for image work, audio for voice/audio work, editing for storyboard/assembly, and the QC rubric for review. This prevents a visual preference from quietly becoming a narrative template.

## Trigger and audit

1. A Profile may store one optional default Mode reference in `profiles/<name>/.easel-profile.json`. It contains only `default_creative_mode`; providers, voice IDs, BGM and renderer settings remain runtime concerns.
2. In the Easel sidebar, choose a Profile and a Creative Mode before the first message of a new chat. An explicit `自由表达` choice overrides the Profile default for that chat.
3. The browser stores both on that chat session and sends `persona` plus `creativeMode` to `POST /api/chat/stream`.
4. A media-producing request creates a persistent work record under `outputs/_creations/<id>/creation.json`. Its stages are `content_core -> director_plan -> storyboard -> assets -> assemble -> qc`; each completed stage records real output paths.
5. `python3 -m easel.creation context --id <id> --stage image|video|tts|audio|assemble|qc` returns only the relevant Mode Bible after its prerequisite stage is complete.
6. `GET /api/creative-modes` lists active packages; `GET /api/creative-mode/{id}` returns its contract for inspection. `POST /api/creations` creates a work record without invoking any Agent or provider.
7. A Mode-governed production project must record `creative_mode` and `creative_mode_version` in `outputs/<topic>/.easel.json`.

Changing a Mode after a chat has messages is deliberately disabled. A conversation has one visible creative context; start a new chat to choose a different one.
