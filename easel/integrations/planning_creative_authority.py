"""D1 bounded Director Claim carrier for current New-Only Planning.

New Attempts may explicitly freeze OWNER_POLICY in the *existing* Planning
Owner; earlier prototype helpers remain pure and testable. No independent
model dispatcher, Rights/Creator grant, new Repair budget, Material Domain
extension, second workflow Owner or auto-enabled production rollout. Native
Planning capture/Journal owns original A/Repair tool bytes and SHA.
"""
from __future__ import annotations

from copy import deepcopy

from jsonschema import Draft202012Validator

from easel.integrations import planning_authority as authority
from easel.integrations import planning_candidate_review as candidate_review
from easel.integrations import planning_semantic_review as semantic_review
from easel.integrations.semantic_planning import source_catalog

POLICY = "planning-creative-delegation-prototype@1"
CLAIM_POLICY = "planning-visual-claim-wire-prototype@2"
REPAIR_POLICY = "planning-shared-repair-claim-wire-prototype@1"
VISUAL = frozenset({"image", "video"})
CLAIM_KINDS = (
    "confirmed_obligation", "frozen_director_rule",
    "director_local_choice", "creative_preference",
)
ALLOWED = ("visual_composition", "shot_execution", "editing_expression",
           "bounded_visual_continuity", "aesthetic_choice")
DENIED = ("change_confirmed_script_or_scenes", "invent_factual_claim_or_person_identity",
          "assert_rights_or_asset_available", "change_paid_or_publish_authority")


def digest(value):
    return authority.digest(value)


def compile_envelope(attempt, canonical, planning_context, mode,
                     *, allow_missing_canonical=False):
    """Compile a scope from verified frozen originals, never model authority."""
    inputs = authority.load_inputs(
        attempt, canonical, planning_context, mode,
        allow_missing_canonical=allow_missing_canonical,
    )
    proposal = inputs.get("proposal")
    if not isinstance(proposal, dict) or proposal.get("schema") != "easel-video-proposal@4":
        raise ValueError("Only current confirmed Proposal @4 can delegate")
    refs = planning_context["context_refs"]
    if not isinstance(refs, dict) or not refs.get("creative_mode_sha256"):
        raise ValueError("Missing frozen Creative Mode identity")
    catalog = source_catalog(canonical, {
        "creator_context": inputs["creator_context"], "proposal": proposal,
    })
    source_refs = {name: sorted(catalog.get(name, {}))
                   for name in ("global", "scene", "segment", "event")}
    context = {
        "creation_id": attempt["creation_id"], "attempt_id": attempt["attempt_id"],
        "proposal_sha256": proposal["sha256"],
        "handoff_sha256": inputs["handoff_sha256"],
        "creative_mode_sha256": refs["creative_mode_sha256"],
        "mode_documents_sha256": digest(inputs["mode_documents"]),
        "confirmed_sha256": digest(inputs["confirmed"]),
        "context_refs_sha256": digest(refs),
        "creator_context_sha256": digest(inputs["creator_context"]),
        "truth_packet_sha256": digest(inputs["truth_packet"]),
        "source_catalog_sha256": digest(catalog),
    }
    scope = {
        "policy": POLICY,
        "context": context,
        "source_refs": source_refs,
        "allowed": list(ALLOWED),
        "denied": list(DENIED),
    }
    return {**scope, "scope_ref": digest(scope)}


def _envelope(envelope):
    if (not isinstance(envelope, dict) or set(envelope) != {
        "policy", "context", "source_refs", "allowed", "denied", "scope_ref"
    } or envelope["policy"] != POLICY or envelope["allowed"] != list(ALLOWED)
            or envelope["denied"] != list(DENIED)
            or not isinstance(envelope["context"], dict)
            or not all(isinstance(v, str) and v for v in envelope["context"].values())
            or set(envelope["context"]) != {
                "creation_id", "attempt_id", "proposal_sha256", "handoff_sha256",
                "creative_mode_sha256", "mode_documents_sha256", "confirmed_sha256",
                "context_refs_sha256", "creator_context_sha256", "truth_packet_sha256",
                "source_catalog_sha256",
            } or not isinstance(envelope["source_refs"], dict)
            or set(envelope["source_refs"]) != {"global", "scene", "segment", "event"}
            or any(not isinstance(v, list) or any(not isinstance(x, str) for x in v)
                   for v in envelope["source_refs"].values())
            or digest({k: v for k, v in envelope.items() if k != "scope_ref"}) != envelope["scope_ref"]):
        raise ValueError("Unverified or changed creative delegation envelope")


def _claim_schema(scope, *, allowed_refs=None):
    """The Need source is program-bound; this model ref is a frozen *basis*.

    Legacy pure carriers may require the same ref by default. The current
    New-Only Owner explicitly supplies the frozen source catalog instead.
    """
    ref_rule = ({"type": "string", "const": scope} if allowed_refs is None else
                {"type": "string", "enum": sorted(set(allowed_refs))})
    return {
        "type": "object", "additionalProperties": False,
        "properties": {
            "claimed_kind": {"type": "string", "enum": list(CLAIM_KINDS)},
            "creative_goal_ref": ref_rule,
            "reason": {"type": "string", "minLength": 8, "maxLength": 512},
            "claimed_strength": {"type": "string", "enum": ["required", "preference"]},
        },
        "required": ["claimed_kind", "creative_goal_ref", "reason", "claimed_strength"],
    }


def _check_claim(claim, condition, scope, schema):
    Draft202012Validator(schema).validate(claim)
    if (claim["claimed_strength"] != condition["strength"]
            or claim["claimed_kind"] == "creative_preference"
            and condition["strength"] != "preference"):
        raise ValueError("Claim strength, scope or declared authority conflicts with condition")
    # Other claimed_kind values remain proposed by A. They are never independently
    # accepted as confirmed facts, Mode requirements, Creator authorization or Rights.


class VisualClaimCarrier:
    """Opt-in temporary overlay over the EXISTING staged A-details wire.

    It does not change StagedProposal, SemanticProposal or the model dispatch.
    """
    def __init__(self, staged, selection, envelope):
        _envelope(envelope)
        self.envelope = deepcopy(envelope)
        self.staged = staged
        self.selection = deepcopy(selection)
        base = staged.details_contract(selection)
        self.base_identity = deepcopy(base["identity"])
        self.schema = deepcopy(base["schema"])
        self.visual_slots = {}
        for i, header in enumerate(selection["needs"]):
            if header["scope"] not in {x for choices in envelope["source_refs"].values() for x in choices}:
                raise ValueError("Need source is outside frozen authority")
            if header["modality"] not in VISUAL:
                continue
            slot = f"slot_{i:03d}"
            row = self.schema["properties"]["slots"]["properties"][slot]
            condition = row["properties"]["conditions"]["items"]
            if not condition.get("additionalProperties") is False:
                raise ValueError("Visual condition schema must remain closed")
            condition["properties"]["claim"] = _claim_schema(
                header["scope"], allowed_refs=_frozen_source_refs(self.envelope))
            condition["required"] = [*condition["required"], "claim"]
            self.visual_slots[slot] = (i, header["scope"])
        Draft202012Validator.check_schema(self.schema)
        self.identity = {
            "policy": CLAIM_POLICY, "envelope_scope_ref": envelope["scope_ref"],
            "selection_sha256": digest(selection),
            "base_identity_sha256": digest(base["identity"]),
            "wire_schema_sha256": digest(self.schema),
        }

    def decode(self, raw, identity):
        if identity != self.identity:
            raise ValueError("A details wire identity changed")
        Draft202012Validator(self.schema).validate(raw)
        details = deepcopy(raw)
        claims = {}
        for slot, (need_index, scope) in self.visual_slots.items():
            for i, condition in enumerate(details["slots"][slot]["conditions"]):
                claim = condition.pop("claim")
                _check_claim(claim, condition, scope, _claim_schema(
                    scope, allowed_refs=_frozen_source_refs(self.envelope)))
                path = f"needs/{need_index}/conditions/{i}"
                claims[path] = {
                    "claim": deepcopy(claim),
                    "need_source_ref": scope,
                    "condition_sha256": digest(condition),
                    "scope_ref": self.envelope["scope_ref"],
                    "path": path,
                    "record_sha256": digest({
                        "scope_ref": self.envelope["scope_ref"], "path": path,
                        "need_source_ref": scope,
                        "condition": condition, "claim": claim,
                        "selection_sha256": self.identity["selection_sha256"],
                    }),
                }
        # Full original closed A carrier/canonical admission: no pop-and-ignore
        # of unknown fields and no altered MaterialNeed contract.
        canonical = self.staged.assemble(self.selection, details, self.base_identity)
        return canonical, details, claims

    def encode(self, details, claims):
        """Only encode caller-supplied claims, never infer missing model claims."""
        rows = deepcopy(details)
        paths = {f"needs/{ni}/conditions/{ci}"
                 for slot, (ni, _) in self.visual_slots.items()
                 for ci in range(len(details["slots"][slot]["conditions"]))}
        if set(claims) != paths:
            raise ValueError("Claim coverage does not equal original visual conditions")
        for slot, (ni, _) in self.visual_slots.items():
            for ci, condition in enumerate(rows["slots"][slot]["conditions"]):
                condition["claim"] = deepcopy(claims[f"needs/{ni}/conditions/{ci}"])
        # Check via decoder before emitting; this is just a test-only round trip.
        self.decode(rows, self.identity)
        return rows


class AtomicSharedRepairCarrier:
    """D1 prototype overlay on SAME existing B Shared Repair target slots.

    Supports visual complete_obligation targets only. Other target kinds are
    deliberately rejected until reviewed in D2; does not create Repair calls.
    """
    def __init__(self, envelope, original, targets, claims):
        _envelope(envelope)
        if (not isinstance(original, dict) or not isinstance(targets, list)
                or not 1 <= len(targets) <= 16 or len({tuple(t.get("path", ())) for t in targets}) != len(targets)):
            raise ValueError("Invalid or duplicate frozen Repair targets")
        self.envelope = deepcopy(envelope)
        self.original = deepcopy(original)
        self.targets = deepcopy(targets)
        self.claims = deepcopy(claims)
        self.mapping = {}
        schema = candidate_review.patch_schema(targets, slots=True)
        self.schema = deepcopy(schema)
        for i, target in enumerate(targets):
            if target.get("kind") != "complete_obligation":
                raise ValueError("Prototype cannot alter other/shared Repair categories")
            path = target.get("path")
            if (not isinstance(path, list) or len(path) != 2
                    or any(type(x) is not int for x in path)):
                raise ValueError("Repair target identity must be concrete condition index")
            ni, ci = path
            try:
                need = original["needs"][ni]
                before = need["conditions"][ci]
            except (IndexError, KeyError, TypeError):
                raise ValueError("Repair path outside original candidate") from None
            if need["modality"] not in VISUAL:
                raise ValueError("Only visual conditions may receive creative claims")
            key = f"needs/{ni}/conditions/{ci}"
            old = claims.get(key)
            if (not isinstance(old, dict) or old.get("condition_sha256") != digest(before)
                    or old.get("scope_ref") != envelope["scope_ref"]
                    or old.get("path") != key):
                raise ValueError("Repair target lost its original claim binding")
            slot = f"target-{i:04d}"
            row = self.schema["properties"][slot]
            if row.get("additionalProperties") is not False:
                raise ValueError("Shared Repair is not a closed condition")
            row["properties"]["claim"] = _claim_schema(need["scope"])
            row["required"] = [*row["required"], "claim"]
            self.mapping[slot] = (key, need["scope"])
        Draft202012Validator.check_schema(self.schema)
        self.identity = {
            "policy": REPAIR_POLICY, "envelope_scope_ref": envelope["scope_ref"],
            "original_sha256": digest(original), "targets_sha256": digest(targets),
            "prior_claims_sha256": digest(claims), "schema_sha256": digest(self.schema),
        }

    def apply(self, wire, identity):
        if identity != self.identity:
            raise ValueError("Repair version or frozen targets changed")
        Draft202012Validator(self.schema).validate(wire)
        canonical_slots = deepcopy(wire)
        updated = deepcopy(self.claims)
        for slot, (key, scope) in self.mapping.items():
            original_item = canonical_slots[slot]
            claim = original_item.pop("claim")
            _check_claim(claim, original_item, scope, _claim_schema(scope))
            ni, ci = map(int, key.split("/")[1::2])
            updated[key] = {
                "claim": deepcopy(claim), "condition_sha256": digest(original_item),
                "scope_ref": self.envelope["scope_ref"], "path": key,
                "record_sha256": digest({
                    "scope_ref": self.envelope["scope_ref"], "path": key,
                    "condition": original_item, "claim": claim,
                    "repair_identity": self.identity,
                }),
            }
        patch = candidate_review.decode_patch_slots(canonical_slots, self.targets)
        # Original canonical repair rules operate with the SAME slots and values.
        candidate = candidate_review.apply_patches(self.original, patch, self.targets)
        for slot, (key, _) in self.mapping.items():
            ni, ci = map(int, key.split("/")[1::2])
            if candidate["needs"][ni]["conditions"][ci] != canonical_slots[slot]:
                raise ValueError("Canonical Repair disagrees with claimed replacement")
        # Atomic local result only. Caller must persist original bytes+new claims
        # together and invalidate B; this prototype never writes a checkpoint.
        return candidate, updated, {
            "base": self.identity, "original_wire_sha256": digest(wire),
            "patched_candidate_sha256": digest(candidate),
            "updated_claims_sha256": digest(updated),
            "recheck_required": True, "decision": "PENDING_B_REVIEW",
        }


# Extended D1 *offline* policies are separate from the preceding accepted
# single-condition prototype. Nothing in Production Owner imports these.
HEADER_POLICY = "planning-visual-header-wire-prototype@2"
MULTI_REPAIR_POLICY = "planning-visual-mixed-repair-prototype@2"
COLD_POLICY = "planning-creative-cold-receipt-prototype@1"


def _header_fields(need):
    return {name: deepcopy(need[name])
            for name in ("scope", "role", "modality", "necessity", "continuity_choices")}


def _header_claim_schema(scope, necessity, continuity, *, allowed_refs=None):
    ref_rule = ({"type": "string", "const": scope} if allowed_refs is None else
                {"type": "string", "enum": sorted(set(allowed_refs))})
    return {"type": "object", "additionalProperties": False,
            "properties": {
                "claimed_kind": {"type": "string", "enum": list(CLAIM_KINDS)},
                "creative_goal_ref": ref_rule,
                "reason": {"type": "string", "minLength": 8, "maxLength": 512},
                "claimed_necessity": {"type": "string", "const": necessity},
                "continuity_choices_sha256": {"type": "string", "const": digest(continuity)},
            },
            "required": ["claimed_kind", "creative_goal_ref", "reason",
                         "claimed_necessity", "continuity_choices_sha256"]}


def _frozen_source_refs(envelope):
    """Only actual frozen Proposal source refs; never model-supplied IDs."""
    return {ref for group in envelope["source_refs"].values() for ref in group}


def _verify_header_claim(claim, need, envelope):
    if need["modality"] not in VISUAL:
        raise ValueError("Only visual Header may carry Director claim")
    sources = _frozen_source_refs(envelope)
    if need["scope"] not in sources:
        raise ValueError("Unregistered frozen scene for visual Header")
    Draft202012Validator(_header_claim_schema(
        need["scope"], need["necessity"], need["continuity_choices"],
        allowed_refs=sources)).validate(claim)
    # Claim remains a proposal. Model assertions of confirmed_obligation or
    # frozen_director_rule are not proven by this syntactic check.


class VisualHeaderClaimCarrier:
    """A-selection-only wire overlay; no extra model invocation.

    Header necessity and continuity have independent B review questions.
    The same A model call may propose a reason, but never Creator authority.
    """
    def __init__(self, staged, envelope):
        _envelope(envelope)
        self.staged = staged
        self.envelope = deepcopy(envelope)
        self.schema = deepcopy(staged.selection_schema)
        item = self.schema["properties"]["needs"]["items"]
        item["properties"]["header_claim"] = {
            "type": "object", "additionalProperties": False,
            "properties": {
                "claimed_kind": {"type": "string", "enum": list(CLAIM_KINDS)},
                "creative_goal_ref": {"type": "string", "enum": sorted(_frozen_source_refs(envelope))},
                "reason": {"type": "string", "minLength": 8, "maxLength": 512},
                "claimed_necessity": {"type": "string", "enum": ["required", "optional"]},
                "continuity_choices_sha256": {"type": "string", "pattern": "^[a-f0-9]{64}$"},
            },
            "required": ["claimed_kind", "creative_goal_ref", "reason",
                         "claimed_necessity", "continuity_choices_sha256"],
        }
        item["allOf"] = [{
            "if": {"properties": {"modality": {"enum": sorted(VISUAL)}},
                   "required": ["modality"]},
            "then": {"required": ["header_claim"]},
            "else": {"not": {"required": ["header_claim"]}},
        }]
        Draft202012Validator.check_schema(self.schema)
        self.identity = {"policy": HEADER_POLICY,
                         "envelope_scope_ref": envelope["scope_ref"],
                         "original_schema_sha256": digest(staged.selection_schema),
                         "wire_schema_sha256": digest(self.schema)}

    def decode(self, raw, identity):
        if identity != self.identity:
            raise ValueError("A Header frozen identity changed")
        Draft202012Validator(self.schema).validate(raw)
        selection = deepcopy(raw)
        records = {}
        for index, need in enumerate(selection["needs"]):
            if need["modality"] not in VISUAL:
                continue
            claim = need.pop("header_claim")
            _verify_header_claim(claim, need, self.envelope)
            path = f"needs/{index}/header"
            records[path] = {
                "path": path, "scope_ref": self.envelope["scope_ref"],
                "header_sha256": digest(_header_fields(need)),
                "need_source_ref": need["scope"],
                "claim": deepcopy(claim),
                "record_sha256": digest({
                    "policy": HEADER_POLICY, "path": path,
                    "scope_ref": self.envelope["scope_ref"],
                    "need_source_ref": need["scope"],
                    "header": _header_fields(need), "claim": claim,
                }),
            }
        Draft202012Validator(self.staged.selection_schema).validate(selection)
        return selection, records

    def encode(self, selection, claims):
        Draft202012Validator(self.staged.selection_schema).validate(selection)
        expected = {f"needs/{i}/header" for i, need in enumerate(selection["needs"])
                    if need["modality"] in VISUAL}
        if set(claims) != expected:
            raise ValueError("Missing or extra visual Header claim")
        wire = deepcopy(selection)
        for i, need in enumerate(wire["needs"]):
            if need["modality"] in VISUAL:
                need["header_claim"] = deepcopy(claims[f"needs/{i}/header"])
        self.decode(wire, self.identity)
        return wire




def _bounded_claim_schema(envelope, *, header=False):
    """Finite Wire-only authority candidate domain; never a model-signed scope."""
    scopes = sorted({ref for group in envelope["source_refs"].values() for ref in group})
    if not scopes:
        raise ValueError("No frozen sources for bounded visual Claim")
    fields = {
        "claimed_kind": {"type": "string", "enum": list(CLAIM_KINDS)},
        "creative_goal_ref": {"type": "string", "enum": scopes},
        "reason": {"type": "string", "minLength": 8, "maxLength": 512},
    }
    # Header necessity and continuity digest are deterministic properties of
    # the actual new/repaired Need. Do not ask an LLM to echo them or invent SHA.
    if not header:
        fields["claimed_strength"] = {"type": "string", "enum": ["required", "preference"]}
    return {"type": "object", "additionalProperties": False,
            "properties": fields, "required": list(fields)}


def _original_target_identity(targets):
    """Stable digest of original approved repair identities, incl. typed leaves."""
    from pydantic import TypeAdapter
    normalized = deepcopy(targets)
    for target in normalized:
        if "annotation" in target:
            annotation = target.pop("annotation")
            target["annotation_schema_sha256"] = digest(TypeAdapter(annotation).json_schema())
    return digest(normalized)
class ExtendedSharedRepairCarrier:
    """D1 dry-run: preserve each existing bounded Shared Repair value contract.

    Only visual complete_obligation, visual_choices, frozen_visual_coverage
    receive creative claims. Confirmed_necessity is *program-derived* from
    original B judgment, not from an A claim; other original repair kinds
    preserve their schemas and do not gain Director authority.
    """
    def __init__(self, envelope, original, targets, condition_claims, header_claims):
        _envelope(envelope)
        if not isinstance(targets, list) or not 1 <= len(targets) <= 16:
            raise ValueError("Shared Repair target capacity invalid")
        if any(not isinstance(t, dict) or "path" not in t or "kind" not in t
               for t in targets):
            raise ValueError("Original Repair target identity malformed")
        if len({digest({"kind": t["kind"], "path": t["path"]}) for t in targets}) != len(targets):
            raise ValueError("Duplicate Shared Repair target")
        self.envelope = deepcopy(envelope)
        self.original = deepcopy(original)
        self.targets = deepcopy(targets)
        self.condition_claims = deepcopy(condition_claims)
        self.header_claims = deepcopy(header_claims)
        self.schema = deepcopy(candidate_review.patch_schema(targets, slots=True))
        self.visual_slots = {}
        self.program_slots = {}
        self.passive_slots = {}
        original_needs = original.get("needs") if isinstance(original, dict) else None
        if any(t["kind"] == "candidate_answer" for t in targets) and any(
                t["kind"] != "candidate_answer" for t in targets):
            raise ValueError("B answer correction cannot rewrite an A candidate")
        for i, target in enumerate(targets):
            kind = target["kind"]
            slot = f"target-{i:04d}"
            if kind not in {"complete_obligation", "visual_choices", "frozen_visual_coverage",
                            "confirmed_necessity", "candidate_answer", "confirmed_music_coverage",
                            "structural_leaf", "answer"}:
                raise ValueError("Unsupported Repair category cannot gain authority")
            if kind in {"complete_obligation", "visual_choices", "frozen_visual_coverage"}:
                if not isinstance(original_needs, list):
                    raise ValueError("No visual candidate for creative repair")
                target_path = target["path"]
                if kind != "frozen_visual_coverage":
                    if (not isinstance(target_path, list) or len(target_path) != 2
                            or type(target_path[0]) is not int or
                            (kind == "complete_obligation" and type(target_path[1]) is not int)):
                        # Visual choices uses a single [need_index] path.
                        if kind != "visual_choices" or not (
                            isinstance(target_path, list) and len(target_path) == 1
                            and type(target_path[0]) is int):
                            raise ValueError("Repair target path has changed")
                    ni = target_path[0]
                    if not 0 <= ni < len(original_needs) or original_needs[ni]["modality"] not in VISUAL:
                        raise ValueError("Repair would modify an unrelated/nonvisual Need")
                    if kind == "complete_obligation":
                        ci = target_path[1]
                        if not 0 <= ci < len(original_needs[ni]["conditions"]):
                            raise ValueError("Condition target out of bounds")
                        key = f"needs/{ni}/conditions/{ci}"
                        old = condition_claims.get(key)
                        if not isinstance(old, dict) or old.get("condition_sha256") != digest(
                                original_needs[ni]["conditions"][ci]) or old.get("scope_ref") != envelope["scope_ref"]:
                            raise ValueError("Missing original Condition claim binding")
                    else:
                        hk = f"needs/{ni}/header"
                        old = header_claims.get(hk)
                        if not isinstance(old, dict) or old.get("header_sha256") != digest(
                                _header_fields(original_needs[ni])) or old.get("scope_ref") != envelope["scope_ref"]:
                            raise ValueError("Missing old Header claim binding")
                field = deepcopy(self.schema["properties"][slot])
                self.schema["properties"][slot] = {
                    "type": "object", "additionalProperties": False,
                    "properties": {
                        "value": field,
                        "authority": {
                            "type": "object", "additionalProperties": False,
                            "properties": {
                                "header_claim": ({"type": "null"} if kind == "complete_obligation"
                                                  else _bounded_claim_schema(envelope, header=True)),
                                "condition_claims": {
                                    "type": "array", "minItems": 1,
                                    "maxItems": 12,
                                    "items": _bounded_claim_schema(envelope),
                                },
                            },
                            "required": ["header_claim", "condition_claims"],
                        },
                    }, "required": ["value", "authority"],
                }
                self.visual_slots[slot] = kind
            elif kind == "confirmed_necessity":
                path = target["path"]
                if (not isinstance(path, list) or len(path) != 3
                        or path[0] != "needs" or path[2] != "necessity"
                        or type(path[1]) is not int or not isinstance(original_needs, list)
                        or not 0 <= path[1] < len(original_needs)
                        or original_needs[path[1]]["modality"] not in VISUAL
                        or original_needs[path[1]]["necessity"] != "optional"):
                    raise ValueError("Program-derived necessity must bind one optional visual Header")
                hk = f"needs/{path[1]}/header"
                record = header_claims.get(hk)
                if (not isinstance(record, dict)
                        or record.get("scope_ref") != envelope["scope_ref"]
                        or record.get("header_sha256") != digest(_header_fields(original_needs[path[1]]))):
                    raise ValueError("Confirmed necessity lost its frozen visual Header identity")
                self.program_slots[slot] = kind
            elif kind == "structural_leaf":
                # Current canonical Repair can fix malformed *representation*,
                # but no value-only patch may silently alter visual HOW/Hard
                # without a new Claim. Do not broaden its permitted targets.
                path = target["path"]
                if (isinstance(path, list) and len(path) >= 3
                        and path[0] == "needs" and type(path[1]) is int
                        and isinstance(original_needs, list)
                        and 0 <= path[1] < len(original_needs)
                        and original_needs[path[1]].get("modality") in VISUAL
                        and path[2] != "queries"):
                    raise ValueError("Visual semantic leaf needs a new Claim; current structural Repair is unsafe")
                self.passive_slots[slot] = kind

            else:
                # Original schema/validator remains responsible for fixing
                # exact B answer, music and structural representation faults.
                self.passive_slots[slot] = kind
        Draft202012Validator.check_schema(self.schema)
        from easel.integrations.planning_result_contract import MAX_RESULT_BYTES, maximum_compact_bytes
        if maximum_compact_bytes(self.schema) > MAX_RESULT_BYTES:
            raise ValueError("Extended Repair Claim schema exceeds original response capacity")
        self.identity = {
            "policy": MULTI_REPAIR_POLICY, "envelope_scope_ref": envelope["scope_ref"],
            "original_sha256": digest(original), "targets_sha256": _original_target_identity(targets),
            "old_condition_claims_sha256": digest(condition_claims),
            "old_header_claims_sha256": digest(header_claims),
            "base_schema_sha256": digest(candidate_review.patch_schema(targets, slots=True)),
            "wire_schema_sha256": digest(self.schema),
        }
    def apply(self, wire, identity):
        if identity != self.identity:
            raise ValueError("Shared Repair version/identity/target changed")
        Draft202012Validator(self.schema).validate(wire)
        canonical_wire = deepcopy(wire)
        updated_conditions = deepcopy(self.condition_claims)
        updated_headers = deepcopy(self.header_claims)
        appended_index = len(self.original['needs']) if isinstance(self.original, dict) and isinstance(self.original.get('needs'), list) else 0
        for slot, kind in self.visual_slots.items():
            payload = canonical_wire[slot]
            value = payload["value"]
            auth = payload["authority"]
            if kind == "complete_obligation":
                target = self.targets[int(slot.split("-")[1])]
                ni, ci = target["path"]
                need = self.original["needs"][ni]
                # The current Condition-only Repair does not re-author a Header.
                if auth["header_claim"] is not None or len(auth["condition_claims"]) != 1:
                    raise ValueError("Condition Repair must carry exactly its own Claim")
                claim = auth["condition_claims"][0]
                _check_claim(claim, value, need["scope"], _claim_schema(
                    need["scope"], allowed_refs=_frozen_source_refs(self.envelope)))
                key = f"needs/{ni}/conditions/{ci}"
                updated_conditions[key] = {
                    "path": key, "scope_ref": self.envelope["scope_ref"],
                    "need_source_ref": need["scope"],
                    "condition_sha256": digest(value), "claim": deepcopy(claim),
                    "record_sha256": digest({"scope_ref": self.envelope["scope_ref"],
                                            "need_source_ref": need["scope"],
                                            "path": key, "value": value, "claim": claim,
                                            "repair_identity": self.identity}),
                }
            else:
                if not isinstance(value, dict) or value.get("modality") not in VISUAL:
                    raise ValueError("Visual Repair must preserve visual modality")
                # The Repair model supplies creative judgment only; it is not
                # capable of minting matching Need identity/SHA evidence.
                model_header = auth["header_claim"]
                if not isinstance(model_header, dict):
                    raise ValueError("Repaired visual Header needs a Director Claim")
                auth["header_claim"] = {
                    **model_header,
                    "claimed_necessity": value["necessity"],
                    "continuity_choices_sha256": digest(value["continuity_choices"]),
                }
                _verify_header_claim(auth["header_claim"], value, self.envelope)
                cond = value.get("conditions")
                if not isinstance(cond, list) or len(cond) != len(auth["condition_claims"]):
                    raise ValueError("Replacement visual Need must supply one Claim per Condition")
                for ci, (condition, claim) in enumerate(zip(cond, auth["condition_claims"], strict=True)):
                    _check_claim(claim, condition, value["scope"], _claim_schema(
                        value["scope"], allowed_refs=_frozen_source_refs(self.envelope)))
                if kind == "visual_choices":
                    ni = self.targets[int(slot.split("-")[1])]["path"][0]
                else:
                    ni = appended_index
                    appended_index += 1
                hk = f"needs/{ni}/header"
                updated_headers[hk] = {
                    "path": hk, "scope_ref": self.envelope["scope_ref"],
                    "header_sha256": digest(_header_fields(value)),
                    "need_source_ref": value["scope"],
                    "claim": deepcopy(auth["header_claim"]),
                    "record_sha256": digest({"scope_ref": self.envelope["scope_ref"],
                                            "path": hk, "need_source_ref": value["scope"],
                                            "header": _header_fields(value),
                                            "claim": auth["header_claim"],
                                            "repair_identity": self.identity}),
                }
                for ci, (condition, claim) in enumerate(zip(cond, auth["condition_claims"], strict=True)):
                    key = f"needs/{ni}/conditions/{ci}"
                    updated_conditions[key] = {
                        "path": key, "scope_ref": self.envelope["scope_ref"],
                        "need_source_ref": value["scope"],
                        "condition_sha256": digest(condition), "claim": deepcopy(claim),
                        "record_sha256": digest({"scope_ref": self.envelope["scope_ref"],
                                                "need_source_ref": value["scope"],
                                                "path": key, "condition": condition,
                                                "claim": claim, "repair_identity": self.identity}),
                    }
            canonical_wire[slot] = deepcopy(value)
        # Each original target is decoded and applied by the existing function,
        # including its exact policy, original B judgment and no-downgrade rules.
        patch = candidate_review.decode_patch_slots(canonical_wire, self.targets)
        result = candidate_review.apply_patches(self.original, patch, self.targets)
        # Validate the complete resulting Claim map *after* program-derived
        # necessity has updated its Header record below.
        for slot in self.program_slots:
            target = self.targets[int(slot.split("-")[1])]
            ni = target["path"][1]
            need = result["needs"][ni]
            hk = f"needs/{ni}/header"
            prior = updated_headers.get(hk)
            # Preserve the Director's separately reviewed proposal for the
            # pre-promotion Header. The necessity upgrade is *only* a verified
            # program-derived judgment, not a new model authorization.
            visual_changed = any(
                self.targets[int(vslot.split("-")[1])]["kind"] == "visual_choices"
                and self.targets[int(vslot.split("-")[1])]["path"] == [ni]
                for vslot in self.visual_slots)
            director_claim = deepcopy(prior.get("claim")) if prior and visual_changed else None
            necessity_evidence = {
                "origin": "program_derived_from_frozen_B_necessity",
                "target_sha256": digest(target),
                "claim_header_sha256": (
                    prior["header_sha256"] if director_claim is not None else None),
                "recheck_required": True,
            }
            updated_headers[hk] = {
                "path": hk, "scope_ref": self.envelope["scope_ref"],
                "header_sha256": digest(_header_fields(need)),
                "need_source_ref": need["scope"],
                "origin": "program_derived_from_frozen_B_necessity",
                "claim": director_claim,
                "necessity_evidence": necessity_evidence,
                "recheck_required": True,
                "record_sha256": digest({
                    "scope_ref": self.envelope["scope_ref"], "path": hk,
                    "need_source_ref": need["scope"],
                    "header": _header_fields(need),
                    "director_claim": director_claim,
                    "necessity_evidence": necessity_evidence,
                    "repair_identity": self.identity,
                }),
            }
        for key, record in updated_headers.items():
            if key.startswith('needs/') and record.get('header_sha256'):
                index = int(key.split('/')[1])
                if index >= len(result['needs']) or record['header_sha256'] != digest(_header_fields(result['needs'][index])):
                    raise ValueError('Shared Repair Header Claim was overwritten or misbound')
        for key, record in updated_conditions.items():
            if key.startswith('needs/') and record.get('condition_sha256'):
                parts = key.split('/')
                index, ci = int(parts[1]), int(parts[3])
                if index >= len(result['needs']) or ci >= len(result['needs'][index]['conditions']) or record['condition_sha256'] != digest(result['needs'][index]['conditions'][ci]):
                    raise ValueError('Shared Repair Condition Claim was overwritten or misbound')
        return result, updated_conditions, updated_headers, {
            "policy": MULTI_REPAIR_POLICY, "wire_sha256": digest(wire),
            "result_sha256": digest(result),
            "condition_claims_sha256": digest(updated_conditions),
            "header_claims_sha256": digest(updated_headers),
            "decision": "PENDING_B_REVIEW", "recheck_required": True,
        }


def freeze_offline_receipt(envelope, identity, wire, verified_result):
    """Serialize exact raw bytes for a throwaway cold-recovery fixture.

    Caller verifies using a *new* compiler built from the original Handoff.
    This cannot be persisted as a production checkpoint.
    """
    import json
    _envelope(envelope)
    raw = json.dumps(wire, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    values = {"policy": COLD_POLICY, "envelope_scope_ref": envelope["scope_ref"],
              "codec_identity": deepcopy(identity), "raw_tool_arguments": raw,
              "decoded_sha256": digest(verified_result)}
    return {**values, "record_sha256": digest(values)}


def verify_offline_receipt(record, envelope, identity, decode):
    """Fail closed for version, input SHA, raw receipt, schema or Claim mismatch.

    decode is a trusted local decoder rebuilt from newly verified frozen inputs,
    not a callback from a model response. No tool dispatch takes place here.
    """
    from easel.integrations.planning_staged_proposal import StagedProposal
    _envelope(envelope)
    if (not isinstance(record, dict) or set(record) != {
        "policy", "envelope_scope_ref", "codec_identity", "raw_tool_arguments",
        "decoded_sha256", "record_sha256"
    } or record["policy"] != COLD_POLICY
            or record["envelope_scope_ref"] != envelope["scope_ref"]
            or record["codec_identity"] != identity
            or digest({k: v for k, v in record.items() if k != "record_sha256"}) != record["record_sha256"]):
        raise ValueError("Cold receipt identity or immutable evidence changed")
    if not isinstance(record["raw_tool_arguments"], str):
        raise ValueError("Cold receipt lacks original tool arguments")
    raw = StagedProposal.parse_raw(record["raw_tool_arguments"])
    result = decode(raw, identity)
    if digest(result) != record["decoded_sha256"]:
        raise ValueError("Cold receipt decoded semantic result or Claims changed")
    return result


SOURCE_BRIDGE_POLICY = "planning-d1-source-header-bridge@2"
BATCH_CLAIM_POLICY = "planning-d1-batched-claim-boundary@4"


class OpaqueHeaderBridge:
    """D1 offline adapter: real SourceSelection src_* <-> canonical Claim.

    All wire scopes are source-produced opaque handles. The source_codec,
    including its original closed modality branches, remains authoritative.
    """
    def __init__(self, source_codec, staged, envelope):
        _envelope(envelope)
        from easel.integrations.planning_input_view import SourceSelection
        if not isinstance(source_codec, SourceSelection):
            raise ValueError("Use the actual SourceSelection codec")
        self.source_codec = source_codec
        self.canonical = VisualHeaderClaimCarrier(staged, envelope)
        self.schema = deepcopy(source_codec.schema)
        outer = self.schema["properties"]["needs"]["items"]
        for branch in outer["anyOf"]:
            modality = branch["properties"]["modality"]["const"]
            if modality not in VISUAL:
                continue
            props = branch["properties"]
            props["header_claim"] = {
                "type": "object", "additionalProperties": False,
                "properties": {
                    "claimed_kind": {"type": "string", "enum": list(CLAIM_KINDS)},
                    "creative_goal_ref": {"type": "string", "enum": source_codec.allowed_scopes[modality]},
                    "reason": {"type": "string", "minLength": 8, "maxLength": 512},
                },
                "required": ["claimed_kind", "creative_goal_ref", "reason"],
            }
            branch["required"] = [*branch["required"], "header_claim"]        # The outer closed SourceSelection item also lists permitted props;
        # its per-modality anyOf branches remain the strict authority.
        outer["properties"]["header_claim"] = {"type": "object"}
        Draft202012Validator.check_schema(self.schema)
        self.identity = {
            "policy": SOURCE_BRIDGE_POLICY,
            "source_identity": deepcopy(source_codec.identity),
            "envelope_scope_ref": envelope["scope_ref"],
            "canonical_header_identity": deepcopy(self.canonical.identity),
            "wire_schema_sha256": digest(self.schema),
        }

    def encode(self, selection, claims):
        canonical = self.canonical.encode(selection, claims)
        wire = self.source_codec.encode(selection)
        for i, (need, headed) in enumerate(zip(wire["needs"], canonical["needs"], strict=True)):
            if need["modality"] not in VISUAL:
                continue
            claim = deepcopy(headed["header_claim"])
            # Keep the MODEL-proposed creative basis, not a fabricated source
            # copied from the selected Need. Both have independent identities.
            basis = self.source_codec.to_wire.get(claim["creative_goal_ref"])
            if basis not in self.source_codec.allowed_scopes[need["modality"]]:
                raise ValueError("Claim basis source is outside frozen visual scope")
            claim["creative_goal_ref"] = basis
            # Header/continuity digests are compiled from the selected Need,
            # not model-authored identities. Only the three semantic fields
            # are sent to the structured model contract.
            claim.pop("claimed_necessity")
            claim.pop("continuity_choices_sha256")
            need["header_claim"] = claim
        self.decode(wire, self.identity)
        return wire

    def decode(self, wire, identity):
        if identity != self.identity:
            raise ValueError("Source mapping, version or Header Claim identity changed")
        Draft202012Validator(self.schema).validate(wire)
        original = deepcopy(wire)
        claims = {}
        for i, need in enumerate(original["needs"]):
            if need["modality"] not in VISUAL:
                continue
            claim = need.pop("header_claim")
            # need.scope is the frozen location of this Material Need. The
            # creative_goal_ref is a distinct, model-cited creative BASIS.
            # Preserve that original cite; B independently reviews its truth.
            basis = claim["creative_goal_ref"]
            if basis not in self.source_codec.allowed_scopes[need["modality"]]:
                raise ValueError("Claim basis is outside frozen modality sources")
            claim["creative_goal_ref"] = self.source_codec.references[basis]["original"]
            # Original A wire remains untouched. These two mechanical fields
            # originate in the same model-selected Need, never an invented SHA
            # or a model claim of additional Creator/Director authority.
            claim["claimed_necessity"] = need["necessity"]
            claim["continuity_choices_sha256"] = digest(need.get("continuity_choices", []))
            claims[f"needs/{i}/header"] = claim
        decoded = self.source_codec.decode(original, self.source_codec.identity)
        canonical_wire = self.canonical.encode(decoded, claims)
        selection, records = self.canonical.decode(canonical_wire, self.canonical.identity)
        if selection != decoded:
            raise ValueError("Source decode and canonical Header mapping are not reversible")
        return selection, records


class BatchedVisualClaimCarrier:
    """Model-facing A-details uses SourceSelection src_*; canonical stays internal.

    Raw model batches are kept untouched. The frozen SourceSelection alone
    validates and resolves the model-cited creative basis before B Review.
    """
    def __init__(self, staged, selection, envelope, *, source_bridge_identity, source_codec):
        _envelope(envelope)
        from easel.integrations.planning_input_view import SourceSelection
        if (not isinstance(source_codec, SourceSelection)
                or source_bridge_identity.get("source_identity") != source_codec.identity):
            raise ValueError("A-details source codec differs from frozen A-selection")
        self.source_codec = source_codec
        self.staged = staged
        self.selection = deepcopy(selection)
        self.carrier = VisualClaimCarrier(staged, selection, envelope)
        self.plan = staged.detail_batches(selection, modality_family=True)
        self.batches = {}
        self.slot_modality = {}
        for batch in self.plan["batches"]:
            schema = deepcopy(self.carrier.schema)
            container = schema["properties"]["slots"]
            container["properties"] = {key: container["properties"][key] for key in batch["slots"]}
            container["required"] = list(batch["slots"])
            for slot in batch["slots"]:
                need = selection["needs"][int(slot.removeprefix("slot_"))]
                if need["modality"] not in VISUAL:
                    continue
                allowed = source_codec.allowed_scopes[need["modality"]]
                if source_codec.to_wire.get(need["scope"]) not in allowed:
                    raise ValueError("A-details selected Need source has no frozen modality mapping")
                claim = (container["properties"][slot]["properties"]["conditions"]
                         ["items"]["properties"]["claim"])
                canonical = claim["properties"]["creative_goal_ref"]["enum"]
                if set(canonical) != _frozen_source_refs(envelope):
                    raise ValueError("A-details canonical Claim authority changed")
                claim["properties"]["creative_goal_ref"] = {"type": "string", "enum": list(allowed)}
                self.slot_modality[slot] = need["modality"]
            Draft202012Validator.check_schema(schema)
            self.batches[batch["key"]] = schema
        self.identity = {
            "policy": BATCH_CLAIM_POLICY,
            "source_bridge_identity_sha256": digest(source_bridge_identity),
            "source_identity": deepcopy(source_codec.identity),
            "source_mapping_sha256": digest(source_codec.references),
            "selection_sha256": digest(selection),
            "carrier_identity": deepcopy(self.carrier.identity),
            "batch_plan_identity": deepcopy(self.plan["identity"]),
            "batch_schemas_sha256": digest(self.batches),
        }

    def _convert_batch(self, batch, *, to_wire):
        """Encode/decode the independent creative basis with one frozen codec."""
        result = deepcopy(batch)
        for slot, content in result["slots"].items():
            modality = self.slot_modality.get(slot)
            if modality is None:
                continue
            allowed = self.source_codec.allowed_scopes[modality]
            for condition in content["conditions"]:
                claim = condition["claim"]
                basis = claim["creative_goal_ref"]
                if to_wire:
                    handle = self.source_codec.to_wire.get(basis)
                    if handle not in allowed:
                        raise ValueError("A-details creative basis outside frozen modality")
                    claim["creative_goal_ref"] = handle
                else:
                    if basis not in allowed or basis not in self.source_codec.references:
                        raise ValueError("A-details opaque creative basis outside frozen modality")
                    claim["creative_goal_ref"] = self.source_codec.references[basis]["original"]
        return result

    def split(self, details_with_claims):
        """Offline canonical fixture → same opaque Wire used by the real model."""
        self.carrier.decode(details_with_claims, self.carrier.identity)
        replies = {}
        for batch in self.plan["batches"]:
            canonical = {
                "slots": {key: deepcopy(details_with_claims["slots"][key])
                          for key in batch["slots"]},
                "unresolved": deepcopy(details_with_claims["unresolved"] if batch == self.plan["batches"][0] else []),
            }
            wire = self._convert_batch(canonical, to_wire=True)
            Draft202012Validator(self.batches[batch["key"]]).validate(wire)
            replies[batch["key"]] = wire
        return replies

    def merge(self, replies, identity):
        if identity != self.identity or set(replies) != set(self.batches):
            raise ValueError("Frozen D1 batch mapping or stage coverage changed")
        combined = {"slots": {}, "unresolved": []}
        originals = {}
        for batch in self.plan["batches"]:
            key = batch["key"]
            raw = replies[key]
            Draft202012Validator(self.batches[key]).validate(raw)
            if set(raw["slots"]) & set(combined["slots"]):
                raise ValueError("Duplicate visual details slot across frozen batches")
            canonical_batch = self._convert_batch(raw, to_wire=False)
            combined["slots"].update(canonical_batch["slots"])
            combined["unresolved"].extend(deepcopy(raw["unresolved"]))
            originals[key] = digest(raw)
        canonical, stripped, claims = self.carrier.decode(combined, self.carrier.identity)
        plain = {batch["key"]: {"slots": {slot: deepcopy(stripped["slots"][slot])
                                                for slot in batch["slots"]},
                                  "unresolved": deepcopy(replies[batch["key"]]["unresolved"])}
                 for batch in self.plan["batches"]}
        underlying = self.staged.assemble_batches_candidate(
            self.selection, self.plan, plain, repair_missing_leaves=False)
        from easel.integrations.planning_result_contract import SemanticProposal
        normalized_underlying = SemanticProposal.model_validate(
            underlying, context={"flexible_queries": self.staged.union.flexible_queries}
        ).model_dump(mode="json")
        if canonical != normalized_underlying:
            raise ValueError("D1 Claim merge changed original staged A semantics")
        return canonical, claims, {
            "policy": BATCH_CLAIM_POLICY,
            "identity": deepcopy(self.identity),
            "original_batch_sha256": originals,
            "canonical_sha256": digest(canonical),
            "claims_sha256": digest(claims),
            "recheck_required": True,
        }

    def verify_snapshot(self, replies, snapshot, *, current_identity):
        """Reconstruct every full batch from frozen caller-held raw tool bytes."""
        if current_identity != self.identity:
            raise ValueError("D1 cold source/selection/batch identity changed")
        canonical, claims, regenerated = self.merge(replies, current_identity)
        if regenerated != snapshot:
            raise ValueError("D1 batch capture/Claim checkpoint differs from frozen originals")
        return canonical, claims

D1_REVIEW_BINDING_POLICY = "planning-d1-review-dependency@1"


def bind_review_claims(directory, *, envelope, conditions, headers):
    """Pure frozen B-question projection; use before initial B and after Repair."""
    _envelope(envelope)
    if not isinstance(directory, dict) or not isinstance(directory.get("questions"), list):
        raise ValueError("Missing B question directory")
    result = deepcopy(directory)
    if len({q["question"] for q in result["questions"]}) != len(result["questions"]):
        raise ValueError("Duplicate original B question identity")
    for q in result["questions"]:
        target = q.get("target")
        if q.get("kind") == "complete_obligation" and isinstance(target, list) and len(target) == 2:
            refs = [f"needs/{target[0]}/header", f"needs/{target[0]}/conditions/{target[1]}"]
        elif q.get("kind") in {"visual_choices", "need_necessity"} and isinstance(target, list) and len(target) == 1:
            refs = [f"needs/{target[0]}/header", *sorted(
                key for key in conditions if key.startswith(f"needs/{target[0]}/conditions/"))]
        elif q.get("kind") in {"frozen_visual_coverage", "unresolved_classification"}:
            refs = [*sorted(headers), *sorted(conditions)]
        else:
            continue
        fingerprints = {}
        for ref in refs:
            record = headers.get(ref) if ref.endswith("/header") else conditions.get(ref)
            if record is None or record.get("scope_ref") != envelope["scope_ref"]:
                raise ValueError("B Review Claim coverage incomplete")
            fingerprints[ref] = digest(record)
        q["creative_dependency"] = {
            "policy": D1_REVIEW_BINDING_POLICY,
            "envelope_scope_ref": envelope["scope_ref"],
            "claim_sha256_by_ref": fingerprints,
        }
    return result


def freeze_original_capture(envelope, codec_identity, original_reply, verified_result):
    """Bind exactly captured UTF-8 tool bytes; never serialize decoded JSON."""
    import hashlib
    from easel.integrations.planning_staged_proposal import StagedProposal
    _envelope(envelope)
    if not isinstance(original_reply, str) or not isinstance(
            StagedProposal.parse_raw(original_reply), dict):
        raise ValueError("Original reply must be captured JSON object bytes")
    payload = {
        "policy": "planning-d1-original-capture@1",
        "envelope_scope_ref": envelope["scope_ref"],
        "codec_identity": deepcopy(codec_identity),
        "original_reply": original_reply,
        "original_reply_sha256": hashlib.sha256(original_reply.encode()).hexdigest(),
        "decoded_sha256": digest(verified_result),
    }
    return {**payload, "record_sha256": digest(payload)}


def verify_original_capture(record, envelope, codec_identity, decode):
    import hashlib
    from easel.integrations.planning_staged_proposal import StagedProposal
    _envelope(envelope)
    if not isinstance(record, dict) or set(record) != {
        "policy", "envelope_scope_ref", "codec_identity", "original_reply",
        "original_reply_sha256", "decoded_sha256", "record_sha256"
    } or record["policy"] != "planning-d1-original-capture@1" or (
            record["envelope_scope_ref"], record["codec_identity"]) != (
            envelope["scope_ref"], codec_identity):
        raise ValueError("Original captured D1 policy/identity changed")
    if not isinstance(record["original_reply"], str) or (
            hashlib.sha256(record["original_reply"].encode()).hexdigest()
            != record["original_reply_sha256"]):
        raise ValueError("Original captured D1 reply SHA changed")
    if digest({k:v for k,v in record.items() if k != "record_sha256"}) != record["record_sha256"]:
        raise ValueError("Original D1 capture record changed")
    decoded = decode(StagedProposal.parse_raw(record["original_reply"]), codec_identity)
    if digest(decoded) != record["decoded_sha256"]:
        raise ValueError("Original D1 decoded Claim changed")
    return decoded

OWNER_POLICY = "planning-creative-owner@1"


def verify_a_claim_origin(envelope, bridge, batched, original_selection,
                          original_batches, original_capture, current_header,
                          current_conditions, *, effective_batches=None, capture_keys=None):
    """Reconstruct all pre-Repair Claims from the same captured A bytes.

    The caller must supply the actual original capture records (not model
    supplied Claim records); byte identity is verified against native capture
    request/session in the Planning Owner.
    """
    import hashlib
    from easel.integrations.planning_staged_proposal import StagedProposal
    _envelope(envelope)
    if capture_keys is not None and (not isinstance(capture_keys, dict)
            or set(capture_keys) - set(original_batches)):
        raise ValueError('A-details effective Capture key mapping changed')
    for key, raw in {"A-selection": original_selection, **original_batches}.items():
        # The Owner validates every failed original and every generation before
        # selecting one final authenticated model capture. It never forges a
        # completed original Stage Call merely to satisfy the D1 origin guard.
        origin_key = capture_keys.get(key, key) if capture_keys else key
        call = original_capture.get(origin_key)
        if (not isinstance(raw, str) or not isinstance(call, dict)
                or call.get("reply") != raw
                or call.get("reply_sha256") != hashlib.sha256(raw.encode()).hexdigest()
                or call.get("result") not in {"MODEL_COMPLETED", "ACCEPTED"}):
            raise ValueError("D1 accepted A capture/provenance cannot be authenticated")
    selection, rebuilt_headers = bridge.decode(
        StagedProposal.parse_raw(original_selection), bridge.identity)
    if selection != batched.selection:
        raise ValueError("D1 source selection differs from original A reply")
    batches = {key: StagedProposal.parse_raw(raw)
               for key, raw in original_batches.items()}
    if effective_batches is not None:
        if set(effective_batches) != set(batches):
            raise ValueError('A-details recovered Claim batch coverage changed')
        # Caller must separately reconstruct the original and explicit patch
        # bytes and validate every patch SHA. Never reinterpret raw as accepted.
        batches = deepcopy(effective_batches)
    _, rebuilt_conditions, _ = batched.merge(batches, batched.identity)
    if (rebuilt_headers != current_header or
            rebuilt_conditions != current_conditions):
        raise ValueError("D1 old Claim does not match frozen original A capture")
    return True




