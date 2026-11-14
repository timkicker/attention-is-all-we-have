# Agents

Any purchasing agent can buy through Validio if it speaks MCP or plain HTTP. Our own agent in `src/backend/validio/agent/` has no back door and uses the same six tools as everyone else. Every JSON block below is a real answer from a replay run on the seeded demo store. `tests/test_agents_doc.py` checks each one against the live OpenAPI and MCP schemas, so a renamed field in the API fails the tests. Long lists are cut to a few entries and supplier text is shortened (marked with …), but no value is changed.

## Connect

Start Validio with `make demo` in `validio/`. It listens on `127.0.0.1:8410` and offers the same tools two ways.

| Way | Address | Spend Pass |
| --- | --- | --- |
| MCP over streamable HTTP | `http://127.0.0.1:8410/mcp/` | the `spendPass` argument of a write tool |
| OpenAPI 3.1 | `http://127.0.0.1:8410/openapi.json`, browsable at `/docs` | the header `Authorization: SD-JWT <presentation>` |

For an MCP host the whole configuration is in `examples/mcp.json`:

```
{"mcpServers": {"validio": {"type": "http", "url": "http://127.0.0.1:8410/mcp/"}}}
```

Keep the slash at the end of the URL. A POST to `/mcp` without it never reaches the MCP server and gets a 405.

On a hosted Validio every kitchen has its own address: `/mcp/k/<account>/` for MCP and `/agent/v1/k/<account>/...` for HTTP, with the same tools and paths as below. The kitchen's Agent page shows both. Over MCP that kitchen's nonce is the resource `validio://k/<account>/nonce`. An unknown account gets a 404. The local `/mcp/` and `/agent/v1/...` serve the one kitchen of `make demo`.

### Pairing

The kitchen presses "Connect agent" and gets an 8 character code, valid ten minutes. The agent sends it with its name and its public P-256 key:

<!-- check: body POST /agent/v1/pair -->
```json
{
  "code": "7KQ4-M2XD",
  "name": "Kitchen buyer",
  "publicJwk": {"kty": "EC", "crv": "P-256", "x": "f83OJ3D2xF1Bg8vub9tLe1gHMzV76e8Tus9uPHvRVEU", "y": "x_FEzRu9m36HLN_tue659LNpXW6pCyStikYjKIWI5a0"}
}
```

<!-- check: response POST /agent/v1/pair -->
```json
{
  "status": "consent"
}
```

The kitchen now sees the agent's name and what it may do, and allows or denies. The agent asks with the same code until the answer is there. On Allow the kitchen signs Spend Pass M-1 again, bound to the agent's key, and the answer carries it:

<!-- check: response GET /agent/v1/pass -->
```json
{
  "status": "allowed",
  "spendPass": "eyJhbGciOiJFUzI1NiJ9.…~WyJ…~"
}
```

A wrong or expired code gets a 404, and five wrong codes end the pairing. `status` is `consent` while the kitchen has not answered and `denied` after Deny. While the kitchen pauses the agent, every call with the pass gets a 401 `the kitchen paused this agent`. After Disconnect the agent's copy is refused as superseded.

## Spend Pass

The Spend Pass is the kitchen's signed permission to spend. It is an SD-JWT issued by `kitchen:hotel-espoo` and bound to the agent's own P-256 key through its `cnf` claim, so a stolen pass is useless without that key. Pass M-1 of the demo allows 1200.00 EUR per order without a person, never more than 2000.00 EUR, only lactose-free products from three product groups and delivery by 16 November. It is valid from 14 November 10:00 to 17 November 00:00 Helsinki time.

On this demo `make seed` plays the kitchen. It issues M-1 to the public key in `data/keys/agent-es256.json` and creates that key when there is none. To bind the pass to your own agent, put your private P-256 key there as a JWK before `make seed`. Then print the pass from `src/backend`:

```
uv run validio-agent --print-pass > pass.txt
```

Every write needs a fresh presentation, built in four steps.

1. Fetch a nonce from `GET /agent/v1/nonce` (over MCP from the resource `validio://nonce`). A nonce is good once and for five minutes. The answer also carries `iat`, Validio's clock in Unix seconds. In the demo that clock stands still at Sat 14 Nov 10:00.
2. Keep the issuer JWT and only the disclosures for `autoLimitCents`, `hardCapCents` and `diet`. Validio decides with these three, so the other fields stay hidden.
3. Sign a key binding JWT with your key, header `{"alg": "ES256", "typ": "kb+jwt"}` and payload `iat` (the one from the nonce answer), `aud` (always `validio:agent-v1`), `nonce` and `sd_hash`. The hash is SHA-256 in base64url over `<issuer JWT>~<disclosure>~…~`.
4. Append the key binding JWT to that string. The result is the presentation.

`presentation()` in `examples/agent_client.py` does all of this in ten lines. Validio checks the issuer signature, the key binding and its `iat` (at most ten minutes old, at most a minute ahead), issuer, audience, nonce, that every disclosure belongs to the pass, and the validity window. Anything that fails one of these gets a 401.

Both writes also take an `idempotencyKey`. A retry with the same key returns the same request or order and never orders twice.

## Tools

| Tool | HTTP | Spend Pass |
| --- | --- | --- |
| `search_products` | `GET /agent/v1/products` | no |
| `request_supply` | `POST /agent/v1/requests` | yes |
| `get_request` | `GET /agent/v1/requests/{request_id}` | no |
| `confirm_order` | `POST /agent/v1/orders` | yes |
| `get_order` | `GET /agent/v1/orders/{order_id}` | no |
| `renew_steady_order` | MCP only, runs `POST /api/steady/{order_id}/renew` | yes |

The usual run is `request_supply`, then a look at `decision.outcome`. With `auto_order` the agent confirms the `chosen` product and amount of each line and is done. For `ask_human` Validio already holds the order for the owner, who answers on the phone, so the agent reads the order and waits. With `block` nothing is ordered. Prices in `confirm_order` are never taken from the agent because Validio asks Valio again before it places anything.

Supplier text comes in `descriptionUntrusted` and `supplierText` with the grade `untrusted`. It never decides anything inside Validio and an agent should not let it decide anything either, because one of the demo products carries a line that tries to talk to AI agents.

The nonce for step 1 of the Spend Pass:

<!-- check: response GET /agent/v1/nonce -->
```json
{
  "nonce": "D5TolIaHmYcJNcOyXdWEhIqGGGLGbl1c",
  "aud": "validio:agent-v1",
  "iat": 1794643200
}
```

### search_products

Searches Validio's copy of Valio's catalog. It is static data and makes no live call to Valio. Every claim carries its Fact Grade.

<!-- check: mcp search_products -->
```json
{
  "text": "lactose free milk",
  "claims": [
    "FREE_FROM_LACTOSE"
  ],
  "limit": 2
}
```

Over HTTP the same call is `GET /agent/v1/products?q=lactose%20free%20milk&claims=FREE_FROM_LACTOSE&limit=2`. One of the two products it returns:

<!-- check: response GET /agent/v1/products -->
```json
[
  {
    "id": "460448",
    "name": "Valio Play® milk chocolate drink 1 l lactose free",
    "category": "22540",
    "salesUnit": "KI",
    "claims": [
      {
        "claim": "FREE_FROM_COLOURING_AGENTS",
        "grade": "unchecked",
        "note": "nothing in the data to check it against"
      },
      {
        "claim": "FREE_FROM_LACTOSE",
        "grade": "consistent",
        "note": "lactose 0 g per 100 g"
      }
    ],
    "allergensContains": [
      "AM"
    ],
    "labels": [
      "Hyvää Suomesta",
      "Rainforest Alliance"
    ],
    "descriptionUntrusted": {
      "text": "Valio Play® chocolate milk…",
      "grade": "untrusted",
      "planted": false,
      "reader": null
    }
  }
]
```

### request_supply

Takes free text or `{productId, quantity, unit}` lines and returns ranked options per line, the decision and how many product ids were checked live. The HTTP body:

<!-- check: body POST /agent/v1/requests -->
```json
{
  "lines": [
    {
      "text": "1000 litres of lactose-free milk by Monday, budget 1200 euro"
    }
  ],
  "deliverBy": "2026-11-16",
  "idempotencyKey": "kitchen-2026-11-14-milk"
}
```

Over MCP the Spend Pass travels as an argument:

<!-- check: mcp request_supply -->
```json
{
  "spendPass": "<presentation>",
  "lines": [
    {
      "text": "1000 litres of lactose-free milk by Monday, budget 1200 euro"
    }
  ],
  "deliverBy": "2026-11-16",
  "idempotencyKey": "kitchen-2026-11-14-milk"
}
```

The answer, here with 3 of 31 options and 2 facts each:

<!-- check: response POST /agent/v1/requests -->
```json
{
  "id": "R-1",
  "requestId": "R-1",
  "createdAt": "2026-11-14T10:00:00+02:00",
  "agent": "agent:buyer-1",
  "text": "1000 litres of lactose-free milk by Monday, budget 1200 euro",
  "deliverBy": "2026-11-16",
  "status": "working",
  "spendPassId": "M-1",
  "lines": [
    {
      "lineId": "L-1",
      "text": "1000 litres of lactose-free milk by Monday, budget 1200 euro",
      "need": {
        "what": "milk",
        "quantity": 1000.0,
        "unit": "L",
        "diet": [
          "lactose free"
        ],
        "deliverBy": "2026-11-16",
        "productId": null
      },
      "options": [
        {
          "productId": "464306",
          "name": "Valio Hyvä suomalainen Arki® Eila® semi skimmed milk drink 1 l lactose free",
          "rank": 1,
          "verdict": "chosen",
          "quantity": 1000,
          "unit": "ST",
          "totalCents": 101000,
          "sentence": "Cheapest safe option; Valio delivered it as ordered every time in its records; Has the Hyvää Suomesta label, which your Spend Pass does not ask for; Footprint 1.1 kg CO2e per kg, a group average.",
          "facts": [
            {
              "field": "quantity",
              "value": "1e+10 ST",
              "grade": "attested",
              "source": "Valio availability API",
              "note": "Valio reports 9999999999, a placeholder, not a real count; treated as in stock",
              "until": null
            },
            {
              "field": "price",
              "value": "1.01 EUR",
              "grade": "attested_until",
              "source": "Valio price API",
              "note": "until 2026-12-31",
              "until": "2026-12-31"
            }
          ],
          "onValioList": null,
          "isSubstitute": false,
          "supplierText": {
            "text": "Valio Hyvä suomalainen Arki®…",
            "grade": "untrusted",
            "planted": false,
            "reader": null
          }
        },
        {
          "productId": "462921",
          "name": "Valio Eila®  Luomu™ semi skimmed milk drink 1 l lactose free, organic",
          "rank": null,
          "verdict": "blocked",
          "quantity": 200,
          "unit": "KI",
          "totalCents": 219400,
          "sentence": "Order cut-off 12 Nov 15:00 has passed; the quantity is unknown. Blocked: 2194.00 EUR is over the hard cap of 2000.00 EUR.",
          "facts": [
            {
              "field": "quantity",
              "value": null,
              "grade": "unknown",
              "source": "Valio availability API",
              "note": "Terminal: Valio reports 999999 KI, the goods sit at the supplier",
              "until": null
            },
            {
              "field": "price",
              "value": "10.97 EUR",
              "grade": "attested",
              "source": "Valio price API",
              "note": "catalog price, no end date",
              "until": null
            }
          ],
          "onValioList": null,
          "isSubstitute": false,
          "supplierText": {
            "text": "Valio Eila® Luomu™ organic…",
            "grade": "untrusted",
            "planted": false,
            "reader": null
          }
        },
        {
          "productId": "469287",
          "name": "Valio Eila® semi skimmed milk drink 1,75 l lactose free",
          "rank": null,
          "verdict": "rejected",
          "quantity": 48,
          "unit": "KI",
          "totalCents": 131472,
          "sentence": "Order cut-off 12 Nov 15:00 has passed; the quantity is unknown.",
          "facts": [
            {
              "field": "quantity",
              "value": null,
              "grade": "unknown",
              "source": "Valio availability API",
              "note": "Terminal: Valio reports 999999 KI, the goods sit at the supplier",
              "until": null
            },
            {
              "field": "price",
              "value": "27.39 EUR",
              "grade": "attested",
              "source": "Valio price API",
              "note": "catalog price, no end date",
              "until": null
            }
          ],
          "onValioList": null,
          "isSubstitute": false,
          "supplierText": {
            "text": "Valio Eila® lactose-free semi-skimmed…",
            "grade": "untrusted",
            "planted": false,
            "reader": null
          }
        }
      ],
      "substitutes": null,
      "beyondList": null,
      "swapSentence": null,
      "chosen": {
        "productId": "464306",
        "salesQty": 1000,
        "isSubstitute": false,
        "onValioList": false
      },
      "note": "All these products have the same footprint in Valio's data (1.1 kg CO2e per kg, a group average), so it does not change the choice."
    }
  ],
  "decision": {
    "outcome": "auto_order",
    "ruleIds": [
      "auto-order"
    ],
    "sentence": "May order 464306 alone: 1010.00 EUR is inside the auto limit of 1200.00 EUR and every fact it needs is attested."
  },
  "totalCents": 101000,
  "liveChecked": {
    "calls": 4,
    "ids": 12,
    "idsPerCall": [
      12,
      12,
      1,
      1
    ]
  },
  "orderId": null,
  "question": null,
  "simulated": null
}
```

### get_request

Reads a request again, for example after the owner has answered.

<!-- check: mcp get_request -->
```json
{"requestId": "R-1"}
```

After the order below is placed the request reads `ordered_alone` (options cut to the chosen one):

<!-- check: response GET /agent/v1/requests/{request_id} -->
```json
{
  "id": "R-1",
  "requestId": "R-1",
  "createdAt": "2026-11-14T10:00:00+02:00",
  "agent": "agent:buyer-1",
  "text": "1000 litres of lactose-free milk by Monday, budget 1200 euro",
  "deliverBy": "2026-11-16",
  "status": "ordered_alone",
  "spendPassId": "M-1",
  "lines": [
    {
      "lineId": "L-1",
      "text": "1000 litres of lactose-free milk by Monday, budget 1200 euro",
      "need": {
        "what": "milk",
        "quantity": 1000.0,
        "unit": "L",
        "diet": [
          "lactose free"
        ],
        "deliverBy": "2026-11-16",
        "productId": null
      },
      "options": [
        {
          "productId": "464306",
          "name": "Valio Hyvä suomalainen Arki® Eila® semi skimmed milk drink 1 l lactose free",
          "rank": 1,
          "verdict": "chosen",
          "quantity": 1000,
          "unit": "ST",
          "totalCents": 101000,
          "sentence": "Cheapest safe option; Valio delivered it as ordered every time in its records; Has the Hyvää Suomesta label, which your Spend Pass does not ask for; Footprint 1.1 kg CO2e per kg, a group average.",
          "facts": [
            {
              "field": "quantity",
              "value": "1e+10 ST",
              "grade": "attested",
              "source": "Valio availability API",
              "note": "Valio reports 9999999999, a placeholder, not a real count; treated as in stock",
              "until": null
            },
            {
              "field": "price",
              "value": "1.01 EUR",
              "grade": "attested_until",
              "source": "Valio price API",
              "note": "until 2026-12-31",
              "until": "2026-12-31"
            }
          ],
          "onValioList": null,
          "isSubstitute": false,
          "supplierText": {
            "text": "Valio Hyvä suomalainen Arki®…",
            "grade": "untrusted",
            "planted": false,
            "reader": null
          }
        }
      ],
      "substitutes": null,
      "beyondList": null,
      "swapSentence": null,
      "chosen": {
        "productId": "464306",
        "salesQty": 1000,
        "isSubstitute": false,
        "onValioList": false
      },
      "note": "All these products have the same footprint in Valio's data (1.1 kg CO2e per kg, a group average), so it does not change the choice."
    }
  ],
  "decision": {
    "outcome": "auto_order",
    "ruleIds": [
      "auto-order"
    ],
    "sentence": "Ordered 1000 ST of 464306 Valio Hyvä suomalainen Arki® Eila® semi skimmed milk drink 1 l lactose free for 1010.00 EUR without a human. Stock quantity attested by Valio, contract price until 31 Dec 2026, delivery 16 Nov. Inside mandate M-1 (auto limit disclosed: 1200.00 EUR). Valio reports 9999999999 for 464306, a placeholder, not a real count; treated as in stock."
  },
  "totalCents": 101000,
  "liveChecked": {
    "calls": 4,
    "ids": 12,
    "idsPerCall": [
      12,
      12,
      1,
      1
    ]
  },
  "orderId": "O-1",
  "question": null,
  "simulated": null
}
```

### confirm_order

Confirms products and amounts from a request's options. Only `productId` and `salesQty` count.

<!-- check: mcp confirm_order -->
```json
{
  "spendPass": "<presentation>",
  "requestId": "R-1",
  "choice": [
    {
      "productId": "464306",
      "salesQty": 1000
    }
  ],
  "idempotencyKey": "kitchen-2026-11-14-milk-order"
}
```

Over HTTP it is the body below, sent to `POST /agent/v1/orders` with the Spend Pass header:

<!-- check: body POST /agent/v1/orders -->
```json
{
  "requestId": "R-1",
  "choice": [
    {
      "productId": "464306",
      "salesQty": 1000
    }
  ],
  "idempotencyKey": "kitchen-2026-11-14-milk-order"
}
```

<!-- check: response POST /agent/v1/orders -->
```json
{
  "id": "O-1",
  "requestId": "R-1",
  "state": "placed",
  "lines": [
    {
      "productId": "464306",
      "name": "Valio Hyvä suomalainen Arki® Eila® semi skimmed milk drink 1 l lactose free",
      "quantity": 1000,
      "unit": "ST",
      "priceCents": 101,
      "totalCents": 101000,
      "priceValidTo": "2026-12-31",
      "deliveryDate": "2026-11-16",
      "deliverable": true,
      "isSubstitute": false,
      "onValioList": false,
      "facts": [
        {
          "field": "quantity",
          "value": "1e+10 ST",
          "grade": "attested",
          "source": "Valio availability API",
          "note": "Valio reports 9999999999, a placeholder, not a real count; treated as in stock",
          "until": null
        }
      ]
    }
  ],
  "totalCents": 101000,
  "history": [
    {
      "state": "placed",
      "at": "2026-11-14T10:00:00+02:00"
    }
  ],
  "decision": {
    "outcome": "auto_order",
    "ruleIds": [
      "auto-order"
    ],
    "sentence": "May order 464306 alone: 1010.00 EUR is inside the auto limit of 1200.00 EUR and every fact it needs is attested."
  },
  "spendPassId": "M-1",
  "deliverBy": "2026-11-16",
  "approvedBy": null
}
```

### get_order

Reads an order and its state, which is `waiting`, `approved`, `placed`, `rejected` or `blocked`.

<!-- check: mcp get_order -->
```json
{"orderId": "O-1"}
```

<!-- check: response GET /agent/v1/orders/{order_id} -->
```json
{
  "id": "O-1",
  "requestId": "R-1",
  "state": "placed",
  "lines": [
    {
      "productId": "464306",
      "name": "Valio Hyvä suomalainen Arki® Eila® semi skimmed milk drink 1 l lactose free",
      "quantity": 1000,
      "unit": "ST",
      "priceCents": 101,
      "totalCents": 101000,
      "priceValidTo": "2026-12-31",
      "deliveryDate": "2026-11-16",
      "deliverable": true,
      "isSubstitute": false,
      "onValioList": false,
      "facts": [
        {
          "field": "quantity",
          "value": "1e+10 ST",
          "grade": "attested",
          "source": "Valio availability API",
          "note": "Valio reports 9999999999, a placeholder, not a real count; treated as in stock",
          "until": null
        }
      ]
    }
  ],
  "totalCents": 101000,
  "history": [
    {
      "state": "placed",
      "at": "2026-11-14T10:00:00+02:00"
    }
  ],
  "decision": {
    "outcome": "auto_order",
    "ruleIds": [
      "auto-order"
    ],
    "sentence": "May order 464306 alone: 1010.00 EUR is inside the auto limit of 1200.00 EUR and every fact it needs is attested."
  },
  "spendPassId": "M-1",
  "deliverBy": "2026-11-16",
  "approvedBy": null
}
```

### renew_steady_order

Renews this week's Steady Order. Lines that match the kitchen's usual pattern are ordered alone and the rest wait for the owner with a reason and a button label. A second renewal in the same week orders nothing twice. The tool exists only over MCP and calls the web app's renewal route behind the Spend Pass check.

<!-- check: mcp renew_steady_order -->
```json
{
  "spendPass": "<presentation>",
  "orderId": "S-1"
}
```

The answer, here with 2 of its 4 lines:

<!-- check: response POST /api/steady/{order_id}/renew -->
```json
{
  "id": "S-1",
  "name": "Weekly Monday order",
  "weekday": "Monday",
  "guestsPerWeek": 400,
  "weeksLearned": 8,
  "simulatedHistory": true,
  "renewedAt": "2026-11-14T10:00:00+02:00",
  "lines": [
    {
      "productId": "464306",
      "name": "Valio Hyvä suomalainen Arki® Eila® semi skimmed milk drink 1 l lactose free",
      "unit": "packs",
      "usualQuantity": 300,
      "thisWeekQuantity": 300,
      "totalCents": 30300,
      "result": "renewed",
      "sentence": "Same as usual.",
      "flags": [],
      "orderId": "O-2",
      "ruleIds": [
        "auto-order"
      ]
    },
    {
      "productId": "471376",
      "name": "Lagerblad Foods Pancake vegan 30 g / 3,0kg Fried Frozen",
      "unit": "cartons",
      "usualQuantity": 30,
      "thisWeekQuantity": 27,
      "totalCents": 90531,
      "result": "waiting",
      "sentence": "27 of 30 cartons can come. 476523 Findus Pancake, vegan ca 100x60g would break a rule: Not gluten free: lists gluten cereals as contained; lists wheat as contained; Valio does not confirm its stock (Terminal). Order 27 now?",
      "flags": [
        {
          "kind": "stock_below",
          "sentence": "Only 27 cartons in stock, the usual line is 30."
        }
      ],
      "acceptLabel": "Order 27 now"
    }
  ]
}
```

## Errors

Over HTTP every refusal is a JSON object with one field `detail`. A 401 means the Spend Pass was refused and comes with `WWW-Authenticate: SD-JWT`. A 404 names the id that does not exist, 409 is a conflict (an idempotency key reused for a different body or an order in the wrong state) and 422 means Validio could not read or accept the request.

<!-- check: error 401 POST /agent/v1/requests -->
```json
{
  "detail": "no Spend Pass in the Authorization header"
}
```

<!-- check: error 404 GET /agent/v1/orders/{order_id} -->
```json
{
  "detail": "no order O-99"
}
```

A body that does not fit the schema is the one exception. Its 422 comes from FastAPI, which makes `detail` a list with one entry per problem.

Over MCP a refusal is a tool result with `isError` set. Its text starts with the HTTP status and a short reason, then the same message:

```
Error executing tool confirm_order: 401 Spend Pass refused: no key binding
Error executing tool get_order: 404 not found: no order O-99
```

## Examples

`examples/agent_client.py` is a complete third-party agent for scene 2 in under 80 lines with httpx and jwcrypto. Plain httpx cannot make the one ES256 signature, so jwcrypto does that part. It reads the pass and its key and then requests, confirms and reads the order:

```
uv run python ../../examples/agent_client.py --pass pass.txt --key ../../data/keys/agent-es256.json
```

`tests/test_examples.py` runs it against the server in process and checks that order O-1 is placed for 1000 ST of 464306 at 1010.00 EUR.

Our own agent is the command `validio-agent` (the same as `make agent`). It prints every tool call with Validio's answer for the demo's left pane and writes the transcript of what its model saw to `artifacts/agent/scene-n.md`.

```
uv run validio-agent --scene 2
uv run validio-agent --scene 4 --local
```
