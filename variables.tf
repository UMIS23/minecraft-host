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
  description = "OCI Private Key Path"
}

variable "region_key" {
  type        = string
  description = "OCI Region"
}
