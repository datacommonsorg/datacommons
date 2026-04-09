resource "google_workflows_workflow" "ingestion_orchestrator" {
  count               = var.deploy_data_ingestion_workflow ? 1 : 0
  name                = "${var.namespace}-ingestion-orchestrator"
  region              = var.region
  description         = "Triggers the Dataflow Flex Template Graph Ingestion Pipeline with runtime parameters"
  service_account     = google_service_account.dcp_ingestion_runner[0].id
  deletion_protection = var.deletion_protection

  source_contents = <<-EOF
  main:
    params: [input]
    steps:
      - init:
          assign:
            - project_id: '${var.project_id}'
            - launch_params:
                projectId: '$${project_id}'
                spannerInstanceId: '$${input.spannerInstanceId}'
                spannerDatabaseId: '$${input.spannerDatabaseId}'
                importList: '$${input.importList}'
                tempLocation: '$${input.tempLocation}'
      - run_flex_template:
          call: googleapis.dataflow.v1b3.projects.locations.flexTemplates.launch
          args:
            projectId: '$${project_id}'
            location: '$${input.region}'
            body:
              launchParameter:
                jobName: '$${"ingestion-job-" + string(int(sys.now()))}'
                containerSpecGcsPath: 'gs://datcom-templates/templates/flex/ingestion.json'
                parameters: '$${launch_params}'
          result: launch_result
      - return_result:
          return: '$${launch_result}'
  EOF
}

# Automatically provision a GCS bucket for the customer's custom graph ingestion files, if enabled
resource "google_storage_bucket" "data_ingestion_bucket" {
  count                       = var.deploy_data_ingestion_workflow && var.create_ingestion_bucket ? 1 : 0
  name                        = "${var.namespace}-ingestion-bucket-${var.project_id}"
  location                    = var.region
  uniform_bucket_level_access = true
  force_destroy               = !var.deletion_protection
}
