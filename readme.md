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
5. Download the **Private Key** (`.pem` file) → save it to this project folder
6. Click **Add** → copy the **Fingerprint** shown
7. Set key permissions: `chmod 400 key1.pem`

---

## Step 2: Create SSH Key

Run in terminal:

```bash
ssh-keygen -t ed25519 -f key1 -N ""
```

Upload the public key to Oracle:

1. Profile icon → **My Profile** → Left menu → **SSH Keys**
2. **Add Public Key** → paste contents of `key1.pub`
3. Click **Add**

---

## Step 3: Gather Your OCIDs

| Value | Where to find |
|-------|---------------|
| **Tenancy OCID** | Profile icon → **Tenancy** → Copy OCID |
| **User OCID** | Profile icon → Copy OCID |
| **Compartment OCID** | Menu (top left) → **Identity & Security** → **Compartments** → select your compartment → Copy OCID |
| **Fingerprint** | Profile → Tokens and Keys → API Keys → copy fingerprint |
| **Region** | Look at the top of the page or open Cloud Shell → shown at the top |

---

## Step 4: First Boot

1. Start an SSH tunnel:

```bash
ssh -i key1.pem -L 8080:127.0.0.1:80 ubuntu@<SERVER_IP>
```

> If you haven't deployed yet, you won't have a SERVER_IP. That's okay — you can deploy from the web panel directly.

2. Open in browser: `http://localhost:8080`

3. Go to **Oracle Cloud** page (sidebar)

4. Fill in the 6 fields with values from Step 3:

| Field | Paste your |
|-------|-----------|
| Tenancy OCID | `ocid1.tenancy.oc1..aaaa...` |
| User OCID | `ocid1.user.oc1..aaaa...` |
| Compartment OCID | `ocid1.tenancy.oc1..aaaa...` |
| Fingerprint | `xx:xx:xx:xx:xx:xx:xx:xx:xx:xx:xx:xx:xx:xx:xx:xx` |
| Private Key Path | `key1.pem` |
| Region | `il-jerusalem-1` |

5. Click **Save Credentials**

6. Click **Deploy** — wait 5-8 minutes

7. After deploy, go to **Settings** → the server IP will now show the public IP of your VM. Copy it into the **Server IP** field → Save.

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

### Oracle Cloud
OCI credentials, Deploy/Destroy buttons, current infrastructure state.

---

## Supported Server Types

`vanilla`, `forge`, `fabric`, `paper`, `spigot`, `bukkit`, `purpur`, `quilt`, `neoforge`

## Supported MC Versions

1.16.x and above (Java 17 / Java 21)
