"""Captured Hypit source and typed native AST for the explicitly selected profile.

The installed parser owns syntax. Easel resolves only its verified structured
surfaces and local captured recipes; no source module or user handler executes.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType

from .cli import HypitCLI
from .errors import HypitIntegrationError
from easel.integrations.output_receipts import OutputReceiptError

PROFILE = "easel-hypit-source@1"
MAX_SOURCE_BYTES = 512 * 1024
MAX_RESPONSE_BYTES = 16 * 1024 * 1024
SURFACES = {
    "@hypit/media@1": ("Image", "Audio", "Video", "Font"),
    "@hypit/media-pipeline@1": ("Normalize", "StillVideo", "Transform", "ExtractAudio", "ExtractFrame"),
    "@hypit/timeline-author@1": ("Timeline", "Clock"),
    "@hypit/spatial@1": ("Canvas", "Point", "Path", "Extent", "RegionTimeline", "Frame", "AnchoredFrame", "AspectFrame"),
    "@hypit/media-track@1": ("Track",),
    "@hypit/audio-track@1": ("Track",),
    "@hypit/film@1": ("Film",),
    "@hypit/render-hyperframes@1": ("Video",),
    "@hypit/typography-track@1": ("Style", "Motion", "Track", "Mask"),
    "@hypit/text@1": ("Value", "Render"),
    "@hypit/fonts-open@1": ("Face", "Stack"),
    "@easel/audio-mix@1": ("Duck",),
}
# Native handlers own nested syntax; child prefixes do not select a new module.
# Unsupported nested forms are explicit Easel-profile limits, not XML errors.
NESTED = {
    ("@hypit/timeline-author", "Timeline"): {"Take"},
    ("@hypit/audio-track", "Track"): {"Item"},
    ("@hypit/film", "Film"): {"Track"},
    ("@hypit/media-track", "Track"): {"Item", "Sequence"},
    ("@hypit/media-track", "Sequence"): {"Member", "Handoff", "Sound"},
    ("@hypit/media-track", "Item"): {"Sampling", "Layer", "Paint", "Sound"},
    ("@hypit/media-track", "Member"): {"Sampling", "Layer", "Paint", "Sound"},
    ("@hypit/media-track", "Layer"): {"Sampling"},
    ("@hypit/typography-track", "Track"): {"Point", "Area", "Path"},
    ("@hypit/typography-track", "Point"): {"P"},
    ("@hypit/typography-track", "Area"): {"P"},
    ("@hypit/typography-track", "Path"): {"P"},
    ("@hypit/typography-track", "P"): {"Span", "Break"},
}
PINNED_SOURCES = {
    "node_modules/@esbuild/darwin-arm64/bin/esbuild": "b82c6243eb58d520d0bc55cddcf6993dd0f5572f3ab8dc2ba6d77058be043e62",
    "node_modules/@esbuild/darwin-arm64/package.json": "2716c24eaffc7327a0f910d977a72e266daa0d88f2155390dc31af0e164f4a0e",
    "node_modules/esbuild/lib/main.js": "bce772de103e1cbb118f1b7313916caa81f0e85461b3b6e3531607e7ed75ec85",
    "node_modules/esbuild/package.json": "9ce21c976ffbbb95001f460e9e8af7c6d719f748eb70441e617a14dd0b68a5b8",
    "node_modules/get-tsconfig/dist/index.cjs": "1c040b0a49d0e7dbc555c4e1e8acbdc1f74478011ebeec008dd9e38c83722273",
    "node_modules/get-tsconfig/dist/index.mjs": "2bb1e82fea648d598e1067cc5b643105493a63502458694b486f0c581b506503",
    "node_modules/get-tsconfig/package.json": "4e5880985b33ecaa87f6aef1b6581dec5555d88a0738a7379576e80891873355",
    "node_modules/resolve-pkg-maps/dist/index.cjs": "dc0ffaba25e180745bb1ce1622be094bbc97d07dc275c52413eb546580d9ff49",
    "node_modules/resolve-pkg-maps/dist/index.mjs": "5472eb24afa47c614e7edaccb0ccb4c6259f897d875c27057ee00b7c2cdc3672",
    "node_modules/resolve-pkg-maps/package.json": "e372f809865bc3fc6ad75be76a90b031eece36e9d12d283de9955aca6be8537d",
    "node_modules/tsx/dist/client-BQVF1NaW.mjs": "334ad3dbfaf820eeb08dd2fa40750c8316e6f8a61311bdf99defd3c361fbece4",
    "node_modules/tsx/dist/esm/api/index.mjs": "477bed5ef167ef825ec4cb99ed010ac6d70833d1b4e8b46e23825cc6de543d8e",
    "node_modules/tsx/dist/esm/index.mjs": "9fab711543eb155d50fb147f8984e104db348a73b74daee4e3974bec109aa381",
    "node_modules/tsx/dist/get-pipe-path-BHW2eJdv.mjs": "307483caa22c2406677b4bd513bf602b4de3986f3e23eac7724e99c0d7ddc8d6",
    "node_modules/tsx/dist/index-7AaEi15b.mjs": "47851348bc3bbc11413edd4bf44758b7a85e28419847583231d74a182b044e22",
    "node_modules/tsx/dist/index-gbaejti9.mjs": "76febbe946957c96066d1d59293c4a26fc874c05876394cf4c178e4f4d0b6ba8",
    "node_modules/tsx/dist/lexer-DQCqS3nf.mjs": "6b77bebaee2dd7741177e287a78ef4329d9ef91f6939d09cfcf0029b3859f883",
    "node_modules/tsx/dist/node-features-_8ZFwP_x.mjs": "dbf95f05cce9b129a9a89f33f43b7804ab641aa8b256e7cf64ad9f92b880cecc",
    "node_modules/tsx/dist/register-B7jrtLTO.mjs": "10184ddf4354bab38743d80a5844796f26ffc4589d2820781da90c6a67507aaf",
    "node_modules/tsx/dist/register-CFH5oNdT.mjs": "7c7d2d4f757a1a35610b483e0348aee2eb1140968631f4b2105c4b4ad9ffbf0a",
    "node_modules/tsx/dist/require-DQxpCAr4.mjs": "dc1b6944ffaa8f4d70e5007116b9aeac77c1cdf80a62526763eab34a123fa902",
    "node_modules/tsx/dist/temporary-directory-CwHp0_NW.mjs": "e0771b7d9b216d438ff2ade7494a7a3ac6202c66cb752f2cd99bffb3d78226fe",
    "node_modules/tsx/package.json": "6e764b21991c21595441f82387c1451ccd10a3e7a3f0973cc5e3649a12dea7d2",
    "package.json": "1dfb1c44bf70e2b22e8d93ba2ea5892153d2deb2411233206a4be860c62356ae",
    "packages/markup/package.json": "8f252bf21ab60aa8001b836e669bab4ba5d36cd1c176b515e826ac5a2d56d58b",
    "packages/markup/src/element.ts": "b5b3a407acd6d50a96151d3b2b22e01120d82aa209157dafcf62238d57ee234e",
    "packages/markup/src/error.ts": "8548c95fe3732ebd2d60db4e2744af5039d9dd82bbed17e422ade97453294ebe",
    "packages/markup/src/frontend.ts": "06a235c1443904a2d04ab223000c1d6bf227689b715d8621a8b94b717a8d0178",
    "packages/markup/src/host-facet.ts": "8fe277d4b242df5020623babc348ed67f8005a70ead336d4b7659dce8ff62aad",
    "packages/markup/src/index.ts": "48e159c7d9f8cf256906541a568ca8f70459a000bd897295709b75c08d08b693",
    "packages/markup/src/registry.ts": "f6048261d3f73012db0f3795a288314f4419226542c0af2e6780d4b5a7058988",
    "packages/markup/src/syntax.ts": "486d3d6be06e453311e6a399b374535c6f444831ed901fd2badc8d1623eb6bf6",
    "packages/package-loader-node/package.json": "afc816b1727027274bdca012493fbf470f7294b82bb9dac3596f6e8f6655ab9e",
    "packages/package-loader-node/src/distribution-resolution.ts": "cde18c7956abbe2b1eaa679b4f365072f05b06134fd51127bbe4d1802539b6c1",
    "packages/package-loader-node/src/location.ts": "688060dbff9c52cc3f24d4b2b481cb2c903d253881ad2acd8637536e0f29040c",
    "packages/protocol/package.json": "05def9b24e58b4d051e7a5411a248ba2804ba73de8840085ee3e0077e2070d72",
    "packages/protocol/src/build-id.ts": "0b7b5b3dccab184c83cdeaa1a9a3f793b7c72150a3fcd77e9a4fa96cc831ebc7",
    "packages/protocol/src/canonical.ts": "aa9bd48f2272c097f3a0cb6ec666a4b4c951132611fb3cef03972cfed297c128",
    "packages/protocol/src/error.ts": "4964bda4ac1c42f21993eec5ce9ad9c54e3e9e8bcf7c9d1db52de99264f51e9f",
    "packages/protocol/src/identity.ts": "b23960535f32b9d183bcf1e8fca3a698dd06d644fda143205f13623f9d34ae80",
    "packages/protocol/src/index.ts": "dfb3eb775f2905da7d0937c7bba803041ba2b513c66d8471f2ab320d3bc77e8d",
    "packages/protocol/src/module.ts": "6a547aedf8a6465094d5d57b38c074c2ef175d98fab8a1f6d9afdae6c5982123",
    "packages/protocol/src/value.ts": "9f3527819ac7fbfefd6db2afc73a3365e39980a0c97326d3ec701b8c042ebcd8",
    "packages/run-markup/package.json": "c53e6a84630800fd945838265fb5c0847aa47dcb8dab6fb4a17d3bd7c75f4e1c",
    "packages/run-markup/src/syntax.ts": "f5eab8e0f258f0d4543fdc65358fbb02f4d0a007c25d9cb294e71cc7e7aa27ee",
    "packages/source/package.json": "6d8fb91c362597cb2939b5cb02c29ee89644c7303b62264df10e117dafad30ea",
    "packages/source/src/header.ts": "7c5f11ffbff4477fa5735feeca3fcd2ef146368ce8052131284a2c5e996e5fde",
    "packages/svs/package.json": "f120a6758930a70258b325addcddd1e822a45924593acb40b479e63d9c2a280c",
    "packages/svs/src/parser.ts": "6fb4b39fa66bd6c2a1db3deed1c4d1f22162e312c96077c6cc3558900bd327a5"
}


class NativeSourceError(HypitIntegrationError):
    def __init__(self, diagnostic):
        self.diagnostic = diagnostic
        location = (f" [{diagnostic.get('source', '')}, UTF-16 offset {diagnostic['offset']}]"
                    if "offset" in diagnostic else "")
        super().__init__(diagnostic["code"] + location + ": " + diagnostic["message"])


def _error(code, message, source=None, position=None):
    detail = {"code": code, "message": message, "kind": "source"}
    if source is not None:
        detail["source"] = source.name
    if position is not None:
        detail.update(offset=position["start"], offset_unit="utf16-code-unit")
    raise NativeSourceError(detail)


def enabled(attempt):
    from easel.integrations import result_protocols
    return result_protocols.selected(attempt, "hypit_source") == PROFILE


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def workspace_for(source):
    source = Path(source)
    if source.parts[-4:-1] == ("productions", "easel-authoring", "authors"):
        return source.parents[3]
    return source.parent


def _safe(root, path):
    root, path = Path(root), Path(path)
    try:
        relative = path.relative_to(root)
    except ValueError as exc:
        raise OutputReceiptError("Native source path is outside its captured workspace") from exc
    if ".." in relative.parts or root.is_symlink():
        raise OutputReceiptError("Native source path is unsafe")
    current = root
    for part in relative.parts:
        current /= part
        if current.is_symlink():
            raise OutputReceiptError("Native source path contains a symlink")
    return path


def read_source(path, root):
    path = _safe(root, path)
    try:
        before = path.stat()
        if not path.is_file() or before.st_size > MAX_SOURCE_BYTES:
            raise OutputReceiptError("Native source is not a bounded regular file")
        raw = path.read_bytes()
        after = path.stat()
        if (before.st_ino, before.st_size, before.st_mtime_ns) != (after.st_ino, after.st_size, after.st_mtime_ns):
            raise OutputReceiptError("Native source changed during capture")
        return Snapshot(path.relative_to(root).as_posix(), raw)
    except OSError as exc:
        raise OutputReceiptError("Native source capture failed; recover locally") from exc


def installed_parser():
    try:
        cli = HypitCLI()
        binary = Path(cli.executable).resolve(strict=True)
        distribution = binary.parent.parent
        package = json.loads((distribution / "package.json").read_bytes())
        entry = package.get("bin", {}).get("hypit")
        if (package.get("name") != "@hypit/hypit" or package.get("version") != "0.2.7"
                or not isinstance(entry, str) or (distribution / entry).resolve() != binary):
            raise OutputReceiptError("Hypit executable is not the verified parser distribution")
        for relative, expected in PINNED_SOURCES.items():
            if hashlib.sha256((distribution / relative).read_bytes()).hexdigest() != expected:
                raise OutputReceiptError("Installed Hypit parser changed; the fixed profile cannot be reinterpreted")
        node = (distribution.parents[3] / "bin/node").resolve(strict=True)
        env = cli._environment()
        version = subprocess.run([str(node), "--version"], capture_output=True, timeout=10,
                                 check=True, env=env).stdout.decode("ascii").strip()
        bridge = Path(__file__).with_name("native_parser.mjs")
        return {"profile": PROFILE, "version": package["version"], "node_version": version,
                "node_sha256": hashlib.sha256(node.read_bytes()).hexdigest(),
                "loader_policy": {"tsconfig": False, "disk_cache": False},
                "distribution": str(distribution), "executable": str(binary), "node": str(node),
                "source_sha256": PINNED_SOURCES,
                "adapter_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                "bridge_sha256": hashlib.sha256(bridge.read_bytes()).hexdigest()}
    except (OSError, ValueError, UnicodeError, subprocess.SubprocessError) as exc:
        raise OutputReceiptError("The installed native parser cannot be verified; recover locally") from exc


def _parse(snapshots, kinds, identity):
    payload = {"profile": PROFILE, "distribution_root": identity["distribution"],
               "sources": [{"name": source.name, "text": source.text, "sha256": source.sha256, "kind": kind}
                           for source, kind in zip(snapshots, kinds, strict=True)]}
    raw = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode()
    if len(raw) > 4 * 1024 * 1024:
        raise OutputReceiptError("Native source bundle exceeds the fixed parser capacity")
    try:
        parser_env = HypitCLI()._environment()
        parser_env["TSX_DISABLE_CACHE"] = "1"
        result = subprocess.run([identity["node"], str(Path(__file__).with_name("native_parser.mjs"))],
            input=raw, cwd=Path(__file__).parent, env=parser_env,
            capture_output=True, timeout=30, check=False)
        if len(result.stdout) > MAX_RESPONSE_BYTES:
            raise OutputReceiptError("Native parser response exceeds its fixed capacity")
        data = json.loads(result.stdout.decode("utf-8"))
    except (OSError, ValueError, UnicodeError, subprocess.SubprocessError) as exc:
        raise OutputReceiptError("Native parser execution failed locally") from exc
    if not isinstance(data, dict) or type(data.get("ok")) is not bool:
        raise OutputReceiptError("Native parser returned a malformed result envelope")
    if data.get("schema") != PROFILE:
        raise OutputReceiptError("Native parser returned an unknown protocol")
    if not data.get("ok"):
        error = data.get("error", {})
        if not isinstance(error, dict) or any(not isinstance(error.get(key), str) for key in ("kind", "code", "message")):
            raise OutputReceiptError("Native parser returned a malformed diagnostic")
        if error.get("kind") == "bootstrap":
            raise OutputReceiptError("Native parser bootstrap failed: " + str(error.get("code")))
        raise NativeSourceError(error)
    if not isinstance(data.get("sources"), list) or any(not isinstance(row, dict) for row in data["sources"]):
        raise OutputReceiptError("Native parser returned malformed source results")
    if (result.returncode or data.get("parser") != {
            "version": identity["version"], "node_version": identity["node_version"],
            "node_sha256": identity["node_sha256"], "loader_policy": identity["loader_policy"],
            "source_sha256": identity["source_sha256"]} or len(data.get("sources", [])) != len(snapshots)):
        raise OutputReceiptError("Native parser identity or source result count changed")
    for expected, kind, parsed in zip(snapshots, kinds, data["sources"], strict=True):
        if (parsed.get("name"), parsed.get("sha256"), parsed.get("kind")) != (expected.name, expected.sha256, kind):
            raise OutputReceiptError("Native parser result lost its original source binding")
    return data["sources"]


@dataclass(frozen=True)
class Snapshot:
    name: str
    raw: bytes

    def __post_init__(self):
        if len(self.raw) > MAX_SOURCE_BYTES:
            raise OutputReceiptError("Native source exceeds its captured byte capacity")
        try:
            text = self.raw.decode("utf-8")
        except UnicodeError as exc:
            raise NativeSourceError({"code": "SOURCE_UTF8", "message": "Source is not strict UTF-8", "source": self.name}) from exc
        offsets, code_units, byte_offset = {0: 0}, 0, 0
        for char in text:
            code_units += 2 if ord(char) > 0xffff else 1
            byte_offset += len(char.encode("utf-8"))
            offsets[code_units] = byte_offset
        object.__setattr__(self, "text", text)
        object.__setattr__(self, "sha256", hashlib.sha256(self.raw).hexdigest())
        object.__setattr__(self, "_offsets", offsets)

    def span(self, value):
        if (not isinstance(value, dict) or set(value) != {"start", "end"}
                or any(type(value[k]) is not int or value[k] not in self._offsets for k in ("start", "end"))
                or value["start"] > value["end"]):
            raise OutputReceiptError("Native source location is not a complete UTF-16 scalar boundary")
        return {"unit": "utf8-byte", "start": self._offsets[value["start"]], "end": self._offsets[value["end"]],
                "source_sha256": self.sha256}

    def slice(self, value):
        position = self.span(value)
        return self.raw[position["start"]:position["end"]].decode("utf-8")


@dataclass(frozen=True)
class Reference:
    path: str


@dataclass(frozen=True, eq=False)
class Text:
    value: str
    range: dict


@dataclass(frozen=True, eq=False)
class Element:
    name: str
    attributes: object
    children: tuple
    range: dict
    opening_range: dict
    attribute_ranges: object
    self_closing: bool
    module: str
    local_name: str
    source: Snapshot

    def literal(self, key, default=None):
        value = self.attributes.get(key, default)
        if value is not None and not isinstance(value, str):
            _error("EASEL_EXPECTED_LITERAL", "Expected literal attribute " + key, self.source, self.range)
        return value

    def ref(self, key):
        value = self.attributes.get(key)
        return value if isinstance(value, Reference) else None

    def __iter__(self):
        return (child for child in self.children if isinstance(child, Element))

    def iter(self):
        yield self
        for child in self:
            yield from child.iter()

    def references(self):
        for child in self.iter():
            for value in child.attributes.values():
                if isinstance(value, Reference):
                    yield value


class Document:
    def __init__(self, source, parsed, sheets, identity, workspace):
        self.source, self.identity, self.workspace = source, identity, Path(workspace)
        self.imports, self.scope, self.sheets = parsed["discovery"]["imports"], {}, sheets
        self.aliases = {i["alias"] for i in self.imports if "alias" in i}
        for entry in self.imports:
            source.span(entry["range"])
            if entry["kind"] != "module":
                continue
            for tag in SURFACES[entry["from"]]:
                name = (entry["alias"] + ":" if entry.get("alias") is not None else "") + tag
                if name in self.scope:
                    _error("EASEL_SURFACE_COLLISION", "Imported structured surfaces collide", source, entry["range"])
                self.scope[name] = (entry["from"].rsplit("@", 1)[0], tag)
        ast = parsed["ast"]
        if ast["name"] != "svml" or ast["attributes"]:
            _error("EASEL_ROOT", "Expected an attribute-free native svml root", source, ast["range"])
        seen_body, declared = False, []
        for child in ast["children"]:
            if child["kind"] == "text":
                continue
            if child["name"] == "import":
                if seen_body or not child["selfClosing"]:
                    _error("EASEL_IMPORT_AFTER_BODY", "Imports must be self-closing declarations in the native prologue", source, child["range"])
                declared.append(child["range"])
            else:
                seen_body = True
        if declared != [entry["range"] for entry in self.imports]:
            _error("EASEL_IMPORT_COVERAGE", "Complete AST imports differ from native discovery", source)
        self.parents, self.nodes = {}, {}

        def build(node, owner=None, parent_kind=None, top=False):
            source.span(node["range"])
            if node["kind"] == "text":
                return Text(node["value"], node["range"])
            name = node["name"]
            if top and name == "import":
                kind = ("", "import")
            elif top:
                kind = self.scope.get(name)
                if kind is None:
                    _error("EASEL_SURFACE_UNSUPPORTED", "Unbound top-level structured surface", source, node["range"])
            elif owner is None:
                kind = ("", "svml")
            else:
                local = name.rsplit(":", 1)[-1]
                if local not in NESTED.get(parent_kind, set()):
                    _error("EASEL_NESTED_UNSUPPORTED", "Nested form is outside the verified Easel profile", source, node["range"])
                kind = (owner, local)
            attributes = {}
            for key, value in node["attributes"].items():
                if isinstance(value, str):
                    attributes[key] = value
                elif isinstance(value, dict) and set(value) == {"kind", "path"} and value["kind"] == "reference":
                    attributes[key] = Reference(value["path"])
                else:
                    raise OutputReceiptError("Native attribute value lost its typed representation")
            for position in node.get("attributeValueRanges", {}).values():
                source.span(position)
            opening = node["openingRange"]
            source.span(opening)
            children = tuple(build(child, kind[0], kind, top=kind == ("", "svml")) for child in node["children"])
            element = Element(name, MappingProxyType(attributes), children, node["range"], opening,
                              MappingProxyType(node.get("attributeValueRanges", {})), node["selfClosing"], *kind, source)
            for child in element:
                self.parents[child] = element
            identity_value = element.literal("id")
            if identity_value:
                if identity_value in self.nodes:
                    _error("EASEL_DUPLICATE_ID", "Duplicate native element identity", source, node["range"])
                self.nodes[identity_value] = element
            return element

        self.root = build(ast)
        self.elements = tuple(child for child in self.root if child.local_name != "import")
        if any(isinstance(child, Text) and child.value.strip() for child in self.root.children):
            _error("EASEL_ROOT_TEXT", "Top-level source body must contain structured elements", source)
        if any(key == alias or key.startswith(alias + ".") for key in self.nodes for alias in sheets):
            _error("EASEL_REFERENCE_COLLISION", "Local IDs overlap captured source alias paths", source)
        self.sources = {source.name: source, **{sheet[0].name: sheet[0] for sheet in sheets.values()}}
        self.source_identity = {"profile": PROFILE, "parser": identity, "sources": [
            {"name": item.name, "sha256": item.sha256, "bytes": len(item.raw)}
            for item in sorted(self.sources.values(), key=lambda item: item.name)]}

    @staticmethod
    def kind(element):
        return element.module, element.local_name

    def iter(self):
        return self.root.iter()

    def find(self, module, name):
        return [element for element in self.iter() if self.kind(element) == (module, name)]

    def one(self, module, name):
        found = self.find(module, name)
        if len(found) != 1:
            _error("EASEL_GRAPH_UNIQUENESS", "Expected exactly one " + module + ":" + name, self.source)
        return found[0]

    def target(self, reference, *, required=False):
        result = None
        if isinstance(reference, Reference):
            matches = [key for key in self.nodes if reference.path == key or reference.path.startswith(key + ".")]
            result = self.nodes[max(matches, key=len)] if matches else None
        if required and result is None:
            _error("EASEL_REFERENCE_UNRESOLVED", "A required typed local reference has no captured target", self.source)
        return result

    def recipe(self, reference):
        if not isinstance(reference, Reference):
            _error("EASEL_RECIPE_REFERENCE", "Recipe must be a typed reference", self.source)
        alias, separator, selector = reference.path.partition(".")
        if not separator or alias not in self.sheets:
            _error("EASEL_RECIPE_REFERENCE", "Recipe alias has no captured local source", self.source)
        snapshot, parsed = self.sheets[alias]
        recipes = [row for row in parsed["ast"]["recipes"] if row["value"]["path"] == selector]
        if len(recipes) != 1:
            _error("EASEL_RECIPE_UNRESOLVED", "Recipe path is absent from its captured SVS source", snapshot)
        recipe = recipes[0]
        snapshot.span(recipe["range"])
        for prop in recipe["properties"]:
            snapshot.span(prop["range"])
            snapshot.span(prop["valueRange"])
        return recipe["value"]["properties"]

    def name_for(self, module, tag):
        names = [name for name, kind in self.scope.items() if kind == (module, tag)]
        if len(names) != 1:
            _error("EASEL_GENERATED_ALIAS", "Generated component needs one unambiguous imported surface", self.source)
        return names[0]

    def nested_name(self, parent, tag):
        if tag not in NESTED.get(self.kind(parent), set()):
            _error("EASEL_NESTED_UNSUPPORTED", "Generated nested form is unsupported", self.source)
        return parent.name.rsplit(":", 1)[0] + ":" + tag if ":" in parent.name else tag

    def replaced(self, changes):
        positions = []
        for span, replacement in changes:
            position = self.source.span(span)
            positions.append((position["start"], position["end"], replacement.encode("utf-8")))
        positions.sort(key=lambda row: (row[0], row[1]))
        if any(left[1] > right[0] for left, right in zip(positions, positions[1:])):
            raise OutputReceiptError("Native candidate transformations overlap")
        raw = self.source.raw
        for start, end, replacement in reversed(positions):
            raw = raw[:start] + replacement + raw[end:]
        return raw.decode("utf-8")


def verify_audio_support(workspace, *, required=True):
    expected = Path(__file__).with_name("native_audio")
    for name in ("package.json", "activation.mjs", "envelope.mjs"):
        path = _safe(workspace, Path(workspace) / "packages/audio-mix" / name)
        try:
            if not path.exists() and not required:
                continue
            if path.read_bytes() != (expected / name).read_bytes():
                raise OutputReceiptError("Native audio support differs from its checked-in source")
        except OSError as exc:
            raise OutputReceiptError("Native audio support is unavailable") from exc


def parse_text(text, path, *, workspace=None, identity=None, require_support=True):
    path = Path(path)
    workspace = Path(workspace) if workspace is not None else workspace_for(path)
    path = _safe(workspace, path)
    source = Snapshot(path.relative_to(workspace).as_posix(), text.encode("utf-8"))
    identity = identity or installed_parser()
    parsed = _parse([source], ["markup"], identity)[0]
    imports = parsed["discovery"]["imports"]
    if any(item["from"] == "@easel/audio-mix@1" for item in imports):
        verify_audio_support(workspace, required=require_support)
    unique, aliases = {}, {}
    for item in imports:
        if item["kind"] == "source":
            source_path = path.parent / Path(item["from"])
            name = source_path.relative_to(workspace).as_posix()
            if name not in unique:
                unique[name] = read_source(source_path, workspace)
            aliases[item["alias"]] = name
    sources = list(unique.values())
    recipes = _parse(sources, ["svs"] * len(sources), identity) if sources else []
    parsed_sheets = {snapshot.name: (snapshot, syntax) for snapshot, syntax in zip(sources, recipes, strict=True)}
    sheets = {alias: parsed_sheets[name] for alias, name in aliases.items()}
    return Document(source, parsed, sheets, identity, workspace)


def parse_file(path, *, workspace=None, identity=None, require_support=True):
    path = Path(path)
    workspace = Path(workspace) if workspace is not None else workspace_for(path)
    source = read_source(path, workspace)
    return parse_text(source.text, path, workspace=workspace, identity=identity, require_support=require_support)


def parse_run(path, *, workspace=None, identity=None):
    path = Path(path)
    workspace = Path(workspace) if workspace is not None else path.parent
    source = read_source(path, workspace)
    identity = identity or installed_parser()
    parsed = _parse([source], ["run"], identity)[0]
    return source, parsed["ast"]["document"], identity
