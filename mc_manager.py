#!/usr/bin/env python3
"""
Minecraft Server Manager for Oracle Cloud (Terraform-based)

Manages a remote Minecraft server deployed via Terraform on Oracle Cloud.
Uses Docker (itzg/minecraft-server) with SSH access.

Commands:
    mc_manager.py status                     - Show server status and info
    mc_manager.py install <mod_name>         - Search and install a mod from Modrinth
    mc_manager.py remove <mod_name>          - Remove an installed mod
    mc_manager.py list                       - List all installed mods
    mc_manager.py set-version <version>      - Change Minecraft version and restart
    mc_manager.py set-type <type>            - Change server type (forge, fabric, paper, etc.)
    mc_manager.py set-motd <message>         - Change server MOTD
    mc_manager.py restart                    - Restart the server container
    mc_manager.py stop                       - Stop the server container
    mc_manager.py start                      - Start the server container
    mc_manager.py console                    - Attach to server console (interactive)

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
        memory = config.get("ram_gb", 4)
        port = config.get("server_port", 25565)
        online_mode = str(config.get("online_mode", False)).upper()
        max_players = config.get("max_players", 10)
        view_distance = config.get("view_distance", 15)
        enable_rcon = str(config.get("enable_rcon", True)).upper()
        motd = config.get("server_name", "A Cool Server")

        docker_run = (
            f"docker rm -f mc 2>/dev/null; "
            f"docker run -d "
            f"--name mc "
            f"--restart unless-stopped "
            f"-p {port}:{port}/tcp "
            f"-p {port}:{port}/udp "
            f"-e EULA=TRUE "
            f"-e VERSION={version} "
            f"-e TYPE={type_val.upper()} "
            f"-e MEMORY={memory}G "
            f"-e ONLINE_MODE={online_mode} "
            f"-e MAX_PLAYERS={max_players} "
            f"-e VIEW_DISTANCE={view_distance} "
            f"-e ENABLE_RCON={enable_rcon} "
            f'-e MOTD="{motd}" '
            f"-v /opt/minecraft/data:/data "
            f"itzg/minecraft-server"
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
        memory = config.get("ram_gb", 4)
        port = config.get("server_port", 25565)
        online_mode = str(config.get("online_mode", False)).upper()
        max_players = config.get("max_players", 10)
        view_distance = config.get("view_distance", 15)
        enable_rcon = str(config.get("enable_rcon", True)).upper()
        motd = config.get("server_name", "A Cool Server")

        docker_run = (
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
            f"itzg/minecraft-server"
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


def cmd_console():
    """Attach to server console (interactive). Type 'exit' to leave."""
    ip = get_server_ip()
    if not ip:
        print("[ERROR] Server IP not found. Run 'terraform apply' first.")
        sys.exit(1)

    config = load_config()
    key_path = str(Path(os.path.expanduser(config.get("ssh_key_path", "~/.ssh/id_rsa"))))
    if not Path(key_path).exists():
        print(f"[ERROR] SSH key not found: {key_path}")
        sys.exit(1)

    print("Connecting to server console... (type 'exit' to leave)")
    user = config.get("ssh_user", "ubuntu")
    os.execvp("ssh", ["ssh", "-t", "-i", key_path, f"{user}@{ip}", "docker attach mc"])


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Minecraft Server Manager for Oracle Cloud",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Commands:
  status                       Show server status
  install <name>               Search and install a mod from Modrinth
  remove <name>                Remove an installed mod
  list                         List installed mods
  set-version <version>        Change Minecraft version (e.g. 1.21)
  set-type <type>              Change server type (forge, fabric, paper, etc.)
  set-motd <message>           Change server MOTD
  restart                      Restart the server
  stop                         Stop the server
  start                        Start the server
  console                      Attach to server console

Valid server types: vanilla, forge, fabric, paper, spigot, bukkit,
                    purpur, sponge, velocity, quilt, neoforge, bedrock
        """
    )

    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("status", help="Show server status")

    install_parser = subparsers.add_parser("install", help="Install a mod")
    install_parser.add_argument("mod_name", help="Mod name or slug to search and install")

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
    subparsers.add_parser("console", help="Attach to server console")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    commands = {
        "status": cmd_status,
        "install": lambda: cmd_install(args.mod_name),
        "remove": lambda: cmd_remove(args.mod_name),
        "list": cmd_list,
        "set-version": lambda: cmd_set_version(args.version),
        "set-type": lambda: cmd_set_type(args.server_type),
        "set-motd": lambda: cmd_set_motd(args.message),
        "restart": cmd_restart,
        "stop": cmd_stop,
        "start": cmd_start,
        "console": cmd_console,
    }

    cmd = commands.get(args.command)
    if cmd:
        cmd()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
