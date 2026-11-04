# Oxidized (Python & Django Edition)

A network device configuration backup tool inspired by [Oxidized](https://github.com/ytti/oxidized), converted entirely from Ruby to **Python** and **Django**, with a **PostgreSQL** database backend for all settings, configuration files, and `router.db` node records.

---

## Features

- **Python Core Engine**:
  - Multi-threaded worker scheduler pulling device configurations concurrently.
  - Pluggable inputs: SSH (via Paramiko), Telnet, Exec, and Mock.
  - Pluggable outputs: Local File system and Git repository (via Dulwich).
  - Pluggable sources: PostgreSQL database (Django ORM) and CSV-formatted files.
  - Device Model DSL supporting OS models such as Cisco IOS, Juniper JunOS, Arista EOS, and extensible to any network device.
  - Hook system supporting event triggers (`node_start`, `node_end`).

- **Django Web Framework & REST API**:
  - Full UI parity with `oxidized-web` including Bootstrap styling, live dataTables, theme toggle, and search.
  - RESTful endpoints matching original Oxidized-web:
    - `GET /nodes` (and `/nodes.json`): List all nodes and their status.
    - `GET /nodes/group/<group>` (and `.json`): Filter nodes by group.
    - `GET /nodes/model/<model>` (and `.json`): Filter nodes by model.
    - `GET /node/show/<node>` (and `.json`): View detailed node attributes.
    - `GET /node/fetch/<node>` (and `group/<node>`): Retrieve the latest configuration.
    - `GET/PUT /node/next/<node>`: Move a node to the front of the queue and trigger backup.
    - `GET /reload` (and `.json`): Reload node inventory from backend sources.
    - `POST /nodes/conf_search`: Search strings across backed-up device configurations.
    - `GET /nodes/stats` (and `.json`): Overview statistics of backup statuses.
    - `GET /node/version`: List version history for a device.
    - `GET /node/version/view`: View a specific historical version.
    - `GET /node/version/diffs`: View diff between two versions.

- **Configurable in Django Admin with PostgreSQL**:
  - **Oxidized Configuration**: Edit YAML settings directly in Django Admin (`/admin/oxidized_web/oxidizedsetting/`).
  - **router.db File**: Edit the raw CSV `router.db` content directly in Django Admin (`/admin/oxidized_web/routerdbentry/`).
  - **Structured Devices**: Add, edit, enable/disable individual devices in Django Admin (`/admin/oxidized_web/device/`).

---

## Requirements

- Python 3.10+
- PostgreSQL 14+
- System packages: `libpq-dev` (for psycopg2 compilation if using wheels/source)

---

## Installation

### 1. Clone the repository

```bash
git clone <repo-url>
cd configlogger
```

### 2. Set up virtual environment and install dependencies

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Configure PostgreSQL Database

Create the database and role in PostgreSQL:

```bash
sudo su - postgres -c "psql -c \"CREATE USER oxidized WITH PASSWORD 'oxidized' SUPERUSER;\""
sudo su - postgres -c "psql -c 'CREATE DATABASE oxidized OWNER oxidized;'"
```

By default, the application connects to:
- **Host**: `localhost` (port `5432`)
- **Database**: `oxidized`
- **User**: `oxidized`
- **Password**: `oxidized`

You can customize these using environment variables:
- `POSTGRES_DB`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `POSTGRES_HOST`
- `POSTGRES_PORT`

### 4. Run Migrations & Create Superuser

```bash
python3 manage.py migrate
python3 manage.py createsuperuser
```

---

## Usage

### 1. Launch the Django Web Application

Start the web interface and API:

```bash
python3 manage.py runserver 0.0.0.0:8000
```

- Web UI: Navigate to `http://localhost:8000/nodes`
- Admin Interface: Navigate to `http://localhost:8000/admin/`

### 2. Configuring via Django Admin

1. Open `http://localhost:8000/admin/` in your browser and log in with your superuser.
2. Under **OXIDIZED_WEB**:
   - **Oxidized Configuration**: Update the global YAML configuration (thread count, timeouts, default output driver, Git repo path, etc.).
   - **Router.db File**: Maintain router definitions in standard CSV format (`name:model:group` or `name:ip:model:username:password`).
   - **Devices (router.db nodes)**: Visually create and edit network devices, assign models, credentials, custom variables, and toggle enabled state.

### 3. Running the Oxidized Daemon

#### Option A: Django Management Command

```bash
# Run backup daemon continuously:
python3 manage.py run_oxidized

# Run single backup pass for all nodes:
python3 manage.py run_oxidized --run-once

# Run backup for a single node:
python3 manage.py run_oxidized --node core-router-01
```

#### Option B: Standalone CLI Binary

The `bin/oxidized` executable is also available:

```bash
# Run continuously:
./bin/oxidized

# Run single pass with debug logging:
./bin/oxidized -1 -d

# Run specific node:
./bin/oxidized --node core-router-01
```

---

## Testing

Run the test suite using `pytest`:

```bash
python3 -m pytest -v
```

All tests run against PostgreSQL to verify model execution, Git/File outputs, config loading, and Django API endpoints.
