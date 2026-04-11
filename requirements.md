# arkanaMDD Requirements

## Purpose

`arkanaMDD` is a framework that selects data from one or more databases and produces JSON documents based on configurable model frames.

A frame defines:

- which databases can be used
- which tables or queries are loaded
- how loaded data is referenced
- how fields are mapped into the final JSON model
- which input parameters are required
- how one model can reference another model

The framework must allow a user to define frames declaratively and execute them without writing custom extraction code for each output JSON.

## Core Objective

The framework shall transform relational data into structured JSON by executing a specific `Modelframe` definition.

Each frame acts as a data extraction and mapping contract.

## Main Concepts

### 1. Modelframe

The main configuration object is `Modelframe`.

```json
{
  "frame_id": 0,
  "user_group_id": "string",
  "dbs": [
    {
      "connection_id": 0,
      "db_key": "string"
    }
  ],
  "tables": [
    {
      "table_key": "string",
      "db": "string",
      "select_statement": "string",
      "values": [],
      "distinct": false,
      "prim_keys": {},
      "forgain_keys": {},
      "select_order": 0
    }
  ],
  "load_function": "",
  "table_refs": [
    {
      "table": "string",
      "db_key": "string",
      "field": "string",
      "description": "string"
    }
  ],
  "model_ref": [
    {
      "model_key": "string",
      "frame_id": 0,
      "parameter": {
        "parameter": "field_key"
      }
    }
  ],
  "model_fields": {
    "field_name": {
      "path": "string",
      "type": "string"
    }
  },
  "input_parameters": {
    "param_key": "string"
  }
}
```

### 2. Database Definitions

The `dbs` section defines the database connections available to the frame.

Requirements:

- Each database entry must have a unique `db_key` within the frame.
- `connection_id` must point to a registered database connection.
- `db_key` is used by tables and references to identify the source database.

### 3. Table Load Definitions

The `tables` section defines the dataset sources used by the frame.

Each table entry must support:

- `table_key`: internal alias of the loaded dataset
- `db`: the `db_key` to use
- `select_statement`: SQL statement used to load rows
- `values`: parameter values bound into the SQL statement
- `distinct`: whether duplicate rows are removed
- `prim_keys`: primary key definition for row identity
- `forgain_keys`: foreign key definition for relations
- `select_order`: execution order for dependent loads

Requirements:

- `table_key` must be unique within a frame.
- `db` must match an existing `db_key`.
- `select_statement` may be a full query and is not limited to direct table selects.
- `values` may reference frame input parameters or previously resolved values.
- `select_order` controls loading order when dependencies exist.
- `forgain_keys` is assumed to mean foreign keys and should be normalized internally as `foreign_keys`.

### 4. Load Function

`load_function` defines an optional custom loader strategy.

Requirements:

- If empty, the default relational loader is used.
- If specified, the named function must exist in the framework runtime.
- A custom load function may override table loading, join behavior, or post-processing.

### 5. Table References

`table_refs` provides named access points to loaded table fields.

Each reference contains:

- `table`: target table alias
- `db_key`: source database alias
- `field`: source field name
- `description`: semantic meaning of the field

Requirements:

- `table` must match an existing `table_key`.
- `db_key` must match the database assigned to that table or be validated as compatible.
- Table references should be usable in field mappings and parameter substitution.

### 6. Model References

`model_ref` allows a frame to embed or call another model frame.

Each model reference contains:

- `model_key`: logical name of the referenced model
- `frame_id`: target frame identifier
- `parameter`: parameter mapping from current frame values to the referenced frame inputs

Requirements:

- The framework must support recursive model composition.
- Parameter mappings must resolve current frame values before calling the referenced model.
- Circular model references must be detected and rejected.

### 7. Model Fields

`model_fields` defines the output JSON structure.

Each entry maps a target JSON field to:

- `path`: source path expression
- `type`: target data type

Example:

```json
{
  "customer_name": {
    "path": "table:customer-name-0",
    "type": "str"
  }
}
```

Requirements:

- Every output field must define a valid `path`.
- Every output field must define a target `type`.
- The framework must convert values into the requested type when possible.
- Invalid casts must raise a structured error.

### 8. Input Parameters

`input_parameters` defines the parameters required to execute a frame.

Requirements:

- Each parameter must have a unique key.
- Each parameter must define a type.
- Missing required input parameters must stop execution with validation errors.

Suggested normalized form:

```json
{
  "input_parameters": {
    "param_key": {
      "type": "str"
    }
  }
}
```

## Path Definition

The framework uses path expressions to resolve values.

### Supported path roots

- `parameter:<parameter-name>`
- `table:<table_key>`
- `model:<model_key>`
- `const`

### Detailed table field path

Format:

```text
table:table_key-field-line
```

Meaning:

- `table_key`: source table alias
- `field`: field/column name
- `line`: row index or selected row position

Examples:

- `table:customer-name-0`
- `table:invoice-total-0`

### Table root path

Format:

```text
table:table_key
```

This path returns the full loaded dataset for a table.

### Model path

Format:

```text
model:model_key
```

This path returns the resolved output of a referenced model.

### Constant path

Format:

```text
const
```

This path is used when a field value is static and provided directly by configuration.

## String Interpolation

The framework must support inline string interpolation inside configured text values.

Format:

```text
text text text ^-^{field/inputkey}^-^ text text text
```

Requirements:

- Interpolation must resolve both field references and input parameters.
- Unresolved placeholders must raise an error unless explicitly marked optional.
- Interpolation should preserve surrounding text exactly.

Example:

```text
Customer ^-^{customer_name}^-^ placed order ^-^{order_id}^-^
```

## Security and Access Model

### User Group

Frame execution is restricted by user group.

`user_group` structure:

- `user_group_id`: int
- `group_name`: str
- `parent_id`: int

Requirements:

- A frame may only be executed by authorized users in the configured group or inherited parent group.
- Group inheritance through `parent_id` must be supported.

### User

`user` structure:

- `user_id`: str
- `user_name`: str
- `user_auth`: implementation-defined auth payload

### Group Assignment

`group_assignment` structure:

- `group_id`
- `user_id`

Requirements:

- The framework must validate that the current user belongs to the frame's `user_group_id`.
- Authorization must occur before any database query execution.

## Functional Requirements

### Frame Lifecycle

The framework must support the following execution flow:

1. Validate user authorization.
2. Validate input parameters.
3. Resolve database connections.
4. Load tables in `select_order`.
5. Build table references.
6. Resolve model references.
7. Map `model_fields` into the output JSON.
8. Return the final JSON document.

### Validation

The framework must validate:

- missing database definitions
- duplicate `db_key` or `table_key`
- invalid path syntax
- undefined model references
- unresolved input parameters
- invalid field types
- cyclic model dependencies

### Output

The result of a frame execution must be JSON.

Output requirements:

- Output must contain all configured `model_fields`.
- Output may contain nested objects from `model_ref`.
- Output must preserve the configured field names.
- Output must be deterministic for the same inputs and source data.

### Error Handling

The framework must return structured errors for:

- authorization failures
- validation failures
- database execution failures
- mapping failures
- type conversion failures
- missing referenced values

Suggested error structure:

```json
{
  "error_code": "FRAME_VALIDATION_ERROR",
  "message": "Invalid path definition for field customer_name",
  "frame_id": 12,
  "field": "customer_name"
}
```

## Non-Functional Requirements

- The framework should support multiple database backends through connection adapters.
- The framework should separate frame definition, execution engine, and output mapping.
- The framework should be testable with mocked database connectors.
- The framework should support extension points for custom loaders and type converters.
- The framework should log frame execution steps for traceability.

## Recommended Normalizations

The original input contains a few fields that should be normalized for implementation clarity:

- `forgain_keys` should be renamed to `foreign_keys`
- `input_parameters` should store typed objects instead of plain strings
- `user_group_id` in `Modelframe` should use a consistent type with `user_group.user_group_id`
- `model_ref.parameter` should be renamed to `parameters`

## Example Execution Intent

Example use case:

- Load customer data from one database.
- Load invoice data from another database.
- Resolve the current customer by input parameter.
- Map both datasets into one JSON response.
- Optionally embed a referenced child model for line items.

## Summary

`arkanaMDD` is a metadata-driven framework where a `Modelframe` defines how to query relational sources and convert the results into JSON. The framework must support database abstraction, declarative mappings, frame composition, parameterized execution, and authorization by user group.
