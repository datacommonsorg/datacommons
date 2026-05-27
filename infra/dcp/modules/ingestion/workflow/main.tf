locals {
  name_prefix = var.namespace != "" ? "${var.namespace}-" : ""
}

resource "google_service_account" "workflow_sa" {
  count        = var.deploy ? 1 : 0
  account_id   = "${local.name_prefix}dc-ing-wf-sa"
  display_name = "Data Commons Ingestion Workflow SA"
}

resource "google_workflows_workflow" "ingestion_orchestrator" {
  count               = var.deploy ? 1 : 0
  name                = "${local.name_prefix}dc-ingestion-workflow"
  region              = var.region
  description         = "Triggers the Dataflow Flex Template Graph Ingestion Pipeline with runtime parameters"
  service_account     = google_service_account.workflow_sa[0].email
  deletion_protection = var.stateless_deletion_protection

  source_contents = <<-EOF2
  main:
    params: [input]
    steps:
      - init:
          assign:
            - project_id: '${var.project_id}'
            - workflow_id: '$${sys.get_env("GOOGLE_CLOUD_WORKFLOW_EXECUTION_ID")}'
            - version: '$${"version-" + string(int(sys.now()))}'
            - bucket_name: '$${text.split(input.tempLocation, "/")[2]}'
            - latest_version_gcs_path: '$${"gs://" + bucket_name + "/imports/" + input.importName + "/" + version}'
            - execution_error: null
            - lock_timeout: ${var.lock_acquisition_timeout}
            - launch_params:
                projectId: '$${project_id}'
                spannerInstanceId: '$${input.spannerInstanceId}'
                spannerDatabaseId: '$${input.spannerDatabaseId}'
                importList: '$${input.importList}'
                tempLocation: '$${input.tempLocation}'
                stagingLocation: '$${input.tempLocation}'
                forceCombineNodes: 'true'
      - acquire_lock:
          try:
            call: http.post
            args:
              url: '${var.ingestion_helper_url}'
              auth:
                type: OIDC
              body:
                actionType: "acquire_ingestion_lock"
                workflowId: '$${workflow_id}'
                timeout: '$${lock_timeout}'
            result: lock_result
          retry:
            predicate: '$${http.default_retry_predicate}'
            max_retries: 60 # Approx 5 hours
            backoff:
              initial_delay: 60
              max_delay: 300 # Max 5 minutes retry interval
              multiplier: 2
      - process_ingestion:
          try:
            steps:
              - set_import_staging:
                  call: http.post
                  args:
                    url: '${var.ingestion_helper_url}'
                    auth:
                      type: OIDC
                    body:
                      actionType: "update_import_status"
                      importName: '$${input.importName}'
                      status: "STAGING"
                      latestVersion: '$${latest_version_gcs_path}'
                  result: staging_result
              - run_flex_template:
                  call: googleapis.dataflow.v1b3.projects.locations.flexTemplates.launch
                  args:
                    projectId: '$${project_id}'
                    location: '$${input.region}'
                    body:
                      launchParameter:
                        jobName: '$${"${replace(lower(var.namespace), "_", "-")}-" + text.substring(text.replace_all(text.to_lower(input.importName), "_", "-"), 0, 35) + "-" + string(int(sys.now()))}'
                        containerSpecGcsPath: 'gs://datcom-templates/templates/flex/ingestion.json'
                        parameters: '$${launch_params}'
                        environment:
                          serviceAccountEmail: '${var.dataflow_service_account_email}'
                          tempLocation: '$${input.tempLocation}'
                          stagingLocation: '$${input.tempLocation}'
                  result: launch_result
              - get_job_id:
                  assign:
                    - job_id: '$${launch_result.job.id}'
              - poll_job:
                  steps:
                    - get_status:
                        call: googleapis.dataflow.v1b3.projects.locations.jobs.get
                        args:
                          projectId: '$${project_id}'
                          location: '$${input.region}'
                          jobId: '$${job_id}'
                        result: job_status
                    - check_terminal:
                        switch:
                          - condition: '$${job_status.currentState in ["JOB_STATE_DONE", "JOB_STATE_FAILED", "JOB_STATE_CANCELLED", "JOB_STATE_UPDATED", "JOB_STATE_DRAINED"]}'
                            next: check_success
                    - wait_and_retry:
                        call: sys.sleep
                        args:
                          seconds: 60
                        next: poll_job
              - check_success:
                  switch:
                    - condition: '$${job_status.currentState == "JOB_STATE_DONE"}'
                      next: %{ if var.enable_bigquery_postprocessing || var.enable_embedding_ingestion }run_optional_tasks%{ else }promote_version%{ endif }
              - fail_on_job_status:
                  raise: '$${ "Dataflow job failed with state: " + job_status.currentState }'
%{ if var.enable_bigquery_postprocessing || var.enable_embedding_ingestion }
              - run_optional_tasks:
                  parallel:
                    branches:
%{ if var.enable_bigquery_postprocessing }
                      - postprocessing:
                          steps:
                            - run_postprocessings:
                                call: http.post
                                args:
                                  url: '${var.ingestion_helper_url}'
                                  auth:
                                    type: OIDC
                                  body:
                                    actionType: "run_aggregation"
                                    importList: '$${json.decode(input.importList)}'
                                result: postprocessing_result
%{ endif }
%{ if var.enable_embedding_ingestion }
                      - embeddings:
                          steps:
                            - run_embeddings:
                                call: http.post
                                args:
                                  url: '${var.ingestion_helper_url}'
                                  auth:
                                    type: OIDC
                                  body:
                                    actionType: "embedding_ingestion"
                                    importList: '$${json.decode(input.importList)}'
                                result: embedding_result
%{ endif }
%{ endif }
              - promote_version:
                  call: http.post
                  args:
                    url: '${var.ingestion_helper_url}'
                    auth:
                      type: OIDC
                    body:
                      actionType: "update_import_version"
                      importName: '$${input.importName}'
                      version: '$${version}'
                      comment: '$${"Auto-promoted by workflow " + workflow_id}'
                  result: promote_result
              - update_ingestion_history_step:
                  call: http.post
                  args:
                    url: '${var.ingestion_helper_url}'
                    auth:
                      type: OIDC
                    body:
                      actionType: "update_ingestion_status"
                      workflowId: '$${workflow_id}'
                      jobId: '$${job_id}'
                      status: 'SUCCESS'
                      importList:
                        - importName: '$${input.importName}'
                          latestVersion: '$${version}'
                  result: history_result
          except:
            as: e
            steps:
              - capture_error:
                  assign:
                    - execution_error: '$${e}'
      - release_lock_step:
          call: http.post
          args:
            url: '${var.ingestion_helper_url}'
            auth:
              type: OIDC
            body:
              actionType: "release_ingestion_lock"
              workflowId: '$${workflow_id}'
          result: release_lock_result
      - fail_workflow:
          switch:
            - condition: '$${execution_error != null}'
              raise: '$${execution_error}'
%{if var.enable_datacommons_services}
      - restart_service:
          call: googleapis.run.v2.projects.locations.services.patch
          args:
            name: "projects/${var.project_id}/locations/${var.region}/services/${local.name_prefix}dc-datacommons-service"
            updateMask: "template.labels"
            body:
              template:
                labels:
                  restarted-at: '$${string(int(sys.now()))}'
%{if var.enable_redis_cache_clearing}
      - clear_cache_step:
          call: http.post
          args:
            url: '${var.ingestion_helper_url}'
            auth:
              type: OIDC
            body:
              actionType: "clear_redis_cache"
          result: clear_cache_result
%{endif}
%{endif}
      - return_result:
          return: '$${launch_result}'
  EOF2
}

resource "google_service_account_iam_member" "workflow_act_as_dataflow_sa" {
  count              = var.deploy ? 1 : 0
  service_account_id = "projects/${var.project_id}/serviceAccounts/${var.dataflow_service_account_email}"
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.workflow_sa[0].email}"
}

resource "google_cloud_run_v2_service_iam_member" "helper_invoker" {
  count    = var.deploy && var.ingestion_helper_service_name != "" ? 1 : 0
  location = var.region
  name     = var.ingestion_helper_service_name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.workflow_sa[0].email}"
}

resource "google_project_iam_member" "workflow_run_viewer" {
  count   = var.deploy ? 1 : 0
  project = var.project_id
  role    = "roles/run.viewer"
  member  = "serviceAccount:${google_service_account.workflow_sa[0].email}"
}
