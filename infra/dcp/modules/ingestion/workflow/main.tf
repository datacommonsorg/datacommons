locals {
  name_prefix               = var.namespace != "" ? "${var.namespace}-" : ""
  should_run_postprocessing = var.enable_bigquery_postprocessing || var.enable_embeddings_generation
  clean_namespace_prefix    = var.namespace != "" ? "${replace(lower(var.namespace), "_", "-")}-" : ""
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
            - execution_error: null
            - current_stage: "dataflow"
            - job_id: null
            - lock_timeout: ${var.lock_acquisition_timeout}
            - run_embeddings: ${var.enable_embeddings_generation}
            - run_postproc: ${var.enable_bigquery_postprocessing}
            - postprocessing_result: null
            - embedding_result: null
            - decoded_imports: '$${json.decode(input.importList)}'
            - num_imports: '$${len(decoded_imports)}'
            - combined_import_name: ""
            - imports_status_list: []
            - imports_history_list: []
            - imports_version_list: []
            - launch_params:
                projectId: '$${project_id}'
                spannerInstanceId: '$${input.spannerInstanceId}'
                spannerDatabaseId: '$${input.spannerDatabaseId}'
                importList: '$${input.importList}'
                tempLocation: '$${input.tempLocation}'
                stagingLocation: '$${input.tempLocation}'
                forceCombineNodes: 'true'
                isBaseDc: 'false'
      - build_lists:
          for:
            value: imp
            in: $${decoded_imports}
            steps:
              - append_lists:
                  assign:
                    - item_gcs_path: '$${"gs://" + bucket_name + "/${var.ingestion_artifacts_path}/" + imp.importName + "/" + version}'
                    - status_item: {}
                    - status_item.importName: '$${imp.importName}'
                    - status_item.latestVersion: '$${item_gcs_path}'
                    - status_item.graphPath: '$${imp.graphPath}'
                    - status_item.status: "STAGING"
                    - history_item: {}
                    - history_item.importName: '$${imp.importName}'
                    - history_item.latestVersion: '$${version}'
                    - imports_status_list: '$${list.concat(imports_status_list, status_item)}'
                    - imports_history_list: '$${list.concat(imports_history_list, history_item)}'
                    - imports_version_list: '$${list.concat(imports_version_list, imp.importName)}'
                    - clean_item: '$${text.replace_all(text.replace_all(text.to_lower(imp.importName), "/", "-"), "_", "-")}'
                    - join_prefix: '$${if(combined_import_name == "", "", "-")}'
                    - combined_import_name: '$${combined_import_name + join_prefix + clean_item}'
      - set_dataflow_job_name:
          assign:
            - import_name_len: '$${len(combined_import_name)}'
            - substring_end: '$${if(import_name_len < 35, import_name_len, 35)}'
            - sanitized_short_import: '$${text.substring(combined_import_name, 0, substring_end)}'
            - dataflow_job_name: '$${"${local.clean_namespace_prefix}" + sanitized_short_import + "-" + string(int(sys.now()))}'
      - acquire_lock:
          try:
            call: http.post
            args:
              url: '${var.ingestion_helper_url}/database/lock/acquire'
              auth:
                type: OIDC
              body:
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
      - update_history_pending:
          call: update_history
          args:
            workflow_id: '$${workflow_id}'
            status: 'PENDING'
            stage: 'dataflow'
            job_id: null
            import_list: '$${imports_history_list}'
      - process_ingestion:
          try:
            steps:
              - set_import_staging:
                  call: http.post
                  args:
                    url: '${var.ingestion_helper_url}/imports/status'
                    auth:
                      type: OIDC
                    body:
                      imports: '$${imports_status_list}'
                      status: "STAGING"
                  result: staging_result
              - run_flex_template:
                  call: googleapis.dataflow.v1b3.projects.locations.flexTemplates.launch
                  args:
                    projectId: '$${project_id}'
                    location: '$${input.region}'
                    body:
                      launchParameter:
                        jobName: '$${dataflow_job_name}'
                        containerSpecGcsPath: '${var.dataflow_template_gcs_path}'
                        parameters: '$${launch_params}'
                        environment:
                          serviceAccountEmail: '${var.dataflow_service_account_email}'
                          tempLocation: '$${input.tempLocation}'
                          stagingLocation: '$${input.tempLocation}'
%{if var.dataflow_ip_configuration != "WORKER_IP_UNSPECIFIED"}
                          ipConfiguration: '${var.dataflow_ip_configuration}'
%{endif}
%{if var.dataflow_subnetwork != ""}
                          subnetwork: '${var.dataflow_subnetwork}'
%{endif}
                  result: launch_result
              - get_job_id:
                  assign:
                    - job_id: '$${launch_result.job.id}'
              - update_history_running:
                  call: update_history
                  args:
                    workflow_id: '$${workflow_id}'
                    status: 'RUNNING'
                    stage: 'dataflow'
                    job_id: '$${job_id}'
                    import_list: null
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
                      next: update_history_dataflow_success
              - update_history_dataflow_success:
                  call: update_history
                  args:
                    workflow_id: '$${workflow_id}'
                    status: 'SUCCESS'
                    stage: 'dataflow'
                    job_id: '$${job_id}'
                    import_list: '$${imports_history_list}'
                  next: %{if local.should_run_postprocessing}ingestion_postprocessing%{else}promote_version%{endif}
              - fail_on_job_status:
                  raise: '$${ "Dataflow job failed with state: " + job_status.currentState }'
              - ingestion_postprocessing:
                  steps:
                    - set_stage_postproc:
                        assign:
                          - current_stage: "postprocessing"
                    - update_history_postproc_running:
                        call: update_history
                        args:
                          workflow_id: '$${workflow_id}'
                          status: 'RUNNING'
                          stage: 'postprocessing'
                          job_id: null
                          import_list: null
                    - run_postprocessing_parallel:
                        parallel:
                          shared: [postprocessing_result, embedding_result]
                          branches:
                            - postprocessing_branch:
                                steps:
                                  - check_postproc_flag:
                                      switch:
                                        - condition: '$${not run_postproc}'
                                          next: end_postproc_branch
                                  - run_postprocessings:
                                      call: http.post
                                      args:
                                        url: '${var.ingestion_helper_url}/aggregation/run'
                                        auth:
                                          type: OIDC
                                        body:
                                          importList: '$${json.decode(input.importList)}'
                                      result: postprocessing_result
                                  - end_postproc_branch:
                                      assign:
                                        - dummy: true
                            
                            - embeddings_branch:
                                steps:
                                  - check_embeddings_flag:
                                      switch:
                                        - condition: '$${not run_embeddings}'
                                          next: end_embeddings_branch
                                  - run_embeddings:
                                      call: http.post
                                      args:
                                        url: '${var.ingestion_helper_url}/embeddings/ingest'
                                        auth:
                                          type: OIDC
                                        body:
                                          enableEmbeddings: true
                                        timeout: ${var.embeddings_timeout}
                                      result: embedding_result
                                  - end_embeddings_branch:
                                      assign:
                                        - dummy: true
              - promote_version:
                  call: http.post
                  args:
                    url: '${var.ingestion_helper_url}/imports/version'
                    auth:
                      type: OIDC
                    body:
                      imports: '$${imports_version_list}'
                      version: '$${version}'
                      comment: '$${"Auto-promoted by workflow " + workflow_id}'
                  result: promote_result
              - update_ingestion_history_step:
                  call: http.post
                  args:
                    url: '${var.ingestion_helper_url}/imports/ingestion-status'
                    auth:
                      type: OIDC
                    body:
                      workflowId: '$${workflow_id}'
                      jobId: '$${job_id}'
                      status: 'SUCCESS'
                      importList: '$${imports_history_list}'
                  result: history_result
              - update_history_postproc_success:
                  call: update_history
                  args:
                    workflow_id: '$${workflow_id}'
                    status: 'SUCCESS'
                    stage: null
                    job_id: null
                    import_list: null
          except:
            as: e
            steps:
              - update_history_failure:
                  call: update_history
                  args:
                    workflow_id: '$${workflow_id}'
                    status: 'FAILURE'
                    stage: '$${current_stage}'
                    job_id: '$${job_id}'
                    import_list: '$${imports_history_list}'
              - update_ingestion_status_failure:
                  call: http.post
                  args:
                    url: '${var.ingestion_helper_url}/imports/ingestion-status'
                    auth:
                      type: OIDC
                    body:
                      workflowId: '$${workflow_id}'
                      jobId: '$${if(job_id != null, job_id, "N/A")}'
                      status: 'RETRY'
                      importList: '$${imports_history_list}'
                  result: history_result
              - capture_error:
                  assign:
                    - execution_error: '$${e}'
      - release_lock_step:
          call: http.post
          args:
            url: '${var.ingestion_helper_url}/database/lock/release'
            auth:
              type: OIDC
            body:
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
            url: '${var.ingestion_helper_url}/cache/clear'
            auth:
              type: OIDC
          result: clear_cache_result
%{endif}
%{endif}
      - return_result:
          return: '$${launch_result}'

  update_history:
    params: [workflow_id, status, stage, job_id, import_list]
    steps:
      - call_helper:
          call: http.post
          args:
            url: '${var.ingestion_helper_url}/imports/ingestion-history'
            auth:
              type: OIDC
            body:
              workflowId: $${workflow_id}
              status: $${status}
              stage: $${stage}
              jobId: $${job_id}
              importList: $${import_list}
          result: res
      - return_result:
          return: $${res}
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
