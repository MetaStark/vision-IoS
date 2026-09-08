"""
Daemon singleton lock via PID file.

Usage in any daemon:
    from daemon_lock import acquire_lock, release_lock
    if not acquire_lock('my_daemon_name'):
        sys.exit(0)  # Another instance running
    try:
        # daemon work
    finally:
        release_lock('my_daemon_name')
"""
import os
import sys
import logging

LOCK_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.locks')
logger = logging.getLogger(__name__)


def _lock_path(daemon_name: str) -> str:
    return os.path.join(LOCK_DIR, f'{daemon_name}.pid')


def _is_process_alive(pid: int) -> bool:
    """Check if a process with given PID is still running."""
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def acquire_lock(daemon_name: str) -> bool:
    """
    Acquire a PID-based singleton lock.
    Returns True if lock acquired, False if another instance is running.
    Stale lock files (dead PID) are cleaned automatically.
    """
    os.makedirs(LOCK_DIR, exist_ok=True)
    path = _lock_path(daemon_name)

    if os.path.exists(path):
        try:
            with open(path, 'r') as f:
                old_pid = int(f.read().strip())
            if _is_process_alive(old_pid):
                logger.warning(
                    f'SINGLETON BLOCK: {daemon_name} already running (PID={old_pid}). Exiting.'
                )
                return False
            else:
                logger.info(f'Stale lock for {daemon_name} (PID={old_pid} dead). Reclaiming.')
                os.remove(path)
        except (ValueError, IOError):
            os.remove(path)

    with open(path, 'w') as f:
        f.write(str(os.getpid()))

    logger.info(f'Lock acquired: {daemon_name} (PID={os.getpid()})')
    return True


def release_lock(daemon_name: str) -> None:
    """Release the PID lock file."""
    path = _lock_path(daemon_name)
    try:
        if os.path.exists(path):
            with open(path, 'r') as f:
                stored_pid = int(f.read().strip())
            if stored_pid == os.getpid():
                os.remove(path)
                logger.info(f'Lock released: {daemon_name}')
            else:
                logger.warning(f'Lock owned by PID={stored_pid}, not releasing (we are {os.getpid()})')
    except (ValueError, IOError) as e:
        logger.warning(f'Lock release error for {daemon_name}: {e}')
