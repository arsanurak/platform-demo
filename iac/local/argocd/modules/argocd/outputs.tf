output "root_app_path" {
  description = "Folder of this repo the root app syncs."
  value       = one([for s in helm_release.root_app.set : s.value if s.name == "applications.root.source.path"])
}
