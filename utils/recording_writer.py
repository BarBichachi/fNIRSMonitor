import queue
import threading
import time
from typing import IO, Optional


class RecordingWriter:
    # Background-thread writer for two parallel TSV files (raw OD + calculated Hb).
    # SessionRecorder owns the files and headers; this class only owns the I/O loop.
    # Enqueues are non-blocking; if the queue is full, the row is dropped and
    # dropped_count is incremented. Caller is expected to surface that.

    def __init__(self, max_queue: int = 10000, flush_interval_s: float = 1.0):
        self._queue: queue.Queue = queue.Queue(maxsize=max_queue)
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._raw_file: Optional[IO[str]] = None
        self._calc_file: Optional[IO[str]] = None
        self._dropped_count = 0
        self._flush_interval_s = flush_interval_s

    def start(self, raw_file: IO[str], calc_file: IO[str]) -> None:
        # Files must already be open with headers written.
        self._raw_file = raw_file
        self._calc_file = calc_file
        self._dropped_count = 0
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run, daemon=True, name="RecordingWriter"
        )
        self._thread.start()

    def enqueue(self, raw_row: str, calc_row: str) -> bool:
        # Non-blocking; returns False if dropped due to queue full.
        try:
            self._queue.put_nowait((raw_row, calc_row))
            return True
        except queue.Full:
            self._dropped_count += 1
            return False

    @property
    def dropped_count(self) -> int:
        return self._dropped_count

    def stop(self, timeout: float = 5.0) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=timeout)
            self._thread = None

        # Drain anything the worker did not get to before join timed out.
        while not self._queue.empty():
            try:
                raw_row, calc_row = self._queue.get_nowait()
            except queue.Empty:
                break
            self._write_pair(raw_row, calc_row)

        if self._raw_file is not None:
            self._raw_file.flush()
        if self._calc_file is not None:
            self._calc_file.flush()

    def _write_pair(self, raw_row: str, calc_row: str) -> None:
        if self._raw_file is not None:
            self._raw_file.write(raw_row)
        if self._calc_file is not None:
            self._calc_file.write(calc_row)

    def _run(self) -> None:
        last_flush = time.monotonic()
        while True:
            try:
                raw_row, calc_row = self._queue.get(timeout=0.1)
            except queue.Empty:
                if self._stop_event.is_set():
                    return
                continue

            self._write_pair(raw_row, calc_row)

            now = time.monotonic()
            if now - last_flush >= self._flush_interval_s:
                if self._raw_file is not None:
                    self._raw_file.flush()
                if self._calc_file is not None:
                    self._calc_file.flush()
                last_flush = now
