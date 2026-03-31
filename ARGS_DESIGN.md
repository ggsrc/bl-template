# args.yaml Design Document

## Overview

`args.yaml` is used to describe all configurable parameters in the template repository, enabling blcli to self-describe all required parameters, making it convenient for users to know which parameters they can fill in.

## args.yaml Discovery Mechanism

### 1. Convention First (Automatic Inference)

The CLI automatically infers the location of `args.yaml` based on the `path` field in `config.yaml`:

- **If `path` is a directory**: Look for `{path}/args.yaml`
  - Example: `path: terraform/modules/gke` → Look for `terraform/modules/gke/args.yaml`
  
- **If `path` is a file**: Look for `{dirname(path)}/args.yaml`
  - Example: `path: terraform/init/projects.tf.tmpl` → Look for `terraform/init/args.yaml`

### 2. Explicit Specification (Optional Override)

In `config.yaml`, you can add an optional `args` field to components to explicitly specify the path of `args.yaml`:

```yaml
init:
  - name: projects
    path: terraform/init/projects.tf.tmpl
    args: terraform/init/args.yaml  # Explicit specification (optional)
    install: terraform apply -var-file=terraform/basic/projects.tf.tmpl
    upgrade: terraform apply -var-file=terraform/basic/projects.tf.tmpl

modules:
  - gke:
    name: gke
    path: terraform/modules/gke
    args: terraform/modules/gke/args.yaml  # Explicit specification (optional, if not specified, automatically inferred as terraform/modules/gke/args.yaml)
```

### 3. Hierarchical Lookup (Parameter Inheritance)

The CLI supports upward lookup of parent directory's `args.yaml` for shared parameters:

1. First, look for the component's own `args.yaml` (based on path or explicitly specified args)
2. If it doesn't exist, look up the parent directory's `args.yaml`
3. Continue looking up until the root directory or until found

Example:
- `terraform/modules/gke/args.yaml` doesn't exist
- Look for `terraform/modules/args.yaml`
- If it still doesn't exist, look for `terraform/args.yaml`
- If it still doesn't exist, look for root directory's `args.yaml`

## args.yaml Structure

### Basic Structure

```yaml
version: 1.0.0

# Parameter definitions (grouped by scope)
parameters:
  # Global parameters (apply to all templates in the directory)
  global:
    OrganizationID:
      type: string
      description: "GCP Organization ID. Use \"0\" to disable org_id in Terraform init output (variable and resource lines omitted)."
      required: false
      default: "0"
      example: "123456789012"
    
    BillingAccountID:
      type: string
      description: "GCP Billing Account ID"
      required: true
      example: "01ABCD-2EFGH3-4IJKL5"
  
  # Component-level parameters (correspond to component names in config.yaml)
  components:
    projects:  # Corresponds to init.projects; use ${project.<name>.id} placeholders in default.yaml, resolved at init-args
      ProjectServices:
        type: map[list[string]]
        description: "Map of project IDs to enabled GCP services. Keys use ${project.<name>.id} placeholders in default, resolved to actual IDs."
        required: false
        default: {}
    
    gke:  # Corresponds to modules.gke
      project_id:
        type: string
        description: "GCP Project ID"
        required: true
      
      cluster_name:
        type: string
        description: "Name of the GKE cluster"
        required: true
        pattern: "^[a-z0-9-]+$"  # Regex validation
      
      region:
        type: string
        description: "GCP Region"
        default: "us-west1"
        enum: ["us-west1", "us-east1", "asia-east1"]  # Optional values
      
      machine_type:
        type: string
        description: "Primary node pool machine type"
        default: "e2-medium"
      
      min_node_count:
        type: number
        description: "Minimum number of nodes"
        default: 1
        min: 1
        max: 100
```

### Parameter Field Descriptions

- `type`: Parameter type (string, number, bool, list, map, object)
- `description`: Parameter description
- `required`: Whether required (true/false)
- `default`: Default value
- `example`: Example value
- `enum`: List of optional values (for enumeration)
- `pattern`: Regex validation (for strings) — also supported via `validation`
- `min`/`max`: Value range (for numbers) — also supported via `validation` kind `numberRange` / `stringLength`
- `scope`: Scope (global, component, template)

### Parameter Validation

Parameters can define **validation** rules that blcli enforces during `blcli init` (before writing any files). Each rule is a map with a required `kind` and kind-specific params:

| kind | params | description |
|------|--------|-------------|
| `required` | `message` (optional) | Value must be non-empty |
| `stringLength` | `min`, `max`, `message` | String length constraints |
| `pattern` | `value` or `pattern`, `message` | Regex match |
| `format` | `value` (e.g. `email`, `numeric`), `message` | Format check |
| `enum` | `values` (list), `message` | Value must be in list |
| `numberRange` | `min`, `max`, `message` | Numeric range |

Example:

```yaml
ProjectName:
  type: string
  required: true
  validation:
    - kind: required
    - kind: stringLength
      min: 6
      max: 30
      message: "GCP project ID: 6-30 characters"
    - kind: pattern
      value: "^[a-z][a-z0-9-]{4,28}[a-z0-9]$"
```

If `validation` is present, legacy top-level `required` and `pattern` are ignored; otherwise they are converted to rules for backward compatibility.

### Top-level validation.unique

To ensure uniqueness across a collection (e.g. project names), add a top-level `validation.unique` section:

```yaml
validation:
  unique:
    - path: "terraform.projects[].name"
      message: "Project names must be unique"
```

The `path` uses dot notation with `[]` for array segments (e.g. `terraform.projects[].global.ProjectName`).

## Directory Structure Recommendations

```
terraform/
  args.yaml              # Global parameters for terraform directory
  init/
    args.yaml            # Parameters for init (optional, can inherit from parent)
  modules/
    args.yaml            # Common parameters for modules
    gke/
      args.yaml          # GKE module specific parameters
    vm-server/
      args.yaml          # vm-server module specific parameters
  project/
    args.yaml            # Parameters for project
```

## CLI Usage Examples

### 1. List All Parameters

```bash
blcli args list
# Or specify directory
blcli args list --dir terraform
```

### 2. Show Parameters for a Specific Component

```bash
blcli args show gke
# Or
blcli args show init.projects
```

### 3. Validate Parameters

```bash
blcli args validate --file values.yaml
```

### 4. Generate Parameter Template

```bash
blcli args generate-template --output values-template.yaml
```

## Implementation Recommendations

When implementing the CLI, it should:

1. **Parse config.yaml**: Read all component definitions
2. **Find args.yaml**:
   - Prefer explicitly specified `args` field
   - Otherwise, automatically infer based on `path`
   - Support hierarchical lookup
3. **Merge parameters**: Merge global parameters and component parameters
4. **Validate parameters**: Validate user input according to type, pattern, enum, and other rules
