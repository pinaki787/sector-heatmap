"""OS-backed cross-process locks; never silently fall back to thread-only locks."""
import os
import time


def lock_file(fd, blocking=True):
    if os.name != 'nt':
        import fcntl
        fcntl.flock(fd, fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB))
        return
    import msvcrt
    # Windows byte-range locking requires a byte and a stable offset.
    if os.fstat(fd).st_size == 0:
        os.write(fd, b'\0')
    while True:
        os.lseek(fd, 0, os.SEEK_SET)
        try:
            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            return
        except OSError:
            if not blocking:
                raise
            time.sleep(0.05)


def unlock_file(fd):
    if os.name != 'nt':
        import fcntl
        fcntl.flock(fd, fcntl.LOCK_UN)
    else:
        import msvcrt
        os.lseek(fd, 0, os.SEEK_SET)
        msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
