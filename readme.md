# Quick Setup Guide

Follow these simple steps to deploy your infrastructure on Oracle Cloud using Terraform.

---

### 1. Get Your Oracle Credentials

Log in to the Oracle Cloud Console:

* **Tenancy OCID:** Click Profile (top right) -> Tenancy: your_name -> Copy OCID.
* **User OCID:** Click Profile -> Copy OCID.
* **Compartment OCID:** Go to Menu (top left) -> Identity & Security -> Compartments -> Click on your compartment -> Copy OCID. *(Note: If you don't have a custom compartment, you can use your Tenancy OCID).*
* **Region Key** Click Developer Tools(left side of the profile) -> Cloud shell -> It's looking at you! 
---

### 2. Create API Key

1. Go to Profile -> Tokens and Keys -> API Keys (under Resources on the left).
2. Click **Add API Key** -> Select **Generate API Key Pair**.
3. Download the **Private Key** (`.pem` file) and save it inside your project folder.
4. Click **Add** and copy the generated **Fingerprint**.
5. **Set Key Permissions:** Open your terminal and restrict access to your private key file to prevent permission errors by running: `chmod 400 your_api_key.pem`

---

### 3. Configure Variables

1. Rename `terraform.tfvars.example` to `terraform.tfvars`.
2. Open `terraform.tfvars` with a text editor.
3. Paste the information collected above into the matching sections of the file and save it.
4. Copy `config.example.json` to `config.json` and edit it with your preferred Minecraft server settings (version, RAM, MOTD, etc.).

> **Note:** `terraform.tfvars` and `config.json` are gitignored for security. A `.example` file is provided for each — copy and rename them, then fill in your own values before deploying.

---

### 4. Deploy

Open your terminal in the project directory and run the following commands:

```bash
terraform init
terraform plan
terraform apply
```

After deployment, note the server IP from the output.

---

### 5. Connect via SSH

```bash
ssh ubuntu@<SERVER_IP>
```

Replace `<SERVER_IP>` with the IP shown in the Terraform output (or run `terraform output ssh_ip`).

---

### 6. Server Console

After connecting via SSH, run:

```bash
sudo docker exec -it mc rcon-cli
```

Useful commands:
- `list` — Show online players
- `say <message>` — Broadcast a message
- `op <player>` — Make a player operator
- `whitelist on/off` — Toggle whitelist
- `stop` — Stop the server

---

## Minecraft Server Manager (`mc_manager.py`)

A Python CLI tool to manage your Minecraft server remotely via SSH. Install/remove mods, change server version or type, and monitor server status — all from your local terminal.

### Setup

```bash
pip install -r requirements.txt
```

### Commands

#### Server Status

```bash
python3 mc_manager.py status
```

Shows container status, port availability, CPU/memory usage, Java version, disk usage, and server properties.

#### Install a Mod

```bash
python3 mc_manager.py install <mod_name>
```

Searches Modrinth for the mod, lets you pick from results, downloads the `.jar` file, and uploads it to the server's mods folder. Optionally restarts the server to apply.

#### Install a Modpack

```bash
python3 mc_manager.py install-pack <pack_name>
```

Searches Modrinth for modpacks, lets you pick one, downloads the `.mrpack` file, extracts overrides and additional mods, removes known client-side mods (Iris, Sodium, etc.), updates the server type automatically, and restarts the server. Includes automatic crash detection and problematic mod removal.

#### Uninstall a Modpack

```bash
python3 mc_manager.py uninstall-pack
```

Removes all mods, config files, and modpack data from the server. Resets the server type to vanilla and restarts. Optionally deletes world data (you'll be prompted). Use this to revert to a clean vanilla server after removing a modpack.

#### Remove a Mod

```bash
python3 mc_manager.py remove <mod_name>
```

Finds and removes a mod file from the server. Supports partial name matching. If multiple mods match, you'll be prompted to select which one to remove.

#### List Installed Mods

```bash
python3 mc_manager.py list
```

Lists all `.jar` mod files in the server's mods directory with file sizes.

#### Change Server Version

```bash
python3 mc_manager.py set-version <version>
```

Stops the current container, updates the Minecraft version, and recreates the container with the new version. Data (world, mods, configs) is preserved.

#### Change Server Type

```bash
python3 mc_manager.py set-type <type>
```

Switches between server types. The server will restart with the new type.

**Valid types:** `vanilla`, `forge`, `fabric`, `paper`, `spigot`, `bukkit`, `purpur`, `sponge`, `velocity`, `quilt`, `neoforge`, `bedrock`

#### Change Server MOTD

```bash
python3 mc_manager.py set-motd <message>
```

Updates the Message of the Day (the text shown in the Minecraft server list).

#### Restart / Stop / Start

```bash
python3 mc_manager.py restart
python3 mc_manager.py stop
python3 mc_manager.py start
```

- **restart** — Restarts the Docker container. Use after installing/removing mods or changing settings.
- **stop** — Stops the server completely. Players cannot connect.
- **start** — Starts a stopped server container.

