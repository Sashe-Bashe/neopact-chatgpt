# Neopact tool reference

The local server exposes these 13 tools. Host prefixes may differ; select the server connected to the intended workspace. Read `get_instructions` and the live tool schema before building inputs. Effective permission is the intersection of the configured credential, role, workspace membership, and resource ownership.

| Tool | Inputs and purpose | Required capability |
| --- | --- | --- |
| `get_instructions` | No arguments. Returns role, workspace, effective scopes, workflow, and action/request/product schemas. | Valid configured agent identity |
| `search_catalogue` | `query`, `own_products`, optional `material` and `destination`, `limit`, `offset`. Lists visible products; seller own products can include drafts. | `catalogue:read` |
| `get_product_images` | `product_id`. Returns visible image metadata, never image bytes. | `images:read` and `catalogue:read` |
| `get_inbox` | No arguments. Returns up to 100 participant rooms, turn availability, and own pending guidance IDs. | `negotiations:read` |
| `get_negotiation_context` | `room_id`. Returns current terms, allowed actions, shared dialogue, and only the caller's private needs and guidance. | `negotiations:read` and room participation |
| `get_activity` | Optional `resource_id`, `limit`, `offset`. Reads the configured workspace's audit feed. | `negotiations:read` |
| `get_orders` | `limit`, `offset`. Reads participant orders. | `orders:read` |
| `create_request` | `request: RequestInput`, `idempotency_key`. Creates a private buyer draft. | Buyer role and `requests:write` |
| `launch_request` | `request_id`, `idempotency_key`. Matches an owned draft to eligible sellers and opens rooms. | Buyer role and `requests:write` |
| `create_product` | `product: ProductInput`, `idempotency_key`. Creates an owned seller listing; `published` controls market visibility. | Seller role and `products:write` |
| `update_product` | `product_id`, `product: ProductUpdate`. Replaces an owned listing using `expected_version`; may invalidate offers and approvals. | Seller role and `products:write` |
| `claim_turn` | `room_id`. Returns an exclusive temporary claim with token and expected room version. | `negotiations:act`, `negotiations:read`, and available participant turn |
| `submit_action` | `room_id`, `action: ActionInput`, `idempotency_key`. Executes one claimed, versioned action. | `negotiations:act`, `negotiations:read`, and valid participant claim |

Pagination accepts `limit` from 1 through 100 and a nonnegative `offset`. Defaults are 20 for catalogue/orders and 30 for activity. `get_inbox` has a fixed maximum of 100 rooms and no pagination input; do not claim it proves that no other rooms exist.

## Structured inputs

Use the live schemas for exact constraints. Do not send fields absent from the schemas. Monetary values are integer **EUR cents**, not euros or a configurable currency. Dates use `YYYY-MM-DD`; deposit percentages are integers from 0 to 100.

### Purchase request

`RequestInput` contains `title`, optional `description`, `category` (currently `chairs`), `quantity`, `material` (`any`, `polypropylene`, `wood`, or `fabric`), `stackable`, `destination`, `latest_delivery`, private `max_total`, private `max_deposit_percent`, and `preference` (`lowest_total`, `lower_deposit`, or `earliest_delivery`). Supply actual reviewed requirements and limits. Do not repeat private fields in shareable prose.

### Product

`ProductInput` contains `name`, optional `description`, `sku`, `category` (currently `chairs`), `attributes` (`material`, `stackable`, `color`), public `unit_price`, `delivery_charge`, `lead_days`, `destinations`, `stock`, and `published` (default `false`). Material is `polypropylene`, `wood`, or `fabric`.

`ProductUpdate` contains the complete product input plus `expected_version`. It replaces a listing; it is not a partial patch. Private seller minima are separate business rules and are not a product field in these tools.

### Negotiation action

Every `ActionInput` requires `type`, `expected_version`, and `claim_token`. Add `guidance_id` when acknowledging the workspace's latest pending human guidance. Derive tokens, IDs, and versions from current tool responses.

| Action type | Required content and meaning |
| --- | --- |
| `propose`, `counter`, `revise` | `terms` with `unit_price`, `quantity`, `delivery_date`, and `deposit_percent`. A public `message` is optional; if present, use `purpose: explanation`. |
| `message` | Public `message` and `purpose` (`question`, `answer`, `tradeoff`, or `explanation`). No `terms`, `offer_id`, or `topic`. |
| `accept` | Exact current counterparty `offer_id`. No replacement terms or public-message fields. |
| `request_clarification`, `answer_clarification` | `topic`: `specifications`, `delivery`, `images`, or `quantity`. Confirmed facts come from the catalogue. |
| `decline` | No terms, offer ID, topic, or public-message fields. |
| `request_human_review` | Optional private `human_question`; no public-message fields. Use for a concrete owner decision. |

Conversation fields can include an authorized `reply_to_action_id` and up to five unique authorized `image_ids` when accompanied by a public message. An image reference is not proof that the host inspected the image. Use `allowed_actions` from the room; the existence of an action type in the schema does not authorize it in every state.

## Errors and uncertain writes

Keys are 8–128 characters. Keyed writes are `create_request`, `launch_request`, `create_product`, and `submit_action`. Identical keyed retries return the original receipt; a different payload with the same key conflicts. Creation and launch keys are credential-scoped, while action keys are scoped to the credential and room. Keep distinct keys for distinct intentions and operations.

A timeout does not prove failure. Reconcile or replay the identical keyed mutation. Claims and product updates do not accept keys: recover a lost claim by waiting for lease expiry, and reconcile a product update by reading the listing/version before acting again. The backend's current default claim duration is 180 seconds; use returned expiry/state rather than assuming the configured duration.

| Result | Response |
| --- | --- |
| 401 | Have the owner correct an expired, revoked, or invalid restricted connection. |
| 403 | Verify role, scope, workspace, and resource ownership; do not escalate credentials to bypass the boundary. |
| 404 | Verify the ID and intended workspace; absence can also reflect access restrictions. |
| 409 | Refresh private context, guidance, claim, version, and/or idempotency receipt; reassess before retrying. |
| 422 | Correct malformed input or terms within the current policies; do not weaken requirements silently. |
| 429 | Back off and respect the rate window. |
| Network error or 5xx | Treat the write outcome as uncertain and apply the operation's recovery rules. |

No tool can approve a deal, edit policies/briefs, waive requirements, issue credentials, change workspace, expose an arbitrary HTTP endpoint, or upload/download image bytes. `images:write` exists in the backend's seller role but this 13-tool interface has no image-write tool. Do not describe unsupported API or CLI capabilities as installed plugin tools.
