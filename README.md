# Ignition 8.1 MQTT Sparkplug feasibility demo

This runbook builds and manually commissions a local five-service demo:

```text
Primary Ignition → MQTT Transmission → MQTT Distributor
                                  ├→ Development MQTT Engine
                                  └→ Test MQTT Engine
Primary Ignition → MySQL historian
```

It is a local feasibility environment, not a production deployment. Gateway
HTTP is loopback-only; MySQL and MQTT have no host ports. TLS is intentionally
disabled only for this private Docker-network demonstration. Authentication,
exact MQTT ACLs, and module command blocks are required compensating controls.

## What this repository contains

The repository contains only source, Compose configuration, pinned image and
module references, and two small bootstrap helpers. It intentionally contains
no module binaries, passwords, encoding keys, Gateway backups, database
backups, browser sessions, or runtime data. Never commit any of those files.

The setup is deliberately manual after startup: an operator accepts each
module license/certificate and enters the MQTT and Gateway configuration in the
four Gateway browsers. There is no Designer, Gateway Network, host MQTT port,
or automated configuration import.

## Prerequisites

- Docker Engine and Docker Compose, with at least 6 GiB available to Docker.
- A supported browser for the four local Gateway pages.
- Access to the official Cirrus Link module URLs in
  [`artifacts/modules.sources`](artifacts/modules.sources), plus authority to
  download and accept the associated licenses.
- `shasum` (included with macOS and most Linux distributions). The commands
  below use Docker's Python image, so a host Python installation is not
  required.

## 1. Clone and prepare local-only directories

Clone the public repository, then create the directories Git cannot preserve
because their contents are intentionally ignored:

```sh
git clone <repository-url>
cd ignition
mkdir -p \
  secrets \
  artifacts/downloads \
  artifacts/backups/gateway/primary \
  artifacts/backups/gateway/mqtt \
  artifacts/backups/gateway/development \
  artifacts/backups/gateway/test \
  artifacts/backups/mysql
docker version
docker compose version
docker compose config --quiet
```

`docker compose config --quiet` validates the Compose file without starting
containers. An empty `git status --short` is expected after a clone and before
the local bootstrap files are generated.

### Start with fresh data volumes

The generated secret files are used only when MySQL and each Gateway initialize
their data volume for the first time. They are permanently coupled to that
initialized state: do **not** generate replacement bootstrap secrets for an
existing set of volumes.

On a clean Docker host, continue with the default commands below. If the host
already has an older `ignition-feasibility` deployment, choose one of these
safe paths before continuing:

- Reuse that deployment's original local secret files and volumes; do not rerun
  Step 2.
- Start a separate clean demo with a unique Compose project name and four
  unused loopback ports. Use the same project-name and port overrides on every
  subsequent Compose command in this guide. For example:

  ```sh
  export COMPOSE_PROJECT_NAME=ignition-demo-$(date +%Y%m%d)
  export PRIMARY_HTTP_PORT=19088
  export MQTT_HTTP_PORT=19188
  export DEVELOPMENT_HTTP_PORT=19288
  export TEST_HTTP_PORT=19388
  ```

Do not delete existing volumes merely to begin this guide unless you have
confirmed that their data is disposable and any needed backups have been made.

To change only loopback ports or timezone, copy the non-secret example:

```sh
cp .env.example .env
```

Do not put passwords or encoding keys in `.env`.

## 2. Generate the bootstrap secrets

Compose requires ten local secret files before the four Gateways and MySQL can
be initialized. The following command uses the retained generator directly in
the Python container; it creates mode-0600 files and never prints values. Run
it once in a new clone. It refuses to overwrite an existing file.

```sh
docker run --rm --network none --cap-drop ALL \
  --user "$(id -u):$(id -g)" \
  --mount type=bind,src="$PWD/docker/utility",dst=/app,readonly \
  --mount type=bind,src="$PWD/secrets",dst=/workspace/secrets \
  python:3.13.14-slim-bookworm \
  python /app/generate_secrets.py --output /workspace/secrets
```

This creates four Gateway administrator passwords, four Gateway encoding keys,
and two MySQL passwords. The encoding keys must be retained for the lifetime
of their corresponding Gateway data volumes; changing one after commissioning
can make saved encrypted credentials unreadable.

Do not display a secret with `cat`, paste it into a shell command, screenshot
it, or add it to Git. Read a value locally only when typing it into its matching
masked Gateway field.

## 3. Download and verify the signed modules

Download each signed module into `artifacts/downloads/`. These commands use
the retained download helper. They need network access because the modules come
from the official Cirrus Link release URLs.

```sh
docker run --rm --cap-drop ALL \
  --user "$(id -u):$(id -g)" \
  --mount type=bind,src="$PWD/docker/utility",dst=/app,readonly \
  --mount type=bind,src="$PWD/artifacts/downloads",dst=/workspace/downloads \
  python:3.13.14-slim-bookworm \
  python /app/fetch_modules.py \
  --url https://releases.inductiveautomation.com/third-party/cirrus-link/4.0.36/MQTT-Transmission-signed.modl \
  --output /workspace/downloads/mqtt-transmission-4.0.36.modl

docker run --rm --cap-drop ALL \
  --user "$(id -u):$(id -g)" \
  --mount type=bind,src="$PWD/docker/utility",dst=/app,readonly \
  --mount type=bind,src="$PWD/artifacts/downloads",dst=/workspace/downloads \
  python:3.13.14-slim-bookworm \
  python /app/fetch_modules.py \
  --url https://releases.inductiveautomation.com/third-party/cirrus-link/4.0.36/MQTT-Distributor-signed.modl \
  --output /workspace/downloads/mqtt-distributor-4.0.36.modl

docker run --rm --cap-drop ALL \
  --user "$(id -u):$(id -g)" \
  --mount type=bind,src="$PWD/docker/utility",dst=/app,readonly \
  --mount type=bind,src="$PWD/artifacts/downloads",dst=/workspace/downloads \
  python:3.13.14-slim-bookworm \
  python /app/fetch_modules.py \
  --url https://releases.inductiveautomation.com/third-party/cirrus-link/4.0.36/MQTT-Engine-signed.modl \
  --output /workspace/downloads/mqtt-engine-4.0.36.modl
```

Verify the downloaded files before building. The expected hashes are also
recorded in [`artifacts/modules.lock`](artifacts/modules.lock).

```text
mqtt-transmission-4.0.36.modl  bc08e2e5195add832c0f5ced9aa90f2afd3466185829a42b50133f8ba500f3df
mqtt-distributor-4.0.36.modl   5470cb507d4baf87a9ce2e5b5580251e01cf65cf893f10b4c5364a02f9b0d771
mqtt-engine-4.0.36.modl        ee26a783f1dc8c9dad38cefa4967089754673d2b720ea1c0409bc29eb372814b
```

```sh
shasum -a 256 artifacts/downloads/mqtt-transmission-4.0.36.modl \
  artifacts/downloads/mqtt-distributor-4.0.36.modl \
  artifacts/downloads/mqtt-engine-4.0.36.modl
```

Stop if a digest differs.

## 4. Build and start the base stack

Build the three derivative Gateway images. Test reuses the image built for
Development.

```sh
docker compose build primary-ignition mqtt-ignition development-ignition
docker compose up --detach --no-build
docker compose ps
```

Wait until MySQL shows `healthy` in `docker compose ps`, then wait for all four
Gateway HTTP endpoints. Press `Ctrl-C` if an endpoint does not become ready and
inspect `docker compose logs <service>` before continuing.

```sh
for port in 9088 9188 9288 9388; do
  until curl --fail --silent --show-error "http://127.0.0.1:${port}/StatusPing"; do
    sleep 5
  done
done
```

If `curl` is unavailable, open each Gateway address in a browser and wait for
its login page instead. When using the isolated-port example above, substitute
ports `19088`, `19188`, `19288`, and `19388` in the addresses below.

The default browser addresses and administrator usernames are:

| Gateway | Address | Username | Installed module |
| --- | --- | --- | --- |
| Primary | <http://127.0.0.1:9088> | `primary-admin` | MQTT Transmission |
| MQTT | <http://127.0.0.1:9188> | `mqtt-admin` | MQTT Distributor |
| Development | <http://127.0.0.1:9288> | `development-admin` | MQTT Engine |
| Test | <http://127.0.0.1:9388> | `test-admin` | MQTT Engine |

Sign in to every Gateway using the matching locally generated
`*-admin-password.txt` file. On each fresh or rebuilt Gateway, accept the
Cirrus Link certificate and license prompts, then confirm the matching module
is running in Trial mode. Do not create Gateway Network connections.

## 5. Generate the three MQTT passwords

Generate the credentials for the three manually configured MQTT identities:

```sh
docker run --rm --network none --cap-drop ALL \
  --user "$(id -u):$(id -g)" \
  --mount type=bind,src="$PWD/docker/utility",dst=/app,readonly \
  --mount type=bind,src="$PWD/secrets",dst=/workspace/secrets \
  python:3.13.14-slim-bookworm \
  python /app/generate_secrets.py --output /workspace/secrets \
  --only mqtt-primary-transmission-password \
  --only mqtt-development-engine-password \
  --only mqtt-test-engine-password
```

| MQTT identity | Local password file | Client ID |
| --- | --- | --- |
| `primary-transmission` | `mqtt-primary-transmission-password.txt` | `Ignition-Primary-Transmission` |
| `development-engine` | `mqtt-development-engine-password.txt` | `Ignition-Development-Engine` |
| `test-engine` | `mqtt-test-engine-password.txt` | `Ignition-Test-Engine` |

Read each value locally and type it only into the matching masked Gateway
field. Do not pass the values through environment variables or Compose.

## 6. Configure MQTT Distributor

On the MQTT Gateway:

1. Enable one internal TCP listener on port `1883`.
2. Disable WebSocket and anonymous access. Do not map MQTT to a host port.
3. Create the three users in the preceding table with their matching passwords.
4. Add exactly these case-sensitive ACL rows.

| Identity | Permission | Topic |
| --- | --- | --- |
| `primary-transmission` | R | `spBv1.0/IgnitionDemo/NCMD/Primary` |
|  | R | `spBv1.0/IgnitionDemo/DCMD/Primary/#` |
|  | R | `spBv1.0/STATE/Ignition-Development` |
|  | W | `spBv1.0/IgnitionDemo/NBIRTH/Primary` |
|  | W | `spBv1.0/IgnitionDemo/NDATA/Primary` |
|  | RW | `spBv1.0/IgnitionDemo/NDEATH/Primary` |
| `development-engine` | R | `a/#` |
|  | R | `spBv1.0/IgnitionDemo/#` |
|  | W | `spBv1.0/IgnitionDemo/NCMD/Primary` |
|  | RW | `spBv1.0/STATE/Ignition-Development` |
| `test-engine` | R | `a/#` |
|  | R | `spBv1.0/IgnitionDemo/#` |
|  | W | `spBv1.0/IgnitionDemo/NCMD/Primary` |

After the intended clients connect, remove the default broad `admin` user. Do
not grant `W #`, `RW #`, write access to `a/#`, or DCMD write access to any
identity.

## 7. Configure Development first

On Development MQTT Engine, create:

- a set named `Development Primary`, with Primary Host enabled and Primary Host
  ID `Ignition-Development`;
- an `Internal Distributor` server at `tcp://mqtt-ignition:1883`, associated
  with that set and authenticated as `development-engine`;
- a Sparkplug B namespace explicitly associated with that set and server,
  filtered to Group `IgnitionDemo` and Edge `Primary`.

Enable only Sparkplug B. Keep Block Node Commands, Block Device Commands, and
Ignore Files enabled. Disable Elecsys, Sparkplug A, Xirgo, custom namespaces,
legacy STATE, UNS, file handling/acknowledgement, and alarm acknowledgement.

## 8. Configure Primary historian and publisher

On Primary, create a MySQL connection named `MySQL_Historian_DB` with:

| Field | Value |
| --- | --- |
| Host | `mysql:3306` |
| Database | `ignition_historian` |
| Username | `ignition_primary` |
| Password | locally read `mysql-primary-password.txt` |

Create the `Demo_History` tag history provider using that connection. Then
create exactly six direct application tags at `Demo/Pump01`, with no child
folder:

```text
Running
SpeedHz
FlowGPM
TemperatureF
HighTemperatureAlarm
LastUpdate
```

Historize the first five tags only. `HighTemperatureAlarm` is Boolean;
`LastUpdate` is not historized.

Create the following MQTT Transmission records:

- a set named `Development Primary`, with Primary Host ID
  `Ignition-Development` and RPC disabled;
- an `Internal Distributor` server at `tcp://mqtt-ignition:1883`, associated
  with that set and authenticated as `primary-transmission`;
- one initially disabled transmitter named `Pump01 Edge Publisher`, with
  provider `default`, path `Demo/Pump01`, Group `IgnitionDemo`, Edge `Primary`,
  no Device ID, aliases enabled, compression `NONE`, alarm events disabled, no
  history store, and Block Commands enabled.

Explicitly select `Development Primary` on the transmitter. Wait until the
Development Primary Host STATE is online, then enable this one transmitter. Do
not add a Device publisher or any auxiliary MQTT publisher.

## 9. Configure Test as a read-only consumer

On Test MQTT Engine, create:

- a set named `Test Read Only`, with Primary Host disabled and a blank Primary
  Host ID;
- an `Internal Distributor` server at `tcp://mqtt-ignition:1883`, associated
  with that set and authenticated as `test-engine`;
- a Sparkplug B namespace explicitly associated with `Test Read Only` and the
  server, filtered to Group `IgnitionDemo` and Edge `Primary`.

Apply the same namespace restrictions and command blocks as Development. Test
must remain non-primary and read-only.

## 10. Confirm the working demo

Use the authenticated Gateway pages to confirm all of the following:

- Primary publishes automatic NBIRTH and NDATA for Edge `Primary` under
  `spBv1.0/IgnitionDemo`.
- The NBIRTH includes the six approved Pump01 application metrics. Additional
  documented Sparkplug protocol/control metrics are acceptable.
- Development and Test each show six Good-quality tags at
  `Edge Nodes/IgnitionDemo/Primary`.
- Development is the sole Primary Host; the three intended MQTT clients are
  connected; no auxiliary publisher or user remains.
- Primary's `Demo_History` and `MySQL_Historian_DB` are running.

The configuration persists in Docker named volumes. `docker compose stop` and
`docker compose up --detach --no-build` retain that state. Do not run
`docker compose down -v` unless you deliberately intend to erase the complete
commissioned demo and start again from Step 1. If you intentionally reset
volumes, remove the corresponding local bootstrap secret files as well and
generate a new matching set in Step 2 before starting the stack again.

## Scope and safety boundaries

This demo is intentionally limited to private Docker networking and manual
browser configuration. It does not provide production TLS, a Designer,
automated restoration, forced NDEATH testing, manual rebirth testing, or a
portable preconfigured-state archive. Keep all generated files local and
ignored; a different user must repeat the bootstrap and browser steps above.
