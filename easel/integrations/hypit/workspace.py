"""Create isolated, reproducible Hypit authoring workspaces."""

from __future__ import annotations

import json
import os
import re
import shutil
from pathlib import Path
from typing import Any

from easel.integrations.hypit.errors import HypitIntegrationError
from easel.integrations.hypit.handoff import verify_handoff_directory

_CREATION_ID_RE = re.compile(r"^cr_[0-9a-f]{32}$")
_ATTEMPT_ID_RE = re.compile(r"^fa_[0-9a-f]{32}$")


def workspace_root() -> Path:
    configured = os.environ.get("EASEL_HYPIT_HOME")
    return (Path(configured).expanduser() if configured else Path.home() / ".easel" / "hypit").resolve()


def attempt_workspace(creation_id: str, attempt_id: str, *, root: Path | None = None) -> Path:
    if not _CREATION_ID_RE.fullmatch(creation_id) or not _ATTEMPT_ID_RE.fullmatch(attempt_id):
        raise HypitIntegrationError("作品或 Attempt ID 非法")
    target = ((root or workspace_root()) / "workspaces" / creation_id / attempt_id).resolve()
    project_root = Path(__file__).resolve().parents[3]
    if target == project_root or project_root in target.parents:
        raise HypitIntegrationError("Hypit workspace 必须位于 Easel 仓库之外")
    return target


def create_workspace(
    creation_id: str,
    attempt_id: str,
    handoff_dir: Path,
    *,
    handoff_id: str,
    handoff_hash: str,
    root: Path | None = None,
) -> Path:
    selected_root = (root or workspace_root()).resolve()
    target = attempt_workspace(creation_id, attempt_id, root=selected_root)
    source = handoff_dir.resolve()
    if not source.is_dir():
        raise HypitIntegrationError("Handoff package 不存在")
    source_manifest, _ = verify_handoff_directory(source, handoff_hash)
    expected_package = {
        "name": f"easel-{creation_id}-{attempt_id}".lower(),
        "version": "0.0.0",
        "private": True,
        "description": "Isolated Hypit authoring workspace managed by Easel",
    }
    expected_task = _authoring_task(handoff_id, handoff_hash, source_manifest)
    if target.exists():
        try:
            copied_manifest, _ = verify_handoff_directory(target / "handoff", handoff_hash)
            package_json = json.loads((target / "package.json").read_text(encoding="utf-8"))
            task = (target / "AUTHORING_TASK.md").read_text(encoding="utf-8")
        except (OSError, json.JSONDecodeError, HypitIntegrationError) as exc:
            raise HypitIntegrationError("同一 Attempt 的 Hypit workspace 不完整；拒绝覆盖") from exc
        if (copied_manifest.get("handoff_id") != handoff_id
                or package_json != expected_package or task != expected_task
                or not all((target / name).is_dir() for name in ("references", "productions", "runs"))):
            raise HypitIntegrationError("同一 Attempt 的 Hypit workspace 身份不匹配；拒绝覆盖")
        return target

    target.parent.mkdir(parents=True, exist_ok=True)
    target.mkdir()
    try:
        for name in ("handoff", "references", "productions", "runs"):
            (target / name).mkdir()
        shutil.copytree(source, target / "handoff", dirs_exist_ok=True)
        copied_manifest, _ = verify_handoff_directory(target / "handoff", handoff_hash)
        if copied_manifest.get("handoff_id") != handoff_id:
            raise HypitIntegrationError("Hypit workspace 中的 Handoff ID 不匹配")
        _set_readonly_tree(target / "handoff")
        (target / "package.json").write_text(
            json.dumps(expected_package, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (target / "AUTHORING_TASK.md").write_text(
            expected_task, encoding="utf-8")
    except BaseException:
        shutil.rmtree(target, ignore_errors=True)
        raise
    return target


def refresh_authoring_task(
    workspace: Path, *, handoff_id: str, handoff_hash: str,
) -> bool:
    """Refresh only Easel's generated task after a failed authoring attempt.

    The frozen Handoff remains the authority; authored outputs are untouched.
    This lets a retry pick up corrected Hypit syntax without creating a new
    Attempt or asking the operator to repair stale instructions by hand.
    """
    root = workspace.resolve(strict=True)
    manifest, _ = verify_handoff_directory(root / "handoff", handoff_hash)
    if manifest.get("handoff_id") != handoff_id:
        raise HypitIntegrationError("Hypit workspace 中的 Handoff ID 不匹配")
    task_path = root / "AUTHORING_TASK.md"
    if task_path.is_symlink() or not task_path.is_file():
        raise HypitIntegrationError("Hypit Authoring Task 必须是 workspace 内的普通文件")
    expected = _authoring_task(handoff_id, handoff_hash, manifest)
    if task_path.read_text(encoding="utf-8") == expected:
        return False
    task_path.write_text(expected, encoding="utf-8")
    return True


def _set_readonly_tree(root: Path) -> None:
    for path in sorted(root.rglob("*"), key=lambda item: len(item.parts), reverse=True):
        path.chmod(0o555 if path.is_dir() else 0o444)
    root.chmod(0o555)


def _authoring_task(handoff_id: str, handoff_hash: str, manifest: dict[str, Any]) -> str:
    core = manifest.get("content", {}).get("content_core", {})
    truth = manifest.get("content", {}).get("truth_packet", {})
    creator = manifest.get("creator_context", {})
    mode = manifest.get("creative_mode", {})
    production = manifest.get("production_request", {})
    references = manifest.get("references", {})
    return f"""# Hypit Authoring Task

## A. Creation Identity

- Creation: `{manifest.get('creation_id', '')}`
- Handoff: `{handoff_id}`
- Handoff SHA-256: `{handoff_hash}`
- Route: `hypit_video`
- Creative Mode: `{mode.get('mode_id', '')}` v`{mode.get('version', '')}` (immutable snapshot in `handoff/{mode.get('path', 'creative-mode')}/`)

## B. Content Core

Read `handoff/{core.get('path', 'content-core.json')}`. Easel owns the topic, core idea, tension, audience, intended takeaway, and scope boundaries. Preserve their meaning.

## C. Truth Packet

Read `handoff/{truth.get('path', 'truth-packet.json')}` before authoring. Keep claim types, sources, confidence, first-person permissions, public permissions, and forbidden inventions intact.

## D. Creator Context

Read `handoff/{creator.get('path', 'creator-context.json')}`. This is the minimal work-specific snapshot, not permission to infer additional private facts.

## E. Creative Mode Snapshot

Use only the frozen Mode files under `handoff/{mode.get('path', 'creative-mode')}/`. It is a Director Method / Film Language contract, not a fixed script, story, or storyboard template. Let different Content Cores produce different narratives while preserving the same authored voice and film language.

## F. Production Requirements

```json
{json.dumps(production, ensure_ascii=False, indent=2)}
```

Produce a vertical short-form video authoring project. The Mode gives preferred duration and expressive constraints; adapt them to the Content Core rather than forcing a fixed scene count or structure.

## G. References

Read `handoff/{references.get('path', 'references.json')}`. Use only supplied references listed there. Do not fabricate evidence or claim access to assets that are not present in this isolated workspace.

## H. Material Layer Handoff

When this Attempt contains `planning/manifest.json` with `PLANNING_READY` and
`materials/readiness.json` with `READY`, read `materials/plan.json`,
`materials/bundle.json`, and the copied planning artifacts under
`productions/easel-authoring/`. Production Authoring owns the final explicit
asset selection through the assets it actually references in SVML. Easel
records those references in `productions/easel-authoring/material-selection.json`
with the frozen Plan/Bundle/Readiness identity; do not edit that JSON file.
Use the workspace-relative `src` paths for ordinary `media:Image`,
`media:Video`, or `media:Audio` inputs. Do not add Hypit `Candidate`/`satisfy` bindings for
ordinary workspace assets, and do not let material supply rewrite Director
intent.

### Hypit Markup authoring contract (installed v0.2.7)

Read `productions/easel-authoring/POSTPRODUCTION_REQUIREMENTS.json` when present.
Its source-bound clauses are pending Production responsibilities, not material
requirements or proof of completion. Implement them using the installed
contracts and preserve the frozen text, real subjects and source actions.
Unclassified Needs still follow SCRIPT/SCENES and the MaterialPlan. Do not edit
this server-owned input or claim its existence proves the expression is done.

The author source is Hypit Structured Markup, not a custom Easel XML schema.
Every isolated authoring turn receives `hypit-contracts/*.json`, exported
by Easel from the installed `hypit vocabulary` without Runtime or execution.
Read the relevant package's attributes, child declarations, Recipe properties,
notes and reference types before writing its components. These formal contracts
take precedence over illustrative snippets. Never borrow attributes from an
adjacent component; never edit the contracts or leave the isolated workspace.
The `<svml>` root has no attributes and no XML namespace declarations. Declare
each vocabulary with a leading `<import>` inside the root; use component outputs
and typed references, not invented `Scene`, `Overlay`, `Libraries`, `Tracks`,
`Metadata`, or `Param` elements. Hypit `check` is the final authority.

For existing stills and a silent authored timeline, use these installed
packages and contracts:

```svml
<?svml using="@hypit/markup@1"?>
<svml>
  <import as="media" from="@hypit/media@1"/>
  <import as="time" from="@hypit/timeline-author@1"/>
  <import as="space" from="@hypit/spatial@1"/>
  <import as="media-track" from="@hypit/media-track@1"/>
  <import as="film" from="@hypit/film@1"/>
  <import as="render" from="@hypit/render-hyperframes@1"/>
  <import as="typo" from="@hypit/typography-track@1"/>
  <import as="copy" from="@hypit/text@1"/>
  <import as="recipes" source="./recipes.svs"/>
  <!-- media:Image src; time:Clock id="clock" frame-rate="24" +
       time:Timeline id="program" clock={{clock}} end="12s" (replace 12s with the frozen duration);
       space:Canvas id="canvas" width="1080" height="1920" (empty);
       space:Extent id="source-extent" width/height from the selected image;
       space:Frame id="canvas-frame" within={{canvas}} left="0px" top="0px"
         right="1080px" bottom="1920px";
       media-track:Item image/source extent/frame at/for from the scene plan
         appearance={{recipes.media.still}};
       media-track:Sampling is an empty element at start/end;
       film:Film canvas={{canvas}} timeline={{program.timeline}} appearance={{recipes.film.memo}}
         with film:Track source={{visual-track.visual}};
       render:Video composition={{film.composition}} timeline={{program.timeline}}. -->
</svml>
```

Use only surfaces documented by the installed package READMEs/Surface
vocabularies. Make one Timeline using the frozen work's duration and
`media-track:Item` windows (`at` + `for`) for its actual scenes; include that Track's
`.visual` in `film:Film`. Timeline references use Hypit brace expressions:
write `clock={{clock}}`, not the quoted string `clock="clock"`. Timeline only accepts `id`, `clock`, and `end`; use `end="12s"` for a frozen 12-second work, never `duration` or `for`. A still
`Item` uses `image={...}` plus a factual source-dimension
`extent={...}` and a canvas placement `frame={...}`; its empty `media-track:Sampling` elements
use `at="start"` / `at="end"`, `zoom`, and pixel `x`/`y` (not verbal motion
names). Use `copy:Value` and `typo:Track`/`typo:Area` for text, not
`copy:Copy`, `typo:Area text`, or a generic overlay. Typography's Film source
is `.track`, not `.visual`; `film:Track` takes `source`, not `id`. Decide
`fit: contain` or `fit: cover` using the source aspect ratio and placement.
Only
reference admitted asset paths from MaterialBundle. Do not use namespace
attributes or put Easel identity/hash/rights metadata in SVML; those remain in
Easel's selection and Material records.

Every `media-track:Item` requires an `appearance` reference to an SVS Recipe;
`film:Film` requires `id`, `canvas`, `timeline`, and an `appearance` Recipe. Author
`productions/easel-authoring/authors/recipes.svs` alongside `main.svml` and
import it as `recipes` from `./recipes.svs`. This is the installed SVS shape:

```svs
<?svml using="@hypit/svs@1"?>
<sheet version="1">
  media.still {{ stack-order: 10; fit: cover; }}
  film.memo {{ background: #101820; }}
</sheet>
```

Choose the actual appearance in line with the frozen Creative Mode. Every
still Item can reference `appearance={{recipes.media.still}}`, and Film can
reference `appearance={{recipes.film.memo}}`. `stack-order` is required for
media Item appearance; `background` is required for Film appearance. Do not
invent an inline `appearance` attribute or omit this dependency.

The `space:Canvas` surface is a required empty element with its own positive
integer `width` and `height` attributes. It accepts no children. Declare the
`space:Extent` and `space:Frame` as separate siblings; connect Frame with
`within={{canvas}}` and explicit edges. For the 9:16 project, use 1080×1920.

```svml
<space:Canvas id="canvas" width="1080" height="1920"/>
<space:Extent id="canvas-extent" width="1080" height="1920"/>
<space:Frame id="canvas-frame" within={{canvas}} left="0px" top="0px"
  right="1080px" bottom="1920px"/>
```

### Moving video contract (installed v0.2.7)

A raw `media:Video` cannot be used as an Item's `video` attribute. Normalize
its direct BlobArtifact record first (`source={{shot}}`, never `source={{shot.video}}`), then reference Normalize's `.media` output on the Item. Declare
`pipeline` even for a silent video; the import is not limited to audio work.
For a silent production select `audio="none"`, do not opt into `source-audio`,
and include only the visual Track output in Film. Example (replace the source
with the admitted asset and the timing with frozen scene timing):

```svml
<import as="pipeline" from="@hypit/media-pipeline@1"/>
<media:Video id="shot" src="../../../materials/assets/ASSET/original.mp4"/>
<pipeline:Normalize id="shot-media" source={{shot}}
  video="primary-moving" audio="none" span-authority="video" clock={{clock}}/>
<media-track:Track id="pictures" canvas={{canvas}} timeline={{program.timeline}}>
  <media-track:Item media={{shot-media.media}} frame={{canvas-frame}}
    at="0s" for="4s" appearance={{recipes.media.clip}}/>
</media-track:Track>
```

The SVS `media.clip` Recipe requires `stack-order` and may use `fit: cover`.
Native `playback: once-start` truncates the source to the Item window; an
exhausted source does not magically extend. `trim-start` and `trim-end`, if
used, are paired integer source frame boundaries, not second strings.
A soft cross-dissolve belongs to a Media Sequence with ordered Members and
an explicit Handoff for each adjacent pair, using a transition Recipe.
The transition Recipe uses `operator: crossfade`, `duration-frames: 12`
(for 0.5 seconds at 24 fps), `boundary-ratio: 0.5`, and `audio: cut`.
Do not invent `duration`, `type`, or `dissolve` on Handoff; the Handoff has
`id`, `from` (outgoing Member id), and `transition={{recipes.transition.soft}}`.
Timeline overlaps alone do not create dissolves. Preserve the confirmed
transition and full duration; never silently substitute cuts.

### Typography and Film type references (installed v0.2.7)

For Simplified Chinese use an installed open font rather than inventing a
font family on a text Area. A `typo:Style` requires an exact `font` and an SVS
`recipe`; `typo:Area` requires `placement`, `style`, and content. Example:

```svml
<import as="fonts" from="@hypit/fonts-open@1"/>
<fonts:Face id="caption-font" family="noto-sans-sc" weight="400" style="normal"/>
<typo:Style id="caption-style" recipe={{recipes.text.caption}} font={{caption-font}}/>
<copy:Value id="caption-copy">Replace with the exact frozen text.</copy:Value>
<typo:Track id="titles" timeline={{program.timeline}}>
  <typo:Area id="caption" content={{caption-copy}} placement={{canvas-frame}}
    style={{caption-style}} at="0s" for="4s"/>
</typo:Track>
<film:Film id="movie" canvas={{canvas}} timeline={{program.timeline}}
  appearance={{recipes.film.memo}}>
  <film:Track source={{pictures.visual}}/>
  <film:Track source={{titles.track}}/>
</film:Film>
```

Declare `text.caption` in SVS with `stack-order`, `size` (not font-size),
`fill`, `align`, and `block-align` appropriate to the frozen layout. `pictures`
is the actual Media Track id, not a new component. All four Film attributes
are mandatory. A local static check of Video → Normalize → Sequence/Handoff
→ Typography → Film → Render passed on installed v0.2.7; adapt only admitted
asset references, scene windows, text and creative appearance, preserving the
frozen requirements.

## I. Truth Boundary

- Do not change Easel's Content Core, Truth Packet, Creator Context, or canonical Creative Mode.
- Preserve Truth Packet provenance exactly: `user_statement` is verbatim user input, `model_inference` is a model-derived interpretation, `source_evidence` requires its cited source, and `unknown` remains unverified.
- Never rewrite a `model_inference` as `user_statement`; do not upgrade unknown material based on plausibility.
- Do not invent creator experiences, workplace incidents, dialogue, dates, amounts, outcomes, or credentials.
- A plan is not an experience; learning is not proven capability.
- Keep unsupported statements labeled as uncertain or omit them.
- Do not create another Easel Creation.

## J. Hypit Authoring Workflow

YOU OWN:
- Treatment and video script
- Scene / Action and semantic timing
- Captions and tracks
- Composition and project components
- Film-specific SVML / SVS authoring

YOU DO NOT OWN:
- changing the Content Core or its truth boundary
- editing the canonical Creative Mode
- creating another Easel Creation
- treating legacy Easel storyboard artifacts as directing constraints

Do not read an old Easel storyboard as a required template. Create the Treatment, Script, scenes/actions, and required manifests in this isolated workspace. Keep authored sources under `productions/` or `runs/`; name any final Output explicitly so Easel can export it later. This task stops before `hypit build`; a Build requires a separate operator-approved action.

### Easel-to-Hypit Run adapter (installed Hypit v0.2.7)

`authors/main.svml` is the Hypit Author Source: it must use
`<?svml using="@hypit/markup@1"?>` and a bare `<svml>...</svml>` root.
`runs/main.svrun`, despite its extension, is an Easel JSON manifest, not a
Hypit Source. Write schema `easel-authoring-svrun@1` with the exact frozen
`creation_id`, `attempt_id`, `plan_id`, `plan_revision`, `bundle_id`,
`bundle_revision`, and `readiness_revision`; set `authoring_source` to
`../authors/main.svml`, `material_selection` to
`../material-selection.json`, `status` to `AUTHORING_READY`, and
`publication_allowed` to `false`. Include `build.enabled=false` and
`build.reason="stops_before_hypit_build"`. Copy identity/revision values from
the current Attempt, `planning/manifest.json`, `materials/bundle.json`, and
`materials/readiness.json`; never invent them. Do not put Hypit markup in this
JSON manifest. Easel validates those frozen fields and converts the manifest
to the installed self-described Hypit Run markup before running local `hypit
check`; that check remains authoritative for the installed Hypit Source.

This workspace is isolated from the Easel repository. Provider credentials and
Runtime Profile selection remain in Hypit's own credential store.

## K. Audio Production Contract (Hypit v0.2.7)

When the current MaterialPlan contains required Voice or BGM Needs, select a
qualified admitted audio Asset for every required audio Need. Narration content
must remain the frozen productions/easel-authoring/SCRIPT.md text. The voice
identity is the provider-neutral identity recorded in the Need; do not invent a
provider voice ID. AI narration supply belongs to the Material Layer's later
generation stage; this Hypit authoring turn only edits admitted audio assets.

Read productions/easel-authoring/VOICE_TIMING.json before setting subtitle and
shot timing. Each READY entry binds the admitted audio SHA, frozen Script SHA,
actual inspected audio duration and provider sentence alignment. Use those
source times for the selected voice; never substitute character-count estimates
or the preliminary SCENES time grid. Provider alignment is not a listening or
quality approval. unavailable_need_ids means no verified timing is available;
do not fabricate a transcript or claim that the narration has been aligned.

For a selected READY voice, Easel compiles sentence captions and full narration
placement before the installed Hypit check. Use the native aliases `time`,
`media`, `pipeline`, `audio`, `film`, `copy`, `typo`, `space`. Author one Clock,
one Timeline and one Film, a separate voice AudioTrack with one untrimmed,
non-stretched Item, and a frame-aligned narration start (`at`, or `during="program"`).
Choose the subtitle recipe/font and safe placement according to the frozen
Director: declare `typo:Style id="easel-caption-style"` and
`space:Frame id="easel-caption-frame"` before a reserved empty track
`<typo:Track id="easel-captions" timeline={{program.timeline}}/>`.
The compiler fills that track with the frozen script and measured sentence
windows, adds its Film reference, preserves the chosen style/frame and voice
gain/start, and plays the complete voice once without fades. Give the Timeline
enough frames for the inspected audio plus the chosen start; adjust pictures
to this duration instead of clipping or stretching the voice. Do not duplicate
narration captions in other tracks or invent word/karaoke timing. Headings and
other editorial text remain separately authored. BGM is a separate track.
When the frozen Mode declares music_ducking, Easel wraps admitted BGM AudioTracks
in its checked-in native envelope component after authoring. Keep the BGM in a
separate audio:Track and include it once in Film. Choose its base gain, placement,
trim, looping and fades; the wrapper preserves those choices and only lowers the
level around measured speech. Do not generate component code, manual envelope
points, another BGM copy, or repeatedly restart music for each sentence. A fixed
low gain alone is not ducking; automatic ducking is not an actual loudness check.

For each selected audio Asset, declare its workspace-relative source with
media:Audio, pass it through pipeline:Normalize with audio="default",
place the normalized .media in an audio:Item, and include the resulting
AudioTrack .audio in the enclosing film:Film as a peer film:Track.
Use the installed v0.2.7 component names and references (replace the source
path and IDs with this Attempt's values):

```svml
<import as="pipeline" from="@hypit/media-pipeline@1"/>
<import as="audio" from="@hypit/audio-track@1"/>
<media:Audio id="voice-source" src="../../../materials/assets/ASSET/original.mp3"/>
<pipeline:Normalize id="voice-media" source={{voice-source}}
  video="none" audio="default" span-authority="audio" clock={{clock}}/>
<audio:Track id="voice-track" timeline={{program.timeline}}>
  <audio:Item source={{voice-media.media}} during="program"/>
</audio:Track>
<film:Track source={{voice-track.audio}}/>
```

The film:Track belongs inside film:Film. The `audio` prefix is the declared
import alias; another declared alias such as `audio-track` is equally valid
when used consistently. Do not use `media={{voice-source}}` on the audio Item;
it must consume the normalized `.media` output through `source`.
Narration and BGM Needs require separate AudioTracks. BGM placement must state
its gain and fade intent. Hypit v0.2.7 does not infer automatic music ducking;
keep the authored BGM level below narration and do not claim audible balance
until the final output has been listened to and reviewed.

Do not create an audio track for an absent/optional Need merely to satisfy a
format check. Easel verifies required Need coverage, selected bytes, the
Normalize → AudioTrack → Film reference chain, and the final audio stream at
Export. Hypit owns timing, trim, track rendering, and mix.
"""
