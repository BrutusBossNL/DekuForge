"""Independent branch contract: original preparation and no vendor fallback."""
from .core import ROOT

STAGES = {
    'archive_inspection': 'implemented',
    'verified_module_preparation': 'implemented',
    'a64_to_c_translation': 'partial',
    'guest_memory_model': 'implemented',
    'module_linking': 'partial',
    'guest_platform_services': 'missing',
    'graphics_translation': 'missing',
    'vulkan_renderer': 'missing',
    'audio_and_input': 'missing',
    'native_game_link': 'missing',
    'gameplay_parity': 'unvalidated',
}


def report(root=ROOT):
    # Original CPU prototype status and evaluated GPL gameplay are separate.
    from pathlib import Path
    from .core import load_installation
    from .open_engine_runtime import launch_options
    active = load_installation(Path(root) / 'local/settings.json')
    experiment = False
    if active:
        try:
            experiment = Path(active).is_file() and launch_options(Path(active), root) is not None
        except (OSError, ValueError, TypeError):
            pass
    return {'backend': 'independent', 'branch': 'independent',
            'playable_build_available': False, 'game_1_1_1_port_validated': False,
            'upstream_fallback': False, 'stages': dict(STAGES),
            'missing': [name for name, state in STAGES.items() if state != 'implemented'],
            'reference': 'main: stable 0.10.1-based engine; comparison only',
            'provenance': 'docs/INDEPENDENT_ENGINE.md',
            'runtime_packaged': False,
            'experimental_game_available': experiment,
            'experimental_provider': 'Hookshot GPL-3.0-or-later; separately evaluated',
            'experimental_evidence': 'docs/INDEPENDENT_EVIDENCE.md',
            'default_builder_ready': False}


def build(filename, notify, destination):
    import json
    from .open_game_build import CONFIG, build as build_experiment
    if CONFIG.is_file():
        config = json.loads(CONFIG.read_text(encoding='utf-8'))
        if config.get('enable_launcher_build') is True:
            notify('log', 'Building the explicitly configured experimental GPL provider; gameplay parity is not accepted.\n')
            return build_experiment(filename, notify, destination or ROOT/'build/independent-game', config=config)
    # Do not extract another multi-gigabyte game while essential backends are absent.
    status = report()
    notify('checked', status)
    notify('log', 'Independent backend has no upstream fallback. Missing: '+', '.join(status['missing'])+'\n')
    raise RuntimeError('independent_backend_incomplete')
