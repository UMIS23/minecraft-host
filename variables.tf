variable "tenancy_ocid" {
  type        = string
  description = "Oracle Cloud Tenancy OCID"
}

variable "user_ocid" {
  type        = string
  description = "Oracle Cloud User OCID"
}

variable "compartment_ocid" {
  type        = string
  description = "Oracle Cloud Compartment OCID"
}

variable "fingerprint" {
  type        = string
  description = "OCI API Key Fingerprint"
}

variable "private_key_path" {
  type        = string
  description = "OCI API Private Key Path"
}

variable "ssh_private_key_path" {
  type        = string
  description = "SSH Private Key Path for VM access (separate from OCI API key)"
  default     = "key1"
}

variable "ssh_public_key_path" {
  type        = string
  description = "SSH Public Key Path installed on the VM (separate from OCI API key)"
  default     = "key1.pub"
}

variable "region_key" {
  type        = string
  description = "OCI Region"
}
