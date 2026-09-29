import hashlib
import json

from easel.runtime_config import EaselRuntimeConfig, ReadinessStatus
from easel.runtime_dependencies import DependencyRegistry, ReadinessProfile


def test_runtime_config_process_environment_overrides_env_file_without_exposing_secret(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "EASEL_HYPIT_RUNTIME_PROFILE=/env-file/runtime.json\n"
        "PEXELS_API_KEY=REPLACE_ME\n",
        encoding="utf-8",
    )
    config = EaselRuntimeConfig.load(
        environ={"EASEL_HYPIT_RUNTIME_PROFILE": "/process/runtime.json"},
        env_file=env_file,
    )
    assert config.get("EASEL_HYPIT_RUNTIME_PROFILE") == "/process/runtime.json"
    assert config.source("EASEL_HYPIT_RUNTIME_PROFILE") == "process environment"
    assert config.hypit.runtime_profile == "/process/runtime.json"
    assert not config.providers.credential_presence["pexels"]
    assert config.generation.execution_owner == "Material Layer"
    assert config.openclaw.profile == "easel"
    assert config.material.library_root.name == "material-library"
    assert not config.credential_configured("PEXELS_API_KEY")


def test_openverse_oauth_client_pair_is_secret_safe_and_counts_as_configured(tmp_path):
    config = EaselRuntimeConfig.load(environ={
        "OPENVERSE_CLIENT_ID": "openverse-client-id",
        "OPENVERSE_CLIENT_SECRET": "openverse-client-secret",
    }, env_file=tmp_path / "none.env")
    assert config.providers.credential_presence["openverse"]
    assert config.credential_configured("OPENVERSE_CLIENT_ID")
    assert config.credential_configured("OPENVERSE_CLIENT_SECRET")
    assert "openverse-client-secret" not in repr(config)

    partial = EaselRuntimeConfig.load(environ={
        "OPENVERSE_CLIENT_ID": "openverse-client-id",
    }, env_file=tmp_path / "none.env")
    assert not partial.providers.credential_presence["openverse"]
    row = next(row for row in DependencyRegistry(partial).inventory(probe_local=False)
               if row.spec.id == "provider.openverse")
    assert row.status is ReadinessStatus.CONTRACT_FAILED


def test_openverse_oauth_pair_is_primary_without_static_token_and_readiness_reports_live_evidence(tmp_path):
    config = EaselRuntimeConfig.load(environ={
        "OPENVERSE_CLIENT_ID": "fixture-client-id",
        "OPENVERSE_CLIENT_SECRET": "fixture-client-secret",
    }, env_file=tmp_path / "none.env")
    row = next(row for row in DependencyRegistry(config).inventory(probe_local=False)
               if row.spec.id == "provider.openverse")

    assert config.providers.credential_presence["openverse"]
    assert not config.credential_configured("OPENVERSE_ACCESS_TOKEN")
    assert "OPENVERSE_ACCESS_TOKEN" in row.spec.config_keys  # compatibility only
    assert "optional static Bearer compatibility fallback" in row.spec.credential_type
    assert row.status is ReadinessStatus.CONFIG_READY
    assert "AUTH_VERIFIED" in row.detail
    assert "SEARCH_VERIFIED" in row.detail
    assert "REAL_WORLD_VERIFIED" in row.detail
    assert "DISCOVERY_ONLY" in row.detail
    assert "fixture-client-secret" not in row.detail


def test_openverse_static_token_remains_optional_compatibility_fallback(tmp_path):
    config = EaselRuntimeConfig.load(environ={
        "OPENVERSE_ACCESS_TOKEN": "fixture-static-token",
    }, env_file=tmp_path / "none.env")
    row = next(row for row in DependencyRegistry(config).inventory(probe_local=False)
               if row.spec.id == "provider.openverse")

    assert config.providers.credential_presence["openverse"]
    assert row.status is ReadinessStatus.NOT_VERIFIED
    assert "建议配置 OAuth client pair" in row.detail


def test_pixabay_runtime_readiness_reports_dated_live_smoke_without_exposing_key(tmp_path):
    config = EaselRuntimeConfig.load(environ={
        "PIXABAY_API_KEY": "fixture-pixabay-key",
    }, env_file=tmp_path / "none.env")
    row = next(row for row in DependencyRegistry(config).inventory(probe_local=False)
               if row.spec.id == "provider.pixabay")

    assert row.status is ReadinessStatus.CONFIG_READY
    assert "AUTH_VERIFIED" in row.detail
    assert "SEARCH_VERIFIED" in row.detail
    assert "REAL_WORLD_VERIFIED" in row.detail
    assert "User-Agent" in row.detail
    assert "fixture-pixabay-key" not in row.detail


def test_provider_full_profile_is_ready_when_five_provider_configs_and_local_root_are_ready(tmp_path):
    local_root = tmp_path / "assets"
    local_root.mkdir()
    config = EaselRuntimeConfig.load(environ={
        "EASEL_MATERIAL_LOCAL_ROOTS": str(local_root),
        "PEXELS_API_KEY": "fixture-pexels",
        "PIXABAY_API_KEY": "fixture-pixabay",
        "COVERR_API_KEY": "fixture-coverr",
        "UNSPLASH_ACCESS_KEY": "fixture-unsplash",
        "OPENVERSE_CLIENT_ID": "fixture-openverse-id",
        "OPENVERSE_CLIENT_SECRET": "fixture-openverse-secret",
    }, env_file=tmp_path / "none.env")

    result = DependencyRegistry(config).profile(ReadinessProfile.PROVIDER_FULL, probe_local=False)

    assert result.status == "READY"
    assert not result.blockers


def test_product_provider_registry_passes_openverse_oauth_pair(monkeypatch):
    from easel.integrations.material_supply import product_provider_registry

    monkeypatch.setenv("OPENVERSE_CLIENT_ID", "fixture-client-id")
    monkeypatch.setenv("OPENVERSE_CLIENT_SECRET", "fixture-client-secret")
    registry, _ = product_provider_registry(())
    provider = registry.get("openverse")

    assert provider._client_id == "fixture-client-id"
    assert provider._client_secret == "fixture-client-secret"
    assert provider.info().access_mode.value == "DISCOVERY_ONLY"


def test_product_provider_registry_passes_pixabay_key_from_runtime_config(monkeypatch):
    from easel.integrations.material_supply import product_provider_registry

    monkeypatch.setenv("PIXABAY_API_KEY", "fixture-pixabay-key")
    registry, missing = product_provider_registry(())
    provider = registry.get("pixabay")

    assert provider._api_key == "fixture-pixabay-key"
    assert "pixabay" not in missing
    assert provider.info().provider_id == "pixabay"


def test_profile_readiness_is_secret_safe_and_separates_audio_capabilities(tmp_path, monkeypatch):
    config = EaselRuntimeConfig.load(environ={
        "EASEL_MATERIAL_LOCAL_ROOTS": str(tmp_path / "missing-root"),
    }, env_file=tmp_path / "none.env")
    monkeypatch.setattr("easel.runtime_config._http_ok", lambda _url: True)
    rows = {row.dependency: row for row in config.readiness(profile="core-video", probe_local=True)}
    assert rows["easel.operator"].status is ReadinessStatus.NOT_REQUIRED
    assert rows["hypit.runtime-profile"].status is ReadinessStatus.MISSING_CONFIG
    assert "audio.bgm" not in rows
    assert "audio.sfx" not in rows
    assert config.material.local_roots == (str(tmp_path / "missing-root"),)
    serialized = repr([row.as_dict() for row in rows.values()])
    assert "Operator Token" not in serialized
    assert "secret" not in rows["easel.operator"].detail


def test_readiness_marks_hypit_doctor_contract_failure_without_raw_output(tmp_path, monkeypatch):
    profile = tmp_path / "runtime.json"
    profile.write_text("{}", encoding="utf-8")
    monkeypatch.setattr("easel.runtime_config.shutil.which", lambda _name: "/usr/bin/hypit")
    monkeypatch.setattr("easel.runtime_config._hypit_doctor",
                        lambda _binary, _profile: (ReadinessStatus.CONTRACT_FAILED, "Hypit doctor 未通过；详细输出未保留"))
    config = EaselRuntimeConfig.load(environ={"EASEL_HYPIT_RUNTIME_PROFILE": str(profile)}, env_file=tmp_path / "none.env")
    rows = {row.dependency: row for row in config.readiness(profile="core-video", probe_local=False)}
    assert rows["hypit.runtime-auth"].status is ReadinessStatus.CONTRACT_FAILED
    assert "secret" not in rows["hypit.runtime-auth"].detail.lower()


def test_startup_status_checks_required_runtime_without_operator_secret(tmp_path):
    config = EaselRuntimeConfig.load(environ={}, env_file=tmp_path / "none.env")
    status = config.startup_required_status()
    assert status["Hypit Runtime Profile"] == "MISSING_CONFIG"
    assert "Easel Operator credential" not in status


def test_dependency_registry_has_profile_scoped_requirements_and_keeps_legacy_visible(tmp_path):
    config = EaselRuntimeConfig.load(environ={}, env_file=tmp_path / "none.env")
    registry = DependencyRegistry(config)
    inventory = {row.spec.id: row for row in registry.inventory(probe_local=False)}
    assert inventory["provider.pexels"].spec.required_by_profiles == ("provider-full", "full-system")
    assert inventory["audio.sfx"].spec.required_by_profiles == ("audio", "full-system")
    assert "v1-release" not in inventory["audio.sfx"].spec.required_by_profiles
    assert "v1-release" in inventory["easel.operator"].spec.required_by_profiles
    assert inventory["easel.operator"].status is ReadinessStatus.NOT_REQUIRED
    assert "v1-release" in inventory["openclaw.model-auth"].spec.required_by_profiles
    assert "v1-release" in inventory["hypit.runtime-profile"].spec.required_by_profiles
    assert inventory["legacy.video-production"].status is ReadinessStatus.LEGACY
    assert inventory["provider.openverse"].spec.config_keys == (
        "OPENVERSE_CLIENT_ID", "OPENVERSE_CLIENT_SECRET", "OPENVERSE_ACCESS_TOKEN",
    )
    assert inventory["provider.openverse"].status is ReadinessStatus.MISSING_CREDENTIAL
    assert "full-system" not in inventory["legacy.video-production"].spec.required_by_profiles

    core = registry.profile(ReadinessProfile.CORE_VIDEO, probe_local=False)
    assert "provider.pexels" not in {row.spec.id for row in core.dependencies}
    assert core.status == "NOT_READY"

    release = registry.profile(ReadinessProfile.V1_RELEASE, probe_local=False)
    release_ids = {row.spec.id for row in release.dependencies}
    assert "openclaw.model-auth" in release_ids
    assert "audio.bgm" in release_ids
    assert "audio.sfx" not in release_ids


def test_library_storage_and_content_are_reported_separately(tmp_path):
    library_root = tmp_path / "library"
    library_root.mkdir()
    config = EaselRuntimeConfig.load(
        environ={"EASEL_MATERIAL_LIBRARY_ROOT": str(library_root)}, env_file=tmp_path / "none.env",
    )
    inventory = {row.spec.id: row for row in DependencyRegistry(config).inventory(probe_local=False)}
    assert inventory["material.library-storage"].status is ReadinessStatus.CONFIG_READY
    assert inventory["material.library-content"].status is ReadinessStatus.CONTENT_EMPTY


def test_audio_product_capabilities_are_wired_but_not_claimed_live_ready(tmp_path):
    config = EaselRuntimeConfig.load(environ={}, env_file=tmp_path / "none.env")
    registry = DependencyRegistry(config)
    rows = {row.spec.id: row for row in registry.inventory(probe_local=False)}

    assert rows["audio.narration"].spec.readiness_check == "minimax-generation"
    assert "MiniMax T2A adapter" in rows["audio.narration"].spec.called_by
    assert rows["audio.narration"].status is ReadinessStatus.MISSING_CREDENTIAL
    assert rows["audio.production"].spec.readiness_check == "not-verified"
    assert rows["audio.production"].status is ReadinessStatus.NOT_VERIFIED
    assert "正式 Web 软件调用边已接通" in rows["audio.production"].detail
    assert rows["material.ai-generation"].status is ReadinessStatus.MISSING_CREDENTIAL

    release = registry.profile(ReadinessProfile.V1_RELEASE, probe_local=False)
    blockers = {row.spec.id for row in release.blockers}
    assert {"audio.narration", "audio.production"} <= blockers


def test_library_readiness_rejects_symlink_roots(tmp_path):
    real_root = tmp_path / "real-library"
    real_root.mkdir()
    link = tmp_path / "library-link"
    link.symlink_to(real_root, target_is_directory=True)
    config = EaselRuntimeConfig.load(
        environ={"EASEL_MATERIAL_LIBRARY_ROOT": str(link)}, env_file=tmp_path / "none.env",
    )
    rows = {row.spec.id: row for row in DependencyRegistry(config).inventory(probe_local=False)}
    assert rows["material.library-storage"].status is ReadinessStatus.CONTRACT_FAILED


def test_dependencies_cli_emits_every_field_without_secret_values(tmp_path, monkeypatch, capsys):
    from easel.cli import main

    monkeypatch.setenv("PEXELS_API_KEY", "secret-cli-token")
    monkeypatch.setattr("easel.runtime_dependencies.PROJECT_ROOT", tmp_path)
    assert main(["runtime", "dependencies", "--json", "--no-probe"]) == 0
    output = capsys.readouterr().out
    assert "secret-cli-token" not in output
    assert '"required_by_profiles"' in output
    assert '"credential_owner"' in output
    assert '"legacy": true' in output


def test_gateway_health_probe_never_contacts_non_loopback_endpoint(tmp_path, monkeypatch):
    config = EaselRuntimeConfig.load(
        environ={"EASEL_GATEWAY_HOST": "example.invalid"}, env_file=tmp_path / "none.env",
    )
    probed = []
    monkeypatch.setattr("easel.runtime_dependencies._http_ok", lambda url: probed.append(url) or True)
    rows = {row.spec.id: row for row in DependencyRegistry(config).inventory(probe_local=True)}
    assert rows["openclaw.gateway"].status is ReadinessStatus.READY
    assert config.openclaw.gateway_url == "http://127.0.0.1:18789/healthz"
    assert probed == ["http://127.0.0.1:18789/healthz"]


def test_rights_readiness_hash_verifies_source_sidecars_and_separates_bgm_from_sfx(tmp_path, monkeypatch):
    from easel.runtime_dependencies import _rights_evidence_count

    monkeypatch.setattr("easel.runtime_dependencies.PROJECT_ROOT", tmp_path)
    roots = tmp_path / "sources"
    audio_dir = roots / "audio"
    audio_dir.mkdir(parents=True)
    library_root = tmp_path / "library"
    image = roots / "photo.jpg"
    image.write_bytes(b"visual bytes")
    bgm = audio_dir / "bgm.mp3"
    bgm.write_bytes(b"licensed music bytes")

    def sidecar(path, status="PUBLIC_DOMAIN", attribution_required=False):
        value = {
            "schema": "easel-local-rights@1",
            "asset_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "rights": {
                "status": status,
                "license_name": "CC0 1.0" if status == "PUBLIC_DOMAIN" else "CC BY 4.0",
                "attribution_required": attribution_required,
                "attribution_text": "Creator credit" if attribution_required else None,
                "evidence": [{"kind": "asset_license_statement", "reference": "https://example.test/license"}],
            },
        }
        path.with_name(path.name + ".rights.json").write_text(json.dumps(value), encoding="utf-8")

    sidecar(image)
    sidecar(bgm, status="ATTRIBUTION_REQUIRED", attribution_required=True)
    (audio_dir / "source.json").write_text(
        json.dumps({"kind": "background-music", "file": bgm.name}), encoding="utf-8"
    )

    # A hash-mismatched sidecar is never counted as a Rights-backed source.
    stale = roots / "stale.jpg"
    stale.write_bytes(b"before")
    sidecar(stale)
    stale.write_bytes(b"after")

    config = EaselRuntimeConfig.load(
        environ={"EASEL_MATERIAL_LOCAL_ROOTS": str(roots), "EASEL_MATERIAL_LIBRARY_ROOT": str(library_root)},
        env_file=tmp_path / "none.env",
    )
    rows = {row.spec.id: row for row in DependencyRegistry(config).inventory(probe_local=False)}
    assert rows["material.rights-evidence"].status is ReadinessStatus.CONTENT_AVAILABLE
    assert rows["material.rights-evidence"].detail.startswith("发现 2 个")
    assert rows["material.visual-source"].status is ReadinessStatus.CONTENT_AVAILABLE
    assert rows["audio.bgm"].status is ReadinessStatus.CONTENT_AVAILABLE
    assert rows["audio.sfx"].status is ReadinessStatus.CONTENT_EMPTY
    assert _rights_evidence_count((str(roots),), library_root, {"audio"}, {"background-music"}) == 1
    assert _rights_evidence_count((str(roots),), library_root, {"audio"}, {"sfx"}) == 0
