#!/usr/bin/env python3
"""
Minecraft Server Manager for Oracle Cloud (Terraform-based)

Manages a remote Minecraft server deployed via Terraform on Oracle Cloud.
Uses Docker (itzg/minecraft-server) with SSH access.

Commands:
    mc_manager.py status                     - Show server status and info
    mc_manager.py install <mod_name>         - Search and install a mod from Modrinth
    mc_manager.py install-pack <pack_name>   - Search and install a modpack from Modrinth
    mc_manager.py uninstall-pack             - Remove modpack and revert to vanilla
    mc_manager.py remove <mod_name>          - Remove an installed mod
    mc_manager.py list                       - List all installed mods
    mc_manager.py set-version <version>      - Change Minecraft version and restart
    mc_manager.py set-type <type>            - Change server type (forge, fabric, paper, etc.)
    mc_manager.py set-motd <message>         - Change server MOTD
    mc_manager.py restart                    - Restart the server container
    mc_manager.py stop                       - Stop the server container
    mc_manager.py start                      - Start the server container

Requires: paramiko, requests (pip install -r requirements.txt)
"""

import json
import os
import sys
import time
import tempfile
import argparse
import re
from pathlib import Path

try:
    import paramiko
except ImportError:
    print("[ERROR] paramiko not installed. Run: pip install -r requirements.txt")
    sys.exit(1)

try:
    import requests
except ImportError:
    print("[ERROR] requests not installed. Run: pip install -r requirements.txt")
    sys.exit(1)

SCRIPT_DIR = Path(__file__).parent
CONFIG_FILE = SCRIPT_DIR / "config.json"
TERRAFORM_DIR = SCRIPT_DIR

MODRINTH_API = "https://api.modrinth.com/v2"

VALID_SERVER_TYPES = [
    "vanilla", "forge", "fabric", "paper", "spigot", "bukkit",
    "purpur", "sponge", "velocity", "quilt", "neoforge", "fml",
    "limbo", "bedrock"
]


def load_config():
    """Load configuration from config.json."""
    with open(CONFIG_FILE) as f:
        return json.load(f)


def save_config(config):
    """Save configuration to config.json."""
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)


def get_java_tag(mc_version):
    """Map MC version to itzg/minecraft-server Docker image Java tag.

    Returns the image tag suffix (e.g. 'java17', 'java21') based on the
    Minecraft version, so the correct JVM is used for the modpack.
    """
    try:
        parts = mc_version.split(".")
        minor = int(parts[1]) if len(parts) > 1 else 0
        patch = int(parts[2]) if len(parts) > 2 else 0
    except (ValueError, IndexError):
        return "java21"

    # MC 1.17.x to 1.20.4 → Java 17
    if minor <= 16:
        return "java17"
    if minor <= 20 and patch <= 4:
        return "java17"
    # MC 1.20.5 to 1.21.4 → Java 21
    if minor == 20 and patch >= 5:
        return "java21"
    if minor == 21 and patch <= 4:
        return "java21"
    # MC 1.21.5+ → Java 21 (safe default, java25 not widely available yet)
    return "java21"


def get_server_ip():
    """Get server public IP from Terraform output."""
    try:
        result = os.popen(
            f"cd {TERRAFORM_DIR} && terraform output -raw ssh_ip 2>/dev/null"
        ).read().strip()
        if result:
            return result
    except Exception:
        pass

    return None


def ssh_connect():
    """Establish SSH connection to the Minecraft server."""
    config = load_config()
    ip = get_server_ip()
    if not ip:
        print("[ERROR] Server IP not found. Run 'terraform apply' first.")
        sys.exit(1)

    key_path = Path(os.path.expanduser(config.get("ssh_key_path", "~/.ssh/id_rsa")))
    if not key_path.exists():
        print(f"[ERROR] SSH key not found: {key_path}")
        sys.exit(1)

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        ssh.connect(
            hostname=ip,
            username=config.get("ssh_user", "ubuntu"),
            key_filename=str(key_path),
            timeout=15
        )
        return ssh
    except paramiko.AuthenticationException:
        print("[ERROR] SSH authentication failed. Check your key and username.")
        sys.exit(1)
    except paramiko.SSHException as e:
        print(f"[ERROR] SSH connection error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"[ERROR] Connection failed: {e}")
        sys.exit(1)


def ssh_exec(ssh, command, timeout=30):
    """Execute a command over SSH and return (exit_code, stdout, stderr)."""
    stdin, stdout, stderr = ssh.exec_command(command, timeout=timeout)
    exit_code = stdout.channel.recv_exit_status()
    return exit_code, stdout.read().decode().strip(), stderr.read().decode().strip()


def docker_cmd(cmd):
    """Wrap a command with docker exec for the mc container."""
    return f"docker exec mc {cmd}"


def docker_compose_cmd(cmd):
    """Wrap a command with docker compose in /opt/minecraft."""
    return f"cd /opt/minecraft && docker compose {cmd}"


def build_docker_run(version, server_type, java_tag, memory, port,
                     online_mode, max_players, view_distance,
                     enable_rcon, motd):
    """Build the docker run command for the Minecraft server."""
    return (
        f"docker rm -f mc 2>/dev/null; "
        f"docker run -d "
        f"--name mc "
        f"--restart unless-stopped "
        f"-p {port}:{port}/tcp "
        f"-p {port}:{port}/udp "
        f"-e EULA=TRUE "
        f"-e VERSION={version} "
        f"-e TYPE={server_type.upper()} "
        f"-e MEMORY={memory}G "
        f"-e ONLINE_MODE={online_mode} "
        f"-e MAX_PLAYERS={max_players} "
        f"-e VIEW_DISTANCE={view_distance} "
        f"-e ENABLE_RCON={enable_rcon} "
        f'-e MOTD="{motd}" '
        f"-v /opt/minecraft/data:/data "
        f"itzg/minecraft-server:{java_tag}"
    )


# ─── Server Status ────────────────────────────────────────────────────────────

def cmd_status():
    """Show server status, Docker info, and port check."""
    config = load_config()
    ip = get_server_ip()
    print(f"\n{'='*60}")
    print(f"  Minecraft Server Status")
    print(f"{'='*60}")
    print(f"  Server IP:     {ip or 'N/A'}")
    print(f"  Port:          {config['server_port']}")
    print(f"  Version:       {config['minecraft_version']}")
    print(f"  Server Type:   {config.get('server_type', 'vanilla')}")
    print(f"  RAM:           {config['ram_gb']}GB")
    print(f"  Max Players:   {config['max_players']}")
    print(f"  Online Mode:   {config['online_mode']}")
    print(f"  MOTD:          {config['server_name']}")
    print(f"{'='*60}")

    try:
        ssh = ssh_connect()
    except SystemExit:
        return

    try:
        # Docker container status
        _, stdout, _ = ssh_exec(ssh, "docker inspect mc --format '{{.State.Status}}' 2>/dev/null")
        if stdout:
            print(f"\n  Container Status: {stdout}")
        else:
            print(f"\n  Container Status: NOT FOUND")

        # Container uptime
        _, stdout, _ = ssh_exec(ssh, "docker inspect mc --format '{{.State.StartedAt}}' 2>/dev/null")
        if stdout:
            print(f"  Started At:      {stdout}")

        # Docker stats (non-streaming snapshot)
        _, stdout, _ = ssh_exec(ssh, "docker stats mc --no-stream --format 'CPU: {{.CPUPerc}} | MEM: {{.MemUsage}} | NET: {{.NetIO}}' 2>/dev/null")
        if stdout:
            print(f"  Resources:       {stdout}")

        # Port check
        _, stdout, _ = ssh_exec(ssh, f"ss -tlnp | grep {config['server_port']}")
        if stdout:
            print(f"  Port {config['server_port']}:    LISTENING ✓")
        else:
            print(f"  Port {config['server_port']}:    NOT LISTENING ✗")

        # Java version in container
        _, stdout, _ = ssh_exec(ssh, docker_cmd("java -version 2>&1 | head -1"), timeout=10)
        if stdout:
            print(f"  Java:           {stdout}")

        # Disk usage
        _, stdout, _ = ssh_exec(ssh, "du -sh /opt/minecraft/data 2>/dev/null")
        if stdout:
            print(f"  Data Size:      {stdout.split()[0]}")

        # Server version from server.properties
        _, stdout, _ = ssh_exec(ssh, docker_cmd("cat /data/server.properties 2>/dev/null | grep 'server-port\\|level-name\\|gamemode\\|difficulty'"))
        if stdout:
            print(f"\n  server.properties:")
            for line in stdout.strip().split("\n"):
                if line.strip():
                    print(f"    {line.strip()}")

    finally:
        ssh.close()

    print(f"{'='*60}\n")


# ─── Mod Management ──────────────────────────────────────────────────────────

def search_modrinth(query, limit=10):
    """Search Modrinth for mods matching the query."""
    config = load_config()
    version = config["minecraft_version"]
    loader = config.get("server_type", "vanilla")

    # Map our server type names to Modrinth loader names
    loader_map = {
        "forge": "forge",
        "fabric": "fabric",
        "paper": "paper",
        "spigot": "spigot",
        "bukkit": "bukkit",
        "purpur": "purpur",
        "quilt": "quilt",
        "neoforge": "neoforge",
        "sponge": "sponge",
        "vanilla": None,
    }

    modrinth_loader = loader_map.get(loader)

    params = {
        "query": query,
        "limit": limit,
        "index": "relevance",
    }

    facets = [["project_type:mod"]]
    if version and modrinth_loader:
        facets.append([f"versions:{version}"])
    if modrinth_loader:
        facets.append([f"categories:{modrinth_loader}"])

    params["facets"] = json.dumps(facets)

    try:
        resp = requests.get(f"{MODRINTH_API}/search", params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        return data.get("hits", [])
    except requests.RequestException as e:
        print(f"[ERROR] Modrinth API error: {e}")
        return []


def download_modrinth_mod(project_id, version_id=None):
    """Download a mod from Modrinth. Returns (filename, temp_path) or None."""
    config = load_config()
    version = config["minecraft_version"]
    loader = config.get("server_type", "vanilla")

    loader_map = {
        "forge": "forge", "fabric": "fabric", "paper": "paper",
        "spigot": "spigot", "bukkit": "bukkit", "purpur": "purpur",
        "quilt": "quilt", "neoforge": "neoforge", "sponge": "sponge",
    }
    modrinth_loader = loader_map.get(loader)

    try:
        if version_id:
            resp = requests.get(f"{MODRINTH_API}/version/{version_id}", timeout=15)
            resp.raise_for_status()
            ver_data = resp.json()
        else:
            # Fetch all versions for this mod
            resp = requests.get(
                f"{MODRINTH_API}/project/{project_id}/version",
                timeout=15
            )
            resp.raise_for_status()
            all_versions = resp.json()

            # Filter by loader
            if modrinth_loader:
                all_versions = [v for v in all_versions if modrinth_loader in v.get("loaders", [])]

            # Try exact version match
            versions = [v for v in all_versions if version in v.get("game_versions", [])]

            # Fallback: prefix match (e.g. 1.21 for 1.21.4)
            if not versions and version:
                prefix = ".".join(version.split(".")[:2])
                versions = [v for v in all_versions if any(pv.startswith(prefix) for pv in v.get("game_versions", []))]

            if not versions:
                print(f"[ERROR] No version found for MC {version} with {loader}.")
                return None
            ver_data = versions[0]
            matched_mc = ver_data.get("game_versions", ["?"])[0]
            matched_loader = ver_data.get("loaders", ["?"])[0]
            print(f"  Matched: MC {matched_mc} / {matched_loader}")

        # Find the primary file
        files = ver_data.get("files", [])
        if not files:
            print("[ERROR] No files found in version.")
            return None

        primary = next((f for f in files if f.get("primary")), files[0])
        download_url = primary["url"]
        filename = primary["filename"]

        print(f"  Downloading: {filename}")
        resp = requests.get(download_url, timeout=60, stream=True)
        resp.raise_for_status()

        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".jar", dir=str(SCRIPT_DIR))
        for chunk in resp.iter_content(chunk_size=8192):
            tmp.write(chunk)
        tmp.close()

        return filename, tmp.name

    except requests.RequestException as e:
        print(f"[ERROR] Download failed: {e}")
        return None


def cmd_install(mod_name):
    """Search and install a mod from Modrinth."""
    print(f"\nSearching for '{mod_name}' on Modrinth...")
    results = search_modrinth(mod_name)

    if not results:
        print("No mods found.")
        return

    # Display results
    print(f"\n{'='*60}")
    print(f"  Found {len(results)} mods:")
    print(f"{'='*60}")
    for i, mod in enumerate(results, 1):
        title = mod.get("title", "Unknown")
        slug = mod.get("slug", "")
        downloads = mod.get("downloads", 0)
        desc = mod.get("description", "")[:80]
        print(f"  [{i}] {title} ({slug})")
        print(f"      Downloads: {downloads:,} | {desc}")
        print()

    # Select mod
    try:
        choice = int(input("Select mod number (0 to cancel): "))
        if choice == 0 or choice > len(results):
            print("Cancelled.")
            return
    except (ValueError, EOFError):
        print("Invalid input.")
        return

    selected = results[choice - 1]
    project_id = selected["slug"] or selected["project_id"]
    title = selected["title"]

    print(f"\nDownloading {title}...")
    result = download_modrinth_mod(project_id)
    if not result:
        return

    filename, tmp_path = result

    # Upload to server
    print(f"  Uploading {filename} to server...")
    ssh = ssh_connect()
    try:
        # Ensure mods directory exists with correct permissions
        ssh_exec(ssh, "sudo mkdir -p /opt/minecraft/data/mods && sudo chmod 777 /opt/minecraft/data/mods")
        sftp = ssh.open_sftp()
        remote_path = f"/opt/minecraft/data/mods/{filename}"
        sftp.put(tmp_path, remote_path)
        sftp.close()
        print(f"  Installed: {filename}")

        # Verify installation
        _, stdout, _ = ssh_exec(ssh, f"ls -la /opt/minecraft/data/mods/{filename}")
        if stdout:
            print(f"  Verified:  {stdout}")

        # Check if restart is needed
        _, container_status, _ = ssh_exec(ssh, "docker inspect mc --format '{{.State.Status}}' 2>/dev/null")
        if container_status == "running":
            restart = input("  Restart server to apply mod? (y/n): ").strip().lower()
            if restart == "y":
                print("  Restarting server...")
                ssh_exec(ssh, "docker restart mc", timeout=60)
                print("  Server restarted.")
    finally:
        ssh.close()

    # Cleanup temp file
    os.unlink(tmp_path)
    print("Done.\n")


def cmd_remove(mod_name):
    """Remove an installed mod from the server."""
    ssh = ssh_connect()
    try:
        # List mods and find matching ones
        _, stdout, _ = ssh_exec(ssh, "ls /opt/minecraft/data/mods/ 2>/dev/null")
        if not stdout:
            print("No mods directory or no mods found.")
            return

        mods = stdout.strip().split("\n")
        # Find mods matching the name (case-insensitive, partial match)
        matching = [m for m in mods if mod_name.lower() in m.lower()]

        if not matching:
            print(f"No mod matching '{mod_name}' found.")
            print("Installed mods:")
            for m in mods:
                if m.strip():
                    print(f"  - {m}")
            return

        if len(matching) == 1:
            target = matching[0]
        else:
            print(f"Multiple matches found:")
            for i, m in enumerate(matching, 1):
                print(f"  [{i}] {m}")
            try:
                choice = int(input("Select mod to remove (0 to cancel): "))
                if choice == 0 or choice > len(matching):
                    print("Cancelled.")
                    return
            except (ValueError, EOFError):
                print("Invalid input.")
                return
            target = matching[choice - 1]

        confirm = input(f"Remove '{target}'? (y/n): ").strip().lower()
        if confirm != "y":
            print("Cancelled.")
            return

        _, _, stderr = ssh_exec(ssh, f"rm /opt/minecraft/data/mods/{target}")
        if stderr:
            print(f"Error removing mod: {stderr}")
        else:
            print(f"Removed: {target}")

            _, container_status, _ = ssh_exec(ssh, "docker inspect mc --format '{{.State.Status}}' 2>/dev/null")
            if container_status == "running":
                restart = input("  Restart server to apply changes? (y/n): ").strip().lower()
                if restart == "y":
                    print("  Restarting server...")
                    ssh_exec(ssh, "docker restart mc", timeout=60)
                    print("  Server restarted.")
    finally:
        ssh.close()

    print("Done.\n")


def cmd_list():
    """List all installed mods on the server."""
    ssh = ssh_connect()
    try:
        _, stdout, _ = ssh_exec(ssh, "ls -la /opt/minecraft/data/mods/ 2>/dev/null")
        if not stdout or "No such file" in stdout:
            print("\nNo mods directory found. Server may not have mods installed.")
            return

        print(f"\n{'='*60}")
        print(f"  Installed Mods")
        print(f"{'='*60}")
        lines = stdout.strip().split("\n")
        mod_count = 0
        for line in lines:
            parts = line.split()
            if len(parts) >= 9 and parts[-1].endswith(".jar"):
                size = parts[4]
                name = " ".join(parts[8:])
                print(f"  {name:<50} ({size} bytes)")
                mod_count += 1
        if mod_count == 0:
            print("  No .jar mod files found.")
        else:
            print(f"\n  Total: {mod_count} mod(s)")
        print(f"{'='*60}\n")
    finally:
        ssh.close()


# ─── Modpack Management ────────────────────────────────────────────────────────

def search_modrinth_modpack(query, limit=10):
    """Search Modrinth for modpacks matching the query."""
    params = {
        "query": query,
        "limit": limit,
        "index": "relevance",
        "facets": json.dumps([["project_type:modpack"]]),
    }
    try:
        resp = requests.get(f"{MODRINTH_API}/search", params=params, timeout=15)
        resp.raise_for_status()
        return resp.json().get("hits", [])
    except requests.RequestException as e:
        print(f"[ERROR] Modrinth API error: {e}")
        return []


def download_modpack(project_id, version_id=None):
    """Download a modpack from Modrinth. Returns (filename, temp_path, server_type, matched_mc) or None."""
    config = load_config()
    version = config["minecraft_version"]

    matched_mc = version
    try:
        if version_id:
            resp = requests.get(f"{MODRINTH_API}/version/{version_id}", timeout=15)
            resp.raise_for_status()
            ver_data = resp.json()
            matched_mc = ver_data.get("game_versions", [version])[0]
        else:
            resp = requests.get(f"{MODRINTH_API}/project/{project_id}/version", timeout=15)
            resp.raise_for_status()
            all_versions = resp.json()

            versions = [v for v in all_versions if version in v.get("game_versions", [])]
            if not versions:
                prefix = ".".join(version.split(".")[:2])
                versions = [v for v in all_versions if any(pv.startswith(prefix) for pv in v.get("game_versions", []))]

            if not versions:
                print(f"[ERROR] No modpack version found for MC {version}.")
                return None
            ver_data = versions[0]
            matched_mc = ver_data.get("game_versions", ["?"])[0]
            matched_loaders = ver_data.get("loaders", ["?"])
            print(f"  Matched: MC {matched_mc} / {matched_loaders[0] if matched_loaders else '?'}")

        files = ver_data.get("files", [])
        if not files:
            print("[ERROR] No files found in modpack version.")
            return None

        primary = next((f for f in files if f.get("primary")), files[0])
        download_url = primary["url"]
        filename = primary["filename"]

        print(f"  Downloading: {filename}")
        resp = requests.get(download_url, timeout=120, stream=True)
        resp.raise_for_status()

        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mrpack", dir=str(SCRIPT_DIR))
        for chunk in resp.iter_content(chunk_size=8192):
            tmp.write(chunk)
        tmp.close()

        server_type = ver_data.get("loaders", ["vanilla"])[0] if ver_data.get("loaders") else "vanilla"
        return filename, tmp.name, server_type, matched_mc

    except requests.RequestException as e:
        print(f"[ERROR] Download failed: {e}")
        return None


CLIENT_ONLY_MODS = [
    "colorwheel", "colorwheel_patcher", "iris", "irisfixes",
    "sodium", "sodium-extra", "sodiumextras", "sodiumdynamiclights",
    "sodiumoptionsapi", "sodiumoptionsmodcompat", "reeses_sodium_options",
    "skinlayers3d", "embeddium", "rubidium", "oculus",
    "betterclouds", "lambdynamiclights", "smartlighting",
    "continuity", "entityculling", "immediatelyfast", "lithium",
    "ferritecore", "lazydfu", "starlight",
    "modmenu", "zoomify", "minihud", "tweakeroo",
    "xaerominimap", "xaeroworldmap", "journeymap",
    "inventoryhud", "craftpresence", "keybindings",
    "presencefootsteps", "sound-physics-remastered",
    "notenoughanimations", "player-animation-lib",
    "better-third-person", "leawind_third_person",
]


def extract_modpack_overrides(ssh, filename):
    """Extract overrides from a modpack .mrpack file on the server."""
    print("  Extracting modpack overrides...")
    ssh_exec(ssh, "sudo mkdir -p /opt/minecraft/data")

    extract_script = """#!/usr/bin/env python3
import zipfile, os, shutil

modpack = '/tmp/{filename}'
extract_dir = '/tmp/modpack_extract'
data_dir = '/opt/minecraft/data'

if os.path.exists(extract_dir):
    shutil.rmtree(extract_dir)

with zipfile.ZipFile(modpack, 'r') as z:
    z.extractall(extract_dir)

overrides = os.path.join(extract_dir, 'overrides')
if os.path.isdir(overrides):
    for item in os.listdir(overrides):
        src = os.path.join(overrides, item)
        dst = os.path.join(data_dir, item)
        if os.path.isdir(src):
            shutil.copytree(src, dst, dirs_exist_ok=True)
        else:
            shutil.copy2(src, dst)

print('OVERRIDES_DONE')
"""
    extract_script = extract_script.replace("{filename}", filename)

    sftp = ssh.open_sftp()
    with sftp.open("/tmp/extract_modpack.py", "w") as f:
        f.write(extract_script)
    sftp.close()

    _, stdout, stderr = ssh_exec(
        ssh,
        "sudo python3 /tmp/extract_modpack.py && sudo rm /tmp/extract_modpack.py",
        timeout=120
    )
    if "OVERRIDES_DONE" in stdout:
        print("  Overrides extracted.")
    else:
        print(f"  [WARN] Extract issue: {stderr}")


def download_modpack_mods(ssh):
    """Download additional mods from modrinth.index.json on the server."""
    print("  Downloading additional mods from modrinth.index.json...")
    download_script = """#!/usr/bin/env python3
import json, urllib.request, os, sys

with open('/tmp/modpack_extract/modrinth.index.json') as f:
    index = json.load(f)

data_dir = '/opt/minecraft/data'
downloaded = 0
skipped = 0
failed = 0

for fi in index.get('files', []):
    path = fi.get('path', '')
    dest = os.path.join(data_dir, path)
    if os.path.exists(dest):
        skipped += 1
        continue
    url = fi.get('downloads', [None])[0]
    if not url:
        continue
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    try:
        urllib.request.urlretrieve(url, dest)
        downloaded += 1
        print(f'Downloaded: {os.path.basename(path)}')
    except Exception as e:
        failed += 1
        print(f'WARN Failed: {os.path.basename(path)}: {e}')

print(f'--- Summary: {downloaded} downloaded, {skipped} skipped, {failed} failed ---')
"""
    sftp = ssh.open_sftp()
    with sftp.open("/tmp/download_modpack.py", "w") as f:
        f.write(download_script)
    sftp.close()

    _, stdout, stderr = ssh_exec(
        ssh,
        "sudo python3 /tmp/download_modpack.py && sudo rm /tmp/download_modpack.py",
        timeout=600
    )
    if stdout:
        for line in stdout.strip().split("\n"):
            if line.strip():
                print(f"  {line.strip()}")


def cleanup_client_mods(ssh):
    """Remove known client-side mods that don't work on a server."""
    print("  Removing known client-only mods...")
    _, mods_list, _ = ssh_exec(ssh, "ls /opt/minecraft/data/mods/ 2>/dev/null")
    if mods_list:
        removed = 0
        for mod_file in mods_list.strip().split("\n"):
            mod_lower = mod_file.lower()
            for pattern in CLIENT_ONLY_MODS:
                if pattern in mod_lower:
                    ssh_exec(ssh, f"sudo rm -f /opt/minecraft/data/mods/{mod_file}")
                    print(f"  Removed client mod: {mod_file}")
                    removed += 1
                    break
        if removed:
            print(f"  Removed {removed} client-only mod(s)")


def detect_crash_and_fix(ssh):
    """Check server logs for client-mod crashes, remove the offending mod, restart."""
    _, logs, _ = ssh_exec(ssh, "docker logs mc --tail 20 2>&1")
    crash_mod = None
    if logs:
        for line in logs.split("\n"):
            if "Cannot load class" in line and "environment type SERVER" in line:
                m = re.search(r"provided by '(\w+)'", line)
                if m:
                    crash_mod = m.group(1)
                break
            if "Failed to start" in line or "Exception" in line:
                m = re.search(r"provided by '(\w+)'", line)
                if m:
                    crash_mod = m.group(1)

    if crash_mod:
        print(f"  Removing problematic mod: {crash_mod}")
        ssh_exec(ssh, f"sudo rm -f /opt/minecraft/data/mods/*{crash_mod}* && sudo rm -f /opt/minecraft/data/mods/*{crash_mod.lower()}*", timeout=15)
        _, found_mods, _ = ssh_exec(ssh, f"ls /opt/minecraft/data/mods/ | grep -i {crash_mod}")
        if found_mods:
            for mf in found_mods.strip().split("\n"):
                if mf.strip():
                    ssh_exec(ssh, f"sudo rm -f /opt/minecraft/data/mods/{mf}")

        print("  Restarting server...")
        ssh_exec(ssh, "docker restart mc", timeout=60)
        time.sleep(20)
        return True
    return False


def cmd_install_pack(pack_name):
    """Search and install a modpack from Modrinth."""
    print(f"\nSearching for modpack '{pack_name}' on Modrinth...")
    results = search_modrinth_modpack(pack_name)

    if not results:
        print("No modpacks found.")
        return

    print(f"\n{'='*60}")
    print(f"  Found {len(results)} modpacks:")
    print(f"{'='*60}")
    for i, pack in enumerate(results, 1):
        title = pack.get("title", "Unknown")
        slug = pack.get("slug", "")
        downloads = pack.get("downloads", 0)
        desc = pack.get("description", "")[:80]
        print(f"  [{i}] {title} ({slug})")
        print(f"      Downloads: {downloads:,} | {desc}")
        print()

    try:
        choice = int(input("Select modpack number (0 to cancel): "))
        if choice == 0 or choice > len(results):
            print("Cancelled.")
            return
    except (ValueError, EOFError):
        print("Invalid input.")
        return

    selected = results[choice - 1]
    project_id = selected["slug"] or selected["project_id"]
    title = selected["title"]

    print(f"\nDownloading {title}...")
    result = download_modpack(project_id)
    if not result:
        return

    filename, tmp_path, new_server_type, matched_mc = result
    config = load_config()

    java_tag = get_java_tag(matched_mc)
    print(f"  Server type from modpack: {new_server_type}")
    print(f"  Java version: {java_tag} (MC {matched_mc})")

    ssh = ssh_connect()
    try:
        print("  Stopping server...")
        ssh_exec(ssh, "docker stop mc", timeout=30)

        print("  Uploading modpack to server...")
        sftp = ssh.open_sftp()
        remote_tmp = f"/tmp/{filename}"
        sftp.put(tmp_path, remote_tmp)
        sftp.close()

        extract_modpack_overrides(ssh, filename)
        download_modpack_mods(ssh)

        print("  Setting permissions...")
        ssh_exec(ssh, "sudo chmod -R 777 /opt/minecraft/data && rm -rf /tmp/modpack_extract", timeout=30)

        cleanup_client_mods(ssh)

        print("  Updating server type and version...")
        loader_map = {
            "forge": "forge", "fabric": "fabric", "quilt": "quilt",
            "neoforge": "neoforge", "liteloader": "liteloader",
        }
        if new_server_type in loader_map:
            config["server_type"] = loader_map[new_server_type]
        config["minecraft_version"] = matched_mc
        save_config(config)

        print("  Restarting server with new modpack...")
        memory = config.get("ram_gb", 16)
        port = config.get("server_port", 25565)
        online_mode = str(config.get("online_mode", False)).upper()
        max_players = config.get("max_players", 20)
        view_distance = config.get("view_distance", 20)
        enable_rcon = str(config.get("enable_rcon", True)).upper()
        motd = config.get("server_name", "A Cool Server")
        mc_version = config["minecraft_version"]

        docker_run = build_docker_run(
            mc_version, new_server_type, java_tag, memory, port,
            online_mode, max_players, view_distance, enable_rcon, motd
        )

        _, stdout, stderr = ssh_exec(ssh, docker_run, timeout=120)
        if stderr and "Error" in stderr:
            print(f"  [WARN] Docker output: {stderr}")

        print("  Waiting for server to start...")
        time.sleep(20)

        max_retries = 5
        for attempt in range(max_retries):
            _, new_status, _ = ssh_exec(ssh, "docker inspect mc --format '{{.State.Status}}' 2>/dev/null")
            if new_status == "running":
                _, health_out, _ = ssh_exec(ssh, "docker inspect mc --format '{{.State.Health.Status}}' 2>/dev/null")
                if health_out.strip() == "healthy":
                    print(f"  Server is running with {title} ({new_server_type})")
                    break

            print(f"  [WARN] Server not ready (attempt {attempt + 1}/{max_retries})")

            if detect_crash_and_fix(ssh):
                continue
            else:
                print("  Waiting more...")
                time.sleep(30)
        else:
            print(f"  [WARN] Server may not be fully ready after {max_retries} attempts")
            _, logs, _ = ssh_exec(ssh, "docker logs mc --tail 10 2>&1")
            if logs:
                print(f"  Recent logs:\n{logs}")

    finally:
        ssh.close()

    os.unlink(tmp_path)
    print("Done.\n")


def cmd_uninstall_pack():
    """Remove installed modpack and revert to vanilla server."""
    config = load_config()
    current_type = config.get("server_type", "vanilla")

    print(f"\n{'='*60}")
    print(f"  Uninstall Modpack")
    print(f"{'='*60}")
    print(f"  Current server type: {current_type}")
    print(f"  This will:")
    print(f"    1. Stop the server")
    print(f"    2. Remove ALL mods from /opt/minecraft/data/mods/")
    print(f"    3. Remove config files from /opt/minecraft/data/config/")
    print(f"    4. Reset server type to vanilla")
    print(f"    5. Restart server as vanilla")
    print(f"{'='*60}")

    confirm = input("\nProceed? (y/n): ").strip().lower()
    if confirm != "y":
        print("Cancelled.")
        return

    # Ask about world data
    world_confirm = input("Also delete world data? (y/n): ").strip().lower()
    delete_world = world_confirm == "y"

    ssh = ssh_connect()
    try:
        # Stop server
        print("\n  Stopping server...")
        ssh_exec(ssh, "docker stop mc", timeout=30)

        # Remove mods
        print("  Removing mods...")
        ssh_exec(ssh, "sudo rm -rf /opt/minecraft/data/mods")
        print("    Deleted: /opt/minecraft/data/mods/")

        # Remove config directory (modpack configs)
        print("  Removing modpack configs...")
        ssh_exec(ssh, "sudo rm -rf /opt/minecraft/data/config")
        print("    Deleted: /opt/minecraft/data/config/")

        # Remove scripts directory if exists (some modpacks add this)
        ssh_exec(ssh, "sudo rm -rf /opt/minecraft/data/scripts")

        # Remove modpack-specific files
        ssh_exec(ssh, "sudo rm -f /opt/minecraft/data/modrinth.index.json")
        ssh_exec(ssh, "sudo rm -f /opt/minecraft/data/.mrpack")

        # Optionally remove world data
        if delete_world:
            print("  Removing world data...")
            ssh_exec(ssh, "sudo rm -rf /opt/minecraft/data/world")
            ssh_exec(ssh, "sudo rm -rf /opt/minecraft/data/world_nether")
            ssh_exec(ssh, "sudo rm -rf /opt/minecraft/data/world_the_end")
            print("    Deleted: world, world_nether, world_the_end")

        # Remove crash reports and logs from modpack
        ssh_exec(ssh, "sudo rm -rf /opt/minecraft/data/crash-reports")
        ssh_exec(ssh, "sudo rm -rf /opt/minecraft/data/logs")

        # Fix permissions
        print("  Fixing permissions...")
        ssh_exec(ssh, "sudo chmod -R 777 /opt/minecraft/data", timeout=30)

        # Update config to vanilla
        print("  Updating config.json to vanilla...")
        config["server_type"] = "vanilla"
        save_config(config)

        # Restart as vanilla
        print("  Starting vanilla server...")
        version = config["minecraft_version"]
        java_tag = get_java_tag(version)
        memory = config.get("ram_gb", 16)
        port = config.get("server_port", 25565)
        online_mode = str(config.get("online_mode", False)).upper()
        max_players = config.get("max_players", 20)
        view_distance = config.get("view_distance", 20)
        enable_rcon = str(config.get("enable_rcon", True)).upper()
        motd = config.get("server_name", "A Cool Server")

        docker_run = build_docker_run(
            version, "vanilla", java_tag, memory, port,
            online_mode, max_players, view_distance, enable_rcon, motd
        )

        _, stdout, stderr = ssh_exec(ssh, docker_run, timeout=120)
        if stderr and "Error" in stderr:
            print(f"  [WARN] Docker output: {stderr}")

        print("  Waiting for server to start...")
        time.sleep(15)

        # Check status
        _, new_status, _ = ssh_exec(ssh, "docker inspect mc --format '{{.State.Status}}' 2>/dev/null")
        if new_status == "running":
            print(f"\n  Server is now running vanilla {version}")
        else:
            print(f"\n  [WARN] Container status: {new_status}")
            _, logs, _ = ssh_exec(ssh, "docker logs mc --tail 20 2>&1")
            if logs:
                print(f"  Recent logs:\n{logs}")

    finally:
        ssh.close()

    print("Done.\n")


# ─── Server Configuration ────────────────────────────────────────────────────

def cmd_set_version(version):
    """Change the Minecraft server version."""
    config = load_config()
    old_version = config["minecraft_version"]

    if old_version == version:
        print(f"Server is already running version {version}.")
        return

    print(f"Changing version: {old_version} -> {version}")

    ssh = ssh_connect()
    try:
        # Check if container exists
        _, status, _ = ssh_exec(ssh, "docker inspect mc --format '{{.State.Status}}' 2>/dev/null")

        if status:
            print("  Stopping current server...")
            ssh_exec(ssh, "docker stop mc", timeout=30)

        # Update config.json
        config["minecraft_version"] = version
        save_config(config)

        # Get current container run configuration
        _, env_output, _ = ssh_exec(ssh, docker_cmd("printenv") if status else "echo ''")

        # Recreate container with new version
        print("  Updating container with new version...")
        type_val = config.get("server_type", "vanilla")
        java_tag = get_java_tag(version)
        memory = config.get("ram_gb", 4)
        port = config.get("server_port", 25565)
        online_mode = str(config.get("online_mode", False)).upper()
        max_players = config.get("max_players", 10)
        view_distance = config.get("view_distance", 15)
        enable_rcon = str(config.get("enable_rcon", True)).upper()
        motd = config.get("server_name", "A Cool Server")

        docker_run = build_docker_run(
            version, type_val, java_tag, memory, port,
            online_mode, max_players, view_distance, enable_rcon, motd
        )

        _, stdout, stderr = ssh_exec(ssh, docker_run, timeout=120)
        if stderr and "Error" in stderr:
            print(f"  [WARN] Docker output: {stderr}")

        print("  Waiting for server to start...")
        time.sleep(10)

        _, new_status, _ = ssh_exec(ssh, "docker inspect mc --format '{{.State.Status}}' 2>/dev/null")
        if new_status == "running":
            print(f"  Server is now running version {version} ({type_val})")
        else:
            print(f"  [WARN] Container status: {new_status}")
            _, logs, _ = ssh_exec(ssh, "docker logs mc --tail 20 2>&1")
            if logs:
                print(f"  Recent logs:\n{logs}")

    finally:
        ssh.close()

    print("Done.\n")


def cmd_set_type(server_type):
    """Change the server type (forge, fabric, paper, etc.)."""
    config = load_config()
    old_type = config.get("server_type", "vanilla")
    server_type = server_type.lower()

    if server_type not in VALID_SERVER_TYPES:
        print(f"Invalid server type: {server_type}")
        print(f"Valid types: {', '.join(VALID_SERVER_TYPES)}")
        return

    if old_type == server_type:
        print(f"Server is already running {server_type}.")
        return

    print(f"Changing server type: {old_type} -> {server_type}")

    ssh = ssh_connect()
    try:
        # Check if container exists
        _, status, _ = ssh_exec(ssh, "docker inspect mc --format '{{.State.Status}}' 2>/dev/null")

        if status:
            print("  Stopping current server...")
            ssh_exec(ssh, "docker stop mc", timeout=30)

        # Update config
        config["server_type"] = server_type
        save_config(config)

        # Recreate container
        print("  Recreating container...")
        version = config["minecraft_version"]
        java_tag = get_java_tag(version)
        memory = config.get("ram_gb", 4)
        port = config.get("server_port", 25565)
        online_mode = str(config.get("online_mode", False)).upper()
        max_players = config.get("max_players", 10)
        view_distance = config.get("view_distance", 15)
        enable_rcon = str(config.get("enable_rcon", True)).upper()
        motd = config.get("server_name", "A Cool Server")

        docker_run = build_docker_run(
            version, server_type, java_tag, memory, port,
            online_mode, max_players, view_distance, enable_rcon, motd
        )

        _, stdout, stderr = ssh_exec(ssh, docker_run, timeout=120)
        if stderr and "Error" in stderr:
            print(f"  [WARN] Docker output: {stderr}")

        print("  Waiting for server to start...")
        time.sleep(10)

        _, new_status, _ = ssh_exec(ssh, "docker inspect mc --format '{{.State.Status}}' 2>/dev/null")
        if new_status == "running":
            print(f"  Server is now running {server_type} (version {version})")
        else:
            print(f"  [WARN] Container status: {new_status}")
            _, logs, _ = ssh_exec(ssh, "docker logs mc --tail 20 2>&1")
            if logs:
                print(f"  Recent logs:\n{logs}")

    finally:
        ssh.close()

    print("Done.\n")


def cmd_set_motd(message):
    """Change the server MOTD (Message of the Day)."""
    config = load_config()
    config["server_name"] = message
    save_config(config)

    ssh = ssh_connect()
    try:
        # Update server.properties via docker exec
        _, status, _ = ssh_exec(ssh, "docker inspect mc --format '{{.State.Status}}' 2>/dev/null")
        if status == "running":
            ssh_exec(ssh, docker_cmd(f'sed -i "s/^motd=.*/motd={message}/" /data/server.properties'))
            print(f"MOTD updated to: {message}")
            restart = input("Restart server to apply? (y/n): ").strip().lower()
            if restart == "y":
                ssh_exec(ssh, "docker restart mc", timeout=60)
                print("Server restarted.")
        else:
            print(f"MOTD saved to config. Will apply on next server start.")
    finally:
        ssh.close()


# ─── Server Control ──────────────────────────────────────────────────────────

def cmd_restart():
    """Restart the Minecraft server container."""
    print("Restarting server...")
    ssh = ssh_connect()
    try:
        _, stdout, stderr = ssh_exec(ssh, "docker restart mc", timeout=60)
        if "Error" in stderr:
            print(f"Error: {stderr}")
        else:
            print("Server restarted successfully.")
            time.sleep(5)
            _, logs, _ = ssh_exec(ssh, "docker logs mc --tail 10 2>&1")
            if logs:
                print(f"\nRecent logs:\n{logs}")
    finally:
        ssh.close()


def cmd_stop():
    """Stop the Minecraft server container."""
    print("Stopping server...")
    ssh = ssh_connect()
    try:
        _, stdout, stderr = ssh_exec(ssh, "docker stop mc", timeout=30)
        if "Error" in stderr:
            print(f"Error: {stderr}")
        else:
            print("Server stopped.")
    finally:
        ssh.close()


def cmd_start():
    """Start the Minecraft server container."""
    print("Starting server...")
    ssh = ssh_connect()
    try:
        _, stdout, stderr = ssh_exec(ssh, "docker start mc", timeout=30)
        if "Error" in stderr:
            print(f"Error: {stderr}")
        else:
            print("Server started.")
            time.sleep(5)
            _, logs, _ = ssh_exec(ssh, "docker logs mc --tail 10 2>&1")
            if logs:
                print(f"\nRecent logs:\n{logs}")
    finally:
        ssh.close()



# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Minecraft Server Manager for Oracle Cloud",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Commands:
  status                       Show server status
  install <name>               Search and install a mod from Modrinth
  install-pack <name>          Search and install a modpack from Modrinth
  uninstall-pack               Remove modpack and revert to vanilla
  remove <name>                Remove an installed mod
  list                         List installed mods
  set-version <version>        Change Minecraft version (e.g. 1.21)
  set-type <type>              Change server type (forge, fabric, paper, etc.)
  set-motd <message>           Change server MOTD
  restart                      Restart the server
  stop                         Stop the server
  start                        Start the server

Valid server types: vanilla, forge, fabric, paper, spigot, bukkit,
                    purpur, sponge, velocity, quilt, neoforge, bedrock
        """
    )

    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("status", help="Show server status")

    install_parser = subparsers.add_parser("install", help="Install a mod")
    install_parser.add_argument("mod_name", help="Mod name or slug to search and install")

    install_pack_parser = subparsers.add_parser("install-pack", help="Install a modpack from Modrinth")
    install_pack_parser.add_argument("pack_name", help="Modpack name or slug to search and install")

    subparsers.add_parser("uninstall-pack", help="Remove modpack and revert to vanilla")

    remove_parser = subparsers.add_parser("remove", help="Remove a mod")
    remove_parser.add_argument("mod_name", help="Mod name to remove")

    subparsers.add_parser("list", help="List installed mods")

    version_parser = subparsers.add_parser("set-version", help="Change server version")
    version_parser.add_argument("version", help="New Minecraft version (e.g. 1.21)")

    type_parser = subparsers.add_parser("set-type", help="Change server type")
    type_parser.add_argument("server_type", help="Server type (forge, fabric, paper, etc.)")

    motd_parser = subparsers.add_parser("set-motd", help="Change server MOTD")
    motd_parser.add_argument("message", help="New MOTD message")

    subparsers.add_parser("restart", help="Restart the server")
    subparsers.add_parser("stop", help="Stop the server")
    subparsers.add_parser("start", help="Start the server")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    commands = {
        "status": cmd_status,
        "install": lambda: cmd_install(args.mod_name),
        "install-pack": lambda: cmd_install_pack(args.pack_name),
        "uninstall-pack": cmd_uninstall_pack,
        "remove": lambda: cmd_remove(args.mod_name),
        "list": cmd_list,
        "set-version": lambda: cmd_set_version(args.version),
        "set-type": lambda: cmd_set_type(args.server_type),
        "set-motd": lambda: cmd_set_motd(args.message),
        "restart": cmd_restart,
        "stop": cmd_stop,
        "start": cmd_start,
    }

    cmd = commands.get(args.command)
    if cmd:
        cmd()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
