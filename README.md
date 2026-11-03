# NetSentry

AI-Assisted Network Configuration Auditing and Remediation Platform.

## Overview

NetSentry is a network security auditing platform designed
to collect device information, inspect configurations,
identify security weaknesses, and provide remediation guidance.

## Initial Scope

- Cisco IOS devices in an authorized PNETLab environment.
- SSH-based read-only information collection.
- Rule-based configuration auditing.
- FastAPI backend.
- Automated tests for security rules.

## Architecture

- Backend: Python, FastAPI
- Device connection: Netmiko
- Rule engine: Python
- Frontend: React + TypeScript (planned)
- Database: SQLite (planned)

## Project Structure

- backend/app/connectors: device connections
- backend/app/rules: security checks
- backend/app/api: API endpoints
- backend/tests: automated tests
- docs: architecture and documentation

## Development Setup

Create a virtual environment:

    python3 -m venv .venv
    source .venv/bin/activate

Install dependencies:

    pip install -r backend/requirements.txt

Run the API:

    uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000

Run tests:

    PYTHONPATH=backend pytest -v

## Security

- Only audit devices that the team is authorized to access.
- Do not commit passwords, private keys, or raw device configurations.
- Initial device collection is read-only.
- Configuration changes require a separate approval workflow.
