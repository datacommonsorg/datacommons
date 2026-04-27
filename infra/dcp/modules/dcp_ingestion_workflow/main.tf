locals {
  name_prefix = var.namespace != "" ? "${var.namespace}-" : ""
}

resource "google_workflows_workflow" "ingestion_orchestrator" {
  count               = var.deploy ? 1 : 0
  name                = "${local.name_prefix}ingestion-orchestrator"
  region              = var.region
  description         = "Triggers the Dataflow Flex Template Graph Ingestion Pipeline with runtime parameters"
  service_account     = var.ingestion_runner_id
  deletion_protection = var.deletion_protection

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
            - lock_timeout: ${var.ingestion_lock_timeout}
            - launch_params:
                projectId: '$${project_id}'
                spannerInstanceId: '$${input.spannerInstanceId}'
                spannerDatabaseId: '$${input.spannerDatabaseId}'
                importList: '$${input.importList}'
                tempLocation: '$${input.tempLocation}'
      - acquire_lock:
          try:
            call: http.post
            args:
              url: '${var.ingestion_helper_uri}'
              auth:
                type: OIDC
              body:
                actionType: "acquire_ingestion_lock"
                workflowId: '$${workflow_id}'
                timeout: '$${lock_timeout}'
            result: lock_result
          retry:
            predicate: '$${http.default_retry_predicate}'
            max_retries: 20
            backoff:
              initial_delay: 300
              max_delay: 600
              multiplier: 2
      - process_ingestion:
          try:
            steps:
              - set_import_staging:
                  call: http.post
                  args:
                    url: '${var.ingestion_helper_uri}'
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
                        jobName: '$${"ingestion-job-" + string(int(sys.now()))}'
                        containerSpecGcsPath: 'gs://datcom-templates/templates/flex/ingestion.json'
                        parameters: '$${launch_params}'
                        environment:
                          serviceAccountEmail: '${var.ingestion_runner_email}'
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
                      next: promote_version
              - fail_on_job_status:
                  raise: '$${ "Dataflow job failed with state: " + job_status.currentState }'
              - promote_version:
                  call: http.post
                  args:
                    url: '${var.ingestion_helper_uri}'
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
                    url: '${var.ingestion_helper_uri}'
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
            url: '${var.ingestion_helper_uri}'
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
      - return_result:
          return: '$${launch_result}'
  EOF2
}
