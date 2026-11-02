"""Standalone durable-job worker; model calls stay outside API request handling."""
import argparse
import logging
import signal
from threading import Event

from .settings import Settings
from .workflow import Studio

logger = logging.getLogger(__name__)


def run_worker(studio, stop: Event, *, once=False, poll_seconds=0.5):
    """Reconcile publication and claim durable jobs until stopped.

    Shutdown finishes the current bounded operation before exiting. An abruptly
    killed worker leaves its lease for the existing explicit-failure recovery;
    this loop never requeues uncertain model calls.
    """
    if poll_seconds <= 0:
        raise ValueError('Worker poll interval must be positive')
    while not stop.is_set():
        try:
            studio.reconcile_pending(continue_on_error=True)
            worked = studio.work_once()
        except Exception:
            logger.exception('Worker/recovery failed')
            if once:
                raise
            worked = False
        if once:
            return
        if not worked:
            stop.wait(poll_seconds)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--once', action='store_true', help='Reconcile and attempt at most one queued job, then exit')
    parser.add_argument('--env-file', default='.env', help='Settings file; use an isolated empty file for controlled runs')
    parser.add_argument('--poll-seconds', type=float, default=0.5)
    args = parser.parse_args(argv)
    if not 0 < args.poll_seconds <= 60:
        parser.error('--poll-seconds must be positive and at most 60')
    logging.basicConfig(level=logging.INFO)
    stop = Event()

    def request_stop(signum, frame):
        stop.set()

    previous = {sig: signal.signal(sig, request_stop) for sig in (signal.SIGTERM, signal.SIGINT)}
    studio = None
    try:
        studio = Studio(Settings(_env_file=args.env_file))
        logger.info('Worker started')
        run_worker(studio, stop, once=args.once, poll_seconds=args.poll_seconds)
    finally:
        if studio is not None:
            studio.db.engine.dispose()
        for sig, handler in previous.items():
            signal.signal(sig, handler)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
