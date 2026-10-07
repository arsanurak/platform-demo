output "root_app_paths" {
  description = "Folder each cluster's root app syncs, keyed by cluster."
  value = {
    old = module.old.root_app_path
    new = module.new.root_app_path
  }
}
