"""Single-host locks serialize both threads and processes; no remote lock service."""
from contextlib import contextmanager
import fcntl
import os
from pathlib import Path
from threading import Lock, RLock
from weakref import WeakValueDictionary
from domains.ads.contracts.material_library import MaterialError

_guard=Lock()
_locks=WeakValueDictionary()

@contextmanager
def exclusive(path):
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    with _guard:
        lock=_locks.get(str(path))
        if lock is None:
            lock=RLock();_locks[str(path)]=lock
    if not lock.acquire(blocking=False): raise MaterialError('material_worker_busy')
    fd=None
    try:
        fd=os.open(path,os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
        try: fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError: raise MaterialError('material_worker_busy') from None
        yield
    finally:
        if fd is not None: os.close(fd)
        lock.release()
