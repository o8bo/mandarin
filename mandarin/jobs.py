"""One conversion batch at a time; callbacks are delivered on the worker thread."""
import threading
from . import engine


class JobRunner:
    def __init__(self):
        self.cancelled = threading.Event()
        self.thread = None
        self._lock = threading.Lock()

    @property
    def busy(self):
        return self.thread is not None and self.thread.is_alive()

    def cancel(self):
        self.cancelled.set()

    def start(self, operation, paths, options, progress, finished):
        with self._lock:
            if self.busy: raise RuntimeError('A conversion is already running')
            self.cancelled.clear()
            def work():
                try:
                    result = engine.run_operation(operation, paths, options, progress, self.cancelled)
                    finished(result, '')
                except Exception as error:
                    finished(getattr(error, 'partial_result', {'outputs': [], 'warnings': []}), str(error))
            self.thread = threading.Thread(target=work, daemon=False, name='mandarin-conversion')
            self.thread.start()
