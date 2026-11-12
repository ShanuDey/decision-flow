# Expressions

Conditions use [CEL](https://cel.dev), a small expression language with no loops or side effects, so an expression always finishes.

```
input.income >= 30000 && input.credit_score >= 600
vars.tier == "gold" || input.amount < 100
has(input.coupon) ? input.coupon == "SAVE10" : false
input.items.exists(i, i.price > vars.limit)
```

## What an expression can read

- `input.<name>`: a [Start](../nodes/start.md) input
- `vars.<name>`: a [variable](variables.md)
- `nodes.<id>.output.<key>`: the output of a node that runs earlier on the same path

Undeclared names, and nodes that do not run before the expression, fail validation. Reading a key that is not set fails the run, naming the node.

Expressions are limited to 2000 characters. Assign and End still use [templates](templates.md).
