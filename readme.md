# MC Server Automation

Deploy a Minecraft server on Oracle Cloud Free Tier and manage it through a web panel.

---

## Prerequisites

- **Oracle Cloud account** — [Sign up](https://cloud.oracle.com) (Free Tier eligible)

---

## Step 1: Create Oracle Cloud API Key

1. Log in to [Oracle Cloud Console](https://cloud.oracle.com)
2. Click your **profile icon** (top right) → **Tokens and Keys**
3. Left menu → **API Keys** → **Add API Key**
4. Select **Generate API Key Pair**
5. Download the **Private Key** (`.pem` file) → the console doesn't ask for a name, so rename it yourself into this project folder (e.g. `mv ~/Downloads/*.pem ./my-oci-key.pem`)
6. Click **Add** → copy the **Tenancy OCID**, **User OCID**, **Fingerprint**, and **Region** shown on screen.
7. For **Compartment OCID**: click the navigation menu (top left) → **Identity & Security** → **Compartments** → select your compartment → **Copy OCID**.
8. Set key permissions: `chmod 400 my-oci-key.pem` (use your own file name)

---

## Step 2: Create SSH Key

Pick any name for your SSH key (e.g. `my-ssh-key`). It must be **different** from the OCI API key above:

```bash
ssh-keygen -t ed25519 -f my-ssh-key -N ""
chmod 600 my-ssh-key
```

> The name after `-f` becomes both files' name: `my-ssh-key` (private) + `my-ssh-key.pub` (public, created automatically). This is where you name your key.

> Terraform automatically adds this key to your VM during deployment.

### Where key names go

| Key | File(s) | Setting |
|---|---|---|
| OCI API private key | `terraform.tfvars` | `private_key_path = "my-oci-key.pem"` |
| SSH private key | `terraform.tfvars` | `ssh_private_key_path = "my-ssh-key"` |
| SSH public key | `terraform.tfvars` | `ssh_public_key_path = "my-ssh-key.pub"` |
| SSH private key | `config.json` | `"ssh_key_path": "my-ssh-key"` |

> Running the panel locally with `docker compose` and custom key names? Export `SSH_KEY_FILE=my-ssh-key` and/or `OCI_KEY_FILE=my-oci-key.pem` first (defaults: `key1` / `key1.pem`).

---

## Step 3: Configure Terraform

1. Copy the example files and rename them:

```bash
cp terraform.tfvars.example terraform.tfvars
cp config.example.json config.json
```

> `config.json` is required — Terraform reads the server settings from it (`main.tf`).

2. Open `terraform.tfvars` and fill in your values from Step 1:

```hcl
tenancy_ocid     = "ocid1.tenancy.oc1..aaaa..."
user_ocid        = "ocid1.user.oc1..aaaa..."
compartment_ocid = "ocid1.tenancy.oc1..aaaa..."
fingerprint      = "xx:xx:xx:xx:xx:xx:xx:xx:xx:xx:xx:xx:xx:xx:xx:xx"
private_key_path = "my-oci-key.pem"
ssh_private_key_path = "my-ssh-key"
ssh_public_key_path  = "my-ssh-key.pub"
region_key       = "il-jerusalem-1"
```

3. Install Terraform: `sudo snap install terraform --classic`

> Requires Terraform >= 1.5 and Python >= 3.12.

4. Install Python dependencies (for `mc_manager.py` CLI):

```bash
sudo apt install -y python3-venv  # Ubuntu/Debian'da venv desteği yoksa
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

> On Ubuntu 23.04+ `pip install` without a venv is blocked (PEP 668). Either use the venv above or add `--break-system-packages`.

---

## Step 4: Deploy

```bash
terraform init
terraform apply
```

Wait 5-8 minutes for deployment to complete. The outputs show two IPs:

```bash
terraform output -raw ssh_ip   # management/SSH (yours only)
terraform output -raw mc_ip    # player address (give this to players)
```

---

## Step 5: Access Web Panel

1. Start an SSH tunnel:

```bash
ssh -i my-ssh-key -L 8080:127.0.0.1:80 ubuntu@<SERVER_IP>
```

> Use your own SSH key name from Step 2.

2. Open in browser: `http://localhost:8080`

3. Go to **Settings** → paste your server's public IP into **Server IP** field → Save.

---

## Web Panel Overview

### Dashboard
Server status, IP, version, RAM/CPU usage. Start / Stop / Restart buttons.

### Logs
- **Minecraft** tab — server console logs
- **Terraform** tab — deploy/infrastructure logs

### Mods
Search and install mods from Modrinth. View and remove installed mods.

### Players
OP management, Whitelist, Ban list.

### Settings
Minecraft version, server type, RAM, players, MOTD, etc.

---

## Supported Server Types

`vanilla`, `forge`, `fabric`, `paper`, `spigot`, `bukkit`, `purpur`, `quilt`, `neoforge`

## Supported MC Versions

1.16.x and above (Java 17 / Java 21)
