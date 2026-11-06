# Oxidized (Python & Django Edition)

A network device configuration backup tool inspired by [Oxidized](https://github.com/ytti/oxidized), converted entirely from Ruby to **Python 3** and **Django**, with a **PostgreSQL** database backend for all settings, configuration files, revisions, and `router.db` node records.

---

## Key Capabilities & Features

### 1. Python Core Engine & Daemon
- **Multi-threaded Worker Pool**: Concurrent device configuration collection with configurable thread count (`threads`).
- **Pluggable Inputs**:
  - `ssh`: Powered by Paramiko with robust prompt handling, legacy crypto support, and debug logging.
  - `telnet`: Native socket-based telnet client with regex expectation matching.
  - `cli` / `exec`: Executes external Linux executables or shell commands outside Python with parameter substitution and exported environment variables.
  - `mock`: Synthetic device responses for development and unit testing.
- **Pluggable Outputs**:
  - `database`: PostgreSQL revision tracking directly stored in `NodeRevision` with diff and version history.
  - `git`: Git repository output powered by Dulwich.
  - `file`: Local filesystem hierarchy storage.
- **Pluggable Sources**:
  - `django`: Loads device inventory and credentials directly from PostgreSQL.
  - `csv`: Reads node records from standard CSV-formatted files.
- **Model Support**:
  - Library of **195 built-in network OS models** (Cisco IOS/XR/NXOS, Juniper JunOS, Arista EOS, FortiOS, VyOS, Huawei VRP, EdgeOS, etc.).
  - Support for **Custom OS Models** defined via web interface or Django Admin with configurable commands, prompts, and credentials.
  - **Regex String Replacement (`clean_filters`)**: Built-in sanitization and secret-scrubbing that applies regex string replacements across all command outputs *before* writing configurations to the database (`NodeRevision`) and *before* displaying them in the web UI or REST API.
- **Resilient Scheduling & Rate Limiting**:
  - System-wide interval scheduling (`interval`, default 3600s) and per-host interval overrides (`Device.interval`).
  - Adaptive failure backoff (`retry_delay` / `fail_timeout`, default 300s) before re-attempting failed devices.
  - **Rapid pulling prevention**: Cooldown throttling (`min_cooldown`, default 60s) and in-flight backup detection returning HTTP 429 to avoid hammering network gear.

### 2. Modern Web Dashboard & REST API
- Clean, structured user interface with fixed sidebar navigation, breadcrumbs, search, and responsive cards (free of legacy branding).
- **Dedicated User-Facing Configuration Pages**:
  - `/devices`: Comprehensive network device inventory management with status pills, attempt counters, failure errors, search, and CRUD forms.
  - `/models`: OS model browser and editor for custom model commands and regexes.
  - `/nodes`: Dashboard and real-time node operational view.
  - `/nodes/stats`: Backup status distribution and engine metrics.
  - `/nodes/conf_search`: Multi-device full-text configuration search.
  - `/node/version`: Historical revision list, snapshot viewing, and unified diff viewer.
- **Full REST API Parity**:
  - `GET /nodes`, `/nodes.json`
  - `GET /nodes/group/<group>`, `/nodes/model/<model>`
  - `GET /node/show/<node>`, `/node/show/<group>/<node>`
  - `GET /node/fetch/<node>`, `/node/fetch/<group>/<node>`
  - `GET/PUT /node/next/<node>`: Request immediate backup (enforces cooldown).
  - `GET /reload`, `/reload.json`: Reload inventory from PostgreSQL.
  - `GET /nodes/stats`, `/nodes/conf_search`

### 3. PostgreSQL Configuration & Admin
- All settings, nodes, model definitions, and backups are stored in PostgreSQL:
  - **`OxidizedSetting`**: Global daemon configuration (threads, intervals, timeouts, default inputs/outputs, CLI command templates).
  - **`Device`**: Per-device attributes (hostname, IP, model, group, interval, credentials, input/output overrides, SSH crypto options, and CLI command templates).
  - **`CustomModel`**: Custom and modified network OS models with commands, regex prompts, and hooks.
  - **`RouterDbEntry`**: Raw CSV `router.db` content for legacy file compatibility.
  - **`NodeRevision`**: Stored configuration snapshots and change timestamps.
- **Granular Permissions**:
  - Group-based access control with granular permissions (`can_view_node`, `can_edit_node`, `can_delete_node`, `can_view_model`, `can_edit_model`, `can_delete_model`).
  - Non-admin users are restricted to devices matching their assigned group.
  - Node configuration bodies are excluded from Django Admin for data governance.

---

## Advanced Features & Usage

### External Linux Executable / CLI Input Mode

Oxidized can execute external Linux utilities (such as custom scripts, `sshpass`, `rancid`, `curl`, `ansible-playbook`, or proprietary tools) to retrieve device configurations.

#### Variable Interpolation
Command templates support dynamic variables:
- `{host}`: Device IP or hostname
- `{ip}`: Device IP address (falls back to hostname)
- `{name}`: Device name
- `{username}` or `{user}`: Effective device username
- `{password}` or `{pass}`: Effective device password
- `{model}`: Device OS model name
- `{group}`: Device group name
- `{port}`: SSH/Telnet port (default 22)
- `{command}` or `{cmd}`: Model command (if applicable)
- Plus any custom variables defined on the device.

#### Subprocess Environment Variables
The invoked command also inherits all node parameters in its environment:
- `OXIDIZED_HOST`
- `OXIDIZED_IP`
- `OXIDIZED_NAME`
- `OXIDIZED_USER` / `OXIDIZED_USERNAME`
- `OXIDIZED_PASSWORD`
- `OXIDIZED_MODEL`
- `OXIDIZED_GROUP`
- `OXIDIZED_PORT`
- `OXIDIZED_CMD`
- `OXIDIZED_VAR_<VARNAME>`

#### Configuration
- **Web UI**: In `/devices/add` or `/devices/<id>/edit`, set **Input Mechanism** to `CLI / External Executable (cli)` and enter the command template in **CLI / External Linux Executable Command Template**.
- **Django Admin**: Set `cli_cmd` on the Device or `input_cli_cmd` in `OxidizedSetting`.
- **Command Line**:
  ```bash
  # Ad-hoc backup using CLI command template:
  ./bin/oxidized --node switch01 --host 192.168.1.1 --input cli \
    --cli-cmd "sshpass -p '{password}' ssh -o StrictHostKeyChecking=no {username}@{host} 'show running-config'" \
    -u admin -p s3cr3t -o db
  ```

---

### Model Regex String Replacement & Sanitization (`clean_filters`)

Custom models support regex string replacement pairs to sanitize secrets, passwords, tokens, or dynamic operational noise before configurations are stored in PostgreSQL or rendered in the web UI / REST API.

#### Syntax & Formats
In `/models/add`, `/models/<id>/edit`, or the Django Admin for `CustomModel`, define `clean_filters` as a JSON array of `[pattern, replacement]` pairs or objects:
```json
[
  ["password\\s+\\S+", "password <REDACTED_PASSWORD>"],
  ["snmp-server community \\S+", "snmp-server community <HIDDEN>"],
  {"pattern": "api_key=[0-9a-fA-F]+", "replace": "api_key=REDACTED_KEY"}
]
```

#### Replacement Guarantees
- **Pre-Storage & Pre-Display Execution**: Applied automatically as `:all` filters during command execution and CLI extraction.
- **Zero Secret Leakage to Database**: Unsanitized raw secrets matching regex patterns are replaced before being committed to PostgreSQL (`NodeRevision`) or output files/Git.
- **Unified Across Interfaces**: Web configuration viewer (`/node/fetch`), version history (`/node/version/view`), and diff comparisons (`/node/version/diffs`) all display the scrubbed configuration.

---

### Per-Host SSH Cryptography & Legacy Ciphers

For legacy network devices that fail modern OpenSSH negotiations:
- **Force Legacy SSH-RSA**: Disable SHA-2 signatures (`rsa-sha2-256`, `rsa-sha2-512`) and negotiate standard `ssh-rsa` key types (`Device.ssh_legacy_rsa`).
- **KEX Algorithms Override**: Specify allowed Key Exchange algorithms, e.g., `+diffie-hellman-group14-sha1,diffie-hellman-group1-sha1`.
- **HostKey Algorithms Override**: Specify allowed host keys, e.g., `+ssh-rsa,ssh-dss`.
- **Cipher Algorithms Override**: Specify allowed ciphers, e.g., `+aes128-cbc,3des-cbc,aes256-cbc`.
- **Ignore Hostkey Verification**: Connect even if host keys have changed or are invalid (`Device.ssh_clear_hostkey`).

All options are configurable per-device on `/devices` forms and in Django Admin.

---

## Installation & Setup

### 1. Prerequisites
- Python 3.10+
- PostgreSQL 14+
- System libraries: `libpq-dev`

### 2. Clone Repository & Setup Virtualenv

```bash
git clone <repo-url>
cd configlogger
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Setup PostgreSQL

Create the PostgreSQL database and user:

```bash
sudo su - postgres -c "psql -c \"CREATE USER oxidized WITH PASSWORD 'oxidized' SUPERUSER;\""
sudo su - postgres -c "psql -c 'CREATE DATABASE oxidized OWNER oxidized;'"
```

Database connection settings can be configured via environment variables:
- `POSTGRES_DB` (default: `oxidized`)
- `POSTGRES_USER` (default: `oxidized`)
- `POSTGRES_PASSWORD` (default: `oxidized`)
- `POSTGRES_HOST` (default: `localhost`)
- `POSTGRES_PORT` (default: `5432`)

### 4. Database Migrations & Initial Setup

```bash
python3 manage.py migrate
python3 manage.py createsuperuser
```

---

## Running the Application

### 1. Run the Web Server

```bash
python3 manage.py runserver 0.0.0.0:8000
```
- **Web UI**: `http://localhost:8000/nodes`
- **Device Management**: `http://localhost:8000/devices`
- **OS Model Library**: `http://localhost:8000/models`
- **Django Admin**: `http://localhost:8000/admin/`

### 2. Run the Backup Daemon

#### Via Django Management Command:
```bash
# Continuous daemon mode:
python3 manage.py run_oxidized

# Single pass for all enabled devices:
python3 manage.py run_oxidized --run-once

# Single pass with verbose debug output:
python3 manage.py run_oxidized --run-once -v

# Target specific node:
python3 manage.py run_oxidized --node core-switch-01
```

#### Via Standalone CLI Executable:
```bash
# Daemon mode:
./bin/oxidized

# Single pass with debug logging:
./bin/oxidized -1 -d

# Ad-hoc node execution without prior database record:
./bin/oxidized --node edge-router-01 --host 10.0.0.1 -m ios -u admin -p secret -1
```

---

## Testing

Run the automated test suite with `pytest`:

```bash
python3 -m pytest tests/ -v
```

Tests cover core worker scheduling, Paramiko SSH negotiation with legacy crypto, CLI/exec driver execution, environment variable propagation, database output storage, and Django web/API endpoints.
