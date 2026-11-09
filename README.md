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

## Production Deployment Instructions

For robust production environments, the **Oxidized Backup Daemon** and the **Django Web Interface** should be managed as independent **systemd services** running behind an Nginx reverse proxy.

---

### Architecture Overview

```
+-------------------------------------------------------------------------+
|                                Nginx                                    |
|                       (Port 80/443 SSL Termination)                     |
+------------------------------------+------------------------------------+
                                     | Reverse Proxy (Unix Socket or HTTP)
                                     v
                  +--------------------------------------+
                  |           Gunicorn / Django          |
                  |     (Web Dashboard, REST API, Admin) |
                  +------------------+-------------------+
                                     | PostgreSQL Queries
                                     v
                  +--------------------------------------+
                  |          PostgreSQL Database         |
                  |  (Settings, Devices, Revisions, Diff)|
                  +------------------+-------------------+
                                     ^ PostgreSQL Queries
                                     |
                  +------------------+-------------------+
                  |        Oxidized Backup Daemon        |
                  |    (Multi-threaded Worker Pool)      |
                  +--------------------------------------+
```

---

### Step 1: Prepare Environment and Static Files

In your application root (`/opt/oxidized` or `/app`):

```bash
# Activate virtual environment
source /opt/oxidized/venv/bin/activate

# Apply migrations
python3 manage.py migrate

# Collect static assets into staticfiles directory
python3 manage.py collectstatic --noinput
```

---

### Step 2: Configure Systemd Services

Create a dedicated system user (e.g., `oxidized`):
```bash
sudo useradd -r -s /bin/false -d /opt/oxidized oxidized
sudo chown -R oxidized:oxidized /opt/oxidized
```

#### 1. Oxidized Daemon Service: `/etc/systemd/system/oxidized.service`

```ini
[Unit]
Description=Oxidized Network Device Backup Daemon
After=network.target postgresql.service
Wants=postgresql.service

[Service]
Type=simple
User=oxidized
Group=oxidized
WorkingDirectory=/opt/oxidized
Environment="DJANGO_SETTINGS_MODULE=oxidized_project.settings"
Environment="POSTGRES_DB=oxidized"
Environment="POSTGRES_USER=oxidized"
Environment="POSTGRES_PASSWORD=oxidized"
Environment="POSTGRES_HOST=127.0.0.1"
Environment="POSTGRES_PORT=5432"
ExecStart=/opt/oxidized/venv/bin/python3 manage.py run_oxidized
ExecReload=/bin/kill -HUP $MAINPID
Restart=always
RestartSec=10
LimitNOFILE=65535

[Install]
WantedBy=multi-user.target
```

#### 2. Oxidized Web Application Service: `/etc/systemd/system/oxidized-web.service`

```ini
[Unit]
Description=Oxidized Django Web Dashboard & REST API
After=network.target postgresql.service
Wants=postgresql.service

[Service]
Type=simple
User=oxidized
Group=oxidized
WorkingDirectory=/opt/oxidized
Environment="DJANGO_SETTINGS_MODULE=oxidized_project.settings"
Environment="POSTGRES_DB=oxidized"
Environment="POSTGRES_USER=oxidized"
Environment="POSTGRES_PASSWORD=oxidized"
Environment="POSTGRES_HOST=127.0.0.1"
Environment="POSTGRES_PORT=5432"
ExecStart=/opt/oxidized/venv/bin/gunicorn oxidized_project.wsgi:application \
          --workers 4 \
          --bind 127.0.0.1:8000 \
          --timeout 120 \
          --access-logfile /var/log/oxidized/web_access.log \
          --error-logfile /var/log/oxidized/web_error.log
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Enable and start both services:
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now oxidized.service
sudo systemctl enable --now oxidized-web.service
```

---

### Step 3: Configure Nginx Reverse Proxy

Create `/etc/nginx/sites-available/oxidized.conf`:

```nginx
server {
    listen 80;
    server_name oxidized.example.com;

    client_max_body_size 64M;

    # Static assets
    location /static/ {
        alias /opt/oxidized/staticfiles/;
        expires 30d;
        add_header Cache-Control "public, no-transform";
    }

    # Proxy to Gunicorn
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 180s;
        proxy_connect_timeout 60s;
    }
}
```

Enable the site and reload Nginx:
```bash
sudo ln -s /etc/nginx/sites-available/oxidized.conf /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

---

## Daemon Control & Reloading from the Web Interface

Oxidized provides web controls to reload node inventory or restart the background daemon without requiring SSH access to the server.

### 1. Operations > Daemon Control (`/daemon`)
- **Status Dashboard**: Displays the current status (`Running` / `Offline`), process ID (`PID`), active PID file location, worker threads, and managed device count.
- **Reload Configuration & Nodes Button**: Sends a `SIGHUP` signal to the background daemon. The daemon instantly refreshes global settings, custom OS models, and node inventory from PostgreSQL without interrupting running backup tasks or dropping connection pools.
- **Restart Daemon Process Button**: Sends a `SIGTERM` signal to gracefully shut down the daemon. Because the service is configured with `Restart=always` under systemd, systemd immediately restarts the daemon with fresh memory and configuration.

### 2. Operations > Reload Inventory (`/reload` and `/reload.json`)
- Calling `/reload` triggers a reload of all nodes and custom models from PostgreSQL and signals the background daemon.
- Also available programmatically via REST API:
  ```bash
  curl -X POST -u admin:password http://oxidized.example.com/reload.json
  ```

### 3. Command-Line Signals
If you have terminal access, you can also signal or restart the daemon directly:
```bash
# Reload inventory without restarting:
kill -HUP $(cat ~/.config/oxidized/pid)

# Restart daemon:
sudo systemctl restart oxidized
```

---

## User Authentication & Microsoft Azure / Entra ID SSO

All web views, device inventories, configuration diffs, and models require authentication. Oxidized supports:
1. **Local Defined Users**:
   - Create local administrators or operators via standard Django user management (`python3 manage.py createsuperuser` or through the admin interface at `/admin/auth/user/`).
   - Log in using username and password at `/login`.
2. **Microsoft Azure / Entra ID SSO**:
   - Single Sign-On using OAuth2 / OpenID Connect powered by MSAL (`msal`).
   - Configure Azure credentials either via the Django Admin page under **Oxidized Configuration > Microsoft Azure / Entra ID SSO Authentication** or using environment variables:
     * `AZURE_SSO_ENABLED=true`
     * `AZURE_TENANT_ID=<your-tenant-id-or-common>`
     * `AZURE_CLIENT_ID=<your-app-registration-client-id>`
     * `AZURE_CLIENT_SECRET=<your-client-secret-value>`
     * `AZURE_REDIRECT_URI=https://<your-oxidized-domain>/auth/azure/callback`
   - When enabled, the login screen displays a **"Sign in with Microsoft Entra ID"** SSO button. Upon successful authentication, user accounts are automatically provisioned and logged in.

---

## Testing

Run the automated test suite with `pytest`:

```bash
python3 -m pytest tests/ -v
```

Tests cover core worker scheduling, Paramiko SSH negotiation with legacy crypto, CLI/exec driver execution, environment variable propagation, database output storage, and Django web/API endpoints.
