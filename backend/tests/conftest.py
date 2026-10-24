import os
import tempfile

os.environ.setdefault("DATABASE_URL", f"sqlite:///{tempfile.mkdtemp()}/test.db")
os.environ.setdefault("TOKEN_ENCRYPTION_KEY", "6J0lY9ozgGkXXJ6cO1U9q2G4o8nVb2mJxwV7m6sYt0Q=")
os.environ.setdefault("SCHEDULER_ENABLED", "false")
os.environ.setdefault("JWT_SECRET", "test-secret-that-is-long-enough-for-hs256-0123456789")
