"""Transactional JSON history and checkpoint storage, compatible with older Stintory."""
import copy
import os
from .models import Session
from .util import data_dir, read_json, write_json_atomic, Log


class SessionStore:
    def __init__(self, directory=None):
        self.directory = directory or data_dir()
        os.makedirs(self.directory, exist_ok=True)
        self.sessions_path = os.path.join(self.directory, 'sessions.json')
        self.current_path = os.path.join(self.directory, 'current.json')
        self.settings_path = os.path.join(self.directory, 'settings.json')
        self.sessions = []
        self._last_checkpoint = None
        self.version = 0
        if os.path.exists(self.sessions_path):
            data = read_json(self.sessions_path)
            if not isinstance(data,list):
                raise RuntimeError(f'Cannot read history. The original file was left unchanged: {self.sessions_path}')
            try:
                self.sessions=[Session.from_json(d) for d in data]
                if len({s.id for s in self.sessions}) != len(self.sessions): raise ValueError('duplicate session IDs')
            except (AttributeError,KeyError,ValueError,TypeError,OverflowError,OSError) as e:
                raise RuntimeError(f'History validation failed. The original file was left unchanged: {self.sessions_path}') from e

    def _commit(self, arr):
        # Validate and write first: failed storage must not update memory/version.
        items=list(arr)
        if len({s.id for s in items})!=len(items): raise ValueError('Duplicate session IDs')
        payload=[s.validate().to_json() for s in items]
        write_json_atomic(self.sessions_path,payload)
        self.sessions=items
        self.version+=1

    def append(self, session):
        # Idempotent for retry after a crash between history write and checkpoint removal.
        if any(s.id==session.id for s in self.sessions): return
        self._commit(self.sessions+[copy.deepcopy(session)])

    def replace_all(self, arr):
        self._commit(sorted(copy.deepcopy(arr),key=lambda s:s.start))

    def delete(self, ids):
        ids=set(ids)
        self._commit([s for s in self.sessions if s.id not in ids])

    def update(self, session):
        if any(s.id==session.id for s in self.sessions):
            self._commit(sorted([copy.deepcopy(session) if s.id==session.id else s for s in self.sessions],key=lambda s:s.start))

    def save_current(self, session):
        if session is not None:
            payload=session.validate().to_json()
            if payload!=self._last_checkpoint:
                write_json_atomic(self.current_path,payload)
                self._last_checkpoint=copy.deepcopy(payload)
        else:
            self._last_checkpoint=None
            try: os.remove(self.current_path)
            except FileNotFoundError: pass
            except OSError as e: Log.write(f'Could not remove checkpoint: {e}')

    def load_current(self):
        if not os.path.exists(self.current_path): return None
        d=read_json(self.current_path)
        try:
            if not isinstance(d,dict): raise ValueError('Invalid checkpoint')
            return Session.from_json(d)
        except (AttributeError,KeyError,ValueError,TypeError,OverflowError,OSError):
            # Preserve unreadable data for manual recovery; do not overwrite it silently.
            import time
            backup=self.current_path+f'.corrupt-{time.time_ns()}'
            os.replace(self.current_path,backup)
            Log.write(f'Invalid checkpoint moved to {backup}')
            return None
