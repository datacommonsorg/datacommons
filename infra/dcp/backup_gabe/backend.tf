terraform {
  backend "gcs" {
    bucket = "datacommons-platform-tf-state-1"
    prefix = "terraform/state"
  }
}
