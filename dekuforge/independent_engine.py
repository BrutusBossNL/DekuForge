"""Independent branch contract: original preparation and no vendor fallback."""
from .core import ROOT

STAGES = {
    'archive_inspection': 'implemented',
    'verified_module_preparation': 'implemented',
    'a64_to_c_translation': 'partial',
    'module_linking': 'missing',
    'guest_platform_services': 'missing',
    'graphics_translation': 'missing',
    'vulkan_renderer': 'missing',
    'audio_and_input': 'missing',
    'native_game_link': 'missing',
    'gameplay_parity': 'unvalidated',
}


def report(root=ROOT):
    return {'backend': 'independent', 'branch': 'independent',
            'playable_build_available': False, 'game_1_1_1_port_validated': False,
            'upstream_fallback': False, 'stages': dict(STAGES),
            'missing': [name for name, state in STAGES.items() if state != 'implemented'],
            'reference': 'main: stable 0.10.1-based engine; comparison only',
            'provenance': 'docs/INDEPENDENT_ENGINE.md',
            'runtime_packaged': False}


def build(filename, notify, destination):
    # Do not extract another multi-gigabyte game while essential backends are absent.
    status = report()
    notify('checked', status)
    notify('log', 'Independent backend has no upstream fallback. Missing: '+', '.join(status['missing'])+'\n')
    raise RuntimeError('independent_backend_incomplete')
