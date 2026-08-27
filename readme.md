# Quick Setup Guide

Follow these simple steps to deploy your infrastructure on Oracle Cloud using Terraform.

---

### 1. Get Your Oracle Credentials

Log in to the Oracle Cloud Console:

* **Tenancy OCID:** Click Profile (top right) -> Tenancy: your_name -> Copy OCID.
* **User OCID:** Click Profile -> User Settings -> Copy OCID.
* **Compartment OCID:** Go to Menu (top left) -> Identity & Security -> Compartments -> Click on your compartment -> Copy OCID. *(Note: If you don't have a custom compartment, you can use your Tenancy OCID).*

---

### 2. Create API Key

1. Go to Profile -> User Settings -> API Keys (under Resources on the left).
2. Click **Add API Key** -> Select **Generate API Key Pair**.
3. Download the **Private Key** (`.pem` file) and save it inside your project folder.
4. Click **Add** and copy the generated **Fingerprint**.
5. **Set Key Permissions (Critical for Linux/WSL):** Open your terminal and restrict access to your private key file to prevent permission errors by running: `chmod 400 your_api_key.pem`

---

### 3. Configure Variables

1. Rename `terraform.tfvars.example` to `terraform.tfvars`.
2. Open `terraform.tfvars` with a text editor.
3. Paste the information collected above into the matching sections of the file and save it.

---

### 4. Deploy

Open your terminal in the project directory and run the following commands:

```bash
terraform init
terraform plan
terraform apply

