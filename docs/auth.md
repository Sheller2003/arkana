# Final Documentation: Auth, Groups, Payment Plans, Usage, Credentials, and Database Functions

## 1. Scope

This document describes the current and target data model for:

- user groups and memberships
- users and roles
- authorization objects
- payment plans
- runtime and token usage limits
- company assignments
- credentials
- implemented PostgreSQL / Supabase functions
- recommended additional functions

It includes both:
- the conceptual model you specified
- the already implemented database functions
- the migration-based extensions introduced for Supabase

---

## 2. Core Domain Overview

The system is centered around these concepts:

- **User**
  - authenticated application user
  - belongs to a company
  - has a role
  - may have a direct payment plan
  - may receive direct authorizations

- **User Group**
  - collection of users
  - used to restrict access to objects or actions
  - ownership-based administration
  - may be object-specific

- **Authorization Object (`auth_obj`)**
  - permission entry for actions, services, or capability classes
  - can be assigned through:
    - user role
    - direct user auth
    - payment plan

- **Payment Plan**
  - commercial or contractual permission bundle
  - can define:
    - auth classes / permission classes
    - runtime usage limits by service
    - token usage limits by model

- **Company**
  - organizational unit
  - can have a company group
  - can have a company payment plan
  - can have paid services

- **Credentials**
  - encrypted secret storage for:
    - individual users
    - groups

---

## 3. Tables

## 3.1 `user_group`

Represents a logical group of users.

### Purpose
- assign a group to an object
- restrict access to only group members
- support public / private / object-bound groups
- track ownership

### Fields
- `group_id:int`
- `owner:uuid`
- `group_name:text`
- `obj_group:bool`
- `parent_group:int nullable`
- `object_key:text nullable`
- `created_at:timestamptz`
- `updated_at:timestamptz`

### Semantics
- only the **owner** can add or remove users from the group
- `obj_group = true` means the group is intended for a single object
- `parent_group` allows group hierarchies
- `object_key` can identify the object domain or object type

### Reserved groups
Requested convention:
- `group_id = 0` → public access for everyone
- `group_id = 1` → private only for the owner

### Important note
Because `owner` is a foreign key to `auth.users(id)`, these reserved groups cannot be seeded with `00000000-0000-0000-0000-000000000000` unless that user actually exists.

### Final solution
Reserved groups are created through:

- `ensure_special_groups(p_owner uuid)`

with a **real existing user UUID**.

---

## 3.2 `user_group_assignment`

Assignment table between users and groups.

### Purpose
- assign users to groups
- allow one user in multiple groups
- support optional group-specific role
- allow users to leave groups without destroying history

### Fields
- `group_id:int`
- `user_id:uuid`
- `group_role:text nullable`
- `joined_at:timestamptz`
- `left_at:timestamptz nullable`
- `created_at:timestamptz`
- `updated_at:timestamptz`

### Semantics
- active membership means `left_at is null`
- one user can belong to many groups
- one group can contain many users
- the same `(group_id, user_id)` is reused and reactivated instead of duplicated

---

## 3.3 `user_role`

Defines application-wide user roles.

### Purpose
Role-based base permission model.

### Fields
- `role_key:text primary key`
- `role_name:text`
- `role_description:text nullable`
- `role_level:int`
- `is_system:bool`
- `created_at:timestamptz`

### Default roles
- `root` → main admin, unrestricted administration
- `admin` → can manage workflows and data
- `editor` → can manage data
- `requester` → can request data

### Notes
- `root` should normally be reserved for a separate Arkana/internal user
- `role_level` can be used for internal priority / hierarchy checks

---

## 3.4 `profiles` (extended)

Existing profile table extended to reference role and payment plan.

### Added / relevant fields
- `user_id_auth:uuid`
- `company_id`
- `role_key:text nullable`
- `payment_plan:int nullable`

### Semantics
- `role_key` → FK to `user_role`
- `payment_plan` → FK to `payment_plan`
- direct user plan can override or complement company plan depending on business rules

---

## 3.5 `auth_obj`

Defines permission entries and authorization classes.

### Purpose
Controls access to actions, objects, services, or feature classes.

### Fields
- `auth_key:text primary key`
- `auth_value:int`
- `auth_class:text nullable`
- `is_auth_class:bool`
- `auth_description:text nullable`
- `created_at:timestamptz`
- `updated_at:timestamptz`

### Semantics
- `auth_key` identifies a permission or permission class
- `auth_value` is numeric and allows graded permissions
- `auth_class` points to another `auth_obj.auth_key`
- `is_auth_class = true` means the auth entry itself is a permission class
- if an auth object has an `auth_class`, the user must also have that class assigned, otherwise an auth exception should be raised

### Example
- `project.edit` may require auth class `project.access`
- user must have both:
  - effective access to `project.edit`
  - assignment to `project.access` as class

---

## 3.6 `user_auth`

Direct user-based authorization assignment.

### Fields
- `user_id:uuid`
- `auth_key:text`
- `auth_value:int`
- `created_at:timestamptz`
- `updated_at:timestamptz`

### Purpose
- direct permission overrides or special grants
- user-specific access beyond role or payment plan

---

## 3.7 `user_role_auth_assignment`

Maps roles to authorization objects.

### Fields
- `role_key:text`
- `auth_key:text`
- `created_at:timestamptz`

### Purpose
- role-based permission inheritance

---

## 3.8 `payment_plan`

Commercial / contractual access model.

### Fields
- `pplan_id:int`
- `pplan_name:text`
- `pplan_description:text nullable`
- `pplan_lv:int`
- `is_active:bool`
- `created_at:timestamptz`
- `updated_at:timestamptz`

### Purpose
- commercial packaging
- permission bundles
- usage limit bundles

---

## 3.9 `pplan_auth_assignment`

Maps payment plans to authorization objects.

### Fields
- `pplan_id:int`
- `auth_key:text`
- `created_at:timestamptz`

### Requirement
According to your rule:
- assigned `auth_key` should represent an auth class
- therefore it should generally reference entries where `is_auth_class = true`

### Purpose
- enable or unlock features by payment plan

---

## 3.10 `pplan_max_runtime_usage`

Runtime limit per payment plan and service.

### Fields
- `pplan_id:int`
- `service_key:text`
- `max_value:int`
- `infinit:bool`
- `period_key:text`
- `created_at:timestamptz`
- `updated_at:timestamptz`

### Purpose
Defines the maximum allowed runtime usage for a service.

### Semantics
- `service_key` identifies the service
- `max_value` is the numeric limit
- `infinit = true` means unlimited runtime
- `period_key` defines the interval:
  - `daily`
  - `weekly`
  - `monthly`
  - `lifetime`

---

## 3.11 `pplan_max_token_usage`

Token limit per payment plan and model.

### Fields
- `pplan_id:int`
- `model_key:text`
- `max_tokens:bigint`
- `infinit:bool`
- `period_key:text`
- `created_at:timestamptz`
- `updated_at:timestamptz`

### Purpose
Defines the maximum allowed token usage for a model.

### Semantics
- `model_key` identifies the model
- `max_tokens` is the quota
- `infinit = true` means unlimited token usage
- `period_key` defines the usage window

---

## 3.12 `company_main` (extended)

Existing company table extended with group and payment plan references.

### Relevant fields
- `company_id`
- `company_name`
- `company_description`
- `company_group:int nullable`
- `company_pplan:int nullable`
- `updated_at:timestamptz`

### Purpose
- attach a default company group
- attach a default payment plan

---

## 3.13 `pservice`

Service catalog for paid company services.

### Fields
- `pservice_id:int`
- `service_key:text`
- `service_name:text`
- `service_description:text nullable`
- `created_at:timestamptz`

---

## 3.14 `company_payed_service`

Assignment of payable / enabled service to a company.

### Fields
- `company_id`
- `pservice_id:int`
- `created_at:timestamptz`
- `created_by:uuid nullable`

### Rule
- can only be created / deleted by **root user**

---

## 3.15 `usage_runtime_log`

Runtime usage ledger.

### Fields
- `usage_id:bigint`
- `user_id:uuid nullable`
- `company_id:bigint nullable`
- `pplan_id:int nullable`
- `service_key:text`
- `runtime_value:int`
- `usage_ts:timestamptz`
- `usage_date:date`
- `source_ref:text nullable`

### Purpose
- stores actual runtime consumption
- basis for quota checks
- enables audit / billing / reporting

---

## 3.16 `usage_token_log`

Token usage ledger.

### Fields
- `usage_id:bigint`
- `user_id:uuid nullable`
- `company_id:bigint nullable`
- `pplan_id:int nullable`
- `model_key:text`
- `token_value:bigint`
- `usage_ts:timestamptz`
- `usage_date:date`
- `source_ref:text nullable`

### Purpose
- stores actual token consumption
- used for enforcement against payment plan limits

---

## 3.17 `object_group_assignment`

Optional object-to-group mapping table.

### Fields
- `object_group_id:bigint`
- `object_key:text`
- `object_id:text`
- `group_id:int`
- `created_at:timestamptz`
- `created_by:uuid nullable`

### Purpose
- explicitly bind one object to one access group
- useful for object-specific access control

---

## 3.18 `user_cred`

Encrypted credentials for users.

### Relevant fields
- `user_id:uuid`
- `service:text`
- `ext_user_name_enc:bytea nullable`
- `pw_enc:bytea`
- `created_at:timestamptz`
- `updated_at:timestamptz`

### Purpose
- store per-user credentials for external systems

---

## 3.19 `group_cred`

Encrypted credentials for groups.

### Relevant fields
- `group_id:int`
- `service:text`
- `ext_user_name_enc:bytea nullable`
- `pw_enc:bytea`
- `created_at:timestamptz`
- `updated_at:timestamptz`

### Purpose
- shared credentials at group level

---

## 4. Authorization Resolution Model

Effective authorization can come from three sources:

1. direct user auth via `user_auth`
2. role-based auth via `user_role_auth_assignment`
3. payment-plan auth via `pplan_auth_assignment`

### Effective auth rule
A user has effective access to `auth_key` if:
- the maximum applicable `auth_value` across all sources is at least the requested value
- and the required `auth_class` is also assigned

### Resolution order
The current implementation effectively computes:
- user-specific auth value
- role-based auth value
- plan-based auth value
- `greatest(...)`

This is flexible and allows user overrides without losing role / plan defaults.

---

## 5. Implemented Functions

This section includes the already implemented functions plus migration-added functions.

## 5.1 Credential encryption functions

### `public.amezit_cred_encrypt(plain text) returns bytea`
Encrypts plain text using:

- `pgp_sym_encrypt`
- key from `current_setting('amezit.cred_key', true)`

### `public.amezit_cred_decrypt(cipher bytea) returns text`
Decrypts encrypted value using:

- `pgp_sym_decrypt`
- key from `current_setting('amezit.cred_key', true)`

### Notes
- requires encryption key to be set in session / config
- intended for `user_cred` and `group_cred`

---

## 5.2 Group functions

### `public.create_group(...)`
There are two relevant versions:

#### Existing initial version
- `create_group(p_group_name text) returns bigint`

#### Extended version in migration
- `create_group(p_group_name text, p_obj_group bool default false, p_parent_group int default null, p_object_key text default null) returns bigint`

### Purpose
- create a group owned by `auth.uid()`
- insert owner as active member with `group_role = 'owner'`

---

### `public.assign_to_group(...)`
There are two relevant versions:

#### Existing initial version
- `assign_to_group(p_user_id uuid, p_group_id integer) returns void`

#### Extended version in migration
- `assign_to_group(p_user_id uuid, p_group_id integer, p_group_role text default null) returns void`

### Purpose
- only group owner can assign users
- inserts or reactivates membership

---

### `public.leave_group(p_group_id integer, p_user_id uuid default auth.uid()) returns void`
### Purpose
- marks active membership as left by setting `left_at`

---

### `public.remove_from_group(p_group_id integer, p_user_id uuid) returns void`
### Purpose
- owner-driven removal
- also implemented as logical leave via `left_at`

---

### `public.delete_group(p_group_id integer) returns void`
### Purpose
- deletes a group
- only group owner is allowed
- assignments are implicitly removed if FK cascade exists

---

### `public.check_user_is_in_group(p_group_id integer, p_user_id uuid) returns boolean`

#### Existing version
Checks whether user has an assignment.

#### Extended version
Checks only **active** membership:
- `left_at is null`

---

### `public.get_group_members(p_group_id integer)`

#### Existing version
- `returns setof uuid`

#### Extended version
- `returns table(user_id uuid, group_role text, joined_at timestamptz, left_at timestamptz)`

### Important migration note
Because the return type changed, PostgreSQL requires:
- `drop function if exists public.get_group_members(integer);`
- then recreate function

---

### `public.assign_object_group(p_object_key text, p_object_id text, p_group_id int) returns void`
### Purpose
- assign a group to an object entry in `object_group_assignment`

---

### `public.ensure_special_groups(p_owner uuid) returns void`
### Purpose
Creates or repairs reserved groups:
- `group_id = 0` → `public`
- `group_id = 1` → `private`

### Reason
Cannot safely auto-seed with zero UUID because of FK to `auth.users`.

---

## 5.3 Credential access functions

### `public.set_user_cred(p_service text, p_pwd text, p_ext_user_name text) returns void`
### Purpose
- upsert encrypted user credentials for current user

---

### `public.get_user_cred(p_service text) returns table(service text, ext_user_name text, pw text)`
### Purpose
- return decrypted credentials for current user

---

### `public.set_group_cred(p_service text, p_group_id integer, p_pwd text, p_ext_user_name text) returns void`

#### Existing version
Checks membership using:
- `public.tableuser_group`

This appears to be inconsistent / likely wrong.

#### Extended version
Checks membership correctly using:
- `public.user_group_assignment`
- active membership only

### Purpose
- upsert encrypted credentials for a group

---

### `public.get_group_cred(p_group_id integer, p_service text) returns table(group_id integer, service text, ext_user_name text, pw text)`

#### Existing version
Returned decrypted credentials without verifying current-user membership.

#### Extended version
Returns credentials only if current user is active member of the group.

### Purpose
- secure group-shared credential retrieval

---

## 5.4 User / auth helper functions

### `public.current_user_role() returns text`
Returns the current user role from `profiles.role_key`.

---

### `public.current_user_payment_plan() returns int`
Returns the current user's direct payment plan from `profiles.payment_plan`.

---

### `public.is_root_user(p_user_id uuid default auth.uid()) returns boolean`
Checks whether the given user has role `root`.

---

### `public.has_auth_class_assignment(p_user_id uuid, p_auth_class text) returns boolean`
Checks whether required auth class is assigned to the user via:
- direct user auth
- role auth
- plan auth

---

### `public.has_effective_auth(p_user_id uuid, p_auth_key text, p_required_value int default 1) returns boolean`
Resolves effective auth across:
- `user_auth`
- `user_role_auth_assignment`
- `pplan_auth_assignment`

Also validates required auth class assignment.

---

### `public.require_effective_auth(p_auth_key text, p_required_value int default 1, p_user_id uuid default auth.uid()) returns void`
Raises exception if effective authorization is missing.

---

### `public.require_root_user(p_user_id uuid default auth.uid()) returns void`
Raises exception unless current / given user is root.

---

## 5.5 Payment plan / usage functions

### `public.get_effective_user_payment_plan(p_user_id uuid default auth.uid())`
Returns:
- `user_id`
- `company_id`
- `pplan_id`

### Resolution
Uses:
- direct user payment plan from `profiles.payment_plan`
- fallback to company payment plan from `company_main.company_pplan`

---

### `public.get_runtime_usage_period_start(p_period_key text, p_ref_ts timestamptz default now()) returns date`
Resolves the start date of the period:
- daily
- weekly
- monthly
- lifetime

---

### `public.log_runtime_usage(p_service_key text, p_runtime_value int, p_source_ref text default null, p_user_id uuid default auth.uid()) returns void`
### Purpose
- enforce runtime usage limit
- insert runtime usage into ledger

### Steps
- determine effective payment plan
- find limit for `service_key`
- calculate used amount in current period
- raise exception if exceeded
- insert log row into `usage_runtime_log`

---

### `public.log_token_usage(p_model_key text, p_used_tokens bigint, p_source_ref text default null, p_user_id uuid default auth.uid()) returns void`
### Purpose
- enforce token limit
- insert token usage into ledger

### Steps
- determine effective payment plan
- find limit for `model_key`
- calculate used amount in current period
- raise exception if exceeded
- insert log row into `usage_token_log`

---

### `public.log_tokens(p_used_tokens integer) returns void`

#### Existing version
Worked against older daily-token logic using:
- `_get_user_payment_model_level()`
- `amezit_runtime_usage`
- `max_tokens_per_d`
- `infinity_tokens`

#### Extended version
Acts as backward-compatible wrapper:

- `log_token_usage('default', p_used_tokens::bigint, null, auth.uid())`

### Recommendation
Use `log_token_usage(...)` directly for new code.

---

### `public.set_company_payed_service(p_company_id bigint, p_pservice_id int) returns void`
### Purpose
- assign a payable service to a company
- root user only

---

### `public.remove_company_payed_service(p_company_id bigint, p_pservice_id int) returns void`
### Purpose
- remove a payable service from a company
- root user only

---

## 5.6 Project / chat / parameter functions already present

These functions are already implemented in the existing system and were included in the previous documentation because they are part of the current schema.

### `public.get_chat(p_project_id bigint, p_user_id uuid default null, p_max_entrys integer default 20, p_up_to_date timestamptz default now()) returns jsonb`
Returns chat history for a project with filtering logic:
- if no user is given, returns all project messages
- if user is given, returns:
  - user messages
  - assistant messages addressed to that user

---

### `public.get_project_overview(p_company_id integer, p_user_id text default '') returns jsonb`
Returns project overview list:
- all projects if `p_company_id = 1`
- otherwise company-specific projects
- optionally filtered by `user_id_auth`

---

### `public.get_project_parameters_json(p_project_id bigint, p_env_id smallint default null) returns jsonb`
Builds a structured JSON document:
- all parameters
- open parameters
- iterable support

---

### `public.getprojectmodel(p_project_id bigint) returns jsonb`
Builds a full project model snapshot with nested data:
- owner / profile
- chat messages
- project parameters
- parameter definitions
- files
- changelog
- feedback
- templates
- last prompt

---

### `public.start_chat_session(p_owner_id uuid, p_project_id bigint, p_chat_action_type chat_action_types) returns chat_sessions`
Creates a chat session for a project based on:
- owner profile
- owner company

---

### `public.update_parameters(p_project_id bigint, p_group_key text, p_param_name text, p_param_value text) returns jsonb`
Validates parameter existence against `cust_project_params`, then upserts parameter value.

---

## 6. Function Inventory Summary

## 6.1 Implemented and documented functions

### Credentials
- `amezit_cred_encrypt`
- `amezit_cred_decrypt`
- `set_user_cred`
- `get_user_cred`
- `set_group_cred`
- `get_group_cred`

### Groups
- `create_group`
- `assign_to_group`
- `leave_group`
- `remove_from_group`
- `delete_group`
- `check_user_is_in_group`
- `get_group_members`
- `assign_object_group`
- `ensure_special_groups`

### Authorization
- `current_user_role`
- `current_user_payment_plan`
- `is_root_user`
- `has_auth_class_assignment`
- `has_effective_auth`
- `require_effective_auth`
- `require_root_user`

### Usage / payment
- `get_effective_user_payment_plan`
- `get_runtime_usage_period_start`
- `log_runtime_usage`
- `log_token_usage`
- `log_tokens`
- `set_company_payed_service`
- `remove_company_payed_service`

### Existing project/chat functions
- `get_chat`
- `get_project_overview`
- `get_project_parameters_json`
- `getprojectmodel`
- `start_chat_session`
- `update_parameters`

---

## 7. Recommended Additional Functions

Below is the list of possible required functions that are still useful or likely needed.

## 7.1 Group management
- `rename_group(p_group_id int, p_group_name text)`
- `change_group_owner(p_group_id int, p_new_owner uuid)`
- `set_group_parent(p_group_id int, p_parent_group int)`
- `get_user_groups(p_user_id uuid default auth.uid())`
- `get_object_group(p_object_key text, p_object_id text)`
- `delete_object_group_assignment(p_object_key text, p_object_id text)`

## 7.2 User / company / role administration
- `set_user_role(p_user_id uuid, p_role_key text)`
- `set_user_payment_plan(p_user_id uuid, p_pplan_id int)`
- `set_company_payment_plan(p_company_id bigint, p_pplan_id int)`
- `set_company_group(p_company_id bigint, p_group_id int)`
- `get_company_users(p_company_id bigint)`

## 7.3 Authorization administration
- `create_auth_obj(p_auth_key text, p_auth_value int, p_auth_class text, p_is_auth_class bool, p_description text)`
- `assign_auth_to_user(p_user_id uuid, p_auth_key text, p_auth_value int default 1)`
- `remove_auth_from_user(p_user_id uuid, p_auth_key text)`
- `assign_auth_to_role(p_role_key text, p_auth_key text)`
- `remove_auth_from_role(p_role_key text, p_auth_key text)`
- `assign_auth_to_pplan(p_pplan_id int, p_auth_key text)`
- `remove_auth_from_pplan(p_pplan_id int, p_auth_key text)`
- `get_effective_user_auths(p_user_id uuid)`

## 7.4 Usage / billing
- `get_runtime_usage_summary(p_user_id uuid, p_service_key text, p_period_key text)`
- `get_token_usage_summary(p_user_id uuid, p_model_key text, p_period_key text)`
- `reset_usage_for_period(...)` only if manual reset is part of business logic
- `get_company_usage_summary(p_company_id bigint, p_period_key text)`
- `check_runtime_usage_allowed(p_user_id uuid, p_service_key text, p_runtime_value int)`
- `check_token_usage_allowed(p_user_id uuid, p_model_key text, p_token_value bigint)`

## 7.5 Credential administration
- `delete_user_cred(p_service text)`
- `delete_group_cred(p_group_id int, p_service text)`
- `list_user_cred_services()`
- `list_group_cred_services(p_group_id int)`

## 7.6 Reserved-group / access helpers
- `get_public_group_id()`
- `get_private_group_id()`
- `ensure_private_group_for_user(p_user_id uuid)`
- `is_object_accessible_for_user(p_object_key text, p_object_id text, p_user_id uuid default auth.uid())`

---

## 8. Important Migration / Implementation Notes

## 8.1 Return-type changes
PostgreSQL does not allow changing the return type of an existing function with `create or replace function`.

Example:
- old: `get_group_members(integer) returns setof uuid`
- new: `returns table(...)`

Required approach:
- `drop function if exists ...`
- then recreate function

---

## 8.2 Reserved special groups
Do not auto-seed group `0` and `1` with a fake zero UUID owner if `owner` is a foreign key to `auth.users`.

Use:
- `ensure_special_groups(p_owner uuid)`

---

## 8.3 `set_group_cred` inconsistency
The original implementation used:
- `public.tableuser_group`

This is likely a wrong or outdated table reference.

Correct version should check:
- `public.user_group_assignment`

---

## 8.4 Old vs. new token logging
The old function `log_tokens` used an older daily-limit design.

The new design is better because it supports:
- model-specific quotas
- flexible periods
- payment-plan-based enforcement
- usage ledger tables

Recommendation:
- keep `log_tokens` only as compatibility wrapper
- use `log_token_usage` and `log_runtime_usage` for all new logic

---

## 9. Final Recommended Operating Model

## 9.1 Access control
Use a layered approach:

1. user must have object access via group or public/private rule
2. user must have effective auth for requested action
3. required auth class must be present
4. payment plan must allow service / model consumption
5. usage logs must stay within quota

## 9.2 Credential access
- user credentials: only owner
- group credentials: only active group members
- mutations:
  - user credentials by self
  - group credentials by active group members or stricter by owner if desired

## 9.3 Payment enforcement
At service runtime:
1. resolve effective plan
2. check service/model quota
3. perform action
4. log actual usage

---

## 10. Final Status

This documentation now includes:

- all discussed and extended tables
- all already provided existing functions
- all newly added helper functions from the migration
- all relevant implementation notes
- recommended next-step functions

