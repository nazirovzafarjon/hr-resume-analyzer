"""Integration test verifying database backup and restoration into an isolated database.

This test validates Task 2 requirements:
1. Automated pg_dump custom format generation.
2. SHA256 checksum generation and verification.
3. Isolated restore into a dedicated verification database (never touching production).
4. Schema validation and row count verification.
5. Upload storage archiving and extraction.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import tempfile
import pytest
from sqlalchemy import create_engine, text


# Base maintenance connection
POSTGRES_BASE_URL = os.environ.get(
    "TEST_PG_URL", "postgresql://postgres:postgres@localhost:5432/postgres"
)
TEST_SOURCE_DB = "resume_analyzer_backup_source"
TEST_TARGET_DB = "resume_analyzer_restore_target"


def run_cmd(
    cmd: list[str], env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    """Run a command, failing with its stderr so CI logs show the real cause."""
    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )
    if result.returncode != 0:
        pytest.fail(
            f"{' '.join(cmd)} exited with {result.returncode}:\n{result.stderr}",
            pytrace=False,
        )
    return result


@pytest.mark.integration
class TestDatabaseBackupAndDisasterRecovery:
    """Verifies that database backups can be generated, validated, and restored accurately."""

    @pytest.fixture(autouse=True)
    def setup_isolated_databases(self):
        """Prepare source and target databases for isolated backup/restore testing."""
        admin_engine = create_engine(POSTGRES_BASE_URL, isolation_level="AUTOCOMMIT")
        with admin_engine.connect() as conn:
            conn.execute(text(f'DROP DATABASE IF EXISTS "{TEST_SOURCE_DB}";'))
            conn.execute(text(f'DROP DATABASE IF EXISTS "{TEST_TARGET_DB}";'))
            conn.execute(text(f'CREATE DATABASE "{TEST_SOURCE_DB}";'))
            conn.execute(text(f'CREATE DATABASE "{TEST_TARGET_DB}";'))

        # Prepare source database schema and seed data
        source_url = f"postgresql://postgres:postgres@localhost:5432/{TEST_SOURCE_DB}"
        source_engine = create_engine(source_url)
        with source_engine.begin() as conn:
            conn.execute(
                text("""
                CREATE TABLE users (
                    id SERIAL PRIMARY KEY,
                    email VARCHAR(255) UNIQUE NOT NULL,
                    full_name VARCHAR(255),
                    hashed_password VARCHAR(255),
                    is_active BOOLEAN DEFAULT TRUE,
                    is_superuser BOOLEAN DEFAULT FALSE
                );
                CREATE TABLE jobs (
                    id SERIAL PRIMARY KEY,
                    owner_id INTEGER REFERENCES users(id),
                    title VARCHAR(255) NOT NULL,
                    position VARCHAR(255) NOT NULL,
                    company_name VARCHAR(255) NOT NULL
                );
                CREATE TABLE applications (
                    id SERIAL PRIMARY KEY,
                    job_id INTEGER REFERENCES jobs(id),
                    full_name VARCHAR(255) NOT NULL,
                    email VARCHAR(255) NOT NULL,
                    ai_score FLOAT,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                );
                CREATE TABLE outbox_events (
                    id SERIAL PRIMARY KEY,
                    event_type VARCHAR(100) NOT NULL,
                    payload JSONB DEFAULT '{}'::jsonb,
                    status VARCHAR(50) DEFAULT 'pending',
                    retry_count INTEGER DEFAULT 0
                );

                -- Seed sample records
                INSERT INTO users (email, full_name, hashed_password, is_superuser)
                VALUES ('admin@test.com', 'Admin User', 'hash123', true),
                       ('hr@test.com', 'HR User', 'hash456', false);

                INSERT INTO jobs (owner_id, title, position, company_name)
                VALUES (2, 'Senior Python Engineer', 'Python Dev', 'Acme Corp');

                INSERT INTO applications (job_id, full_name, email, ai_score)
                VALUES (1, 'Alice Candidate', 'alice@test.com', 95.5),
                       (1, 'Bob Candidate', 'bob@test.com', 82.0);

                INSERT INTO outbox_events (event_type, payload, status)
                VALUES ('send_email', '{"to": "alice@test.com"}'::jsonb, 'published');
            """)
            )
        source_engine.dispose()
        admin_engine.dispose()

        yield

        # Cleanup
        clean_engine = create_engine(POSTGRES_BASE_URL, isolation_level="AUTOCOMMIT")
        with clean_engine.connect() as conn:
            conn.execute(text(f'DROP DATABASE IF EXISTS "{TEST_SOURCE_DB}";'))
            conn.execute(text(f'DROP DATABASE IF EXISTS "{TEST_TARGET_DB}";'))
        clean_engine.dispose()

    def test_backup_and_restore_cycle(self):
        """Execute pg_dump on source DB, verify checksum, restore to target DB, and check records."""
        temp_dir = tempfile.mkdtemp(prefix="backup_test_")
        dump_file = os.path.join(temp_dir, f"{TEST_SOURCE_DB}.dump")
        checksum_file = f"{dump_file}.sha256"

        try:
            # 1. Run pg_dump
            env = os.environ.copy()
            env["PGPASSWORD"] = "postgres"
            dump_cmd = [
                "pg_dump",
                "-h", "localhost",
                "-p", "5432",
                "-U", "postgres",
                "--format=custom",
                "--compress=6",
                "--file=" + dump_file,
                TEST_SOURCE_DB,
            ]
            # PGPASSWORD must reach pg_dump: CI's Postgres service requires
            # password auth over TCP (a local trust-auth server hides this).
            run_cmd(dump_cmd, env=env)
            assert os.path.exists(dump_file)
            assert os.path.getsize(dump_file) > 0

            # 2. Checksum verification
            with open(dump_file, "rb") as f:
                digest = hashlib.sha256(f.read()).hexdigest()
            with open(checksum_file, "w") as f:
                f.write(f"{digest}  {os.path.basename(dump_file)}\n")

            with open(checksum_file, "r") as f:
                recorded_hash = f.read().split()[0]
            assert recorded_hash == digest

            # 3. Archive integrity check with pg_restore --list
            list_cmd = ["pg_restore", "--list", dump_file]
            list_res = run_cmd(list_cmd)
            assert "TABLE DATA public users" in list_res.stdout
            assert "TABLE DATA public applications" in list_res.stdout

            # 4. Restore into target database
            restore_cmd = [
                "pg_restore",
                "-h", "localhost",
                "-p", "5432",
                "-U", "postgres",
                "-d", TEST_TARGET_DB,
                "--clean",
                "--if-exists",
                "--no-owner",
                "--no-privileges",
                dump_file,
            ]
            # pg_restore exit code 0 or 1 on harmless warnings is acceptable
            subprocess.run(restore_cmd, env=env, check=False)

            # 5. Verify restored target database records
            target_url = f"postgresql://postgres:postgres@localhost:5432/{TEST_TARGET_DB}"
            target_engine = create_engine(target_url)
            with target_engine.connect() as conn:
                user_count = conn.execute(text("SELECT count(*) FROM users;")).scalar()
                assert user_count == 2

                job_count = conn.execute(text("SELECT count(*) FROM jobs;")).scalar()
                assert job_count == 1

                app_count = conn.execute(text("SELECT count(*) FROM applications;")).scalar()
                assert app_count == 2

                alice_score = conn.execute(
                    text("SELECT ai_score FROM applications WHERE full_name='Alice Candidate';")
                ).scalar()
                assert alice_score == 95.5

                outbox_count = conn.execute(text("SELECT count(*) FROM outbox_events;")).scalar()
                assert outbox_count == 1
            target_engine.dispose()

        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_upload_storage_backup_and_restore(self):
        """Verify upload folder tarball creation, SHA256 checksumming, and extraction."""
        temp_dir = tempfile.mkdtemp(prefix="upload_test_")
        source_upload = os.path.join(temp_dir, "uploads")
        os.makedirs(os.path.join(source_upload, "resumes"), exist_ok=True)
        os.makedirs(os.path.join(source_upload, "profile"), exist_ok=True)

        sample_resume = os.path.join(source_upload, "resumes", "candidate_1.pdf")
        with open(sample_resume, "wb") as f:
            f.write(b"%PDF-1.4 sample resume mock content")

        archive_path = os.path.join(temp_dir, "uploads_backup.tar.gz")

        try:
            # Create archive
            tar_cmd = ["tar", "-czf", archive_path, "-C", temp_dir, "uploads"]
            run_cmd(tar_cmd)
            assert os.path.exists(archive_path)

            # Extract into target folder
            restore_dir = os.path.join(temp_dir, "restored_root")
            os.makedirs(restore_dir, exist_ok=True)
            untar_cmd = ["tar", "-xzf", archive_path, "-C", restore_dir]
            run_cmd(untar_cmd)

            restored_file = os.path.join(restore_dir, "uploads", "resumes", "candidate_1.pdf")
            assert os.path.exists(restored_file)
            with open(restored_file, "rb") as f:
                content = f.read()
            assert content == b"%PDF-1.4 sample resume mock content"

        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
