"""Bounded application-update outcomes and diagnostic-log selection."""
import hashlib
import json
from itertools import islice
from pathlib import Path


def read_record(path):
    path = Path(path)
    try:
        if path.is_symlink() or path.resolve() != path.absolute() or path.stat().st_size > 65536:
            return {}
        value = json.loads(path.read_text(encoding='utf-8'))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def load_result(root):
    value = read_record(root/'local/update-result.json')
    if type(value.get('success')) is not bool or not isinstance(value.get('release'), str):
        return None
    result = {key: value.get(key, '') for key in ('success', 'release', 'error', 'job')}
    if any(not isinstance(result[key], str) for key in ('release', 'error', 'job')):
        return None
    result['release'] = result['release'][:200]
    result['error'] = result['error'][:4000]
    result['id'] = hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()
    return result


def pending_result(root):
    result = load_result(root)
    seen = read_record(root/'local/update-result-seen.json')
    return result if result and result['id'] != seen.get('id') else None


def log_paths(root, incident):
    if incident.get('kind') != 'application_update':
        return []
    folder = root/'local/update-jobs'
    if folder.is_symlink() or folder.resolve() != folder.absolute() or not folder.is_dir():
        return []
    job = incident.get('job', '')
    if isinstance(job, str) and len(job) == 32 and all(c in '0123456789abcdef' for c in job):
        candidates = [folder/job]
    else:
        # Legacy results have no job ID. Match a bounded set of local job records.
        candidates = sorted(islice(folder.iterdir(), 256), key=lambda p: p.stat().st_mtime, reverse=True)
    for candidate in candidates:
        if candidate.is_symlink() or candidate.resolve() != candidate.absolute():
            continue
        record = read_record(candidate/'job.json')
        log = candidate/'worker.log'
        if record.get('release') == incident.get('release') and log.is_file() and not log.is_symlink():
            return [log]
    return []
