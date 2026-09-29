# Creation Lifecycle

A Creation is one persistent work record, not an Agent, a fixed content template, or a media pipeline. It exists so a Director-led work can survive a chat boundary and show what has actually been decided, produced, reviewed, or blocked.

```text
idea
  -> content_core
  -> director_plan
  -> storyboard
  -> assets
  -> assemble
  -> qc
  -> ready | not_ready
```

## State record

`outputs/_creations/<creation-id>/creation.json` is the source of truth for the work lifecycle. It stores:

- the original idea, selected Profile, Mode id/version, and intended Route;
- every stage's state, real artifact paths, concise summary, and failure reason;
- a timestamped history; and
- the resulting work status: `draft`, `planning`, `producing`, `ready`, `not_ready`, `failed`, or `paused`.

It does not store a provider, voice id, music source, renderer setting, or generated prompt as stable creator identity. Those remain production-runtime choices.

## Director and Mode boundary

The Director creates `content_core` freely before any Mode Bible is read. A Content Core should distinguish real experience, current action, learning, public fact, and unverified thought, then name the tension worth expressing.

After that point, the same Director reads the smallest applicable Mode contract:

| Concern | Mode contract |
| --- | --- |
| Director plan | `director-treatment.md` |
| Storyboard | visual, audio, and editing bibles |
| Image | visual bible |
| Video | visual and editing bibles |
| TTS / audio | audio bible |
| Assembly | audio and editing bibles |
| QC | QC rubric |

The contract controls expression, never the topic, argument, or story shape.

## How to use it

Creating a record has no model, provider, or publishing side effect:

```bash
python3 -m easel.creation create \
  --idea "今天学习 AI Agent 后，我重新理解了程序员的价值" \
  --profile "个人经营实践" \
  --creative-mode clear_memo_video
```

The Director writes a real artifact, then records it. For example:

```bash
python3 -m easel.creation record --id <creation-id> \
  --stage content_core --status completed \
  --artifact _creations/<creation-id>/content-core.json

python3 -m easel.creation context --id <creation-id> --stage director_plan
```

`record` rejects a completed stage without its real files. `context` rejects a production concern until its upstream state is complete. `qc` must explicitly decide `ready` or `not_ready`; a technically generated MP4 is not automatically ready to publish.

The same lifecycle is also available through `/api/creations`. It is intentionally not wired to automatically invoke media Skills in this phase: the Director retains editorial control, and the existing production Skills remain the executors.
