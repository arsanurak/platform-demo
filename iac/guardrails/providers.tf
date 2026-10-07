# This root is written to be read and tested, never applied.
# The provider only accepts the placeholder account 000000000000, which does
# not exist, so a plan or apply with real credentials fails before it can
# read or change anything.

provider "aws" {
  region              = var.region
  allowed_account_ids = ["000000000000"]

  default_tags {
    tags = {
      project    = "platform-demo"
      managed-by = "terraform"
    }
  }
}
