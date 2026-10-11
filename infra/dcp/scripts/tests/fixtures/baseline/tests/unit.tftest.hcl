run "verify_message" {
  command = plan
  assert {
    condition     = local.message == "hello-active"
    error_message = "unexpected message value"
  }
}
