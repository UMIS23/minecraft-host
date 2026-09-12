import json
import os
import subprocess
import tempfile
from pathlib import Path

import requests

from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from app.ssh_client import (
    load_config, save_config, ssh_connect, ssh_exec, docker_cmd,
    get_server_status, get_java_tag, build_docker_run, get_server_ip,
    is_configured, CONFIG_FILE,
)

TERRAFORM_DIR = Path("/tf/terraform")
TERRAFORM_LOG = Path("/tf/terraform/terraform.log")
TFVARS_FILE = TERRAFORM_DIR / "terraform.tfvars"

MODRINTH_API = "https://api.modrinth.com/v2"

LOADER_MAP = {
    "forge": "forge", "fabric": "fabric", "paper": "paper",
    "spigot": "spigot", "purpur": "purpur",
    "quilt": "quilt", "neoforge": "neoforge",
}

CLIENT_ONLY_MODS = [
    "iris", "irisfixes", "oculus", "embeddium", "rubidium", "optifine", "optifog",
    "sodium", "sodium-extra", "sodiumextras", "sodiumdynamiclights",
    "sodiumoptionsapi", "sodiumoptionsmodcompat", "reeses_sodium_options",
    "entity_texture_features", "entity_model_features", "skinlayers3d",
    "dynamiclights", "lambdynamiclights", "betterclouds", "smartlighting",
    "continuity", "immediatelyfast", "lithium", "ferritecore", "lazydfu", "starlight",
    "cavedust", "voidfog", "modmenu", "zoomify", "minihud", "tweakeroo",
    "xaerominimap", "xaeroworldmap", "journeymap", "inventoryhud", "craftpresence",
    "presencefootsteps", "sound-physics-remastered", "notenoughanimations",
    "player-animation-lib", "colorwheel", "colorwheel_patcher", "geckolib-fabric",
]

app = FastAPI(title="MC Server Panel")

BASE_DIR = Path(__file__).parent
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


def load_oci_credentials():
    oci = {}
    if TFVARS_FILE.exists():
        with open(TFVARS_FILE) as f:
            for line in f:
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    key, _, val = line.partition("=")
                    oci[key.strip()] = val.strip().strip('"').strip("'")
    return oci


def save_oci_credentials(oci):
    lines = []
    for key in ["tenancy_ocid", "user_ocid", "compartment_ocid", "fingerprint", "private_key_path", "region_key"]:
        val = oci.get(key, "")
        lines.append(f'{key} = "{val}"')
    with open(TFVARS_FILE, "w") as f:
        f.write("\n".join(lines) + "\n")


def run_terraform(args, timeout=300):
    cmd = ["terraform"] + args
    try:
        result = subprocess.run(
            cmd,
            cwd=str(TERRAFORM_DIR),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        output = result.stdout + "\n" + result.stderr
        with open(TERRAFORM_LOG, "a") as f:
            f.write(f"\n--- {' '.join(cmd)} ---\n")
            f.write(output)
        return output.strip()
    except subprocess.TimeoutExpired:
        msg = f"Timeout after {timeout}s"
        with open(TERRAFORM_LOG, "a") as f:
            f.write(f"\n--- TIMEOUT: {' '.join(cmd)} ---\n{msg}\n")
        return msg
    except FileNotFoundError:
        return "terraform binary not found"
    except Exception as e:
        return f"Error: {e}"


def get_terraform_logs(lines=100):
    if not TERRAFORM_LOG.exists():
        return "No terraform logs yet."
    try:
        with open(TERRAFORM_LOG) as f:
            all_lines = f.readlines()
        return "".join(all_lines[-lines:])
    except Exception as e:
        return f"Error reading logs: {e}"


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    if not is_configured():
        return RedirectResponse("/settings", status_code=303)
    status = get_server_status()
    return templates.TemplateResponse("dashboard.html", {"request": request, "status": status})


@app.post("/server/start")
async def server_start():
    if not is_configured():
        return RedirectResponse("/settings", status_code=303)
    try:
        ssh = ssh_connect()
        ssh_exec(ssh, "docker start mc", timeout=30)
        ssh.close()
    except Exception:
        pass
    return RedirectResponse("/", status_code=303)


@app.post("/server/stop")
async def server_stop():
    if not is_configured():
        return RedirectResponse("/settings", status_code=303)
    try:
        ssh = ssh_connect()
        ssh_exec(ssh, "docker stop mc", timeout=30)
        ssh.close()
    except Exception:
        pass
    return RedirectResponse("/", status_code=303)


@app.post("/server/restart")
async def server_restart():
    if not is_configured():
        return RedirectResponse("/settings", status_code=303)
    try:
        ssh = ssh_connect()
        ssh_exec(ssh, "docker restart mc", timeout=60)
        ssh.close()
    except Exception:
        pass
    return RedirectResponse("/", status_code=303)


@app.get("/logs", response_class=HTMLResponse)
async def logs(request: Request, source: str = "mc", lines: int = 100):
    log_output = ""
    if source == "terraform":
        log_output = get_terraform_logs(lines)
    else:
        if not is_configured():
            return RedirectResponse("/settings", status_code=303)
        try:
            ssh = ssh_connect()
            _, log_output, _ = ssh_exec(ssh, f"docker logs mc --tail {lines} 2>&1", timeout=15)
            ssh.close()
        except Exception as e:
            log_output = f"Error: {e}"
    return templates.TemplateResponse("logs.html", {"request": request, "logs": log_output, "lines": lines, "source": source})


@app.get("/mods", response_class=HTMLResponse)
async def mods_page(request: Request, q: str = "", type: str = "mod"):
    if not is_configured():
        return RedirectResponse("/settings", status_code=303)
    mod_list = []
    search_results = []
    installed_modpack = None
    try:
        ssh = ssh_connect()
        _, stdout, _ = ssh_exec(ssh, "ls /opt/minecraft/data/mods/ 2>/dev/null")
        if stdout and "No such file" not in stdout:
            mod_list = [m for m in stdout.strip().split("\n") if m.strip().endswith(".jar")]

        _, index_out, _ = ssh_exec(ssh, "cat /opt/minecraft/data/modrinth.index.json 2>/dev/null", timeout=10)
        if index_out and index_out.strip().startswith("{"):
            try:
                index_data = json.loads(index_out)
                installed_modpack = {
                    "name": index_data.get("name", "Unknown Modpack"),
                    "version": index_data.get("versionId", ""),
                    "description": index_data.get("summary", ""),
                }
            except json.JSONDecodeError:
                pass
        ssh.close()
    except Exception:
        pass

    if q.strip():
        try:
            config = load_config()
            version = config.get("minecraft_version", "")
            loader = config.get("server_type", "vanilla")
            modrinth_loader = LOADER_MAP.get(loader)

            params = {"query": q, "limit": 10, "index": "relevance"}
            project_type = "modpack" if type == "modpack" else "mod"
            facets = [[f"project_type:{project_type}"]]
            if version:
                facets.append([f"versions:{version}"])
            if modrinth_loader:
                facets.append([f"categories:{modrinth_loader}"])
            params["facets"] = json.dumps(facets)

            resp = requests.get(f"{MODRINTH_API}/search", params=params, timeout=15)
            resp.raise_for_status()
            hits = resp.json().get("hits", [])
            for h in hits:
                search_results.append({
                    "slug": h.get("slug", ""),
                    "title": h.get("title", ""),
                    "description": h.get("description", ""),
                    "downloads": h.get("downloads", 0),
                })
        except Exception:
            pass

    return templates.TemplateResponse("mods.html", {
        "request": request,
        "mods": mod_list,
        "search_results": search_results,
        "query": q,
        "active_type": type,
        "installed_modpack": installed_modpack,
    })


@app.post("/mods/install")
async def mod_install(request: Request):
    if not is_configured():
        return RedirectResponse("/settings", status_code=303)
    form = await request.form()
    mod_name = form.get("mod_name", "")
    result_msg = ""
    result_type = "info"
    mod_list = []

    if not mod_name:
        result_msg = "Mod adı boş olamaz."
        result_type = "error"
    else:
        try:
            config = load_config()
            version = config["minecraft_version"]
            loader = config.get("server_type", "vanilla")
            modrinth_loader = LOADER_MAP.get(loader)

            params = {"query": mod_name, "limit": 5, "index": "relevance"}
            facets = [["project_type:mod"]]
            if version and modrinth_loader:
                facets.append([f"versions:{version}"])
            if modrinth_loader:
                facets.append([f"categories:{modrinth_loader}"])
            params["facets"] = json.dumps(facets)

            resp = requests.get(f"{MODRINTH_API}/search", params=params, timeout=15)
            resp.raise_for_status()
            hits = resp.json().get("hits", [])

            if not hits:
                result_msg = f"'{mod_name}' için sonuç bulunamadı."
                result_type = "error"
            else:
                top = hits[0]
                project_id = top["slug"] or top["project_id"]
                title = top["title"]

                resp_v = requests.get(f"{MODRINTH_API}/project/{project_id}/version", timeout=15)
                resp_v.raise_for_status()
                all_versions = resp_v.json()

                if modrinth_loader:
                    all_versions = [v for v in all_versions if modrinth_loader in v.get("loaders", [])]
                versions = [v for v in all_versions if version in v.get("game_versions", [])]
                if not versions:
                    prefix = ".".join(version.split(".")[:2])
                    versions = [v for v in all_versions if any(pv.startswith(prefix) for pv in v.get("game_versions", []))]

                if not versions:
                    result_msg = f"{title} için uyumlu versiyon bulunamadı."
                    result_type = "error"
                else:
                    ver_data = versions[0]
                    files = ver_data.get("files", [])
                    if not files:
                        result_msg = "Dosya bulunamadı."
                        result_type = "error"
                    else:
                        primary = next((f for f in files if f.get("primary")), files[0])
                        download_url = primary["url"]
                        filename = primary["filename"]

                        ssh = ssh_connect()
                        ssh_exec(ssh, "sudo mkdir -p /opt/minecraft/data/mods && sudo chmod 777 /opt/minecraft/data/mods")

                        r = requests.get(download_url, timeout=60, stream=True)
                        r.raise_for_status()
                        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".jar")
                        for chunk in r.iter_content(chunk_size=8192):
                            tmp.write(chunk)
                        tmp.close()

                        sftp = ssh.open_sftp()
                        sftp.put(tmp.name, f"/opt/minecraft/data/mods/{filename}")
                        sftp.close()
                        os.unlink(tmp.name)

                        _, container_status, _ = ssh_exec(ssh, "docker inspect mc --format '{{.State.Status}}' 2>/dev/null")
                        if container_status == "running":
                            ssh_exec(ssh, "docker restart mc", timeout=60)

                        ssh.close()
                        result_msg = f"{title} yüklendi ve sunucu yeniden başlatıldı."
                        result_type = "success"
        except Exception as e:
            result_msg = f"Hata: {e}"
            result_type = "error"

    try:
        ssh = ssh_connect()
        _, stdout, _ = ssh_exec(ssh, "ls /opt/minecraft/data/mods/ 2>/dev/null")
        if stdout and "No such file" not in stdout:
            mod_list = [m for m in stdout.strip().split("\n") if m.strip().endswith(".jar")]
        ssh.close()
    except Exception:
        pass

    return templates.TemplateResponse("mods.html", {
        "request": request,
        "mods": mod_list,
        "result_msg": result_msg,
        "result_type": result_type,
    })


@app.post("/mods/install-pack")
async def modpack_install(request: Request):
    if not is_configured():
        return RedirectResponse("/settings", status_code=303)
    form = await request.form()
    pack_name = form.get("pack_name", "")
    result_msg = ""
    result_type = "info"

    if not pack_name:
        result_msg = "Modpack adı boş olamaz."
        result_type = "error"
    else:
        try:
            config = load_config()
            version = config["minecraft_version"]

            params = {"query": pack_name, "limit": 5, "index": "relevance"}
            facets = [["project_type:modpack"]]
            if version:
                facets.append([f"versions:{version}"])
            params["facets"] = json.dumps(facets)

            resp = requests.get(f"{MODRINTH_API}/search", params=params, timeout=15)
            resp.raise_for_status()
            hits = resp.json().get("hits", [])

            if not hits:
                result_msg = f"'{pack_name}' için modpack bulunamadı."
                result_type = "error"
            else:
                top = hits[0]
                project_id = top["slug"] or top["project_id"]
                title = top["title"]

                resp_v = requests.get(f"{MODRINTH_API}/project/{project_id}/version", timeout=15)
                resp_v.raise_for_status()
                all_versions = resp_v.json()

                versions = [v for v in all_versions if version in v.get("game_versions", [])]
                if not versions:
                    prefix = ".".join(version.split(".")[:2])
                    versions = [v for v in all_versions if any(pv.startswith(prefix) for pv in v.get("game_versions", []))]

                if not versions:
                    result_msg = f"{title} için uyumlu versiyon bulunamadı (MC {version})."
                    result_type = "error"
                else:
                    ver_data = versions[0]
                    files = ver_data.get("files", [])
                    if not files:
                        result_msg = "Dosya bulunamadı."
                        result_type = "error"
                    else:
                        primary = next((f for f in files if f.get("primary")), files[0])
                        download_url = primary["url"]
                        filename = primary["filename"]
                        new_server_type = ver_data.get("loaders", ["vanilla"])[0] if ver_data.get("loaders") else "vanilla"
                        matched_mc = ver_data.get("game_versions", [version])[0]

                        ssh = ssh_connect()
                        try:
                            ssh_exec(ssh, "docker stop mc", timeout=30)

                            r = requests.get(download_url, timeout=120, stream=True)
                            r.raise_for_status()
                            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mrpack")
                            for chunk in r.iter_content(chunk_size=8192):
                                tmp.write(chunk)
                            tmp.close()

                            sftp = ssh.open_sftp()
                            sftp.put(tmp.name, f"/tmp/{filename}")
                            sftp.close()
                            os.unlink(tmp.name)

                            extract_script = f"""#!/usr/bin/env python3
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
                            sftp = ssh.open_sftp()
                            with sftp.open("/tmp/extract_modpack.py", "w") as f:
                                f.write(extract_script)
                            sftp.close()
                            ssh_exec(ssh, "sudo python3 /tmp/extract_modpack.py && sudo rm /tmp/extract_modpack.py", timeout=120)

                            download_mods_script = """#!/usr/bin/env python3
import json, urllib.request, os
with open('/tmp/modpack_extract/modrinth.index.json') as f:
    index = json.load(f)
data_dir = '/opt/minecraft/data'
downloaded = 0
for fi in index.get('files', []):
    path = fi.get('path', '')
    dest = os.path.join(data_dir, path)
    if os.path.exists(dest):
        continue
    url = fi.get('downloads', [None])[0]
    if not url:
        continue
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    try:
        urllib.request.urlretrieve(url, dest)
        downloaded += 1
    except Exception:
        pass
print(f'DONE:{downloaded}')
"""
                            sftp = ssh.open_sftp()
                            with sftp.open("/tmp/download_modpack.py", "w") as f:
                                f.write(download_mods_script)
                            sftp.close()
                            ssh_exec(ssh, "sudo python3 /tmp/download_modpack.py && sudo rm /tmp/download_modpack.py", timeout=300)

                            ssh_exec(ssh, "sudo mkdir -p /opt/minecraft/data/mods-quarantine")
                            _, mods_list, _ = ssh_exec(ssh, "ls /opt/minecraft/data/mods/ 2>/dev/null")
                            if mods_list:
                                for mod_file in mods_list.strip().split("\n"):
                                    mod_lower = mod_file.lower()
                                    for pattern in CLIENT_ONLY_MODS:
                                        if pattern in mod_lower:
                                            ssh_exec(ssh, f"sudo mv /opt/minecraft/data/mods/{mod_file} /opt/minecraft/data/mods-quarantine/")
                                            break

                            ssh_exec(ssh, "sudo chmod -R 777 /opt/minecraft/data && rm -rf /tmp/modpack_extract", timeout=30)

                            loader_mapped = LOADER_MAP.get(new_server_type)
                            if loader_mapped:
                                config["server_type"] = loader_mapped
                            config["minecraft_version"] = matched_mc
                            save_config(config)

                            java_tag = get_java_tag(matched_mc)
                            memory = config.get("ram_gb", 16)
                            port = config.get("server_port", 25565)
                            online_mode = str(config.get("online_mode", False)).upper()
                            max_players = config.get("max_players", 20)
                            view_distance = config.get("view_distance", 20)
                            enable_rcon = str(config.get("enable_rcon", True)).upper()
                            motd = config.get("server_name", "MC Server")

                            docker_run = build_docker_run(
                                matched_mc, new_server_type, java_tag, memory, port,
                                online_mode, max_players, view_distance, enable_rcon, motd
                            )
                            ssh_exec(ssh, docker_run, timeout=120)

                            result_msg = f"{title} modpack'i kuruldu ({new_server_type}, MC {matched_mc}). Sunucu yeniden başlatıldı."
                            result_type = "success"
                        finally:
                            ssh.close()
        except Exception as e:
            result_msg = f"Hata: {e}"
            result_type = "error"

    return RedirectResponse("/mods?type=modpack", status_code=303)


@app.post("/mods/uninstall-pack")
async def modpack_uninstall(request: Request):
    if not is_configured():
        return RedirectResponse("/settings", status_code=303)
    try:
        config = load_config()
        ssh = ssh_connect()
        try:
            ssh_exec(ssh, "docker stop mc", timeout=30)

            ssh_exec(ssh, "sudo rm -rf /opt/minecraft/data/mods")
            ssh_exec(ssh, "sudo rm -rf /opt/minecraft/data/config")
            ssh_exec(ssh, "sudo rm -rf /opt/minecraft/data/scripts")
            ssh_exec(ssh, "sudo rm -f /opt/minecraft/data/modrinth.index.json")
            ssh_exec(ssh, "sudo rm -f /opt/minecraft/data/.mrpack")
            ssh_exec(ssh, "sudo rm -rf /opt/minecraft/data/crash-reports")
            ssh_exec(ssh, "sudo chmod -R 777 /opt/minecraft/data", timeout=30)

            config["server_type"] = "vanilla"
            save_config(config)

            version = config["minecraft_version"]
            java_tag = get_java_tag(version)
            memory = config.get("ram_gb", 16)
            port = config.get("server_port", 25565)
            online_mode = str(config.get("online_mode", False)).upper()
            max_players = config.get("max_players", 20)
            view_distance = config.get("view_distance", 20)
            enable_rcon = str(config.get("enable_rcon", True)).upper()
            motd = config.get("server_name", "MC Server")

            docker_run = build_docker_run(
                version, "vanilla", java_tag, memory, port,
                online_mode, max_players, view_distance, enable_rcon, motd
            )
            ssh_exec(ssh, docker_run, timeout=120)
        finally:
            ssh.close()
    except Exception:
        pass

    return RedirectResponse("/mods?type=modpack", status_code=303)


@app.post("/mods/remove")
async def mod_remove(request: Request):
    if not is_configured():
        return RedirectResponse("/settings", status_code=303)
    form = await request.form()
    mod_name = form.get("mod_name", "")
    result_msg = ""
    result_type = "info"

    if mod_name:
        try:
            ssh = ssh_connect()
            _, stdout, _ = ssh_exec(ssh, "ls /opt/minecraft/data/mods/ 2>/dev/null")
            if stdout:
                mods = stdout.strip().split("\n")
                matching = [m for m in mods if mod_name.lower() in m.lower()]
                if matching:
                    target = matching[0]
                    ssh_exec(ssh, f"sudo rm /opt/minecraft/data/mods/{target}")
                    _, container_status, _ = ssh_exec(ssh, "docker inspect mc --format '{{.State.Status}}' 2>/dev/null")
                    if container_status == "running":
                        ssh_exec(ssh, "docker restart mc", timeout=60)
                    result_msg = f"{target} kaldırıldı."
                    result_type = "success"
                else:
                    result_msg = f"'{mod_name}' bulunamadı."
                    result_type = "error"
            ssh.close()
        except Exception as e:
            result_msg = f"Hata: {e}"
            result_type = "error"

    mod_list = []
    try:
        ssh = ssh_connect()
        _, stdout, _ = ssh_exec(ssh, "ls /opt/minecraft/data/mods/ 2>/dev/null")
        if stdout and "No such file" not in stdout:
            mod_list = [m for m in stdout.strip().split("\n") if m.strip().endswith(".jar")]
        ssh.close()
    except Exception:
        pass

    return templates.TemplateResponse("mods.html", {
        "request": request,
        "mods": mod_list,
        "result_msg": result_msg,
        "result_type": result_type,
    })


@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    config = load_config()
    return templates.TemplateResponse("settings.html", {"request": request, "config": config, "configured": is_configured()})


@app.post("/settings")
async def settings_save(request: Request):
    form = await request.form()
    config = load_config()

    config["minecraft_version"] = form.get("minecraft_version", config.get("minecraft_version", "1.20.1"))
    config["server_type"] = form.get("server_type", config.get("server_type", "vanilla"))
    config["ram_gb"] = int(form.get("ram_gb", config.get("ram_gb", 4)))
    config["max_players"] = int(form.get("max_players", config.get("max_players", 20)))
    config["view_distance"] = int(form.get("view_distance", config.get("view_distance", 10)))
    config["server_name"] = form.get("server_name", config.get("server_name", "MC Server"))
    config["online_mode"] = form.get("online_mode") == "on"
    config["enable_rcon"] = form.get("enable_rcon") == "on"
    config["server_ip"] = form.get("server_ip", config.get("server_ip", ""))
    config["ssh_user"] = form.get("ssh_user", config.get("ssh_user", "ubuntu"))
    config["server_port"] = config.get("server_port", 25565)

    save_config(config)

    if not is_configured():
        return RedirectResponse("/settings", status_code=303)

    version = config["minecraft_version"]
    java_tag = get_java_tag(version)
    docker_run = build_docker_run(
        version, config["server_type"], java_tag, config["ram_gb"],
        config["server_port"], str(config["online_mode"]).upper(),
        config["max_players"], config["view_distance"],
        str(config["enable_rcon"]).upper(), config["server_name"]
    )

    try:
        ssh = ssh_connect()
        ssh_exec(ssh, docker_run, timeout=120)
        ssh.close()
    except Exception:
        pass

    return RedirectResponse("/settings", status_code=303)


@app.get("/oracle", response_class=HTMLResponse)
async def oracle_page(request: Request):
    oci = load_oci_credentials()
    oci_configured = bool(oci.get("tenancy_ocid"))
    tf_state = "No state available."
    if oci_configured:
        tf_state = run_terraform(["show", "-json"], timeout=30)
        try:
            state_data = json.loads(tf_state)
            resources = state_data.get("values", {}).get("root_module", {}).get("resources", [])
            if resources:
                lines = []
                for r in resources:
                    rtype = r.get("type", "unknown")
                    name = r.get("name", "unknown")
                    values = r.get("values", {})
                    ip = values.get("public_ip") or values.get("private_ip") or ""
                    lines.append(f"{rtype}.{name}: {ip or 'created'}")
                tf_state = "\n".join(lines)
            else:
                tf_state = "No resources deployed."
        except (json.JSONDecodeError, KeyError):
            tf_state = "Could not parse state."
    return templates.TemplateResponse("oracle.html", {
        "request": request, "oci": oci, "oci_configured": oci_configured, "tf_state": tf_state, "result_msg": None, "result_type": None,
    })


@app.post("/oracle")
async def oracle_save(request: Request):
    form = await request.form()
    oci = {
        "tenancy_ocid": form.get("tenancy_ocid", ""),
        "user_ocid": form.get("user_ocid", ""),
        "compartment_ocid": form.get("compartment_ocid", ""),
        "fingerprint": form.get("fingerprint", ""),
        "private_key_path": form.get("private_key_path", "key1.pem"),
        "region_key": form.get("region_key", ""),
    }
    save_oci_credentials(oci)

    oci_configured = bool(oci.get("tenancy_ocid"))
    tf_state = "No state available."
    if oci_configured:
        tf_state = run_terraform(["init", "-input=false"], timeout=120)
        tf_state += "\n\n" + run_terraform(["show", "-json"], timeout=30)

    return templates.TemplateResponse("oracle.html", {
        "request": request, "oci": oci, "oci_configured": oci_configured, "tf_state": tf_state,
        "result_msg": "Credentials saved.", "result_type": "success",
    })


@app.post("/oracle/deploy")
async def oracle_deploy(request: Request):
    oci = load_oci_credentials()
    if not oci.get("tenancy_ocid"):
        return RedirectResponse("/oracle", status_code=303)

    run_terraform(["init", "-input=false"], timeout=120)
    output = run_terraform(["apply", "-auto-approve", "-input=false"], timeout=600)

    oci_configured = bool(oci.get("tenancy_ocid"))
    tf_state = run_terraform(["show", "-json"], timeout=30)
    try:
        state_data = json.loads(tf_state)
        resources = state_data.get("values", {}).get("root_module", {}).get("resources", [])
        if resources:
            lines = []
            for r in resources:
                rtype = r.get("type", "unknown")
                name = r.get("name", "unknown")
                values = r.get("values", {})
                ip = values.get("public_ip") or values.get("private_ip") or ""
                lines.append(f"{rtype}.{name}: {ip or 'created'}")
            tf_state = "\n".join(lines)
        else:
            tf_state = "No resources deployed."
    except (json.JSONDecodeError, KeyError):
        pass

    return templates.TemplateResponse("oracle.html", {
        "request": request, "oci": oci, "oci_configured": oci_configured, "tf_state": tf_state,
        "result_msg": f"Deploy complete. Check logs for details.", "result_type": "success",
    })


@app.post("/oracle/destroy")
async def oracle_destroy(request: Request):
    oci = load_oci_credentials()
    if not oci.get("tenancy_ocid"):
        return RedirectResponse("/oracle", status_code=303)

    output = run_terraform(["destroy", "-auto-approve", "-input=false"], timeout=600)

    oci_configured = bool(oci.get("tenancy_ocid"))
    tf_state = "No resources deployed."

    return templates.TemplateResponse("oracle.html", {
        "request": request, "oci": oci, "oci_configured": False, "tf_state": tf_state,
        "result_msg": "Destroy complete.", "result_type": "success",
    })


@app.get("/players", response_class=HTMLResponse)
async def players_page(request: Request):
    if not is_configured():
        return RedirectResponse("/settings", status_code=303)
    ops = []
    whitelist = []
    bans = []
    try:
        ssh = ssh_connect()
        _, ops_out, _ = ssh_exec(ssh, docker_cmd("cat /data/ops.json 2>/dev/null || echo '[]'"), timeout=10)
        try:
            ops_data = json.loads(ops_out) if ops_out else []
            ops = [o.get("name", "") for o in ops_data]
        except json.JSONDecodeError:
            pass

        _, wl_out, _ = ssh_exec(ssh, docker_cmd("cat /data/whitelist.json 2>/dev/null || echo '[]'"), timeout=10)
        try:
            wl_data = json.loads(wl_out) if wl_out else []
            whitelist = [w.get("name", "") for w in wl_data]
        except json.JSONDecodeError:
            pass

        _, ban_out, _ = ssh_exec(ssh, docker_cmd("cat /data/banned-players.json 2>/dev/null || echo '[]'"), timeout=10)
        try:
            ban_data = json.loads(ban_out) if ban_out else []
            bans = [b.get("name", "") for b in ban_data]
        except json.JSONDecodeError:
            pass

        ssh.close()
    except Exception:
        pass

    return templates.TemplateResponse("players.html", {
        "request": request, "ops": ops, "whitelist": whitelist, "bans": bans
    })


@app.post("/players/op")
async def player_op(request: Request):
    if not is_configured():
        return RedirectResponse("/settings", status_code=303)
    form = await request.form()
    player = form.get("player", "")
    if player:
        try:
            ssh = ssh_connect()
            ssh_exec(ssh, docker_cmd(f"op {player}"), timeout=15)
            ssh.close()
        except Exception:
            pass
    return RedirectResponse("/players", status_code=303)


@app.post("/players/deop")
async def player_deop(request: Request):
    if not is_configured():
        return RedirectResponse("/settings", status_code=303)
    form = await request.form()
    player = form.get("player", "")
    if player:
        try:
            ssh = ssh_connect()
            ssh_exec(ssh, docker_cmd(f"deop {player}"), timeout=15)
            ssh.close()
        except Exception:
            pass
    return RedirectResponse("/players", status_code=303)


@app.post("/players/whitelist-add")
async def whitelist_add(request: Request):
    if not is_configured():
        return RedirectResponse("/settings", status_code=303)
    form = await request.form()
    player = form.get("player", "")
    if player:
        try:
            ssh = ssh_connect()
            ssh_exec(ssh, docker_cmd(f"whitelist add {player}"), timeout=15)
            ssh.close()
        except Exception:
            pass
    return RedirectResponse("/players", status_code=303)


@app.post("/players/whitelist-remove")
async def whitelist_remove(request: Request):
    if not is_configured():
        return RedirectResponse("/settings", status_code=303)
    form = await request.form()
    player = form.get("player", "")
    if player:
        try:
            ssh = ssh_connect()
            ssh_exec(ssh, docker_cmd(f"whitelist remove {player}"), timeout=15)
            ssh.close()
        except Exception:
            pass
    return RedirectResponse("/players", status_code=303)


@app.post("/players/ban")
async def player_ban(request: Request):
    if not is_configured():
        return RedirectResponse("/settings", status_code=303)
    form = await request.form()
    player = form.get("player", "")
    reason = form.get("reason", "Banned by admin")
    if player:
        try:
            ssh = ssh_connect()
            ssh_exec(ssh, docker_cmd(f'ban {player} {reason}'), timeout=15)
            ssh.close()
        except Exception:
            pass
    return RedirectResponse("/players", status_code=303)


@app.post("/players/pardon")
async def player_pardon(request: Request):
    if not is_configured():
        return RedirectResponse("/settings", status_code=303)
    form = await request.form()
    player = form.get("player", "")
    if player:
        try:
            ssh = ssh_connect()
            ssh_exec(ssh, docker_cmd(f"pardon {player}"), timeout=15)
            ssh.close()
        except Exception:
            pass
    return RedirectResponse("/players", status_code=303)
