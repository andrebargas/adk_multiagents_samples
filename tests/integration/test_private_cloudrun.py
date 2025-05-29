import google.auth
from google.cloud import compute_v1
import subprocess
import time
import os
import logging

# --- Configuration ---
PROJECT_ID = "andrebargas-sandbox"
REGION = "us-central1"
ZONE = f"{REGION}-a"

VPC_NAME = "test-automation-vpc"
SUBNET_NAME = "test-automation-subnet"
SUBNET_CIDR = "10.20.0.0/24"
FIREWALL_RULE_NAME = "allow-ssh-iap-for-test-vm" # Allows SSH via IAP
VM_NAME = "cloudrun-test-vm"
VM_MACHINE_TYPE = "e2-small"
VM_IMAGE_PROJECT = "debian-cloud"
VM_IMAGE_FAMILY = "debian-11"
VM_TAG = "allow-ssh-iap" # Tag for the firewall rule

# TODO: Path to your existing bash script that deploys Cloud Run.
# This script MUST output the Cloud Run service NAME to stdout.
DEPLOY_SCRIPT_LOCAL_PATH = "./deploy_cloud_run.sh"

# If None, the default Compute Engine service account is used.
# Ensure this SA has permissions:
# - To run your deploy_cloud_run.sh (e.g., Cloud Run Admin, IAM SA User)
# - roles/iam.serviceAccountTokenCreator (on itself)
# - roles/run.invoker (on the deployed Cloud Run service)
VM_SERVICE_ACCOUNT_EMAIL = None # Example: "your-vm-sa@your-project-id.iam.gserviceaccount.com"

# --- Initialize Logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def wait_for_gcp_operation(operation, project_id, region=None, zone=None, timeout_seconds=300):
    """Waits for a GCP operation to complete."""
    op_client = None
    if zone:
        op_client = compute_v1.ZoneOperationsClient()
        request = compute_v1.WaitZoneOperationRequest(project=project_id, zone=zone, operation=operation.name)
    elif region:
        op_client = compute_v1.RegionOperationsClient()
        request = compute_v1.WaitRegionOperationRequest(project=project_id, region=region, operation=operation.name)
    else: # Global operation (e.g., Network, Firewall creation)
        op_client = compute_v1.GlobalOperationsClient()
        request = compute_v1.WaitGlobalOperationRequest(project=project_id, operation=operation.name)

    try:
        logging.info(f"Waiting for operation '{operation.name}' (type: {'zone' if zone else 'region' if region else 'global'}) to complete...")
        op_done = op_client.wait(request=request, timeout=timeout_seconds)
        if op_done.error:
            logging.error(f"Operation {operation.name} failed: {op_done.error.errors}")
            raise Exception(f"Operation {operation.name} failed: {op_done.error.errors}")
        logging.info(f"Operation '{operation.name}' completed successfully.")
        return op_done
    except Exception as e:
        logging.error(f"Error waiting for operation {operation.name}: {e}")
        raise


def create_vpc_and_subnet(project_id, region, vpc_name, subnet_name, subnet_cidr):
    """Creates a VPC network and a subnet."""
    networks_client = compute_v1.NetworksClient()
    subnetworks_client = compute_v1.SubnetworksClient()

    logging.info(f"Creating VPC network '{vpc_name}'...")
    network_body = compute_v1.Network(
        name=vpc_name,
        auto_create_subnetworks=False,
        mtu=1460
    )
    operation = networks_client.insert(project=project_id, network_resource=network_body)
    wait_for_gcp_operation(operation, project_id)
    vpc_self_link = networks_client.get(project=project_id, network=vpc_name).self_link
    logging.info(f"VPC '{vpc_name}' created: {vpc_self_link}")

    logging.info(f"Creating subnet '{subnet_name}' in '{vpc_name}' with CIDR '{subnet_cidr}'...")
    subnet_body = compute_v1.Subnetwork(
        name=subnet_name,
        ip_cidr_range=subnet_cidr,
        network=vpc_self_link,
        region=region,
        private_ip_google_access=True, # Crucial for internal run.app DNS and Google APIs
    )
    operation = subnetworks_client.insert(project=project_id, region=region, subnetwork_resource=subnet_body)
    wait_for_gcp_operation(operation, project_id, region=region)
    subnet_self_link = subnetworks_client.get(project=project_id, region=region, subnetwork=subnet_name).self_link
    logging.info(f"Subnet '{subnet_name}' created: {subnet_self_link}")
    return vpc_self_link, subnet_self_link

def create_firewall_rule_iap_ssh(project_id, vpc_name, firewall_name, target_tag):
    """Creates a firewall rule to allow SSH via IAP to VMs with a specific tag."""
    firewalls_client = compute_v1.FirewallsClient()
    logging.info(f"Creating firewall rule '{firewall_name}' for IAP SSH...")
    firewall_body = compute_v1.Firewall(
        name=firewall_name,
        network=f"projects/{project_id}/global/networks/{vpc_name}",
        allowed=[compute_v1.Allowed(ip_protocol="tcp", ports=["22"])],
        source_ranges=["35.235.240.0/20"],  # Google's IAP IP range for TCP forwarding
        direction="INGRESS",
        target_tags=[target_tag],
    )
    operation = firewalls_client.insert(project=project_id, firewall_resource=firewall_body)
    wait_for_gcp_operation(operation, project_id)
    logging.info(f"Firewall rule '{firewall_name}' created.")

def create_vm_instance(project_id, zone, vm_name, machine_type, image_project, image_family,
                       subnet_self_link, vm_tag, service_account_email=None):
    """Creates a Compute Engine VM instance."""
    instances_client = compute_v1.InstancesClient()
    logging.info(f"Creating VM instance '{vm_name}' in zone '{zone}'...")
    instance_body = compute_v1.Instance(
        name=vm_name,
        machine_type=f"zones/{zone}/machineTypes/{machine_type}",
        disks=[
            compute_v1.AttachedDisk(
                boot=True,
                auto_delete=True,
                initialize_params=compute_v1.InitializeParams(
                    source_image=f"projects/{image_project}/global/images/family/{image_family}",
                    disk_size_gb=10,
                ),
            )
        ],
        network_interfaces=[
            compute_v1.NetworkInterface(
                subnetwork=subnet_self_link,
                # No access_configs for an internal-only VM. IAP handles external connectivity for SSH.
            )
        ],
        tags=compute_v1.Tags(items=[vm_tag]),
    )
    if service_account_email:
        instance_body.service_accounts = [
            compute_v1.ServiceAccount(
                email=service_account_email,
                scopes=["https://www.googleapis.com/auth/cloud-platform"] # Broad scope; refine if needed
            )
        ]
    else: # Use default GCE service account
         instance_body.service_accounts = [
            compute_v1.ServiceAccount(
                email="default", # Indicates the default GCE SA for the project
                scopes=["https://www.googleapis.com/auth/cloud-platform"]
            )
        ]

    operation = instances_client.insert(project=project_id, zone=zone, instance_resource=instance_body)
    wait_for_gcp_operation(operation, project_id, zone=zone)
    logging.info(f"VM instance '{vm_name}' created.")
    logging.info("Waiting 60 seconds for VM to fully initialize and SSH to be ready...")
    time.sleep(60) # Allow time for VM to boot and sshd to start reliably

def run_gcloud_command(command_args, check=True, capture_output=True, text=True, shell=False):
    """Helper to run gcloud commands."""
    logging.info(f"Running gcloud command: {' '.join(command_args)}")
    try:
        result = subprocess.run(command_args, check=check, capture_output=capture_output, text=text, shell=shell)
        if capture_output:
            logging.debug(f"gcloud stdout: {result.stdout}")
            if result.stderr:
                logging.debug(f"gcloud stderr: {result.stderr}")
        return result
    except subprocess.CalledProcessError as e:
        logging.error(f"gcloud command failed: {e}")
        if capture_output:
            logging.error(f"stdout: {e.stdout}")
            logging.error(f"stderr: {e.stderr}")
        raise

def execute_on_vm_via_ssh(project_id, zone, vm_name, command_string):
    """Executes a command string on the VM via gcloud compute ssh."""
    ssh_args = [
        "gcloud", "compute", "ssh", vm_name,
        f"--project={project_id}",
        f"--zone={zone}",
        "--command", command_string,
        "--quiet" # Reduce gcloud verbosity
    ]
    return run_gcloud_command(ssh_args)


def deploy_and_test_cloud_run_from_vm(project_id, zone, vm_name, local_script_path):
    """Copies deploy script to VM, executes it, and tests the Cloud Run service."""
    remote_script_path = f"/tmp/{os.path.basename(local_script_path)}"

    logging.info(f"Copying '{local_script_path}' to '{vm_name}:{remote_script_path}'...")
    scp_args = [
        "gcloud", "compute", "scp", local_script_path,
        f"{vm_name}:{remote_script_path}",
        f"--project={project_id}", f"--zone={zone}", "--quiet"
    ]
    run_gcloud_command(scp_args)
    logging.info("Script copied successfully.")

    # Commands to execute on the VM:
    # 1. Make script executable.
    # 2. Run script and capture Cloud Run service name.
    # 3. Wait for service to be ready.
    # 4. Curl the service using its internal .run.app URL with an identity token.
    vm_commands = f"""
set -e
echo "Making deployment script executable..."
chmod +x {remote_script_path}

echo "Executing deployment script: {remote_script_path}"
# This script MUST output ONLY the Cloud Run service name
CLOUD_RUN_SERVICE_NAME=$(bash {remote_script_path})
# Remove potential trailing newlines or carriage returns
CLOUD_RUN_SERVICE_NAME=$(echo $CLOUD_RUN_SERVICE_NAME | tr -d '\\n\\r')

if [ -z "$CLOUD_RUN_SERVICE_NAME" ]; then
    echo "ERROR: Deployment script did not output a Cloud Run service name."
    exit 1
fi
echo "Cloud Run service name reported by script: '$CLOUD_RUN_SERVICE_NAME'"

# Construct the internal URL. This usually resolves within the VPC.
# Example: http://my-service.run.app or regional: http://my-service-projecthash-region.a.run.app
# The simple <name>.run.app should work with Private Google Access enabled on subnet.
SERVICE_URL="http://${{CLOUD_RUN_SERVICE_NAME}}.run.app"

echo "Waiting 45 seconds for Cloud Run service ($CLOUD_RUN_SERVICE_NAME) to stabilize..."
sleep 45

echo "Attempting to test Cloud Run service at $SERVICE_URL"
# The VM's SA needs 'Service Account Token Creator' on itself and 'Cloud Run Invoker' on the service.
# The --audiences flag for print-identity-token should match the service URL for security.
if ID_TOKEN=$(gcloud auth print-identity-token --audiences=$SERVICE_URL); then
    echo "Successfully obtained identity token."
    if curl --fail --silent --show-error -H "Authorization: Bearer $ID_TOKEN" "$SERVICE_URL"; then
        echo "CLOUD_RUN_TEST_SUCCESS: Successfully invoked $SERVICE_URL"
        exit 0 # Explicit success
    else
        echo "CLOUD_RUN_TEST_FAILURE: curl command failed for $SERVICE_URL"
        exit 1 # Explicit failure
    fi
else
    echo "CLOUD_RUN_TEST_FAILURE: Failed to obtain identity token."
    exit 1 # Explicit failure
fi
"""
    logging.info(f"Executing deployment and test commands on VM '{vm_name}'...")
    logging.debug(f"VM command block:\n{vm_commands}")
    
    result = execute_on_vm_via_ssh(project_id, zone, vm_name, vm_commands)

    if "CLOUD_RUN_TEST_SUCCESS" in result.stdout:
        logging.info("Cloud Run service test SUCCEEDED from VM.")
        return True
    else:
        logging.error(f"Cloud Run service test FAILED from VM. Output:\n{result.stdout}\n{result.stderr}")
        return False

def cleanup_resources(project_id, region, zone, vm_name, firewall_name, subnet_name, vpc_name,
                      created_vm, created_firewall, created_subnet, created_vpc):
    """Deletes all created resources."""
    instances_client = compute_v1.InstancesClient()
    firewalls_client = compute_v1.FirewallsClient()
    subnetworks_client = compute_v1.SubnetworksClient()
    networks_client = compute_v1.NetworksClient()

    logging.info("--- Starting Cleanup ---")
    if created_vm:
        try:
            logging.info(f"Deleting VM instance '{vm_name}'...")
            operation = instances_client.delete(project=project_id, zone=zone, instance=vm_name)
            wait_for_gcp_operation(operation, project_id, zone=zone, timeout_seconds=600) # Longer timeout for VM deletion
            logging.info(f"VM '{vm_name}' deleted.")
        except Exception as e:
            logging.warning(f"Could not delete VM '{vm_name}': {e}")

    if created_firewall:
        try:
            logging.info(f"Deleting firewall rule '{firewall_name}'...")
            operation = firewalls_client.delete(project=project_id, firewall=firewall_name)
            wait_for_gcp_operation(operation, project_id)
            logging.info(f"Firewall rule '{firewall_name}' deleted.")
        except Exception as e:
            logging.warning(f"Could not delete firewall rule '{firewall_name}': {e}")
    
    if created_subnet: # Must be deleted before the VPC if not auto-deleted with VPC.
        try:
            logging.info(f"Deleting subnet '{subnet_name}'...")
            operation = subnetworks_client.delete(project=project_id, region=region, subnetwork=subnet_name)
            wait_for_gcp_operation(operation, project_id, region=region)
            logging.info(f"Subnet '{subnet_name}' deleted.")
        except Exception as e:
            logging.warning(f"Could not delete subnet '{subnet_name}': {e}")

    if created_vpc:
        try:
            logging.info(f"Deleting VPC network '{vpc_name}'...")
            # Ensure all dependent resources (like subnets, if not deleted explicitly) are gone.
            # For custom mode VPCs, subnets must be deleted first.
            operation = networks_client.delete(project=project_id, network=vpc_name)
            wait_for_gcp_operation(operation, project_id)
            logging.info(f"VPC network '{vpc_name}' deleted.")
        except Exception as e:
            logging.warning(f"Could not delete VPC '{vpc_name}': {e}")
    logging.info("--- Cleanup Complete ---")


def main():
    if PROJECT_ID == "your-gcp-project-id":
        logging.error("FATAL: PROJECT_ID is not set. Please update the script.")
        return

    if not os.path.exists(DEPLOY_SCRIPT_LOCAL_PATH):
        logging.warning(f"Deployment script '{DEPLOY_SCRIPT_LOCAL_PATH}' not found!")
        logging.warning("Attempting to create a DUMMY deploy_cloud_run.sh for demonstration.")
        logging.warning("REPLACE THIS DUMMY SCRIPT with your actual deployment logic.")
        try:
            with open(DEPLOY_SCRIPT_LOCAL_PATH, "w") as f:
                f.write("#!/bin/bash\n")
                f.write("# DUMMY SCRIPT: Replace with your actual Cloud Run deployment\n")
                f.write("set -e\n")
                f.write("SERVICE_NAME=\"my-dummy-$(date +%s)\" # Unique name\n")
                f.write("echo \"Simulating Cloud Run deployment for $SERVICE_NAME... (NO actual deployment)\" >&2\n")
                f.write("sleep 5\n")
                f.write("echo \"Deployment simulated.\" >&2\n")
                f.write("echo $SERVICE_NAME # CRITICAL: Output service name\n")
            os.chmod(DEPLOY_SCRIPT_LOCAL_PATH, 0o755)
            logging.info(f"Dummy '{DEPLOY_SCRIPT_LOCAL_PATH}' created. It will NOT deploy a real service.")
        except Exception as e:
            logging.error(f"Could not create dummy script: {e}")
            return

    created_tracking = {
        "vpc": False, "subnet": False, "firewall": False, "vm": False
    }
    subnet_self_link_val = None # To pass to VM creation

    try:
        logging.info("Starting VPC, VM, and Cloud Run Test Automation...")

        _, subnet_self_link_val = create_vpc_and_subnet(PROJECT_ID, REGION, VPC_NAME, SUBNET_NAME, SUBNET_CIDR)
        created_tracking["vpc"] = True
        created_tracking["subnet"] = True

        create_firewall_rule_iap_ssh(PROJECT_ID, VPC_NAME, FIREWALL_RULE_NAME, VM_TAG)
        created_tracking["firewall"] = True

        create_vm_instance(PROJECT_ID, ZONE, VM_NAME, VM_MACHINE_TYPE, VM_IMAGE_PROJECT,
                           VM_IMAGE_FAMILY, subnet_self_link_val, VM_TAG, VM_SERVICE_ACCOUNT_EMAIL)
        created_tracking["vm"] = True

        test_result = deploy_and_test_cloud_run_from_vm(PROJECT_ID, ZONE, VM_NAME, DEPLOY_SCRIPT_LOCAL_PATH)

        if test_result:
            logging.info(">>>> ✅✅✅ End-to-end Cloud Run test PASSED! ✅✅✅ <<<<")
        else:
            logging.error(">>>> ❌❌❌ End-to-end Cloud Run test FAILED. ❌❌❌ <<<<")

    except Exception as e:
        logging.error(f"An error occurred during the automation process: {e}")
        import traceback
        logging.error(traceback.format_exc())
    finally:
        cleanup_resources(PROJECT_ID, REGION, ZONE, VM_NAME, FIREWALL_RULE_NAME, SUBNET_NAME, VPC_NAME,
                          created_tracking["vm"], created_tracking["firewall"],
                          created_tracking["subnet"], created_tracking["vpc"])

if __name__ == "__main__":
    # Ensure gcloud is authenticated if running locally, or SA has perms if on GCP.
    main()